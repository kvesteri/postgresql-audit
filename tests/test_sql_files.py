# -*- coding: utf-8 -*-
import pytest
import sqlalchemy as sa
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


@pytest.mark.usefixtures('schema', 'table_creator')
class TestCompositePrimaryKey(object):
    @pytest.fixture(scope='module')
    def membership_cls(self, base):
        class Membership(base):
            __tablename__ = 'membership'
            user_id = sa.Column(sa.Integer, primary_key=True)
            group_id = sa.Column(sa.Integer, primary_key=True)
        return Membership

    @pytest.fixture(scope='module')
    def models(self, membership_cls):
        return [membership_cls]

    @pytest.fixture
    def membership(self, session, membership_cls):
        member = membership_cls(user_id=15, group_id=15)
        session.add(member)
        session.flush()
        return member

    def test_concatenates_composite_primary_keys_to_object_id(
        self,
        session,
        membership
    ):
        activity = last_activity(session)
        assert activity['object_id'] == '15|15'
