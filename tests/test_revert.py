# -*- coding: utf-8 -*-
from datetime import datetime

import pytest


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestRevert(object):
    def test_operation_after_commit(
        self,
        activity_cls,
        user_class,
        versioning_manager,
        session
    ):
        user = user_class(name='Jack')
        session.add(user)
        session.commit()
        time = datetime.now()
        user.name = 'John'
        session.commit()
        versioning_manager.revert(user, time)
        session.commit()
        assert user.name == 'Jack'
