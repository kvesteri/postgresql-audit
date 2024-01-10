import pytest
from sqlalchemy import select

from tests.custom_actor.flask_app import AuditLogActivity, db


@pytest.mark.usefixtures("test_client")
class TestAuditLoggerCustomActor:
    def test_custom_actor_class(self, superuser, test_client):
        resp = test_client.post("/article")

        activities = db.session.scalars(select(AuditLogActivity)).all()
        activity = activities[0]

        assert resp.status_code == 200
        assert len(activities) == 1
        assert activity.table_name == "article"
        assert activity.verb == "insert"
        assert activity.old_data == {}
        assert activity.data == activity.changed_data == resp.json
        assert activity.transaction.actor_id == superuser.id
        assert activity.transaction.actor == superuser
