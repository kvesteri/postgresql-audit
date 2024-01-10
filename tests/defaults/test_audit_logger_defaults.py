import pytest
from sqlalchemy import func, insert, select

from tests.defaults.flask_app import AuditLogActivity, User, db


@pytest.mark.usefixtures("test_client")
class TestAuditLoggerDefaults:
    def test_insert(self, user):
        activity = db.session.scalar(select(AuditLogActivity).limit(1))
        assert activity.old_data == {}
        assert activity.changed_data == {"id": user.id, "name": "Jan", "age": 15}
        assert activity.table_name == "user"
        assert activity.native_transaction_id > 0
        assert activity.verb == "insert"

    def test_activity_after_commit(self):
        user = User(id=1, name="Jack")
        db.session.add(user)
        db.session.commit()
        user = User(id=2, name="Jill")
        db.session.add(user)
        db.session.commit()
        assert db.session.scalar(select(func.count()).select_from(AuditLogActivity)) == 2

    def test_activity_after_rollback(self):
        user = User(id=1, name="Jack")
        db.session.add(user)
        db.session.rollback()
        user = User(id=2, name="Jill")
        db.session.add(user)
        db.session.commit()
        assert db.session.scalar(select(func.count()).select_from(AuditLogActivity)) == 1

    def test_audit_logger_no_actor(self):
        user = User(id=1, name="Jack")
        db.session.add(user)
        db.session.commit()
        activity = db.session.scalar(select(AuditLogActivity).limit(1))
        assert activity.transaction.actor_id is None

    def test_audit_logger_with_actor(self, test_client, logged_in_user):
        resp = test_client.post("/article")
        assert resp.status_code == 200
        activity = db.session.scalar(
            select(AuditLogActivity).where(AuditLogActivity.table_name == "article").limit(1)
        )
        assert activity.transaction.actor_id == logged_in_user.id

    def test_raw_inserts(self):
        db.session.execute(insert(User).values(name="John"))
        db.session.execute(insert(User).values(name="John"))
        activities = db.session.scalars(select(AuditLogActivity)).all()
        assert len(activities) == 2

    def test_activity_repr(self):
        activity = AuditLogActivity()
        activity.id = 3
        activity.table_name = "user"
        assert repr(activity) == "<AuditLogActivity table_name='user' id=3>"

    def test_data_expression_sql(self):
        assert str(AuditLogActivity.data.expression) == (
            "activity.old_data || activity.changed_data"
        )

    def test_data_expression(self, user):
        user.name = "Luke"
        db.session.commit()
        activities = db.session.scalars(
            select(AuditLogActivity).where(
                AuditLogActivity.table_name == "user",
                AuditLogActivity.data["id"].astext == str(user.id),
            )
        ).all()
        assert len(activities) == 2
