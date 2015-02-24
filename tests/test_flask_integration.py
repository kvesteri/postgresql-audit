# -*- coding: utf-8 -*-
import pytest

from flask import Flask, url_for
from flask.ext.login import LoginManager
from flask.ext.sqlalchemy import SQLAlchemy

from postgresql_audit.flask import activity_values, versioning_manager


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


@pytest.yield_fixture()
def engine(db):
    yield db.session.bind
    db.session.bind.dispose()


@pytest.yield_fixture()
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
    # application.config['SQLALCHEMY_ECHO'] = True
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


@pytest.yield_fixture()
def activity_cls(db):
    versioning_manager.init(db.Model)
    yield versioning_manager.activity_cls
    versioning_manager.remove_listeners()


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
def table_creator(client, db, models, activity_cls):
    db.configure_mappers()
    conn = db.session.connection()
    conn.execute('DROP SCHEMA IF EXISTS audit CASCADE')
    versioning_manager.activity_cls.__table__.create(conn)
    db.Model.metadata.create_all(conn)
    db.session.commit()
    yield
    conn = db.session.connection()
    db.Model.metadata.drop_all(conn)
    db.session.commit()


@pytest.mark.usefixtures('activity_cls', 'table_creator')
class TestFlaskIntegration(object):
    def test_simple_flushing_view(self, app, db, client, user, user_class):
        login(client, user)
        client.get(url_for('.test_simple_flush'))

        activities = (
            db.session.query(versioning_manager.activity_cls)
            .order_by('id DESC').all()
        )
        assert len(activities) == 2
        assert activities[1].actor_id == user.id
        assert activities[1].client_addr is None

    def test_view_with_overriden_activity_values(
        self,
        app,
        db,
        client,
        user,
        user_class,
        article_class
    ):
        @app.route('/activity-values')
        def test_activity_values():
            with activity_values(actor_id=4, target_id='6'):
                article = article_class()
                article.name = u'Some article'
                db.session.add(article)
                db.session.commit()
            return ''

        login(client, user)
        client.get(url_for('.test_activity_values'))

        activities = (
            db.session.query(versioning_manager.activity_cls)
            .order_by('id DESC').all()
        )
        assert len(activities) == 2
        assert activities[1].actor_id == 4
        assert activities[1].target_id == '6'
        assert activities[1].client_addr is None
