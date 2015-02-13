# -*- coding: utf-8 -*-
import pytest

from postgresql_audit import activity_values, versioning_manager
from .utils import last_activity


@pytest.fixture(scope='module')
def activity_cls(base):
    models = versioning_manager.activity_models_factory(base)
    versioning_manager.attach_listeners()
    return models[0]


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestActivityCreation(object):
    def test_insert(self, user, connection):
        activity = last_activity(connection)
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] is None
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John',
            'age': '15'
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'insert'

    def test_activity_values_context_manager(
        self,
        activity_cls,
        user_class,
        session
    ):
        with activity_values(session.connection(), target_id=1):
            user = user_class(name='John')
            session.add(user)
            session.commit()

        activity = last_activity(session)
        assert activity['target_id'] == '1'

    def test_operation_after_commit(
        self,
        activity_cls,
        user_class,
        session
    ):
        with activity_values(session.connection(), target_id=1):
            user = user_class(name='Jack')
            session.add(user)
            session.commit()
        with activity_values(session.connection(), target_id=1):
            user = user_class(name='Jack')
            session.add(user)
            session.commit()
        activity = last_activity(session)
        assert session.query(activity_cls).count() == 2
        assert activity['target_id'] == '1'

    def test_operation_after_rollback(
        self,
        activity_cls,
        user_class,
        session
    ):
        with activity_values(session.connection(), target_id=1):
            user = user_class(name='John')
            session.add(user)
            session.rollback()
        with activity_values(session.connection(), target_id=1):
            user = user_class(name='John')
            session.add(user)
            session.commit()
        activity = last_activity(session)
        assert session.query(activity_cls).count() == 1
        assert activity['target_id'] == '1'

    def test_manager_defaults(
        self,
        user_class,
        session
    ):
        versioning_manager.values = {'actor_id': 1}
        user = user_class(name='John')
        session.add(user)
        session.commit()
        activity = last_activity(session)
        assert activity['actor_id'] == '1'
