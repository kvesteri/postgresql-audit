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


@pytest.yield_fixture
def engine(dns):
    engine = create_engine(dns)
    engine.echo = bool(os.environ.get('POSTGRESQL_AUDIT_TEST_ECHO'))
    yield engine
    engine.dispose()


@pytest.yield_fixture
def connection(engine):
    conn = engine.connect()
    yield conn
    conn.close()


@pytest.yield_fixture
def session(connection):
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.expunge_all()
    session.close_all()


@pytest.yield_fixture
def versioning_manager(base):
    vm = VersioningManager()
    vm.init(base)
    yield vm
    vm.remove_listeners()


@pytest.fixture
def activity_cls(versioning_manager):
    return versioning_manager.activity_cls


@pytest.fixture
def transaction_cls(versioning_manager):
    return versioning_manager.transaction_cls


@pytest.fixture
def user_class(base):
    class User(base):
        __tablename__ = 'user'
        __versioned__ = {}
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        age = sa.Column(sa.Integer)
    return User


@pytest.fixture
def article_class(base):
    class Article(base):
        __tablename__ = 'article'
        __versioned__ = {}
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
    return Article


@pytest.fixture
def models(user_class, article_class):
    return [user_class, article_class]


@pytest.yield_fixture
def table_creator(
    base,
    versioning_manager,
    connection,
    session,
    models
):
    sa.orm.configure_mappers()
    tx = connection.begin()
    versioning_manager.transaction_cls.__table__.create(connection)
    versioning_manager.activity_cls.__table__.create(connection)
    base.metadata.create_all(connection)
    tx.commit()
    session.commit()
    yield
    session.expunge_all()
    base.metadata.drop_all(connection)
    session.commit()


@pytest.fixture
def article(session, article_class):
    article = article_class(name='Some article')
    session.add(article)
    session.commit()
    return article


@pytest.fixture
def user(session, user_class):
    user = user_class(name='John', age=15)
    session.add(user)
    session.commit()
    return user
