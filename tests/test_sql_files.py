# -*- coding: utf-8 -*-
import pytest

from .utils import last_activity


@pytest.mark.usefixtures('versioning_manager', 'table_creator')
class TestActivityCreationWithColumnExclusion(object):
    @pytest.fixture
    def audit_trigger_creator(self, session, user_class):
        session.execute(
            '''SELECT audit_table('{0}', '{{"age"}}')'''.format(
                user_class.__tablename__
            )
        )

    @pytest.fixture
    def user(self, session, user_class, audit_trigger_creator):
        user = user_class(name='John', age=15)
        session.add(user)
        session.flush()
        return user

    def test_insert(self, user, connection):
        activity = last_activity(connection)
        assert activity['old_data'] is None
        assert activity['changed_data'] == {
            'id': user.id,
            'name': 'John'
        }
        assert activity['table_name'] == 'user'
        assert activity['native_transaction_id'] > 0
        assert activity['verb'] == 'insert'

    def test_update(self, user, session):
        user.name = 'Luke'
        user.age = 18
        session.flush()
        activity = last_activity(session)
        assert activity['changed_data'] == {'name': 'Luke'}
        assert activity['old_data'] == {
            'id': user.id,
            'name': 'John',
        }
        assert activity['table_name'] == 'user'
        assert activity['native_transaction_id'] > 0
        assert activity['verb'] == 'update'

    def test_delete(self, user, session):
        session.delete(user)
        session.flush()
        activity = last_activity(session)
        assert activity['changed_data'] is None
        assert activity['old_data'] == {
            'id': user.id,
            'name': 'John',
        }
        assert activity['table_name'] == 'user'
        assert activity['native_transaction_id'] > 0
        assert activity['verb'] == 'delete'
