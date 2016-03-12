import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression
from sqlalchemy.sql.elements import BindParameter
from sqlalchemy.sql.expression import bindparam


class jsonb_merge(expression.FunctionElement):
    """
    Provides jsonb_merge as a SQLAlchemy FunctionElement.

    ::


        import sqlalchemy as sa
        from postgresql_audit import jsonb_merge


        data = {'key1': 1, 'key3': 4}
        merge_data = {'key1': 2, 'key2': 3}
        query = sa.select([jsonb_merge(data, merge_data)])
        session.execute(query).scalar()  # {'key1': 2, 'key2': 3, 'key3': 4}
    """
    type = JSONB()
    name = 'jsonb_merge'


@compiles(jsonb_merge)
def compile_jsonb_merge(element, compiler, **kw):
    arg1, arg2 = list(element.clauses)
    arg1.type = JSONB()
    arg2.type = JSONB()
    return 'jsonb_merge({0}, {1})'.format(
        compiler.process(arg1),
        compiler.process(arg2)
    )


class jsonb_change_key_name(expression.FunctionElement):
    """
    Provides jsonb_change_key_name as a SQLAlchemy FunctionElement.

    ::


        import sqlalchemy as sa
        from postgresql_audit import jsonb_change_key_name


        data = {'key1': 1, 'key3': 4}
        query = sa.select([jsonb_merge(data, 'key1', 'key2')])
        session.execute(query).scalar()  # {'key2': 1, 'key3': 4}
    """
    type = JSONB()
    name = 'jsonb_change_key_name'


@compiles(jsonb_change_key_name)
def compile_jsonb_change_key_name(element, compiler, **kw):
    arg1, arg2, arg3 = list(element.clauses)
    arg1.type = JSONB()
    return 'jsonb_change_key_name({0}, {1}, {2})'.format(
        compiler.process(arg1),
        compiler.process(arg2),
        compiler.process(arg3)
    )


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


class ActivityReflector(sa.sql.visitors.ReplacingCloningVisitor):
    def __init__(self, activity):
        self.activity = activity

    def replace(self, column):
        if not isinstance(column, sa.Column):
            return
        if column.table.name == self.activity.table_name:
            return bindparam(
                column.key,
                self.activity.data[column.key]
            )

    def __call__(self, expr):
        return self.traverse(expr)


class ObjectReflector(sa.sql.visitors.ReplacingCloningVisitor):
    def __init__(self, obj):
        self.obj = obj

    def replace(self, column):
        if not isinstance(column, sa.Column):
            return
        if column.table == self.obj.__class__.__table__:
            return bindparam(
                column.key,
                getattr(self.obj, column.key)
            )

    def __call__(self, expr):
        return self.traverse(expr)
