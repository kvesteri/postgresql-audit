import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

from tests.custom_actor.flask_app import SuperUser, app, audit_logger, db
from tests.utils import REPO_ROOT, run_audit_logger_migrations

ALEMBIC_CONFIG = REPO_ROOT / "tests" / "custom_actor" / "alembic_config"


# @pytest.fixture
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
def superuser(test_client):
    su = SuperUser(id=123)
    db.session.add(su)
    with audit_logger.disable(db.session):
        db.session.commit()

    with test_client.application.test_request_context():
        yield su


# @pytest.fixture
# def user():
#     user = User(id=1, name="Jan", age=15)
#     db.session.add(user)
#     db.session.commit()
#     yield user
#
#
#
# @pytest.fixture
# def logged_in_user(test_client):
#     user = User(id=100, name="George")
#     db.session.add(user)
#     with audit_logger.disable(db.session):
#         db.session.commit()
#
#     with test_client.application.test_request_context():
#         login_user(user)
#         yield user
