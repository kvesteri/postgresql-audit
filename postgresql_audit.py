import re
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import HSTORE, INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import CreateTable


__version__ = '0.1'


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


def read_file(file_):
    with open(file_) as f:
        s = f.read()
    return s.decode('utf8')


def activity_base(base):
    class ActivityBase(base):
        __abstract__ = True
        event_id = sa.Column(sa.BigInteger, primary_key=True)
        schema_name = sa.Column(sa.Text)
        table_name = sa.Column(sa.Text)
        relid = sa.Column(sa.Integer)
        session_user_name = sa.Column(sa.Text)
        issued_at = sa.Column(sa.DateTime)
        transaction_id = sa.Column(sa.BigInteger)
        application_name = sa.Column(sa.Text)
        client_addr = sa.Column(INET)
        client_port = sa.Column(sa.Integer)
        verb = sa.Column(sa.Text)
        actor_id = sa.Column(sa.Text)
        object_id = sa.Column(sa.Text)
        target_id = sa.Column(sa.Text)
        row_data = sa.Column(HSTORE)
        changed_fields = sa.Column(HSTORE)

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
    tables_with_row = set()

    def __init__(self):
        self.base = sa.ext.declarative.declarative_base()
        self.values = {}

    def attach_table_listeners(self):
        for values in self.table_listeners:
            sa.event.listen(self.activity_cls.__table__, *values)

    def remove_table_listeners(self):
        for values in self.table_listeners:
            sa.event.remove(self.activity_cls.__table__, *values)

    def set_activity_values(self, conn, **kwargs):
        if conn not in self.tables_with_row:
            stmt = self.table.insert()
            self.tables_with_row.add(conn)
        else:
            stmt = self.table.update()

        # Use raw cursor so that SQLAlchemy events are not invoked
        cursor = conn.connection.cursor()
        compiled = stmt.values(**kwargs).compile(conn.engine)
        cursor.execute(str(compiled), compiled.params)

    def reset_activity_values(self, conn):
        conn.execute(self.table.delete())
        self.tables_with_row.remove(conn)

    def before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        cursor.execute(
            str(CreateTable(self.table).compile(conn.engine))
            +
            ' ON COMMIT DELETE ROWS'
        )
        if self.values:
            self.set_activity_values(conn, **self.values)

    def attach_listeners(self):
        self.attach_table_listeners()
        sa.event.listen(
            sa.engine.Engine,
            'before_cursor_execute',
            self.before_cursor_execute
        )

    def remove_listeners(self):
        self.remove_table_listeners()
        sa.event.remove(
            sa.engine.Engine,
            'before_cursor_execute',
            self.before_cursor_execute
        )

    def activity_models_factory(self, base):
        class Activity(activity_base(base)):
            __tablename__ = 'activity'
            __table_args__ = {'schema': 'audit'}

        class ActivityValues(activity_base(self.base)):
            __tablename__ = 'activity_values'
            __table_args__ = {
                'prefixes': ['TEMP'],
                'info': {'ifexists': True}
            }

        self.activity_cls = Activity
        self.activity_values_cls = ActivityValues
        self.table = self.activity_values_cls.__table__
        return [Activity, ActivityValues]


versioning_manager = VersioningManager()


def make_versioned(actor_id_callback=None):
    pass


def remove_versioning():
    pass
