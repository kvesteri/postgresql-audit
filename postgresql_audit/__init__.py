import os
import re
from contextlib import contextmanager
from weakref import WeakSet

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import array, HSTORE, INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import CreateTable, DropTable


__version__ = '0.2.3'
HERE = os.path.dirname(os.path.abspath(__file__))
cached_statements = {}


class ImproperlyConfigured(Exception):
    pass


@compiles(CreateTable)
def _add_if_not_exists_to_create(element, compiler, **kw):
    output = compiler.visit_create_table(element, **kw)
    if element.element.info.get('ifexists'):
        output = re.sub(
            '^\s*(CREATE (TEMP )?TABLE)',
            '\\1 IF NOT EXISTS',
            output,
            re.DOTALL
        )
    return output


@compiles(DropTable)
def _add_if_not_exists_to_drop(element, compiler, **kw):
    output = compiler.visit_drop_table(element, **kw)
    if element.element.info.get('ifexists'):
        output = re.sub(
            '^\s*(DROP (TEMP )?TABLE)',
            '\\1 IF EXISTS',
            output,
            re.DOTALL
        )
    return output


class StatementExecutor(object):
    def __init__(self, stmt):
        self.stmt = stmt

    def __call__(self, target, bind, **kwargs):
        tx = bind.begin()
        bind.execute(self.stmt)
        tx.commit()


def get_cursor(conn):
    if isinstance(conn, sa.engine.Engine):
        return conn.raw_connection().connection.cursor()
    elif isinstance(conn, sa.engine.Connection):
        return conn.connection.cursor()
    else:
        return conn.cursor()


def raw_execute(conn, stmt):
    cursor = get_cursor(conn)
    if isinstance(stmt, str):
        compiled = stmt
        params = []
    else:
        compiled = stmt.compile(conn.engine)
        params = compiled.params
    return cursor.execute(str(compiled), params)


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
        cls.actor = sa.orm.relationship(
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


def audit_table(table, exclude_columns):
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
        client_port = sa.Column(sa.Integer)
        verb = sa.Column(sa.Text)
        object_id = sa.Column(sa.Text)
        target_id = sa.Column(sa.Text)
        row_data = sa.Column(HSTORE)
        changed_fields = sa.Column(HSTORE)

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


@contextmanager
def activity_values(conn, **kwargs):
    versioning_manager.create_temp_table_if_not_exists(conn)
    versioning_manager.set_activity_values(conn, **kwargs)
    yield
    versioning_manager.reset_activity_values(conn)


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
        self.activity_values_base = declarative_base()
        self.values = {}
        self._actor_cls = actor_cls
        self.connections_with_tables = WeakSet()
        self.connections_with_tables_row = WeakSet()
        self.listeners = (
            (
                sa.pool.Pool,
                'checkin',
                self.connection_listener
            ),
            (
                sa.engine.Engine,
                'before_cursor_execute',
                self.before_cursor_execute
            ),
            (
                sa.orm.mapper,
                'instrument_class',
                self.instrument_versioned_classes
            ),
            (
                sa.orm.mapper,
                'after_configured',
                self.configure_versioned_classes
            )
        )
        self.pending_classes = WeakSet()
        self.cached_ddls = {}

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
        assign_actor(
            self.temporary_base,
            self.activity_values_cls,
            self.actor_cls
        )
        assign_actor(self.base, self.activity_cls, self.actor_cls)

    def attach_table_listeners(self):
        for values in self.table_listeners:
            sa.event.listen(self.activity_cls.__table__, *values)

    def remove_table_listeners(self):
        for values in self.table_listeners:
            sa.event.remove(self.activity_cls.__table__, *values)

    def set_activity_values(self, conn, **kwargs):
        raw_conn = conn.connection.connection
        if raw_conn not in self.connections_with_tables_row:
            stmt = self.table.insert()
            self.connections_with_tables_row.add(raw_conn)
        else:
            stmt = self.table.update()

        # Convert callables to scalars
        kwargs_copy = kwargs.copy()
        for k, v in kwargs.items():
            if callable(v):
                kwargs_copy[k] = v()
        # Use raw cursor so that SQLAlchemy events are not invoked
        raw_execute(conn, stmt.values(**kwargs_copy))

    def reset_connection_cache(self, dbapi_connection):
        self.connections_with_tables.discard(dbapi_connection)
        self.connections_with_tables_row.discard(dbapi_connection)

    def reset_activity_values(self, conn):
        raw_execute(conn, DropTable(self.table))
        self.reset_connection_cache(conn.connection.connection)

    def connection_listener(self, dbapi_connection, connection_record):
        self.reset_connection_cache(dbapi_connection)

    def create_temp_table(self, conn):
        conn.execute(
            str(CreateTable(self.table).compile(conn.engine))
            +
            ' ON COMMIT PRESERVE ROWS'
        )

    def create_temp_table_if_not_exists(self, conn):
        raw_conn = conn.connection.connection
        if raw_conn not in self.connections_with_tables:
            self.create_temp_table(conn)
            self.connections_with_tables.add(raw_conn)

    def before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        stmt = statement.strip().lower()
        if stmt.startswith(('insert', 'update', 'delete')):
            self.create_temp_table_if_not_exists(conn)
            if self.values:
                self.set_activity_values(conn, **self.values)

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

    def activity_values_model_factory(self):
        class ActivityValues(activity_base(self.temporary_base)):
            __tablename__ = 'activity_values'
            __table_args__ = {
                'prefixes': ['TEMP'],
                'info': {'ifexists': True}
            }

        return ActivityValues

    def init(self, base):
        self.base = base
        self.temporary_base = declarative_base()
        self.activity_cls = self.activity_model_factory(base)
        self.activity_values_cls = self.activity_values_model_factory()
        self.table = self.activity_values_cls.__table__
        self.attach_listeners()


versioning_manager = VersioningManager()
