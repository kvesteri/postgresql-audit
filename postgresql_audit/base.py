import os
import string
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property

from flask import request
import sqlalchemy as sa
from sqlalchemy import orm, text, literal_column, DDL
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.dialects.postgresql import (
    ExcludeConstraint,
    INET,
    insert,
    JSONB
)
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utils import get_class_by_table
# from alembic_utils.pg_function import PGFunction
# from alembic_utils.pg_extension import PGExtension
# from alembic_utils.pg_trigger import PGTrigger

from postgresql_audit import alembic

HERE = os.path.dirname(os.path.abspath(__file__))


class ImproperlyConfigured(Exception):
    pass


class ClassNotVersioned(Exception):
    pass


@dataclass
class PGExtension:
    schema: str
    signature: str

    @property
    def create_sql(self):
        return text(f"CREATE EXTENSION {self.signature} WITH SCHEMA {self.schema}")

    @property
    def drop_sql(self):
        return text(f"DROP EXTENSION {self.signature}")

@dataclass
class PGFunction:
    schema: str
    signature: str
    create_sql: TextClause

    @property
    def drop_sql(self):
        return text(f'DROP FUNCTION {self.schema}.{self.signature} CASCADE')

@dataclass
class PGTrigger:
    schema: str
    signature: str
    table_name: str
    create_sql: TextClause

    @property
    def drop_sql(self):
        return text(f'DROP TRIGGER {self.signature} ON {self.table_name}')


def read_file(file_):
    with open(os.path.join(HERE, file_)) as f:
        s = f.read()
    return s


def convert_callables(values):
    return {
        key: value() if callable(value) else value
        for key, value in values.items()
    }

def default_actor_id():
    from flask_login import current_user

    try:
        return current_user.id
    except AttributeError:
        return

def default_client_addr():
    # Return None if we are outside of request context.
    return (request and request.remote_addr) or None


class AuditLogger(object):
    _actor_cls = None
    writer = None

    def __init__(
        self,
        db,
        get_actor_id=None,
        get_client_addr=None,
        actor_cls=None,
        schema=None,
    ):
        self._actor_cls = actor_cls or 'User'
        self.get_actor_id = get_actor_id or default_actor_id
        self.get_client_addr = get_client_addr or default_client_addr
        self.db = db
        self.values = {}
        self.schema = schema
        self.versioned_tables = set()
        self.base = db.Model
        self.transaction_cls = self.transaction_model_factory()
        self.activity_cls = self.activity_model_factory()
        self.detect_versioned_tables()
        self.attach_listeners()
        self.initialize_alembic_operations()

    def attach_listeners(self):
        listeners = (
            # (orm.Mapper, 'instrument_class', self.detect_versioned_tables),
            (orm.session.Session, 'before_flush', self.receive_before_flush),
        )
        for listener in listeners:
            sa.event.listen(*listener)

    def initialize_alembic_operations(self):
        alembic.setup_schema(self)
        alembic.setup_functions_and_triggers(self)
        self.writer = alembic.init_migration_ops(self.schema)

    def process_revision_directives(self, context, revision, directives):
        if self.writer:
            self.writer.process_revision_directives(context, revision, directives)

    @property
    def prefix(self):
        return f"{self.schema}." if self.schema else ""

    @cached_property
    def pg_entities(self):
        return [
            self.pg_btree_gist_extension,
            *self.pg_functions,
            *self.pg_triggers,
        ]

    @cached_property
    def pg_functions(self):
        return [
            self.pg_get_setting,
            self.pg_jsonb_subtract,
            self.pg_jsonb_change_key_name,
            self.pg_create_activity,
        ]

    @property
    def pg_triggers(self):
        return [t for triggers in self.pg_triggers_per_table.values() for t in triggers]

    @cached_property
    def pg_triggers_per_table(self):
        triggers_per_table = {}
        for table in self.versioned_tables:
            target_schema = table.schema or "public"
            versioned = table.info.get("versioned", {})
            excluded_columns = ""
            if "exclude" in versioned:
                joined_excludes = ",".join(versioned['exclude'])
                excluded_columns = "'{" + joined_excludes + "}'"

            triggers_per_table[table.name] = [
                PGTrigger(
                    schema=target_schema,
                    table_name=table.name,
                    signature="audit_trigger_insert",
                    create_sql=self.render_sql_template("audit_trigger_insert.sql", table_name=table.name, excluded_columns=excluded_columns),
                ),
                PGTrigger(
                    schema=target_schema,
                    table_name=table.name,
                    signature="audit_trigger_update",
                    create_sql=self.render_sql_template("audit_trigger_update.sql", table_name=table.name, excluded_columns=excluded_columns),
                ),
                PGTrigger(
                    schema=target_schema,
                    table_name=table.name,
                    signature="audit_trigger_delete",
                    create_sql=self.render_sql_template("audit_trigger_delete.sql", table_name=table.name, excluded_columns=excluded_columns),
                )
            ]

        return triggers_per_table

    @property
    def functions_by_signature(self) -> dict[str, PGFunction]:
        return {pg_func.signature: pg_func for pg_func in self.pg_functions}

    @cached_property
    def pg_btree_gist_extension(self) -> PGExtension:
        return PGExtension(schema="public", signature="btree_gist")

    @property
    def pg_get_setting(self) -> PGFunction:
        return PGFunction(
            schema=self.schema,
            signature="get_setting(setting text, fallback text)",
            create_sql=self.render_sql_template("get_setting.sql")
        )

    @property
    def pg_jsonb_subtract(self) -> PGFunction:
        return PGFunction(
            schema=self.schema,
            signature="jsonb_subtract(arg1 jsonb, arg2 jsonb)",
            create_sql=self.render_sql_template("jsonb_subtract.sql")
        )

    @property
    def pg_jsonb_change_key_name(self) -> PGFunction:
        return PGFunction(
            schema=self.schema,
            signature="jsonb_change_key_name(data jsonb, old_key text, new_key text)",
            create_sql=self.render_sql_template("jsonb_change_key_name.sql")
        )

    @property
    def pg_create_activity(self) -> PGFunction:
        return PGFunction(
            schema=self.schema,
            signature="create_activity()",
            create_sql=self.render_sql_template("create_activity.sql")
        )


    def get_transaction_values(self):
        if ('client_addr' not in self.values):
            self.values['client_addr'] = self.get_client_addr()
        if ('actor_id' not in self.values):
            self.values['actor_id'] = self.get_actor_id()

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

    def render_sql_template(self, tmpl_name: str, as_text: bool = True, **kwargs) -> TextClause | DDL:
        file_contents = read_file('templates/{}'.format(tmpl_name)).replace('$$', '$$$$')
        tmpl = string.Template(file_contents)
        context = dict(schema=self.schema)

        if self.schema is None:
            context['schema_prefix'] = ''
            context['revoke_cmd'] = ''
        else:
            context['schema_prefix'] = '{}.'.format(self.schema)
            context['revoke_cmd'] = (
                'REVOKE ALL ON {schema_prefix}activity FROM public;'
            ).format(**context)

        sql = tmpl.substitute(**context, **kwargs)

        if not as_text:
            return DDL(sql)

        return text(sql)

    def receive_before_flush(self, session, flush_context, instances):
        if self.is_session_modified(session):
            self.save_transaction(session)

    def is_session_modified(self, session):
        return any(
            self.is_entity_modified(entity) or entity in session.deleted
            for entity in session
            if entity.__table__.info.get('versioned') is not None
        )

    def is_entity_modified(self, entity):
        versioned = entity.__table__.info.get('versioned')
        if versioned is None:
            raise ClassNotVersioned(entity.__class__.__name__)

        excluded_cols = set(versioned.get('exclude', []))
        modified_cols = {column.name for column in self.modified_columns(entity)}

        return bool(modified_cols - excluded_cols)

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

    def detect_versioned_tables(self):
        for table in self.db.metadata.tables.values():
            if table.info.get("versioned") is not None:
                self.versioned_tables.add(table)

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


    def transaction_model_factory(self):
        class AuditLogTransaction(self.base):
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
                {'schema': self.schema}
            )

            def __repr__(self):
                return '<{cls} id={id!r} issued_at={issued_at!r}>'.format(
                    cls=self.__class__.__name__,
                    id=self.id,
                    issued_at=self.issued_at
                )

        return AuditLogTransaction


    def activity_model_factory(self):
        class AuditLogActivity(self.base):
            __tablename__ = 'activity'
            __table_args__ = {'schema': self.schema}

            id = sa.Column(sa.BigInteger, primary_key=True)
            schema = sa.Column(sa.Text)
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
                    sa.ForeignKey(self.transaction_cls.id)
                )

            @declared_attr
            def transaction(cls):
                return sa.orm.relationship(self.transaction_cls, backref='activities')

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
                table = self.base.metadata.tables[self.table_name]
                cls = get_class_by_table(self.base, table, self.data)
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
