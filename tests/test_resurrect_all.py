# -*- coding: utf-8 -*-
import pytest


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestResurrect(object):
    @pytest.fixture
    def user_id(self, User, session):
        user = User(name='Jack')
        session.add(user)
        session.flush()
        user_id = user.id
        session.delete(user)
        session.commit()
        return user_id

    def test_simple_resurrect(
        self,
        activity_cls,
        User,
        versioning_manager,
        session,
        user_id
    ):
        versioning_manager.resurrect_all(
            session,
            User,
            User.id == user_id
        )
        session.commit()
        assert session.query(User).get(user_id)

    def test_returns_resurrected_objects(
        self,
        activity_cls,
        User,
        versioning_manager,
        session,
        user_id
    ):
        users = versioning_manager.resurrect_all(
            session,
            User,
            User.id == user_id
        )
        session.commit()
        assert users[0].id == user_id

    def test_resurrects_always_latest_version(
        self,
        activity_cls,
        User,
        versioning_manager,
        session,
        user_id
    ):
        versioning_manager.resurrect_all(
            session,
            User,
            User.id == user_id
        )
        session.commit()
        user = session.query(User).get(user_id)
        user.name = 'John'
        session.flush()
        session.delete(user)
        session.commit()
        versioning_manager.resurrect_all(
            session,
            User,
            User.id == user_id
        )
        session.commit()
        resurrected_user = session.query(User).get(user_id)
        assert resurrected_user.name == 'John'
