# -*- coding: utf-8 -*-

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

from postgresql_audit import VersioningManager

from .utils import last_activity


@pytest.fixture
def schema_name():
    return 'audit'


@pytest.yield_fixture
def versioning_manager(base, schema_name):
    vm = VersioningManager(schema_name=schema_name)
    vm.init(base)
    yield vm
    vm.remove_listeners()


@pytest.yield_fixture
def activity_cls(versioning_manager):
    yield versioning_manager.activity_cls


@pytest.yield_fixture()
def table_creator(
    base,
    connection,
    session,
    models,
    versioning_manager,
    schema_name
):
    sa.orm.configure_mappers()
    connection.execute('DROP SCHEMA IF EXISTS {} CASCADE'.format(schema_name))
    tx = connection.begin()
    versioning_manager.transaction_cls.__table__.create(connection)
    versioning_manager.activity_cls.__table__.create(connection)
    base.metadata.create_all(connection)
    tx.commit()
    yield
    session.expunge_all()
    base.metadata.drop_all(connection)
    session.commit()


@pytest.mark.usefixtures('versioning_manager', 'table_creator')
class TestCustomSchemaactivityCreation(object):
    def test_insert(self, user, connection, schema_name):
        activity = last_activity(connection, schema=schema_name)
        assert activity['old_data'] is None
        assert activity['changed_data'] == {
            'id': user.id,
            'name': 'John',
            'age': 15
        }
        assert activity['table_name'] == 'user'
        assert activity['native_transaction_id'] > 0
        assert activity['verb'] == 'insert'

    def test_activity_after_commit(
        self,
        activity_cls,
        user_class,
        session
    ):
        user = user_class(name='Jack')
        session.add(user)
        session.commit()
        user = user_class(name='Jack')
        session.add(user)
        session.commit()
        assert session.query(activity_cls).count() == 2

    def test_activity_after_rollback(
        self,
        activity_cls,
        user_class,
        session
    ):
        user = user_class(name='John')
        session.add(user)
        session.rollback()
        user = user_class(name='John')
        session.add(user)
        session.commit()
        assert session.query(activity_cls).count() == 1

    def test_manager_defaults(
        self,
        user_class,
        session,
        versioning_manager,
        activity_cls
    ):
        versioning_manager.values = {'actor_id': 1}
        user = user_class(name='John')
        session.add(user)
        session.commit()
        activity = session.query(activity_cls).first()
        assert activity.transaction.actor_id == '1'

    def test_callables_as_manager_defaults(
        self,
        user_class,
        session,
        versioning_manager,
        activity_cls
    ):
        versioning_manager.values = {'actor_id': lambda: 1}
        user = user_class(name='John')
        session.add(user)
        session.commit()
        activity = session.query(activity_cls).first()
        assert activity.transaction.actor_id == '1'

    def test_raw_inserts(
        self,
        user_class,
        session,
        versioning_manager,
        activity_cls
    ):
        versioning_manager.values = {'actor_id': 1}
        versioning_manager.set_activity_values(session)
        session.execute(user_class.__table__.insert().values(name='John'))
        session.execute(user_class.__table__.insert().values(name='John'))
        activity = session.query(activity_cls).first()
        assert activity.transaction.actor_id == '1'

    def test_activity_repr(self, activity_cls):
        assert repr(activity_cls(id=3, table_name='user')) == (
            "<Activity table_name='user' id=3>"
        )

    def test_custom_actor_class(self, user_class, schema_name):
        manager = VersioningManager(
            actor_cls=user_class,
            schema_name=schema_name
        )
        manager.init(declarative_base())
        sa.orm.configure_mappers()
        assert isinstance(
            manager.transaction_cls.actor_id.property.columns[0].type,
            sa.Integer
        )
        assert manager.transaction_cls.actor
        manager.remove_listeners()

    def test_data_expression_sql(self, activity_cls):
        assert str(activity_cls.data) == (
            'jsonb_merge(audit.activity.old_data, '
            'audit.activity.changed_data)'
        )

    def test_data_expression(self, user, session, activity_cls):
        user.name = 'Luke'
        session.commit()
        assert session.query(activity_cls).filter(
            activity_cls.table_name == 'user',
            activity_cls.data['id'].cast(sa.Integer) == user.id
        ).count() == 2

    def test_custom_string_actor_class(self, schema_name):
        base = declarative_base()

        class User(base):
            __tablename__ = 'user'
            id = sa.Column(sa.Integer, primary_key=True)

        User()
        manager = VersioningManager(
            actor_cls='User',
            schema_name=schema_name
        )
        manager.init(base)
        sa.orm.configure_mappers()
        assert isinstance(
            manager.transaction_cls.actor_id.property.columns[0].type,
            sa.Integer
        )
        assert manager.transaction_cls.actor
        manager.remove_listeners()
