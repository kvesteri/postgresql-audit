import os
import re
from contextlib import contextmanager
from weakref import WeakSet

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import HSTORE, INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.schema import CreateTable


__version__ = '0.1.5'
HERE = os.path.dirname(os.path.abspath(__file__))


class ImproperlyConfigured(Exception):
    pass


@compiles(CreateTable)
def _add_if_not_exists(element, compiler, **kw):
    output = compiler.visit_create_table(element, **kw)
    if element.element.info.get('ifexists'):
        output = re.sub(
            '^\s*(CREATE (TEMP )?TABLE)',
            '\\1 IF NOT EXISTS',
            output,
            re.DOTALL
        )
    return output


def raw_execute(conn, stmt):
    cursor = conn.connection.cursor()
    compiled = stmt.compile(conn.engine)
    return cursor.execute(str(compiled), compiled.params)


def read_file(file_):
    with open(os.path.join(HERE, file_)) as f:
        s = f.read()
    return s


def assign_actor(base, cls, actor_cls):
    if actor_cls:
        primary_key = sa.inspect(actor_cls).primary_key[0]

        cls.actor_id = declared_attr(
            lambda self: sa.Column(
                primary_key.type,
                sa.ForeignKey(getattr(actor_cls, primary_key.name))
            )
        )

        cls.actor = declared_attr(
            lambda self: sa.orm.relationship(actor_cls)
        )
    else:
        cls.actor_id = sa.Column(sa.Text)


def activity_base(base, actor_cls):
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

    assign_actor(base, ActivityBase, actor_cls)
    return ActivityBase


@contextmanager
def activity_values(conn, **kwargs):
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
        self.pool_listener_args = (
            sa.pool.Pool,
            'checkin',
            self.connection_listener
        )
        self.engine_listener_args = (
            sa.engine.Engine,
            'before_cursor_execute',
            self.before_cursor_execute
        )

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

        # Use raw cursor so that SQLAlchemy events are not invoked
        raw_execute(conn, stmt.values(**kwargs))

    def reset_activity_values(self, conn):
        raw_execute(conn, self.table.delete())
        self.connections_with_tables_row.remove(conn.connection.connection)

    def connection_listener(self, dbapi_connection, connection_record):
        self.connections_with_tables.discard(dbapi_connection)
        self.connections_with_tables_row.discard(dbapi_connection)

    def create_temp_table(self, cursor, conn):
        cursor.execute(
            str(CreateTable(self.table).compile(conn.engine))
            +
            ' ON COMMIT PRESERVE ROWS'
        )

    def before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        raw_conn = conn.connection.connection
        if raw_conn not in self.connections_with_tables:
            self.create_temp_table(cursor, conn)
            self.connections_with_tables.add(raw_conn)
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
        sa.event.listen(*self.engine_listener_args)
        sa.event.listen(*self.pool_listener_args)

    def remove_listeners(self):
        self.remove_table_listeners()
        sa.event.remove(*self.engine_listener_args)
        sa.event.remove(*self.pool_listener_args)

    def activity_model_factory(self, base):
        class Activity(activity_base(base, self.actor_cls)):
            __tablename__ = 'activity'
            __table_args__ = {'schema': 'audit'}

        return Activity

    def activity_values_model_factory(self):
        base = activity_base(declarative_base(), self.actor_cls)

        class ActivityValues(base):
            __tablename__ = 'activity_values'
            __table_args__ = {
                'prefixes': ['TEMP'],
                'info': {'ifexists': True}
            }

        self.activity_values_cls = ActivityValues
        self.table = self.activity_values_cls.__table__
        return ActivityValues

    def init(self, base):
        self.base = base
        self.activity_cls = self.activity_model_factory(base)
        self.activity_values_cls = self.activity_values_model_factory()
        self.attach_listeners()


versioning_manager = VersioningManager()
