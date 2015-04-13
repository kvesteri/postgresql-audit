import pytest

from postgresql_audit import change_column_name, versioning_manager
from .utils import last_activity


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestChangeColumnName(object):
    def test_only_updates_given_table(
        self,
        session,
        article,
        user,
        connection
    ):
        change_column_name(connection, 'user', 'name', 'some_name')
        activity = session.query(versioning_manager.activity_cls).filter_by(
            table_name='article'
        ).one()
        assert 'name' in activity.changed_data

    def test_updates_changed_data(self, session, user, connection):
        change_column_name(connection, 'user', 'name', 'some_name')
        activity = last_activity(connection)
        assert activity['changed_data'] == {
            'id': user.id,
            'some_name': 'John',
            'age': 15
        }

    def test_updates_old_data(self, session, user, connection):
        user.name = 'Luke'
        session.commit()
        change_column_name(connection, 'user', 'name', 'some_name')
        activity = last_activity(connection)
        assert activity['old_data'] == {
            'id': user.id,
            'some_name': 'John',
            'age': 15
        }
