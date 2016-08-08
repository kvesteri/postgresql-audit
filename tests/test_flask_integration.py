# -*- coding: utf-8 -*-
from datetime import datetime

import pytest
from flask import Flask, url_for
from flask.ext.login import LoginManager
from flask.ext.sqlalchemy import SQLAlchemy
import sqlalchemy as sa

from postgresql_audit.flask import activity_values, VersioningManager


def login(client, user):
    with client.session_transaction() as s:
        s['user_id'] = user.id
    return user


def logout(client, user=None):
    with client.session_transaction() as s:
        s['user_id'] = None


@pytest.fixture
def base(db):
    return db.Model


@pytest.fixture
def db():
    return SQLAlchemy()


@pytest.fixture
def login_manager():
    return LoginManager()


@pytest.yield_fixture
def engine(db):
    yield db.session.bind
    db.session.bind.dispose()


@pytest.yield_fixture
def connection(db, engine):
    conn = db.session.connection()
    yield conn
    conn.close()


@pytest.fixture
def app(dns, db, login_manager, user_class, article_class):
    @login_manager.user_loader
    def load_user(id):
        user = db.session.query(user_class).get(id)
        return user

    application = Flask(__name__)
    application.config['SQLALCHEMY_DATABASE_URI'] = dns
    application.secret_key = 'secret'
    application.debug = True
    db.init_app(application)
    login_manager.init_app(application)

    @application.route('/simple-flush')
    def test_simple_flush():
        article = article_class()
        article.name = u'Some article'
        db.session.add(article)
        db.session.commit()
        return ''

    return application


@pytest.yield_fixture
def versioning_manager(db):
    vm = VersioningManager()
    vm.init(db.Model)
    yield vm
    vm.remove_listeners()


@pytest.fixture
def activity_cls(versioning_manager):
    return versioning_manager.activity_cls


@pytest.yield_fixture
def client(app):
    client = app.test_client()
    app_ctx = app.app_context()
    app_ctx.push()
    request_ctx = app.test_request_context()
    request_ctx.push()
    yield client
    request_ctx.pop()
    app_ctx.pop()


@pytest.yield_fixture
def table_creator(client, db, models, activity_cls, versioning_manager):
    db.configure_mappers()
    conn = db.session.connection()
    versioning_manager.transaction_cls.__table__.create(conn)
    versioning_manager.activity_cls.__table__.create(conn)
    db.Model.metadata.create_all(conn)
    db.session.commit()
    yield
    conn = db.session.connection()
    db.Model.metadata.drop_all(conn)
    db.session.commit()


@pytest.fixture
def article_class(base):
    class Article(base):
        __tablename__ = 'article'
        __versioned__ = {'exclude': ['updated_at']}

        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(100))
        updated_at = sa.Column(sa.DateTime)
    return Article


@pytest.mark.usefixtures('versioning_manager', 'table_creator')
class TestFlaskIntegration(object):
    def test_client_addr_with_proxies(
        self,
        client,
        user,
        db,
        activity_cls,
        session
    ):
        login(client, user)
        environ_base = dict(REMOTE_ADDR='')
        proxy_headers = dict(X_FORWARDED_FOR='1.1.1.1,77.77.77.77')
        client.get(
            url_for('.test_simple_flush'),
            environ_base=environ_base,
            headers=proxy_headers
        )
        activities = (
            db.session.query(activity_cls)
            .order_by(activity_cls.id.desc()).all()
        )
        assert len(activities) == 2
        assert activities[0].transaction.actor_id == user.id
        assert activities[0].transaction.client_addr is None

    def test_simple_flushing_view(
        self,
        db,
        client,
        user,
        versioning_manager
    ):
        login(client, user)
        client.get(url_for('.test_simple_flush'))

        activities = (
            db.session.query(versioning_manager.activity_cls)
            .order_by(versioning_manager.activity_cls.id.desc()).all()
        )
        assert len(activities) == 2
        assert activities[0].transaction.actor_id == user.id
        assert activities[0].transaction.client_addr is None

    def test_view_with_overriden_activity_values(
        self,
        db,
        app,
        client,
        user,
        article_class,
        versioning_manager
    ):
        @app.route('/activity-values')
        def test_activity_values():
            args = {
                'actor_id': 4,
                'client_addr': '123.123.123.123'
            }
            with activity_values(**args):
                article = article_class()
                article.name = u'Some article'
                db.session.add(article)
                db.session.commit()
            return ''

        login(client, user)
        client.get(url_for('.test_activity_values'))

        activities = (
            db.session.query(versioning_manager.activity_cls)
            .order_by(versioning_manager.activity_cls.id.desc()).all()
        )
        assert len(activities) == 2
        assert activities[0].transaction.actor_id == 4
        assert activities[0].transaction.client_addr == '123.123.123.123'

    def test_updating_excluded_attr_does_not_create_transaction(
        self,
        app,
        client,
        article_class,
        db,
        transaction_cls,
        user,
        versioning_manager
    ):
        @app.route('/update-excluded-column')
        def test_update_excluded_column():
            article = article_class(name='Some article')
            db.session.add(article)
            db.session.commit()
            article.updated_at = datetime.now()
            db.session.commit()
            return ''

        login(client, user)
        client.get(url_for('.test_update_excluded_column'))
        assert db.session.query(transaction_cls).count() == 1
