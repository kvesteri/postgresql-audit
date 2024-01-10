import pytest
from sqlalchemy import Text, cast, select

from flask_audit_logger.migrations import (
    add_column,
    alter_column,
    change_column_name,
    remove_column,
    rename_table,
)
from tests.defaults.flask_app import AuditLogActivity, db


@pytest.mark.usefixtures("test_client")
class TestRenameTable:
    def test_only_updates_given_table(self, article, user):
        rename_table(db.session, "user", "user2")
        activity = db.session.scalar(
            select(AuditLogActivity).where(AuditLogActivity.table_name == "article").limit(1)
        )
        assert activity

    def test_updates_table_name(self, user):
        rename_table(db.session, "user", "user2")
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.table_name == "user2"


@pytest.mark.usefixtures("test_client")
class TestChangeColumnName:
    def test_only_updates_given_table(self, article, user):
        change_column_name(db.session, "user", "name", "some_name")
        activity = db.session.scalar(
            select(AuditLogActivity).where(AuditLogActivity.table_name == "article").limit(1)
        )
        assert "name" in activity.changed_data

    def test_updates_changed_data(self, user):
        change_column_name(db.session, "user", "name", "some_name")
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.changed_data == {
            "id": user.id,
            "some_name": "Jan",
            "age": 15,
        }

    def test_updates_old_data(self, user):
        user.name = "Luke"
        db.session.commit()
        change_column_name(db.session, "user", "name", "some_name")
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.old_data == {"id": user.id, "some_name": "Jan", "age": 15}


@pytest.mark.usefixtures("test_client")
class TestRemoveColumn:
    def test_only_updates_given_table(self, article, user):
        remove_column(db.session, "user", "name")
        activity = db.session.scalar(
            select(AuditLogActivity).where(AuditLogActivity.table_name == "article").limit(1)
        )
        assert "name" in activity.changed_data

    def test_updates_changed_data(self, user):
        remove_column(db.session, "user", "name")
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.old_data == {}
        assert activity.changed_data == {"id": user.id, "age": 15}

    def test_updates_old_data(self, user):
        user.name = "Luke"
        db.session.commit()
        remove_column(db.session, "user", "name")
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.old_data == {"id": user.id, "age": 15}


@pytest.mark.usefixtures("test_client")
class TestAddColumn:
    def test_only_updates_given_table(self, article, user):
        add_column(db.session, "user", "some_column")
        activity = db.session.scalar(
            select(AuditLogActivity).where(AuditLogActivity.table_name == "article").limit(1)
        )
        assert "some_column" not in activity.changed_data

    def test_updates_changed_data(self, user):
        add_column(db.session, "user", "some_column")
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.old_data == {}
        assert activity.changed_data == {
            "id": user.id,
            "age": 15,
            "name": "Jan",
            "some_column": None,
        }

    def test_updates_old_data(self, user):
        user.name = "Luke"
        db.session.commit()
        add_column(db.session, "user", "some_column")
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.old_data == {
            "id": user.id,
            "age": 15,
            "name": "Jan",
            "some_column": None,
        }
        assert activity.changed_data == {"name": "Luke"}


@pytest.mark.usefixtures("test_client")
class TestAlterColumn:
    def test_only_updates_given_table(self, article, user):
        alter_column(db.session, "user", "id", lambda value, activity_table: cast(value, Text))
        activity = db.session.scalar(
            select(AuditLogActivity).where(AuditLogActivity.table_name == "article").limit(1)
        )
        assert isinstance(activity.changed_data["id"], int)

    def test_updates_changed_data(self, user):
        alter_column(db.session, "user", "id", lambda value, activity_table: cast(value, Text))
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.changed_data == {
            "id": str(user.id),
            "age": 15,
            "name": "Jan",
        }

    def test_updates_old_data(self, user):
        user.name = "Luke"
        db.session.commit()
        alter_column(db.session, "user", "id", lambda value, activity_table: cast(value, Text))
        activity = db.session.scalar(
            select(AuditLogActivity).order_by(AuditLogActivity.issued_at.desc()).limit(1)
        )
        assert activity.old_data == {"id": str(user.id), "age": 15, "name": "Jan"}
