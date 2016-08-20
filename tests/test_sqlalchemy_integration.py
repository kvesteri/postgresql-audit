# -*- coding: utf-8 -*-
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base, synonym_for

from postgresql_audit import VersioningManager

from .utils import last_activity


@pytest.mark.usefixtures('versioning_manager', 'table_creator')
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
        assert activity['native_transaction_id'] > 0
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
        session,
        versioning_manager
    ):
        versioning_manager.values = {'actor_id': 1}
        user = user_class(name='John')
        session.add(user)
        session.commit()
        activity = session.query(versioning_manager.activity_cls).first()
        assert activity.transaction.actor_id == '1'

    def test_callables_as_manager_defaults(
        self,
        user_class,
        session,
        versioning_manager
    ):
        versioning_manager.values = {'actor_id': lambda: 1}
        user = user_class(name='John')
        session.add(user)
        session.commit()
        activity = session.query(versioning_manager.activity_cls).first()
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

        activity = session.query(activity_cls).order_by(
            activity_cls.issued_at
        ).first()

        assert activity.transaction.actor_id == '1'

    def test_activity_repr(self, activity_cls):
        assert repr(activity_cls(id=3, table_name='user')) == (
            "<Activity table_name='user' id=3>"
        )

    def test_custom_actor_class(self, user_class):
        manager = VersioningManager(actor_cls=user_class)
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
            'jsonb_merge(activity.old_data, activity.changed_data)'
        )

    def test_data_expression(self, user, session, activity_cls):
        user.name = 'Luke'
        session.commit()
        assert session.query(activity_cls).filter(
            activity_cls.table_name == 'user',
            activity_cls.data['id'].cast(sa.Integer) == user.id
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
            manager.transaction_cls.actor_id.property.columns[0].type,
            sa.Integer
        )
        assert manager.transaction_cls.actor
        manager.remove_listeners()

    def test_disable_contextmanager(
        self,
        activity_cls,
        user_class,
        session,
        versioning_manager
    ):
        with versioning_manager.disable(session):
            user = user_class(name='Jack')
            session.add(user)
            session.commit()
        assert session.query(activity_cls).count() == 0

        user = user_class(name='Jack')
        session.add(user)
        session.commit()
        assert session.query(activity_cls).count() == 1


@pytest.mark.usefixtures('versioning_manager', 'table_creator')
class TestColumnExclusion(object):
    """
    Test column exclusion with polymorphic inheritance and column aliases to
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
        article,
        session,
        activity_cls
    ):
        article.updated_at = datetime(2002, 1, 1)
        session.commit()
        assert session.query(activity_cls).count() == 2


@pytest.mark.usefixtures('versioning_manager', 'table_creator')
class TestIsModified(object):
    @pytest.fixture
    def article_class(self, base, user_class):
        class Article(base):
            __tablename__ = 'article'
            __versioned__ = {'exclude': ['_updated_at', '_creator_id']}
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String)
            _created_at = sa.Column(sa.DateTime)
            updated_at = sa.Column('_updated_at', sa.DateTime)
            author_id = sa.Column(sa.Integer, sa.ForeignKey(user_class.id))
            author = sa.orm.relationship(
                user_class,
                primaryjoin=author_id == user_class.id
            )
            creator_id = sa.Column(
                '_creator_id',
                sa.Integer,
                sa.ForeignKey(user_class.id)
            )
            creator = sa.orm.relationship(
                user_class,
                primaryjoin=creator_id == user_class.id
            )

            @synonym_for('_created_at')
            @property
            def created_at(self):
                return self._created_at

        return Article

    @pytest.fixture
    def user_class(self, base):
        class User(base):
            __tablename__ = 'user'
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String)

        return User

    def test_class_with_synonyms(
        self,
        article_class,
        versioning_manager,
        session
    ):
        article = article_class(name='Someone', _created_at=datetime.now())
        session.add(article)
        assert versioning_manager.is_modified(article)

    def test_modified_transient_object(
        self,
        versioning_manager,
        article_class,
        session
    ):
        article = article_class(name='Article 1')
        session.add(article)
        assert versioning_manager.is_modified(article)
        assert versioning_manager.is_modified(session)

    def test_modified_excluded_column_with_persistent_object(
        self,
        versioning_manager,
        article,
        session
    ):
        article.updated_at = datetime.now()
        assert not versioning_manager.is_modified(article)
        assert not versioning_manager.is_modified(session)

    def test_modified_persistent_object(
        self,
        versioning_manager,
        article,
        session
    ):
        article.name = 'Article updated'
        assert versioning_manager.is_modified(article)
        assert versioning_manager.is_modified(session)

    def test_modified_excluded_relationship_column(
        self,
        versioning_manager,
        user_class,
        article,
        session
    ):
        article.creator = user_class(name='Someone')
        assert not versioning_manager.is_modified(article)
        assert not versioning_manager.is_modified(session)

    def test_modified_relationship(
        self,
        versioning_manager,
        user_class,
        article,
        session
    ):
        article.author = user_class(name='Someone')
        assert versioning_manager.is_modified(article)
        assert versioning_manager.is_modified(session)

    def test_deleted_object(
        self,
        versioning_manager,
        user_class,
        article,
        session
    ):
        session.delete(article)
        assert versioning_manager.is_modified(session)


@pytest.mark.usefixtures('versioning_manager', 'table_creator')
class TestActivityObject(object):
    def test_activity_object(self, session, activity_cls, user_class):
        user = user_class(name='John')
        session.add(user)
        session.commit()
        activity = session.query(activity_cls).first()
        assert activity.object.__class__ == user.__class__
        assert activity.object.id == user.id
