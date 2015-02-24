# -*- coding: utf-8 -*-
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from postgresql_audit import versioning_manager


@pytest.fixture()
def dns():
    return 'postgres://postgres@localhost/postgresql_audit_test'


@pytest.fixture()
def base():
    return declarative_base()


@pytest.yield_fixture()
def engine(dns):
    engine = create_engine(dns)
    # engine.echo = True
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


@pytest.fixture()
def activity_cls(base):
    versioning_manager.init(base)
    return versioning_manager.activity_cls


@pytest.fixture()
def user_class(base):
    class User(base):
        __tablename__ = 'user'
        __versioned__ = {}
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        age = sa.Column(sa.Integer)
    return User


@pytest.fixture()
def article_class(base):
    class Article(base):
        __tablename__ = 'article'
        __versioned__ = {}
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
    return Article


@pytest.fixture()
def models(user_class, article_class):
    return [user_class, article_class]


@pytest.yield_fixture
def table_creator(base, connection, session, models, activity_cls):
    sa.orm.configure_mappers()
    tx = connection.begin()
    connection.execute('DROP SCHEMA IF EXISTS audit CASCADE')
    versioning_manager.activity_cls.__table__.create(connection)
    base.metadata.create_all(connection)
    tx.commit()
    yield
    base.metadata.drop_all(connection)
    session.commit()


@pytest.fixture
def user(session, user_class):
    user = user_class(name='John', age=15)
    session.add(user)
    session.commit()
    return user
