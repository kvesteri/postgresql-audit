import os
from datetime import timedelta
from weakref import WeakSet

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import array, INET, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import expression
from sqlalchemy_utils import get_class_by_table


HERE = os.path.dirname(os.path.abspath(__file__))
cached_statements = {}


class ImproperlyConfigured(Exception):
    pass


class jsonb_merge(expression.FunctionElement):
    """
    Provides jsonb_merge as a SQLAlchemy FunctionElement.

    ::


        import sqlalchemy as sa
        from postgresql_audit import jsonb_merge


        data = {'key1': 1, 'key3': 4}
        merge_data = {'key1': 2, 'key2': 3}
        query = sa.select([jsonb_merge(data, merge_data)])
        session.execute(query).scalar()  # {'key1': 2, 'key2': 3, 'key3': 4}
    """
    type = JSONB()
    name = 'jsonb_merge'


@compiles(jsonb_merge)
def compile_jsonb_merge(element, compiler, **kw):
    arg1, arg2 = list(element.clauses)
    return 'jsonb_merge({0}, {1})'.format(
        compiler.process(arg1),
        compiler.process(arg2)
    )


def change_column_name(conn, table, old_column_name, new_column_name):
    """
    Changes given audit.activity jsonb data column key. This function is useful
    when you are doing schema changes that require changing a column name.

    :param conn:
        An object that is able to execute SQL (either SQLAlchemy Connection,
        Engine or Alembic Operations object)
    :param table:
        The table to run the column name changes against
    :param old_column_name:
        Name of the column to change
    :param new_column_name:
        New colum name
    """
    activity_table = sa.Table(
        'activity',
        sa.MetaData(bind=conn),
        schema='audit',
        autoload=True
    )
    query = (
        activity_table
        .update()
        .values(
            old_data=jsonb_change_key_name(
                activity_table.c.old_data,
                old_column_name,
                new_column_name
            ),
            changed_data=jsonb_change_key_name(
                activity_table.c.changed_data,
                old_column_name,
                new_column_name
            )
        )
        .where(activity_table.c.table_name == table)
    )
    return conn.execute(query)


def remove_column(conn, table, column_name):
    """
    Removes given audit.activity jsonb data column key. This function is useful
    when you are doing schema changes that require removeing a column.

    Let's say you've been using PostgreSQL-Audit for a while for a table called
    article. Now you want to remove one audited column called 'created_at' from
    this table.

    ::

        from alembic import op
        from postgresql_audit import remove_column


        def upgrade():
            op.remove_column('article', 'created_at')
            remove_column(op, 'article', 'created_at')


    :param conn:
        An object that is able to execute SQL (either SQLAlchemy Connection,
        Engine or Alembic Operations object)
    :param table:
        The table to remove the column from
    :param old_column_name:
        Name of the column to remove
    """
    activity_table = sa.Table(
        'activity',
        sa.MetaData(bind=conn),
        schema='audit',
        autoload=True
    )
    remove = sa.cast(column_name, sa.Text)
    query = (
        activity_table
        .update()
        .values(
            old_data=activity_table.c.old_data - remove,
            changed_data=activity_table.c.changed_data - remove,
        )
        .where(activity_table.c.table_name == table)
    )
    return conn.execute(query)


class jsonb_change_key_name(expression.FunctionElement):
    """
    Provides jsonb_change_key_name as a SQLAlchemy FunctionElement.

    ::


        import sqlalchemy as sa
        from postgresql_audit import jsonb_change_key_name


        data = {'key1': 1, 'key3': 4}
        query = sa.select([jsonb_merge(data, 'key1', 'key2')])
        session.execute(query).scalar()  # {'key2': 1, 'key3': 4}
    """
    type = JSONB()
    name = 'jsonb_change_key_name'


@compiles(jsonb_change_key_name)
def compile_jsonb_change_key_name(element, compiler, **kw):
    arg1, arg2, arg3 = list(element.clauses)
    arg1.type = JSONB()
    return 'jsonb_change_key_name({0}, {1}, {2})'.format(
        compiler.process(arg1),
        compiler.process(arg2),
        compiler.process(arg3)
    )


class StatementExecutor(object):
    def __init__(self, stmt):
        self.stmt = stmt

    def __call__(self, target, bind, **kwargs):
        tx = bind.begin()
        bind.execute(self.stmt)
        tx.commit()


def read_file(file_):
    with open(os.path.join(HERE, file_)) as f:
        s = f.read()
    return s


def assign_actor(base, cls, actor_cls):
    if hasattr(cls, 'actor_id'):
        return
    if actor_cls:
        primary_key = sa.inspect(actor_cls).primary_key[0]

        cls.actor_id = sa.Column('actor_id', primary_key.type)
        cls.actor = orm.relationship(
            actor_cls,
            primaryjoin=cls.actor_id == (
                getattr(
                    actor_cls,
                    primary_key.name
                )
            ),
            foreign_keys=[cls.actor_id]
        )
    else:
        cls.actor_id = sa.Column(sa.Text)


def audit_table(table, exclude_columns=None):
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

    query = sa.select(
        [sa.func.audit.audit_table(*args)]
    )
    if query not in cached_statements:
        cached_statements[query] = StatementExecutor(query)
    listener = (table, 'after_create', cached_statements[query])
    if not sa.event.contains(*listener):
        sa.event.listen(*listener)


def activity_base(base):
    class ActivityBase(base):
        __abstract__ = True
        id = sa.Column(sa.BigInteger, primary_key=True)
        schema_name = sa.Column(sa.Text)
        table_name = sa.Column(sa.Text)
        relid = sa.Column(sa.Integer)
        issued_at = sa.Column(sa.DateTime)
        transaction_id = sa.Column(sa.BigInteger)
        client_addr = sa.Column(INET)
        verb = sa.Column(sa.Text)
        target_id = sa.Column(sa.Text)
        old_data = sa.Column(JSONB)
        changed_data = sa.Column(JSONB)

        @hybrid_property
        def data(self):
            data = self.old_data.copy() if self.old_data else {}
            if self.changed_data:
                data.update(self.changed_data)
            return data

        @data.expression
        def data(cls):
            return jsonb_merge(cls.old_data, cls.changed_data)

        @property
        def object(self):
            table = base.metadata.tables[self.table_name]
            cls = get_class_by_table(base, table, self.data)
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
    return ActivityBase


def convert_callables(values):
    result = {}
    for key, value in values.items():
        if callable(value):
            result[key] = value()
        else:
            result[key] = value
    return result


class VersioningManager(object):
    table_listeners = [
        (
            'before_create',
            sa.schema.DDL(read_file('schema.sql')),
        ),
        (
            'after_create',
            sa.schema.DDL(
                read_file('create_activity.sql').replace('%', '%%') +
                read_file('audit_table.sql').replace('%', '%%')
            )
        ),
        (
            'after_drop',
            sa.schema.DDL('DROP SCHEMA audit CASCADE')
        )
    ]

    def __init__(self, actor_cls=None):
        self.values = {}
        self._actor_cls = actor_cls
        self.listeners = (
            (
                orm.mapper,
                'instrument_class',
                self.instrument_versioned_classes
            ),
            (
                orm.mapper,
                'after_configured',
                self.configure_versioned_classes
            ),
            (
                orm.session.Session,
                'after_flush',
                self.receive_after_flush,
            ),
        )
        self.pending_classes = WeakSet()
        self.cached_ddls = {}

    @property
    def transaction_values(self):
        return self.values

    def set_activity_values(self, session):
        table = self.activity_cls.__table__
        if self.values:
            values = convert_callables(self.transaction_values)
            stmt = (
                table
                .update()
                .values(**values)
                .where(
                    sa.and_(
                        table.c.transaction_id == sa.func.txid_current(),
                        table.c.issued_at > (
                            sa.func.now() - timedelta(days=1)
                        )
                    )
                )
            )
            session.execute(stmt)

    def receive_after_flush(self, session, flush_context):
        self.set_activity_values(session)

    def instrument_versioned_classes(self, mapper, cls):
        """
        Collect versioned class and add it to pending_classes list.

        :mapper mapper: SQLAlchemy mapper object
        :cls cls: SQLAlchemy declarative class
        """
        if hasattr(cls, '__versioned__') and cls not in self.pending_classes:
            self.pending_classes.add(cls)

    def configure_versioned_classes(self):
        """
        Configures all versioned classes that were collected during
        instrumentation process.
        """
        for cls in self.pending_classes:
            audit_table(cls.__table__, cls.__versioned__.get('exclude'))
        assign_actor(self.base, self.activity_cls, self.actor_cls)

    def attach_table_listeners(self):
        for values in self.table_listeners:
            sa.event.listen(self.activity_cls.__table__, *values)

    def remove_table_listeners(self):
        for values in self.table_listeners:
            sa.event.remove(self.activity_cls.__table__, *values)

    @property
    def actor_cls(self):
        if isinstance(self._actor_cls, str):
            if not self.base:
                raise ImproperlyConfigured(
                    'This manager does not have declarative base set up yet. '
                    'Call init method to set up this manager.'
                )
            registry = self.base._decl_class_registry
            try:
                return registry[self._actor_cls]
            except KeyError:
                raise ImproperlyConfigured(
                    'Could not build relationship between Activity'
                    ' and %s. %s was not found in declarative class '
                    'registry. Either configure VersioningManager to '
                    'use different actor class or disable this '
                    'relationship by setting it to None.' % (
                        self._actor_cls,
                        self._actor_cls
                    )
                )
        return self._actor_cls

    def attach_listeners(self):
        self.attach_table_listeners()
        for listener in self.listeners:
            sa.event.listen(*listener)

    def remove_listeners(self):
        self.remove_table_listeners()
        for listener in self.listeners:
            sa.event.remove(*listener)

    def activity_model_factory(self, base):
        class Activity(activity_base(base)):
            __tablename__ = 'activity'
            __table_args__ = {'schema': 'audit'}

        return Activity

    def init(self, base):
        self.base = base
        self.activity_cls = self.activity_model_factory(base)
        self.attach_listeners()


versioning_manager = VersioningManager()
