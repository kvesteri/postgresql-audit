# -*- coding: utf-8 -*-
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope='module')
def dns():
    return 'postgres://postgres@localhost/postgresql_audit_test'


@pytest.fixture(scope='module')
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
    conn.execute('DROP SCHEMA IF EXISTS audit CASCADE')
    conn.execute('CREATE EXTENSION IF NOT EXISTS hstore')
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
def schema(session):
    files = [
        'schema.sql',
        'activity.sql',
        'create_activity.sql',
        'audit_table.sql'
    ]
    for file_ in files:
        with open(file_) as f:
            sql = f.read()
        session.execute(sql)
    session.commit()
    yield
    session.execute('DROP SCHEMA audit CASCADE')
    session.commit()


@pytest.fixture(scope='module')
def user_class(base):
    class User(base):
        __tablename__ = 'user'
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        age = sa.Column(sa.Integer)
    return User


@pytest.fixture(scope='module')
def article_class(base):
    class Article(base):
        __tablename__ = 'article'
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
    return Article


@pytest.fixture(scope='module')
def models(user_class, article_class):
    return [user_class, article_class]


@pytest.yield_fixture
def table_creator(base, connection, session, models):
    sa.orm.configure_mappers()
    base.metadata.create_all(connection, checkfirst=True)
    tx = connection.begin()
    for model in models:
        connection.execute(
            "SELECT audit.audit_table('{0}')".format(model.__tablename__)
        )
    tx.commit()
    yield
    base.metadata.drop_all(connection)


@pytest.fixture
def user(session, user_class):
    user = user_class(name='John', age=15)
    session.add(user)
    session.flush()
    return user
