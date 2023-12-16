from contextlib import contextmanager
from copy import copy

from flask import g, request
from sqlalchemy import text

from .base import AuditLogger as BaseAuditLogger


class AuditLogger(BaseAuditLogger):
    _actor_cls = None
    _get_actor_id = None
    _get_client_addr = None

    def __init__(self, get_actor_id=None, get_client_addr=None, actor_cls=None, **kwargs):
        self._get_actor_id = get_actor_id or default_actor_id
        self._get_client_addr = get_client_addr or default_client_addr
        self._actor_cls = actor_cls or 'User'
        super().__init__(**kwargs)

    def init_app(self, app):
        db = app.extensions["sqlalchemy"]

        with app.app_context():
            self._setup_triggers(app, db)

    def _setup_triggers(self, app, db):
        schema_exists_sql = text(f"SELECT TRUE FROM information_schema.schemata WHERE schema_name = '{self.schema_name}'")
        if not db.session.scalar(schema_exists_sql):
            return

        audit_func_exists_sql = text("SELECT TRUE FROM pg_proc WHERE proname = 'audit_table'")
        if not db.session.scalar(audit_func_exists_sql):
            return

        tables = 0
        for mappers in db.Model.registry.mappers:
            cls = mappers.class_
            if not hasattr(cls, "__versioned__"):
                continue

            table = cls.__table__
            exclude_columns = cls.__versioned__.get('exclude', [])
            setup_triggers_sql = self.build_audit_table_query(table, exclude_columns=exclude_columns)

            db.session.execute(setup_triggers_sql)
            tables += 1

        if tables > 0:
            app.logger.info(f"Configured audit triggers for {tables} tables")
            db.session.commit()

    def get_transaction_values(self):
        values = copy(self.values)
        if g and hasattr(g, 'activity_values'):
            values.update(g.activity_values)
        if (
            'client_addr' not in values and
            self._get_client_addr is not None
        ):
            values['client_addr'] = self._get_client_addr()
        if (
            'actor_id' not in values and
            self._get_actor_id is not None
        ):
            values['actor_id'] = self._get_actor_id()
        return values


def default_actor_id():
    from flask_login import current_user

    try:
        return current_user.id
    except AttributeError:
        return

def default_client_addr():
    # Return None if we are outside of request context.
    return (request and request.remote_addr) or None

def merge_dicts(a, b):
    c = copy(a)
    c.update(b)
    return c


@contextmanager
def activity_values(**values):
    if not g:
        yield  # Needed for contextmanager
        return
    if hasattr(g, 'activity_values'):
        previous_value = g.activity_values
        values = merge_dicts(previous_value, values)
    else:
        previous_value = None
    g.activity_values = values
    yield
    if previous_value is None:
        del g.activity_values
    else:
        g.activity_values = previous_value


audit_logger = AuditLogger()
