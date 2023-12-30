from alembic.autogenerate import renderers, comparators
from alembic.operations import MigrateOperation, Operations

def setup_schema(audit_logger):
    @Operations.register_operation('init_audit_logger_schema')
    class InitAuditLoggerSchemaOp(MigrateOperation):
        @classmethod
        def init_audit_logger_schema(cls, operations):
            op = InitAuditLoggerSchemaOp()
            return operations.invoke(op)

        def reverse(self):
            return RemoveAuditLoggerSchemaOp()

    @Operations.register_operation("remove_audit_logger_schema")
    class RemoveAuditLoggerSchemaOp(MigrateOperation):
        @classmethod
        def remove_audit_logger_schema(cls, operations):
            op = RemoveAuditLoggerSchemaOp()
            return operations.invoke(op)

        def reverse(self):
            return InitAuditLoggerSchemaOp()

    @Operations.implementation_for(InitAuditLoggerSchemaOp)
    def init_audit_logger_schema(operations, operation):
        operations.execute(audit_logger.render_sql_template("create_schema.sql", as_text=False))
        operations.execute(audit_logger.pg_btree_gist_extension.create_sql)

    @Operations.implementation_for(RemoveAuditLoggerSchemaOp)
    def remove_audit_logger_function(operations, operation):
        operations.execute(audit_logger.pg_btree_gist_extension.drop_sql)
        operations.execute(audit_logger.render_sql_template("drop_schema.sql", as_text=False))

    @renderers.dispatch_for(InitAuditLoggerSchemaOp)
    def render_init_audit_logger_schema(autogen_context, op):
        return 'op.init_audit_logger_schema()'

    @renderers.dispatch_for(RemoveAuditLoggerSchemaOp)
    def render_remove_audit_logger_schema(autogen_context, op):
        return 'op.remove_audit_logger_schema()'

    @comparators.dispatch_for("schema")
    def check_for_audit_logger_schema(autogen_context, upgrade_ops, schemas):
        schema_exists_sql = f"SELECT TRUE FROM information_schema.schemata WHERE schema_name = '{audit_logger.schema}'"
        schema_exists = autogen_context.connection.scalar(schema_exists_sql)
        if not schema_exists:
            upgrade_ops.ops.insert(0, InitAuditLoggerSchemaOp())
