import pytest
import sqlalchemy as sa

from postgresql_audit import (
    add_column,
    alter_column,
    change_column_name,
    remove_column,
    rename_table
)

from .utils import last_activity


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestRenameTable(object):
    def test_only_updates_given_table(
        self,
        session,
        article,
        user,
        connection,
        versioning_manager
    ):
        rename_table(connection, 'user', 'user2')
        activity = session.query(versioning_manager.activity_cls).filter_by(
            table_name='article'
        ).one()
        assert activity

    def test_updates_table_name(self, session, user, connection):
        rename_table(connection, 'user', 'user2')
        activity = last_activity(connection)
        assert activity['table_name'] == 'user2'


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestChangeColumnName(object):
    def test_only_updates_given_table(
        self,
        session,
        article,
        user,
        connection,
        versioning_manager
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


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestRemoveColumn(object):
    def test_only_updates_given_table(
        self,
        session,
        article,
        user,
        connection,
        versioning_manager
    ):
        remove_column(connection, 'user', 'name')
        activity = session.query(versioning_manager.activity_cls).filter_by(
            table_name='article'
        ).one()
        assert 'name' in activity.changed_data

    def test_updates_changed_data(self, session, user, connection):
        remove_column(connection, 'user', 'name')
        activity = last_activity(connection)
        assert activity['old_data'] is None
        assert activity['changed_data'] == {
            'id': user.id,
            'age': 15
        }

    def test_updates_old_data(self, session, user, connection):
        user.name = 'Luke'
        session.commit()
        remove_column(connection, 'user', 'name')
        activity = last_activity(connection)
        assert activity['old_data'] == {
            'id': user.id,
            'age': 15
        }


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestAddColumn(object):
    def test_only_updates_given_table(
        self,
        session,
        article,
        user,
        connection,
        versioning_manager
    ):
        add_column(connection, 'user', 'some_column')
        activity = session.query(versioning_manager.activity_cls).filter_by(
            table_name='article'
        ).one()
        assert 'some_column' not in activity.changed_data

    def test_updates_changed_data(self, session, user, connection):
        add_column(connection, 'user', 'some_column')
        activity = last_activity(connection)
        assert activity['old_data'] is None
        assert activity['changed_data'] == {
            'id': user.id,
            'age': 15,
            'name': 'John',
            'some_column': None
        }

    def test_updates_old_data(self, session, user, connection):
        user.name = 'Luke'
        session.commit()
        add_column(connection, 'user', 'some_column')
        activity = last_activity(connection)
        assert activity['old_data'] == {
            'id': user.id,
            'age': 15,
            'name': 'John',
            'some_column': None
        }
        assert activity['changed_data'] == {'name': 'Luke'}


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestAlterColumn(object):
    def test_only_updates_given_table(
        self,
        session,
        article,
        user,
        connection,
        versioning_manager
    ):
        alter_column(
            connection,
            'user',
            'id',
            lambda value, activity_table: sa.cast(value, sa.Text)
        )
        activity = session.query(versioning_manager.activity_cls).filter_by(
            table_name='article'
        ).one()
        assert isinstance(activity.changed_data['id'], int)

    def test_updates_changed_data(self, session, user, connection):
        alter_column(
            connection,
            'user',
            'id',
            lambda value, activity_table: sa.cast(value, sa.Text)
        )
        activity = last_activity(connection)
        assert activity['changed_data'] == {
            'id': str(user.id),
            'age': 15,
            'name': 'John'
        }

    def test_updates_old_data(self, session, user, connection):
        user.name = 'Luke'
        session.commit()
        alter_column(
            connection,
            'user',
            'id',
            lambda value, activity_table: sa.cast(value, sa.Text)
        )
        activity = last_activity(connection)
        assert activity['old_data'] == {
            'id': str(user.id),
            'age': 15,
            'name': 'John'
        }
