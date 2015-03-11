# -*- coding: utf-8 -*-
import pytest
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

from postgresql_audit import versioning_manager, VersioningManager
from .utils import last_activity


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestActivityCreation(object):
    def test_insert(self, user, connection):
        activity = last_activity(connection)
        assert activity['old_data'] is None
        assert activity['changed_data'] == {
            'id': user.id,
            'name': 'John',
            'age': 15
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'insert'

    def test_operation_after_commit(
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

    def test_operation_after_rollback(
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

    def test_raw_inserts(
        self,
        user_class,
        session
    ):
        versioning_manager.values = {'actor_id': 1}
        session.execute(user_class.__table__.insert().values(name='John'))
        session.execute(user_class.__table__.insert().values(name='John'))
        versioning_manager.set_activity_values(session)
        activity = last_activity(session)

        assert activity['actor_id'] == '1'

    def test_activity_repr(self, activity_cls):
        assert repr(activity_cls(id=3, table_name='user')) == (
            "<Activity table_name='user' id=3>"
        )

    def test_custom_actor_class(self, user_class):
        manager = VersioningManager(actor_cls=user_class)
        manager.init(declarative_base())
        sa.orm.configure_mappers()
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
        sa.orm.configure_mappers()
        assert isinstance(
            manager.activity_cls.actor_id.property.columns[0].type,
            sa.Integer
        )
        assert manager.activity_cls.actor


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestColumnExclusion(object):
    """
    Test column exclusion with olymorphic inheritance and column aliases to
    cover as many edge cases as possible.
    """
    @pytest.fixture
    def textitem_cls(self, base):
        class TextItem(base):
            __tablename__ = 'textitem'
            __versioned__ = {'exclude': ['_created_at']}
            id = sa.Column(sa.Integer, primary_key=True)
            title = sa.Column(sa.String)
            created_at = sa.Column('_created_at', sa.DateTime)
            type = sa.Column(sa.String)
            __mapper_args__ = {'polymorphic_on': type}

        return TextItem

    @pytest.fixture
    def article_cls(self, textitem_cls):
        class Article(textitem_cls):
            __tablename__ = 'article'
            __versioned__ = {'exclude': ['_updated_at']}
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey(textitem_cls.id),
                primary_key=True
            )
            updated_at = sa.Column('_updated_at', sa.DateTime)
            content = sa.Column('_content', sa.String)
            __mapper_args__ = {'polymorphic_identity': 'article'}

        return Article

    @pytest.fixture
    def models(self, article_cls, textitem_cls):
        return [article_cls, textitem_cls]

    @pytest.fixture
    def article(self, article_cls, session):
        article = article_cls(
            updated_at=datetime(2001, 1, 1),
            created_at=datetime(2000, 1, 1),
            title='Some title',
            content='Some content'
        )
        session.add(article)
        session.commit()
        return article

    def test_updating_excluded_child_attr_does_not_add_activity(
        self,
        table_creator,
        article,
        session,
        activity_cls
    ):
        article.updated_at = datetime(2002, 1, 1)
        session.commit()
        assert session.query(activity_cls).count() == 2


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestActivityObject(object):
    def test_activity_object(self, session, activity_cls, user_class):
        user = user_class(name='John')
        session.add(user)
        session.commit()
        activity = session.query(activity_cls).first()
        assert activity.object.__class__ == user.__class__
        assert activity.object.id == user.id
