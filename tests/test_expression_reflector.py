from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from postgresql_audit.expressions import ExpressionReflector


@pytest.mark.usefixtures('activity_cls')
class TestExpressionReflector(object):
    @pytest.fixture
    def reflector(self, activity_cls):
        return ExpressionReflector(activity_cls)

    def test_binary_expression_reflected_column_and_scalar(
        self,
        reflector,
        user_class,
    ):
        compiled = reflector(user_class.id == 3).compile(
            dialect=postgresql.dialect()
        )
        assert str(compiled) == (
            "jsonb_merge(activity.old_data, activity.changed_data) ->> "
            "'id' = %(id_1)s"
        )
        assert compiled.params == {'id_1': '3'}

    def test_binary_expression_with_two_reflected_columns(
        self,
        reflector,
        user_class,
    ):
        compiled = reflector(user_class.id == user_class.id).compile(
            dialect=postgresql.dialect()
        )
        assert str(compiled) == (
            "jsonb_merge(activity.old_data, activity.changed_data) ->> "
            "'id' = jsonb_merge(activity.old_data, activity.changed_data) ->> "
            "'id'"
        )
        assert compiled.params == {}

    def test_boolean_clause_list(
        self,
        reflector,
        user_class,
        activity_cls
    ):
        compiled = reflector(
            sa.and_(
                user_class.id == 3,
                activity_cls.issued_at > datetime(2011, 1, 1)
            )
        ).compile(
            dialect=postgresql.dialect()
        )
        assert str(compiled) == (
            "jsonb_merge(activity.old_data, activity.changed_data) ->> 'id'"
            " = %(id_1)s AND activity.issued_at > %(issued_at_1)s"
        )
        assert compiled.params == {
            'id_1': '3',
            'issued_at_1': datetime(2011, 1, 1)
        }

    def test_unary_expression_reflection(
        self,
        reflector,
        user_class,
    ):
        compiled = reflector(~ user_class.id).compile(
            dialect=postgresql.dialect()
        )
        assert str(compiled) == (
            "NOT jsonb_merge(activity.old_data, activity.changed_data) ->> "
            "'id'"
        )
        assert compiled.params == {}
