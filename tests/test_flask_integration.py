# -*- coding: utf-8 -*-
from datetime import datetime

import pytest
import sqlalchemy as sa
from flask import Flask
from flask_login import FlaskLoginClient, LoginManager
from flask_sqlalchemy import SQLAlchemy

from postgresql_audit.flask import activity_values, VersioningManager


@pytest.fixture
def base(db):
    return db.Model


@pytest.fixture
def db():
    return SQLAlchemy()


@pytest.fixture
def login_manager():
    return LoginManager()


@pytest.fixture
def app(dns, db, login_manager, user_class, article_class):
    @login_manager.user_loader
    def load_user(id):
        user = db.session.get(user_class, id)
        return user

    application = Flask(__name__)
    application.config['SQLALCHEMY_DATABASE_URI'] = dns
    application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    application.secret_key = 'secret'
    application.debug = True
    application.test_client_class = FlaskLoginClient

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


@pytest.fixture
def versioning_manager(db):
    vm = VersioningManager()
    vm.init(db.Model)
    yield vm
    vm.remove_listeners()


@pytest.fixture
def table_creator(app, db, models, activity_cls, versioning_manager):
    with app.app_context():
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
        app,
        user,
        db,
        activity_cls,
        session
    ):
        environ_base = dict(REMOTE_ADDR='')
        proxy_headers = dict(X_FORWARDED_FOR='1.1.1.1,77.77.77.77')
        with app.test_client(user=user) as client:
            client.get(
                '/simple-flush',
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
        app,
        db,
        user,
        versioning_manager
    ):
        with app.test_client(user=user) as client:
            client.get('/simple-flush')

        activities = (
            db.session.query(versioning_manager.activity_cls)
            .order_by(versioning_manager.activity_cls.id.desc()).all()
        )
        assert len(activities) == 2
        assert activities[0].transaction.actor_id == user.id
        assert activities[0].transaction.client_addr == '127.0.0.1'

    def test_view_with_overriden_activity_values(
        self,
        db,
        app,
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

        with app.test_client(user=user) as client:
            client.get('/activity-values')

        activities = (
            db.session.query(versioning_manager.activity_cls)
            .order_by(versioning_manager.activity_cls.id.desc()).all()
        )
        assert len(activities) == 2
        assert activities[0].transaction.actor_id == 4
        assert activities[0].transaction.client_addr == '123.123.123.123'

    def test_view_with_nested_overriden_activity_values(
        self,
        db,
        app,
        user,
        article_class,
        versioning_manager
    ):
        def create_article():
            article = article_class()
            article.name = u'Some article'
            db.session.add(article)
            db.session.commit()

        @app.route('/activity-values')
        def test_activity_values():
            args1 = {'actor_id': 4}
            args2 = {'client_addr': '123.123.123.123'}
            create_article()
            with activity_values(**args1):
                create_article()
                with activity_values(**args2):
                    create_article()
                create_article()
            create_article()
            return ''

        with app.test_client(user=user) as client:
            client.get('/activity-values')

        activities = (
            db.session.query(versioning_manager.activity_cls)
            .order_by(versioning_manager.activity_cls.id.desc()).all()
        )
        assert len(activities) == 6
        assert activities[0].transaction.actor_id != 4
        assert activities[0].transaction.client_addr != '123.123.123.123'
        assert activities[1].transaction.actor_id == 4
        assert activities[1].transaction.client_addr != '123.123.123.123'
        assert activities[2].transaction.actor_id == 4
        assert activities[2].transaction.client_addr == '123.123.123.123'
        assert activities[3].transaction.actor_id == 4
        assert activities[3].transaction.client_addr != '123.123.123.123'
        assert activities[4].transaction.actor_id != 4
        assert activities[4].transaction.client_addr != '123.123.123.123'

    def test_updating_excluded_attr_does_not_create_transaction(
        self,
        app,
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

        with app.test_client(user=user) as client:
            client.get('/update-excluded-column')
        assert db.session.query(transaction_cls).count() == 1

    def test_overriden_activity_values_without_request_context(
        self,
        db,
        article_class,
        versioning_manager
    ):
        with activity_values(actor_id=4):
            article = article_class()
            article.name = u'Some article'
            db.session.add(article)
            db.session.commit()

        activities = (
            db.session.query(versioning_manager.activity_cls)
            .order_by(versioning_manager.activity_cls.id.desc()).all()
        )
        assert len(activities) == 1
        assert activities[0].transaction.actor_id == 4
        assert activities[0].transaction.client_addr is None
