from alembic.autogenerate import comparators, renderers
from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text


def setup_schema(audit_logger):
    """These operations ensure the target schema and extensions exist."""

    """ Schema """

    @Operations.register_operation("init_audit_logger_schema")
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

    @Operations.implementation_for(RemoveAuditLoggerSchemaOp)
    def remove_audit_logger_schema(operations, operation):
        operations.execute(audit_logger.render_sql_template("drop_schema.sql", as_text=False))

    @renderers.dispatch_for(InitAuditLoggerSchemaOp)
    def render_init_audit_logger_schema(autogen_context, op):
        return "op.init_audit_logger_schema()"

    @renderers.dispatch_for(RemoveAuditLoggerSchemaOp)
    def render_remove_audit_logger_schema(autogen_context, op):
        return "op.remove_audit_logger_schema()"

    @comparators.dispatch_for("schema")
    def check_for_audit_logger_schema(autogen_context, upgrade_ops, schemas):
        schema_exists_sql = text(
            f"SELECT TRUE FROM information_schema.schemata WHERE schema_name = '{audit_logger.schema}'"
        )
        schema_exists = autogen_context.connection.scalar(schema_exists_sql)
        if not schema_exists:
            upgrade_ops.ops.insert(0, InitAuditLoggerSchemaOp())

    """ Extensions """

    @Operations.register_operation("init_audit_logger_extension")
    class InitAuditLoggerExtensionOp(MigrateOperation):
        def __init__(self, extension):
            self.extension = extension

        @classmethod
        def init_audit_logger_extension(cls, operations, extension):
            op = InitAuditLoggerExtensionOp(extension)
            return operations.invoke(op)

        def reverse(self):
            return RemoveAuditLoggerExtensionOp(self.extension)

    @Operations.register_operation("remove_audit_logger_extension")
    class RemoveAuditLoggerExtensionOp(MigrateOperation):
        def __init__(self, extension):
            self.extension = extension

        @classmethod
        def remove_audit_logger_extension(cls, operations, extension):
            op = RemoveAuditLoggerExtensionOp(extension)
            return operations.invoke(op)

        def reverse(self):
            return InitAuditLoggerExtensionOp(self.extension)

    @Operations.implementation_for(InitAuditLoggerExtensionOp)
    def init_audit_logger_extension(operations, operation):
        assert operation.extension == "btree_gist"
        operations.execute(audit_logger.pg_btree_gist_extension.create_sql)

    @Operations.implementation_for(RemoveAuditLoggerExtensionOp)
    def remove_audit_logger_extension(operations, operation):
        assert operation.extension == "btree_gist"
        operations.execute(audit_logger.pg_btree_gist_extension.drop_sql)

    @renderers.dispatch_for(InitAuditLoggerExtensionOp)
    def render_init_audit_logger_extension(autogen_context, op):
        return f"op.init_audit_logger_extension('{op.extension}')"

    @renderers.dispatch_for(RemoveAuditLoggerExtensionOp)
    def render_remove_audit_logger_extension(autogen_context, op):
        return f"op.remove_audit_logger_extension('{op.extension}')"

    @comparators.dispatch_for("schema")
    def check_for_audit_logger_extensions(autogen_context, upgrade_ops, schemas):
        btree_gist = audit_logger.pg_btree_gist_extension.signature
        extension_exists_sql = text(
            f"SELECT TRUE FROM pg_extension WHERE extname = '{btree_gist}'"
        )
        extension_exists = autogen_context.connection.scalar(extension_exists_sql)
        if not extension_exists:
            upgrade_ops.ops.insert(0, InitAuditLoggerExtensionOp(btree_gist))
