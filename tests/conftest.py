# -*- coding: utf-8 -*-
import os

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import close_all_sessions, declarative_base, sessionmaker

from flask_audit_logger import AuditLogger


@pytest.fixture
def db_user():
    return os.environ.get('FLASK_AUDIT_LOGGER_TEST_USER', 'postgres')


@pytest.fixture
def db_password():
    return os.environ.get('FLASK_AUDIT_LOGGER_TEST_PASSWORD', '')


@pytest.fixture
def db_name():
    return os.environ.get('FLASK_AUDIT_LOGGER_TEST_DB', 'flask_audit_logger_test')


@pytest.fixture
def dns(db_user, db_password, db_name):
    return f'postgresql://{db_user}:{db_password}@localhost/{db_name}'


@pytest.fixture
def base():
    return declarative_base()


@pytest.fixture
def engine(dns):
    engine = create_engine(dns, future=True)
    engine.echo = bool(os.environ.get('FLASK_AUDIT_LOGGER_TEST_ECHO'))

    with engine.begin() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS btree_gist'))

    yield engine

    engine.dispose()


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine, future=True)
    session = Session(future=True)
    yield session
    session.expunge_all()
    close_all_sessions()


@pytest.fixture
def schema():
    return None


@pytest.fixture
def audit_logger(base, schema):
    al = AuditLogger(schema=schema)
    al.init(base)
    yield al
    al.remove_listeners()


@pytest.fixture
def activity_cls(audit_logger):
    return audit_logger.activity_cls


@pytest.fixture
def transaction_cls(audit_logger):
    return audit_logger.transaction_cls


@pytest.fixture
def user_class(base):
    class User(base):
        __tablename__ = 'user'
        __versioned__ = {}
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        age = sa.Column(sa.Integer)

        def get_id(self):
            return str(self.id)

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


@pytest.fixture
def table_creator(
    base,
    audit_logger,
    engine,
    models
):
    sa.orm.configure_mappers()

    with engine.begin() as connection:
        audit_logger.transaction_cls.__table__.create(connection)
        audit_logger.activity_cls.__table__.create(connection)
        base.metadata.create_all(connection)

    yield

    with engine.begin() as connection:
        base.metadata.drop_all(connection)


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
