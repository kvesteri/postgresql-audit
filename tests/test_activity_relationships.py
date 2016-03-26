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
            .filter_by(table_name='user')
            .order_by(Activity.id.desc()).first()
        )
        article_activities = activity.relationships.articles
        assert len(article_activities) == 2
        assert article_activities[0].table_name == 'article'
        assert article_activities[0].data['name'] == 'Article 1'
        assert article_activities[1].table_name == 'article'
        assert article_activities[1].data['name'] == 'Article 2'

    def test_delete_related_object(
        self,
        User,
        Article,
        Activity,
        versioning_manager,
        session
    ):
        user = User(name='Jack')
        articles = [
            Article(name='Article 1', author=user),
            Article(name='Article 2', author=user)
        ]
        session.add_all(articles)
        session.commit()
        session.delete(articles[0])
        session.commit()
        user.name = 'John'
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='user')
            .order_by(Activity.id.desc()).first()
        )
        article_activities = activity.relationships.articles
        assert len(article_activities) == 1
        assert article_activities[0].table_name == 'article'
        assert article_activities[0].data['name'] == 'Article 2'

    def test_nullify_relationship(
        self,
        User,
        Article,
        Activity,
        versioning_manager,
        session
    ):
        user = User(name='Jack')
        articles = [
            Article(name='Article 1', author=user),
            Article(name='Article 2', author=user)
        ]
        session.add_all(articles)
        session.commit()
        articles[0].author = None
        session.commit()
        user.name = 'John'
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='user')
            .order_by(Activity.id.desc()).first()
        )
        article_activities = activity.relationships.articles
        assert len(article_activities) == 1
        assert article_activities[0].table_name == 'article'
        assert article_activities[0].data['name'] == 'Article 2'


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
            .order_by(Activity.id.desc())
            .first()
        )
        user_activity = activity.relationships.author
        assert user_activity is None

    def test_nullify_relationship(
        self,
        article,
        Activity,
        user,
        versioning_manager,
        session
    ):
        article.author_id = None
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='article')
            .order_by(Activity.id.desc())
            .first()
        )
        user_activity = activity.relationships.author
        assert user_activity is None

    def test_adheres_to_relationship_condition(
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
            .order_by(Activity.id.desc())
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
            .order_by(Activity.id.desc())
            .first()
        )
        user_activity = activity.relationships.author
        assert user_activity.data['name'] == 'John'


@pytest.mark.usefixtures('Activity', 'table_creator')
class TestManyToMany(object):
    @pytest.fixture
    def tags(self, Tag, session):
        tags = [
            Tag(name='Tag 1'),
            Tag(name='Tag 2'),
            Tag(name='Tag 3')
        ]
        return tags

    @pytest.fixture
    def articles(self, Article, tags, session):
        articles = [
            Article(name='Article 1', tags=[tags[0]]),
            Article(name='Article 2', tags=tags[1:]),
            Article(name='Article 3', tags=tags[0:1]),
        ]
        session.add_all(articles)
        session.commit()
        return articles

    @pytest.mark.parametrize(
        ('article_number', 'expected_tag_count'),
        (
            (0, 1),
            (1, 2),
            (2, 1)
        )
    )
    def test_existing_objects(
        self,
        articles,
        Activity,
        versioning_manager,
        session,
        article_number,
        expected_tag_count
    ):
        activity = (
            session.query(Activity)
            .filter_by(table_name='article')
            .filter(
                Activity.data['id'] ==
                str(articles[article_number].id)
            ).first()
        )
        tag_activities = activity.relationships.tags
        assert len(tag_activities) == expected_tag_count
        assert tag_activities[0].table_name == 'tag'

    def test_with_deleted_object(
        self,
        articles,
        tags,
        Activity,
        versioning_manager,
        session
    ):
        session.delete(tags[2])
        articles[1].name = 'Updated article'
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='article')
            .filter(
                Activity.data['id'] ==
                str(articles[1].id)
            ).order_by(Activity.id.desc()).first()
        )
        tag_activities = activity.relationships.tags
        assert len(tag_activities) == 1
        assert tag_activities[0].table_name == 'tag'

    def test_with_deleted_association_row(
        self,
        articles,
        tags,
        Activity,
        versioning_manager,
        session
    ):
        articles[1].tags.remove(tags[2])
        articles[1].name = 'Updated article'
        session.commit()
        activity = (
            session.query(Activity)
            .filter_by(table_name='article')
            .filter(
                Activity.data['id'] ==
                str(articles[1].id)
            ).order_by(Activity.id.desc()).first()
        )
        tag_activities = activity.relationships.tags
        assert len(tag_activities) == 1
        assert tag_activities[0].table_name == 'tag'
