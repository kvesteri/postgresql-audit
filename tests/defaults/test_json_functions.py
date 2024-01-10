import pytest
from sqlalchemy import select, text

from flask_audit_logger.expressions import jsonb_change_key_name
from tests.defaults.flask_app import db


@pytest.mark.usefixtures("test_client")
class TestJSONBChangeKeyName:
    @pytest.mark.parametrize(
        ("data", "old_key", "new_key", "expected"),
        (
            ('{"key1": 4, "key2": 3}', "key1", "key3", {"key3": 4, "key2": 3}),
            ('{"key1": 4}', "key2", "key3", {"key1": 4}),
            ('{"key1": 4, "key2": 3}', "key1", "key2", {"key2": 3}),
        ),
    )
    def test_raw_sql(self, data, old_key, new_key, expected):
        result = db.session.scalar(
            text(
                """SELECT jsonb_change_key_name(
                    '{data}'::jsonb,
                    '{old_key}',
                    '{new_key}'
                )""".format(
                    data=data, old_key=old_key, new_key=new_key
                )
            )
        )
        assert result == expected

    @pytest.mark.parametrize(
        ("data", "old_key", "new_key", "expected"),
        (
            ({"key1": 4, "key2": 3}, "key1", "key3", {"key3": 4, "key2": 3}),
            ({"key1": 4}, "key2", "key3", {"key1": 4}),
            ({"key1": 4, "key2": 3}, "key1", "key2", {"key2": 3}),
        ),
    )
    def test_sqlalchemy_function_expr(self, data, old_key, new_key, expected):
        result = db.session.scalar(select(jsonb_change_key_name(data, old_key, new_key)))
        assert result == expected
