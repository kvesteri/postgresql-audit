# -*- coding: utf-8 -*-
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

from postgresql_audit import VersioningManager

from .utils import last_activity


@pytest.mark.usefixtures('Activity', 'table_creator')
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
        Activity,
        User,
        session
    ):
        user = User(name='Jack')
        session.add(user)
        session.commit()
        user = User(name='Jack')
        session.add(user)
        session.commit()
        assert session.query(Activity).count() == 2

    def test_operation_after_rollback(
        self,
        Activity,
        User,
        session
    ):
        user = User(name='John')
        session.add(user)
        session.rollback()
        user = User(name='John')
        session.add(user)
        session.commit()
        assert session.query(Activity).count() == 1

    def test_manager_defaults(
        self,
        User,
        session,
        versioning_manager
    ):
        versioning_manager.values = {'actor_id': 1}
        user = User(name='John')
        session.add(user)
        session.commit()
        activity = last_activity(session)
        assert activity['actor_id'] == '1'

    def test_callables_as_manager_defaults(
        self,
        User,
        session,
        versioning_manager
    ):
        versioning_manager.values = {'actor_id': lambda: 1}
        user = User(name='John')
        session.add(user)
        session.commit()
        activity = last_activity(session)
        assert activity['actor_id'] == '1'

    def test_raw_inserts(
        self,
        User,
        session,
        versioning_manager
    ):
        versioning_manager.values = {'actor_id': 1}
        session.execute(User.__table__.insert().values(name='John'))
        session.execute(User.__table__.insert().values(name='John'))
        versioning_manager.set_activity_values(session)
        activity = last_activity(session)

        assert activity['actor_id'] == '1'

    def test_activity_repr(self, Activity):
        assert repr(Activity(id=3, table_name='user')) == (
            "<Activity table_name='user' id=3>"
        )

    def test_custom_actor_class(self, User):
        manager = VersioningManager(actor_cls=User)
        manager.init(declarative_base())
        sa.orm.configure_mappers()
        assert isinstance(
            manager.activity_cls.actor_id.property.columns[0].type,
            sa.Integer
        )
        assert manager.activity_cls.actor
        manager.remove_listeners()

    def test_data_expression_sql(self, Activity):
        assert str(Activity.data) == (
            'jsonb_merge(activity.old_data, activity.changed_data)'
        )

    def test_data_expression(self, user, session, Activity):
        user.name = 'Luke'
        session.commit()
        assert session.query(Activity).filter(
            Activity.table_name == 'user',
            Activity.data['id'].cast(sa.Integer) == user.id
        ).count() == 2

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
        manager.remove_listeners()

    def test_disable_contextmanager(
        self,
        Activity,
        User,
        session,
        versioning_manager
    ):
        with versioning_manager.disable(session):
            user = User(name='Jack')
            session.add(user)
            session.commit()
        assert session.query(Activity).count() == 0

        user = User(name='Jack')
        session.add(user)
        session.commit()
        assert session.query(Activity).count() == 1


@pytest.mark.usefixtures('Activity', 'table_creator')
class TestColumnExclusion(object):
    """
    Test column exclusion with polymorphic inheritance and column aliases to
    cover as many edge cases as possible.
    """
    @pytest.fixture
    def TextItem(self, base):
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
    def Article(self, TextItem):
        class Article(TextItem):
            __tablename__ = 'article'
            __versioned__ = {'exclude': ['_updated_at']}
            id = sa.Column(
                sa.Integer,
                sa.ForeignKey(TextItem.id),
                primary_key=True
            )
            updated_at = sa.Column('_updated_at', sa.DateTime)
            content = sa.Column('_content', sa.String)
            __mapper_args__ = {'polymorphic_identity': 'article'}

        return Article

    @pytest.fixture
    def models(self, Article, TextItem):
        return [Article, TextItem]

    @pytest.fixture
    def article(self, Article, session):
        article = Article(
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
        Activity
    ):
        article.updated_at = datetime(2002, 1, 1)
        session.commit()
        assert session.query(Activity).count() == 2


@pytest.mark.usefixtures('Activity', 'table_creator')
class TestActivityObject(object):
    def test_object_property(self, session, Activity, user):
        activity = session.query(Activity).first()
        assert activity.object.__class__ == user.__class__
        assert activity.object.id == user.id


@pytest.mark.usefixtures('Activity', 'table_creator')
class TestActivityDataProperty(object):
    def test_for_insert_activity(self, session, Activity, user):
        assert session.query(Activity.data).scalar()['name'] == 'John'

    def test_for_update_activity(self, session, Activity, user):
        user.name = 'Jack'
        session.commit()
        assert (
            session.query(Activity.data)
            .order_by(Activity.transaction_id.desc()).limit(1)
            .scalar()['name']
        ) == 'Jack'


    def test_for_delete_activity(self, session, Activity, user):
        session.delete(user)
        session.commit()
        assert (
            session.query(Activity.data)
            .order_by(Activity.transaction_id.desc()).limit(1)
            .scalar()['name']
        ) == 'John'
