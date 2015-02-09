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


@pytest.yield_fixture(scope='module')
def engine(dns):
    engine = create_engine(dns)
    yield engine
    engine.dispose()


@pytest.yield_fixture(scope='module')
def connection(engine):
    conn = engine.connect()
    conn.execute('CREATE EXTENSION IF NOT EXISTS hstore')
    yield conn
    conn.close()


@pytest.yield_fixture(scope='module')
def session(connection):
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close_all()


@pytest.fixture(scope='module')
def schema(session):
    with open('schema.sql') as f:
        sql = f.read()
    session.execute(sql.decode('utf8'))


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
def table_creator(base, connection, models):
    sa.orm.configure_mappers()
    base.metadata.create_all(connection)
    for model in models:
        connection.execute(
            "SELECT audit.audit_table('{0}')".format(model.__tablename__)
        )
    yield
    base.metadata.drop_all(connection)


@pytest.fixture
def user(session, user_class):
    user = user_class(name='John', age=15)
    session.add(user)
    session.flush()
    return user


def last_activity(connection):
    return dict(
        connection.execute(
            'SELECT * FROM audit.activity ORDER BY issued_at DESC LIMIT 1'
        ).fetchone()
    )


@pytest.mark.usefixtures('schema', 'table_creator')
class TestActivityCreation(object):
    def test_insert(self, user, connection):
        activity = last_activity(connection)
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] is None
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John',
            'age': '15'
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'insert'

    def test_update(self, user, session):
        user.name = 'Luke'
        session.flush()
        activity = last_activity(session)
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] == {'name': 'Luke'}
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John',
            'age': '15'
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'update'

    def test_delete(self, user, session):
        session.delete(user)
        session.flush()
        activity = last_activity(session)
        assert activity['object_id'] == str(user.id)
        assert activity['changed_fields'] is None
        assert activity['row_data'] == {
            'id': str(user.id),
            'name': 'John',
            'age': '15'
        }
        assert activity['table_name'] == 'user'
        assert activity['transaction_id'] > 0
        assert activity['verb'] == 'delete'
