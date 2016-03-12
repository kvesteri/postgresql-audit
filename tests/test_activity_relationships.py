# -*- coding: utf-8 -*-
import pytest



@pytest.mark.usefixtures('Activity', 'table_creator')
class TestOneToMany(object):
    def test_existing_objects(
        self,
        User,
        Article,
        Activity,
        versioning_manager,
        session
    ):
        user = User(name='Jack')
        session.add_all([
            Article(name='Article 1', author=user),
            Article(name='Article 2', author=user)
        ])
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='user').first()
        )
        article_activities = activity.relationships.articles
        assert article_activities[0].table_name == 'article'
        assert article_activities[0].data['name'] == 'Article 1'
        assert article_activities[1].table_name == 'article'
        assert article_activities[1].data['name'] == 'Article 2'


@pytest.mark.usefixtures('Activity', 'table_creator')
class TestOneToOne(object):
    @pytest.fixture
    def user(self, User, session):
        user = User(name='Jack')
        session.add(user)
        session.commit()
        return user

    @pytest.fixture
    def article(self, user, Article, session):
        article = Article(name='Some article', author=user)
        session.add(article)
        session.commit()
        return article

    def test_existing_object(
        self,
        article,
        Activity,
        versioning_manager,
        session
    ):
        activity = (
            session.query(Activity)
            .filter_by(table_name='article').first()
        )
        user_activity = activity.relationships.author
        assert user_activity.table_name == 'user'

    def test_with_deleted_object(
        self,
        article,
        Activity,
        user,
        versioning_manager,
        session
    ):
        session.delete(user)
        article.name = 'Updated article'
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='article')
            .order_by(Activity.transaction_id.desc())
            .first()
        )
        user_activity = activity.relationships.author
        assert user_activity is None

    def test_adhers_to_relationship_condition(
        self,
        user,
        article,
        User,
        Activity,
        versioning_manager,
        session
    ):
        session.add(User(name='John'))
        article.name = 'Updated article'
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='article')
            .order_by(Activity.transaction_id.desc())
            .first()
        )
        user_activity = activity.relationships.author
        assert user_activity.data['name'] == 'Jack'

    def test_with_updated_object(
        self,
        user,
        article,
        Activity,
        versioning_manager,
        session
    ):
        user.name = 'John'
        article.name = 'Updated article'
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='article')
            .order_by(Activity.transaction_id.desc())
            .first()
        )
        user_activity = activity.relationships.author
        assert user_activity.data['name'] == 'John'
