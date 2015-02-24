from __future__ import absolute_import
from contextlib import contextmanager
from copy import copy

from flask import g, request
from flask.globals import _app_ctx_stack, _request_ctx_stack

from .base import VersioningManager


class FlaskVersioningManager(VersioningManager):
    @property
    def transaction_values(self):
        values = copy(self.values)
        if hasattr(g, 'activity_values'):
            values.update(g.activity_values)
        return values


def fetch_current_user_id():
    from flask.ext.login import current_user

    # Return None if we are outside of request context.
    if _app_ctx_stack.top is None or _request_ctx_stack.top is None:
        return

    try:
        return current_user.id
    except AttributeError:
        return


def fetch_remote_addr():
    # Return None if we are outside of request context.
    if _app_ctx_stack.top is None or _request_ctx_stack.top is None:
        return
    return request.remote_addr


@contextmanager
def activity_values(**values):
    g.activity_values = values
    yield
    del g.activity_values


versioning_manager = FlaskVersioningManager(actor_cls='User')
versioning_manager.values['actor_id'] = fetch_current_user_id
versioning_manager.values['client_addr'] = fetch_remote_addr
