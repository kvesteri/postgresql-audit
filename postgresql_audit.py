import re
from contextlib import contextmanager
from weakref import WeakSet

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import HSTORE, INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import CreateTable


__version__ = '0.1.1'


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
    with open(file_) as f:
        s = f.read()
    return s


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
        actor_id = sa.Column(sa.Text)
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

    def __init__(self):
        self.base = sa.ext.declarative.declarative_base()
        self.values = {}
        self.connections_with_tables = WeakSet()
        self.connections_with_tables_row = WeakSet()

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

    def attach_listeners(self):
        self.attach_table_listeners()
        sa.event.listen(
            sa.engine.Engine,
            'before_cursor_execute',
            self.before_cursor_execute
        )
        sa.event.listen(
            sa.pool.Pool,
            'checkin',
            self.connection_listener
        )

    def remove_listeners(self):
        self.remove_table_listeners()
        sa.event.remove(
            sa.engine.Engine,
            'before_cursor_execute',
            self.before_cursor_execute
        )
        sa.event.remove(
            sa.pool.Pool,
            'checkin',
            self.connection_listener
        )

    def activity_model_factory(self, base):
        class Activity(activity_base(base)):
            __tablename__ = 'activity'
            __table_args__ = {'schema': 'audit'}

        return Activity

    def activity_values_model_factory(self):
        class ActivityValues(activity_base(self.base)):
            __tablename__ = 'activity_values'
            __table_args__ = {
                'prefixes': ['TEMP'],
                'info': {'ifexists': True}
            }

        self.activity_values_cls = ActivityValues
        self.table = self.activity_values_cls.__table__
        return ActivityValues

    def init(self, base):
        self.activity_cls = self.activity_model_factory(base)
        self.activity_values_cls = self.activity_values_model_factory()
        self.attach_listeners()


versioning_manager = VersioningManager()
