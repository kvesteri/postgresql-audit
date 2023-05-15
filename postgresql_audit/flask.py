from contextlib import contextmanager
from copy import copy

from flask import g, request

from .base import VersioningManager as BaseVersioningManager


class VersioningManager(BaseVersioningManager):
    _actor_cls = 'User'

    def get_transaction_values(self):
        values = copy(self.values)
        if g and hasattr(g, 'activity_values'):
            values.update(g.activity_values)
        if (
            'client_addr' not in values and
            self.default_client_addr is not None
        ):
            values['client_addr'] = self.default_client_addr
        if (
            'actor_id' not in values and
            self.default_actor_id is not None
        ):
            values['actor_id'] = self.default_actor_id
        return values

    @property
    def default_actor_id(self):
        from flask_login import current_user

        try:
            return current_user.id
        except AttributeError:
            return

    @property
    def default_client_addr(self):
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


versioning_manager = VersioningManager()
