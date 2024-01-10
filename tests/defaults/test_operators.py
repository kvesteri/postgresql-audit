import json

import pytest
from sqlalchemy import text

from tests.defaults.flask_app import db


@pytest.mark.parametrize(
    ("old", "new", "result"),
    (
        ({}, {}, {}),
        ({"age": 13}, {"age": 14}, {"age": 14}),
        ({"name": "Someone"}, {"name": "Someone"}, {}),
        ({"name": "Someone"}, {"name": "Else"}, {"name": "Else"}),
        ({"ids": [1, 2, 3]}, {"ids": [1, 2]}, {"ids": [1, 2]}),
        ({"ids": [1, 2]}, {"ids": []}, {"ids": []}),
        ({"ids": [1, 2]}, {"ids": [1, 2, 3]}, {"ids": [1, 2, 3]}),
        ({"ids": {}}, {"ids": None}, {"ids": None}),
        ({"ids": None}, {"ids": {}}, {"ids": {}}),
        ({"name": "Someone", "age": 15}, {"name": "Else", "age": 15}, {"name": "Else"}),
    ),
)
def test_jsonb_subtract(test_client, old, new, result):
    assert (
        db.session.scalar(
            text("SELECT jsonb_subtract((:new)::jsonb, (:old)::jsonb)"),
            dict(old=json.dumps(old), new=json.dumps(new)),
        )
        == result
    )
