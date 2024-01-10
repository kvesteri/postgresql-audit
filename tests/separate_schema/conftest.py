from datetime import datetime

import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

from tests.separate_schema.flask_app import Article, User, app, db
from tests.utils import REPO_ROOT, run_audit_logger_migrations

ALEMBIC_CONFIG = REPO_ROOT / "tests" / "separate_schema" / "alembic_config"


@pytest.fixture(scope="session")
def test_client():
    test_client = app.test_client()

    with app.app_context():
        with run_audit_logger_migrations(db, ALEMBIC_CONFIG):
            yield test_client


@pytest.fixture(autouse=True)
def enable_transactional_tests(test_client):
    """https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites"""
    connection = db.engine.connect()
    transaction = connection.begin()

    db.session = scoped_session(
        session_factory=sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
    )

    yield

    db.session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def user():
    u = User(id=10, name="Trey", age=100, height=1000)
    db.session.add(u)
    db.session.commit()
    yield u


@pytest.fixture
def article():
    a = Article(id=1, name="Reba sink a boulder in the water", created=datetime.now())
    db.session.add(a)
    db.session.commit()
    yield a
