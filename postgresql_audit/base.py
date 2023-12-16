import os
import string
import warnings
from contextlib import contextmanager
from weakref import WeakSet

import sqlalchemy as sa
from sqlalchemy import orm, text, literal_column
from sqlalchemy.dialects.postgresql import (
    array,
    ExcludeConstraint,
    INET,
    insert,
    JSONB
)
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utils import get_class_by_table

HERE = os.path.dirname(os.path.abspath(__file__))


class ImproperlyConfigured(Exception):
    pass


class ClassNotVersioned(Exception):
    pass


def read_file(file_):
    with open(os.path.join(HERE, file_)) as f:
        s = f.read()
    return s


def convert_callables(values):
    return {
        key: value() if callable(value) else value
        for key, value in values.items()
    }


class AuditLogger(object):
    _actor_cls = None

    def __init__(
        self,
        actor_cls=None,
        schema_name=None,
        use_statement_level_triggers=True
    ):
        if actor_cls is not None:
            self._actor_cls = actor_cls
        self.values = {}
        self.listeners = (
            (
                orm.Mapper,
                'instrument_class',
                self.detect_versioned_models
            ),
            (
                orm.session.Session,
                'before_flush',
                self.receive_before_flush,
            ),
        )
        self.schema_name = schema_name
        self.versioned_models = set()
        self.use_statement_level_triggers = use_statement_level_triggers

    def get_transaction_values(self):
        return self.values

    @contextmanager
    def disable(self, session):
        session.execute(
            text(
                "SET LOCAL postgresql_audit.enable_versioning = 'false'"
            )
        )
        try:
            yield
        finally:
            session.execute(
                text(
                    "SET LOCAL postgresql_audit.enable_versioning = 'true'"
                )
            )

    def render_tmpl(self, tmpl_name):
        file_contents = read_file(
            'templates/{}'.format(tmpl_name)
        ).replace('$$', '$$$$')
        tmpl = string.Template(file_contents)
        context = dict(schema_name=self.schema_name)

        if self.schema_name is None:
            context['schema_prefix'] = ''
            context['revoke_cmd'] = ''
        else:
            context['schema_prefix'] = '{}.'.format(self.schema_name)
            context['revoke_cmd'] = (
                'REVOKE ALL ON {schema_prefix}activity FROM public;'
            ).format(**context)

        temp = tmpl.substitute(**context)
        return temp

    def operators_sql(self):
        return text(self.render_tmpl('operators.sql'))

    def audit_table_sql(self):
        sql = ''
        if self.use_statement_level_triggers:
            sql += self.render_tmpl('create_activity_stmt_level.sql')
            sql += self.render_tmpl('audit_table_stmt_level.sql')
        else:
            sql += self.render_tmpl('create_activity_row_level.sql')
            sql += self.render_tmpl('audit_table_row_level.sql')

        return text(sql)

    def build_audit_table_query(self, table, exclude_columns=None):
        args = [table.name]
        if exclude_columns:
            for column in exclude_columns:
                if column not in table.c:
                    raise ImproperlyConfigured(
                        "Could not configure versioning. Table '{}'' does "
                        "not have a column named '{}'.".format(
                            table.name, column
                        )
                    )
            args.append(array(exclude_columns))

        if self.schema_name is None:
            func = sa.func.audit_table
        else:
            func = getattr(getattr(sa.func, self.schema_name), 'audit_table')
        return sa.select(func(*args))

    def save_transaction(self, session):
        transaction_mapper = sa.inspect(self.transaction_cls)
        engine = session.get_bind(transaction_mapper)
        dialect = engine.dialect
        table = self.transaction_cls.__table__

        if not isinstance(dialect, PGDialect):
            warnings.warn(
                '"{0}" is not a PostgreSQL dialect. No versioning data will '
                'be saved.'.format(dialect.__class__),
                RuntimeWarning
            )
            return

        values = convert_callables(self.get_transaction_values())
        if values:
            values['native_transaction_id'] = sa.func.txid_current()
            values['issued_at'] = sa.text("now() AT TIME ZONE 'UTC'")
            stmt = (
                insert(table)
                .values(**values)
                .on_conflict_do_nothing(
                    constraint='transaction_unique_native_tx_id'
                )
            )
            session.execute(stmt)

    def modified_columns(self, obj):
        columns = set()
        mapper = sa.inspect(obj.__class__)
        for key, attr in sa.inspect(obj).attrs.items():
            if key in mapper.synonyms.keys():
                continue
            prop = getattr(obj.__class__, key).property
            if attr.history.has_changes():
                columns |= set(
                    prop.columns
                    if isinstance(prop, sa.orm.ColumnProperty)
                    else
                    [local for local, remote in prop.local_remote_pairs]
                )
        return columns

    def is_modified(self, obj_or_session):
        if hasattr(obj_or_session, '__mapper__'):
            if not hasattr(obj_or_session, '__versioned__'):
                raise ClassNotVersioned(obj_or_session.__class__.__name__)
            excluded = obj_or_session.__versioned__.get('exclude', [])
            return bool(
                set([
                    column.name
                    for column in self.modified_columns(obj_or_session)
                ]) - set(excluded)
            )
        else:
            return any(
                self.is_modified(entity) or entity in obj_or_session.deleted
                for entity in obj_or_session
                if hasattr(entity, '__versioned__')
            )

    def receive_before_flush(self, session, flush_context, instances):
        if self.is_modified(session):
            self.save_transaction(session)

    def detect_versioned_models(self, mapper, cls):
        """
        Collect versioned class and add it to versioned_models list.

        :mapper mapper: SQLAlchemy mapper object
        :cls cls: SQLAlchemy declarative class
        """
        if hasattr(cls, '__versioned__') and cls not in self.versioned_models:
            self.versioned_models.add(cls)


    @property
    def actor_cls(self):
        if isinstance(self._actor_cls, str):
            if not self.base:
                raise ImproperlyConfigured(
                    'This manager does not have declarative base set up yet. '
                    'Call init method to set up this manager.'
                )
            registry = self.base.registry._class_registry
            try:
                return registry[self._actor_cls]
            except KeyError:
                raise ImproperlyConfigured(
                    'Could not build relationship between Activity'
                    ' and %s. %s was not found in declarative class '
                    'registry. Either configure AuditLogger to '
                    'use different actor class or disable this '
                    'relationship by setting it to None.' % (
                        self._actor_cls,
                        self._actor_cls
                    )
                )
        return self._actor_cls


def transaction_model_factory(Base, schema):
    class AuditLogTransaction(Base):
        __tablename__ = 'transaction'

        id = sa.Column(sa.BigInteger, primary_key=True)
        native_transaction_id = sa.Column(sa.BigInteger)
        issued_at = sa.Column(sa.DateTime)
        client_addr = sa.Column(INET)
        actor_id = sa.Column(sa.Text)

        __table_args__ = (
            ExcludeConstraint(
                (literal_column('native_transaction_id'), '='),
                (literal_column("tsrange(issued_at - INTERVAL '1 HOUR', issued_at)"), '&&'),
                name='transaction_unique_native_tx_id'
            ),
            {'schema': schema}
        )

        def __repr__(self):
            return '<{cls} id={id!r} issued_at={issued_at!r}>'.format(
                cls=self.__class__.__name__,
                id=self.id,
                issued_at=self.issued_at
            )

    return AuditLogTransaction


def activity_model_factory(Base, schema, transaction_cls):
    class AuditLogActivity(Base):
        __tablename__ = 'activity'
        __table_args__ = {'schema': schema}

        id = sa.Column(sa.BigInteger, primary_key=True)
        schema_name = sa.Column(sa.Text)
        table_name = sa.Column(sa.Text)
        relid = sa.Column(sa.Integer)
        issued_at = sa.Column(sa.DateTime)
        native_transaction_id = sa.Column(sa.BigInteger, index=True)
        verb = sa.Column(sa.Text)
        old_data = sa.Column(JSONB, default={}, server_default='{}')
        changed_data = sa.Column(JSONB, default={}, server_default='{}')

        @declared_attr
        def transaction_id(cls):
            return sa.Column(
                sa.BigInteger,
                sa.ForeignKey(transaction_cls.id)
            )

        @declared_attr
        def transaction(cls):
            return sa.orm.relationship(transaction_cls, backref='activities')

        @hybrid_property
        def data(self):
            data = self.old_data.copy() if self.old_data else {}
            if self.changed_data:
                data.update(self.changed_data)
            return data

        @data.expression
        def data(cls):
            return cls.old_data + cls.changed_data

        @property
        def object(self):
            table = Base.metadata.tables[self.table_name]
            cls = get_class_by_table(Base, table, self.data)
            return cls(**self.data)

        def __repr__(self):
            return (
                '<{cls} table_name={table_name!r} '
                'id={id!r}>'
            ).format(
                cls=self.__class__.__name__,
                table_name=self.table_name,
                id=self.id
            )

    return AuditLogActivity

audit_logger = AuditLogger()
