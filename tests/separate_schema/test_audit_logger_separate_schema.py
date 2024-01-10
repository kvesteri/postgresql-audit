from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, text

from tests.separate_schema.flask_app import AuditLogActivity, audit_logger, db


@pytest.mark.usefixtures("test_client")
class TestAuditLoggerSeparateSchema:
    def test_multiple_schemas_exist(self):
        schemas = db.session.scalars(
            text("SELECT schema_name FROM information_schema.schemata")
        ).all()
        assert audit_logger.schema not in [None, "", "public"]
        assert audit_logger.schema in schemas

    def test_audit_log_tables_in_new_schema(self):
        tables = db.session.scalars(
            text(
                f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{audit_logger.schema}'"
            )
        ).all()
        assert sorted(tables) == ["activity", "transaction"]

    def test_one_column_excluded(self, article):
        original_data = {"id": article.id, "name": article.name}
        article.name = "Reba tie a cable to a tree"
        db.session.commit()
        article.created = datetime.now() + timedelta(hours=1)
        db.session.commit()
        activities = db.session.scalars(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at)
        ).all()
        assert len(activities) == 2

        a0 = activities[0]
        assert a0.verb == "insert"
        assert a0.changed_data == original_data

        a1 = activities[1]
        assert a1.verb == "update"
        assert a1.changed_data == {"name": article.name}

    def test_two_columns_excluded(self, user):
        original_data = {"id": user.id, "name": user.name}

        user.age = 150
        user.height = 999
        db.session.commit()

        activities = db.session.scalars(select(AuditLogActivity)).all()
        assert len(activities) == 1

        a0 = activities[0]
        assert a0.verb == "insert"
        assert a0.changed_data == original_data
