from alembic.autogenerate import renderers
from alembic.operations import MigrateOperation, Operations

from postgresql_audit import add_column, remove_column


@Operations.register_operation('add_column_to_activity')
class AddColumnToActivityOp(MigrateOperation):
    """Initialize Activity Table Triggers"""

    def __init__(
        self, table_name, column_name, default_value=None, schema=None
    ):
        self.schema = schema
        self.table_name = table_name
        self.column_name = column_name
        self.default_value = default_value

    @classmethod
    def add_column_to_activity(
        cls, operations, table_name, column_name, **kwargs
    ):
        op = AddColumnToActivityOp(table_name, column_name, **kwargs)
        return operations.invoke(op)

    def reverse(self):
        # only needed to support autogenerate
        return RemoveColumnFromRemoveActivityOp(
            self.table_name,
            self.column_name,
            default_value=self.default_value,
            schema=self.schema
        )


@Operations.register_operation('remove_column_from_activity')
class RemoveColumnFromRemoveActivityOp(MigrateOperation):
    """Drop Activity Table Triggers"""

    def __init__(
        self, table_name, column_name, default_value=None, schema=None
    ):
        self.schema = schema
        self.table_name = table_name
        self.column_name = column_name
        self.default_value = default_value

    @classmethod
    def remove_column_from_activity(
        cls, operations, table_name, column_name, **kwargs
    ):
        op = RemoveColumnFromRemoveActivityOp(
            table_name, column_name, **kwargs
        )
        return operations.invoke(op)

    def reverse(self):
        # only needed to support autogenerate
        return AddColumnToActivityOp(
            self.table_name,
            self.column_name,
            default_value=self.default_value,
            schema=self.schema
        )


@Operations.implementation_for(AddColumnToActivityOp)
def add_column_to_activity(operations, operation):
    add_column(
        operations,
        operation.table_name,
        operation.column_name,
        default_value=operation.default_value,
        schema=operation.schema
    )


@Operations.implementation_for(RemoveColumnFromRemoveActivityOp)
def remove_column_from_activity(operations, operation):
    conn = operations.connection
    remove_column(
        conn,
        operation.table_name,
        operation.column_name,
        operation.schema
    )


@renderers.dispatch_for(AddColumnToActivityOp)
def render_add_column_to_activity(autogen_context, op):
    return 'op.add_column_to_activity(%r, %r, **%r)' % (
        op.table_name,
        op.column_name,
        {'schema': op.schema, 'default_value': op.default_value}
    )


@renderers.dispatch_for(RemoveColumnFromRemoveActivityOp)
def render_remove_column_from_activitys(autogen_context, op):
    return 'op.remove_column_from_activity(%r, %r, **%r)' % (
        op.table_name,
        op.column_name,
        {'schema': op.schema}
    )
