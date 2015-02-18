# -*- coding: utf-8 -*-
import pytest
import sqlalchemy as sa
from flexmock import flexmock
from sqlalchemy.ext.declarative import declarative_base

from postgresql_audit import (
    activity_base,
    activity_values,
    assign_actor,
    versioning_manager,
    VersioningManager
)
from .utils import last_activity


@pytest.fixture(scope='module')
def activity_cls(base):
    versioning_manager.init(base)
    return versioning_manager.activity_cls


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
        assert session.query(activity_cls).count() == 0
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

    def test_activity_values_scope(
        self,
        activity_cls,
        user_class,
        session
    ):
        with activity_values(session.connection(), target_id=1):
            user = user_class(name='John')
            session.add(user)
            session.commit()
        with activity_values(session.connection(), actor_id=1):
            user = user_class(name='John')
            session.add(user)
            session.commit()
        activity = last_activity(session)
        assert session.query(activity_cls).count() == 2
        assert activity['actor_id'] == '1'
        assert activity['target_id'] is None

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

    def test_callables_as_manager_defaults(
        self,
        user_class,
        session
    ):
        versioning_manager.values = {'actor_id': lambda: 1}
        user = user_class(name='John')
        session.add(user)
        session.commit()
        activity = last_activity(session)
        assert activity['actor_id'] == '1'

    def test_raw_insert(
        self,
        user_class,
        session
    ):
        versioning_manager.values = {'actor_id': 1}
        session.execute(user_class.__table__.insert().values(name='John'))
        activity = last_activity(session)
        assert activity['actor_id'] == '1'

    def test_keeps_track_of_created_tables(
        self,
        user_class,
        session
    ):
        # The activity_values table should already be created in test setup
        # phase
        (
            flexmock(versioning_manager)
            .should_receive('create_temp_table')
            .never()
        )
        versioning_manager.values = {'actor_id': 1}
        session.execute(user_class.__table__.insert().values(name='John'))
        session.execute(user_class.__table__.insert().values(name='John'))
        activity = last_activity(session)

        assert activity['actor_id'] == '1'

    def test_connection_cleaning(self, user_class, connection):
        assert len(versioning_manager.connections_with_tables) == 1
        assert len(versioning_manager.connections_with_tables_row) == 1

    def test_activity_repr(self, activity_cls):
        assert repr(activity_cls(id=3, table_name='user')) == (
            "<Activity table_name='user' id=3>"
        )

    def test_custom_actor_class(self, user_class):
        manager = VersioningManager(actor_cls=user_class)
        manager.init(declarative_base())
        assert isinstance(
            manager.activity_cls.actor_id.property.columns[0].type,
            sa.Integer
        )
        assert manager.activity_cls.actor

    def test_custom_string_actor_class(self):
        base = declarative_base()

        class User(base):
            __tablename__ = 'user'
            id = sa.Column(sa.Integer, primary_key=True)

        User()
        manager = VersioningManager(actor_cls='User')
        manager.init(base)
        assert isinstance(
            manager.activity_cls.actor_id.property.columns[0].type,
            sa.Integer
        )
        assert manager.activity_cls.actor

    def test_activity_actor_relationship(self, session):
        base = declarative_base()

        class User(base):
            __tablename__ = 'user'
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String)

        class Activity(activity_base(base, actor_cls=User)):
            __tablename__ = 'activity'

        assign_actor(base, Activity, User)

        base.metadata.create_all(session.connection(), checkfirst=True)
        user = User(name='Someone')
        session.add(user)
        session.flush()
        activity = Activity(actor_id=user.id)
        session.add(activity)
        session.commit()
        assert activity.actor is user
