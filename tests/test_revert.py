# -*- coding: utf-8 -*-
from datetime import datetime

import pytest


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestRevert(object):
    def test_using_transaction_time(
        self,
        activity_cls,
        User,
        versioning_manager,
        session
    ):
        user = User(name='Jack')
        session.add(user)
        session.commit()
        time = datetime.now()
        user.name = 'John'
        session.commit()
        versioning_manager.revert(user, time)
        session.commit()
        assert user.name == 'Jack'

    def test_using_transaction_time_and_multiple_objects(
        self,
        activity_cls,
        User,
        versioning_manager,
        session
    ):
        user = User(name='Jack')
        session.add(user)
        session.commit()
        session.add(User(name='Tim'))
        session.commit()
        time = datetime.now()
        user.name = 'John'
        session.commit()
        versioning_manager.revert(user, time)
        session.commit()
        assert user.name == 'Jack'

    def test_using_activity_id(
        self,
        activity_cls,
        User,
        versioning_manager,
        session
    ):
        user = User(name='Jack')
        session.add(user)
        session.commit()
        activity_id = versioning_manager.get_last_activity_id(user)
        user.name = 'John'
        session.commit()
        versioning_manager.revert(user, activity_id)
        session.commit()
        assert user.name == 'Jack'
