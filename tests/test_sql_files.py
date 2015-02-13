# -*- coding: utf-8 -*-
import pytest
from .utils import last_activity


@pytest.yield_fixture
def activity_values(session):
    session.execute(
        '''CREATE TEMP TABLE activity_values
        ON COMMIT DELETE ROWS AS
        SELECT * FROM audit.activity WHERE 1 = 2
        '''
    )
    yield
    session.execute('DROP TABLE activity_values')


@pytest.mark.usefixtures('schema', 'table_creator')
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

    def test_update_without_actual_changes_does_not_create_activity(
        self,
        user,
        session
    ):
        user.name = 'John'
        session.flush()
        activity = last_activity(session)
        assert activity['verb'] == 'insert'

    def test_update(self, user, session):
        user.name = 'Luke'
        session.flush()
        activity = last_activity(session)
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] == {'name': 'Luke'}
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John',
            'age': '15'
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'update'

    def test_delete(self, user, session):
        session.delete(user)
        session.flush()
        activity = last_activity(session)
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] is None
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John',
            'age': '15'
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'delete'

    @pytest.mark.parametrize(
        ('field', 'value'),
        (
            ('target_id', '1'),
            ('actor_id', '1')
        )
    )
    def test_custom_fields(self, activity_values, session, user, field, value):
        session.execute(
            '''INSERT INTO activity_values ({0}) VALUES ({1})'''.format(
                field, value
            )
        )
        session.delete(user)
        session.commit()
        activity = last_activity(session)
        assert activity[field] == value


@pytest.mark.usefixtures('schema', 'table_creator')
class TestActivityCreationWithColumnExclusion(object):
    @pytest.fixture
    def audit_trigger_creator(self, session, user_class):
        session.execute(
            '''SELECT audit.audit_table('{0}', '{{"age"}}')'''.format(
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
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] is None
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John'
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'insert'

    def test_update(self, user, session):
        user.name = 'Luke'
        user.age = 18
        session.flush()
        activity = last_activity(session)
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] == {'name': 'Luke'}
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John',
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'update'

    def test_delete(self, user, session):
        session.delete(user)
        session.flush()
        activity = last_activity(session)
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] is None
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John',
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'delete'
