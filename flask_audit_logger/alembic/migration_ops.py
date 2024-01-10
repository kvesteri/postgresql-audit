from alembic.autogenerate import renderers, rewriter
from alembic.operations import MigrateOperation, Operations, ops

from flask_audit_logger.migrations import add_column, remove_column


def init_migration_ops(schema: str):
    @Operations.register_operation("add_column_to_activity")
    class AddColumnToActivityOp(MigrateOperation):
        """Initialize Activity Table Triggers"""

        def __init__(self, table_name, column_name, default_value=None):
            self.table_name = table_name
            self.column_name = column_name
            self.default_value = default_value

        @classmethod
        def add_column_to_activity(cls, operations, table_name, column_name, **kwargs):
            op = AddColumnToActivityOp(table_name, column_name, **kwargs)
            return operations.invoke(op)

        def reverse(self):
            # only needed to support autogenerate
            return RemoveColumnFromRemoveActivityOp(
                self.table_name,
                self.column_name,
                default_value=self.default_value,
            )

    @Operations.register_operation("remove_column_from_activity")
    class RemoveColumnFromRemoveActivityOp(MigrateOperation):
        """Drop Activity Table Triggers"""

        def __init__(self, table_name, column_name, default_value=None):
            self.table_name = table_name
            self.column_name = column_name
            self.default_value = default_value

        @classmethod
        def remove_column_from_activity(cls, operations, table_name, column_name, **kwargs):
            op = RemoveColumnFromRemoveActivityOp(table_name, column_name, **kwargs)
            return operations.invoke(op)

        def reverse(self):
            # only needed to support autogenerate
            return AddColumnToActivityOp(
                self.table_name,
                self.column_name,
                default_value=self.default_value,
            )

    @Operations.implementation_for(AddColumnToActivityOp)
    def add_column_to_activity(operations, operation):
        add_column(
            operations,
            operation.table_name,
            operation.column_name,
            default_value=operation.default_value,
            schema=schema,
        )

    @Operations.implementation_for(RemoveColumnFromRemoveActivityOp)
    def remove_column_from_activity(operations, operation):
        conn = operations.connection
        remove_column(conn, operation.table_name, operation.column_name, schema)

    @renderers.dispatch_for(AddColumnToActivityOp)
    def render_add_column_to_activity(autogen_context, op):
        return "op.add_column_to_activity(%r, %r, default_value=%r)" % (
            op.table_name,
            op.column_name,
            op.default_value,
        )

    @renderers.dispatch_for(RemoveColumnFromRemoveActivityOp)
    def render_remove_column_from_activity(autogen_context, op):
        return "op.remove_column_from_activity(%r, %r)" % (
            op.table_name,
            op.column_name,
        )

    writer = rewriter.Rewriter()

    @writer.rewrites(ops.AddColumnOp)
    def add_column_rewrite(context, revision, op):
        table_info = op.column.table.info or {}
        if "versioned" in table_info and op.column.name not in table_info["versioned"].get(
            "exclude", []
        ):
            return [
                op,
                AddColumnToActivityOp(op.table_name, op.column.name),
            ]
        else:
            return op

    @writer.rewrites(ops.DropColumnOp)
    def drop_column_rewrite(context, revision, op):
        column = op.to_column()
        table_info = column.table.info or {}
        if "versioned" in table_info and column.name not in table_info["versioned"].get(
            "exclude", []
        ):
            return [
                op,
                RemoveColumnFromRemoveActivityOp(op.table_name, column.name),
            ]
        else:
            return op

    return writer
