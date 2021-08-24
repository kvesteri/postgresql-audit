import sqlalchemy as sa
from alembic.autogenerate import renderers
from alembic.operations import MigrateOperation, Operations


@Operations.register_operation('register_for_version_tracking')
class RegisterTableForVersionTrackingOp(MigrateOperation):
    """Register Table for Version Tracking"""

    def __init__(
        self,
        tablename,
        excluded_columns,
        original_excluded_columns=None,
        schema=None
    ):
        self.schema = schema
        self.tablename = tablename
        self.excluded_columns = excluded_columns
        self.original_excluded_columns = original_excluded_columns

    @classmethod
    def register_for_version_tracking(
        cls, operations, tablename, exclude_columns, **kwargs
    ):
        op = RegisterTableForVersionTrackingOp(
            tablename, exclude_columns, **kwargs
        )
        return operations.invoke(op)

    def reverse(self):
        # only needed to support autogenerate
        return DeregisterTableForVersionTrackingOp(
            self.tablename, self.original_excluded_columns, schema=self.schema
        )


@Operations.register_operation('deregister_for_version_tracking')
class DeregisterTableForVersionTrackingOp(MigrateOperation):
    """Drop Table from Version Tracking"""

    def __init__(self, tablename, excluded_columns, schema=None):
        self.schema = schema
        self.tablename = tablename
        self.excluded_columns = excluded_columns

    @classmethod
    def deregister_for_version_tracking(cls, operations, tablename, **kwargs):
        op = DeregisterTableForVersionTrackingOp(tablename, (), **kwargs)
        return operations.invoke(op)

    def reverse(self):
        # only needed to support autogenerate
        return RegisterTableForVersionTrackingOp(
            self.tablename, self.excluded_columns, (), schema=self.schema
        )


@Operations.implementation_for(RegisterTableForVersionTrackingOp)
def register_for_version_tracking(operations, operation):
    if operation.schema is None:
        func = sa.func.audit_table
    else:
        func = getattr(getattr(sa.func, operation.schema), 'audit_table')
    operations.execute(
        sa.select(
            [func(operation.tablename, list(operation.excluded_columns))]
        )
    )


@Operations.implementation_for(DeregisterTableForVersionTrackingOp)
def deregister_for_version_tracking(operations, operation):
    operations.execute(
        f'drop trigger if exists audit_trigger_insert on {operation.tablename}'
    )
    operations.execute(
        f'drop trigger if exists audit_trigger_update on {operation.tablename}'
    )
    operations.execute(
        f'drop trigger if exists audit_trigger_delete on {operation.tablename}'
    )
    operations.execute(
        f'drop trigger if exists audit_trigger_row on {operation.tablename}'
    )


@renderers.dispatch_for(RegisterTableForVersionTrackingOp)
def render_register_for_version_tracking(autogen_context, op):
    return 'op.register_for_version_tracking(%r, %r, **%r)' % (
        op.tablename,
        op.excluded_columns,
        {'schema': op.schema}
    )


@renderers.dispatch_for(DeregisterTableForVersionTrackingOp)
def render_deregister_for_version_tracking(autogen_context, op):
    return 'op.deregister_for_version_tracking(%r, **%r)' % (
        op.tablename,
        {'schema': op.schema}
    )
