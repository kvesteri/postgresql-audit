from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import BindParameter


class ExpressionReflector(sa.sql.visitors.ReplacingCloningVisitor):
    def __init__(self, Activity):
        self.Activity = Activity

    def is_replaceable(self, column):
        return (
            isinstance(column, sa.Column) and
            column.table is not self.Activity.__table__
        )

    def replace_binary_expression(self, expr):
        if (
            self.is_replaceable(expr.left) and
            isinstance(expr.right, BindParameter)
        ):
            expr.right.value = str(expr.right.value)
        elif (
            isinstance(expr.left, BindParameter) and
            self.is_replaceable(expr.right)
        ):
            expr.left.value = str(expr.left.value)

    def replace(self, expr):
        if isinstance(expr, sa.sql.elements.BinaryExpression):
            self.replace_binary_expression(expr)
        if (
            not isinstance(expr, sa.Column) or
            expr.table is self.Activity.__table__
        ):
            return
        return self.Activity.data[sa.text("'{0}'".format(expr.name))].astext

    def __call__(self, expr):
        return self.traverse(expr)


@pytest.mark.usefixtures('activity_cls')
class TestExpressionReflector(object):
    @pytest.fixture
    def reflector(self, activity_cls):
        return ExpressionReflector(activity_cls)

    def test_binary_expression_reflection(
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
