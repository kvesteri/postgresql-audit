# -*- coding: utf-8 -*-
import os

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from postgresql_audit import VersioningManager


@pytest.fixture
def db_user():
    return os.environ.get('POSTGRESQL_AUDIT_TEST_USER', 'postgres')


@pytest.fixture
def db_name():
    return os.environ.get('POSTGRESQL_AUDIT_TEST_DB', 'postgresql_audit_test')


@pytest.fixture
def dns(db_user, db_name):
    return 'postgres://{}@localhost/{}'.format(db_user, db_name)


@pytest.fixture
def base():
    return declarative_base()


@pytest.yield_fixture()
def engine(dns):
    engine = create_engine(dns)
    engine.echo = bool(os.environ.get('POSTGRESQL_AUDIT_TEST_ECHO'))
    yield engine
    engine.dispose()


@pytest.yield_fixture()
def connection(engine):
    conn = engine.connect()
    yield conn
    conn.close()


@pytest.yield_fixture()
def session(connection):
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.expunge_all()
    session.close_all()


@pytest.yield_fixture()
def versioning_manager(base):
    vm = VersioningManager()
    vm.init(base)
    yield vm
    vm.remove_listeners()


@pytest.fixture
def Activity(versioning_manager):
    return versioning_manager.activity_cls


@pytest.fixture
def User(base):
    class User(base):
        __tablename__ = 'user'
        __versioned__ = {}
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        age = sa.Column(sa.Integer)
    return User


@pytest.fixture
def Article(base, User):
    class Article(base):
        __tablename__ = 'article'
        __versioned__ = {}
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        author_id = sa.Column(
            sa.Integer, sa.ForeignKey(User.id, ondelete='SET NULL')
        )
        author = sa.orm.relationship(User, backref='articles')
    return Article


@pytest.fixture
def article_tag(base, versioning_manager):
    table = sa.Table(
        'article_tag',
        base.metadata,
        sa.Column('article_id', sa.ForeignKey('article.id'), primary_key=True),
        sa.Column('tag_id', sa.ForeignKey('tag.id'), primary_key=True)
    )
    versioning_manager.audit_table(table)
    return table


@pytest.fixture
def Tag(base, Article, article_tag):
    class Tag(base):
        __tablename__ = 'tag'
        __versioned__ = {}
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        articles = sa.orm.relationship(
            Article,
            secondary=article_tag,
            backref='tags'
        )
    return Tag


@pytest.fixture
def models(User, Article, Tag):
    return [User, Article, Tag]


@pytest.yield_fixture
def table_creator(
    base,
    versioning_manager,
    connection,
    session,
    models,
    Activity
):
    sa.orm.configure_mappers()
    tx = connection.begin()
    versioning_manager.activity_cls.__table__.create(connection)
    base.metadata.create_all(connection)
    tx.commit()
    yield
    base.metadata.drop_all(connection)
    session.commit()


@pytest.fixture
def article(session, Article):
    article = Article(name='Some article')
    session.add(article)
    session.commit()
    return article


@pytest.fixture
def user(session, User):
    user = User(name='John', age=15)
    session.add(user)
    session.commit()
    return user
