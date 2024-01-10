import re
from collections import defaultdict, namedtuple

from alembic.autogenerate import comparators, renderers
from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text


def setup_functions_and_triggers(audit_logger):
    """The comparator at the end controls which functions and triggers
    need to be added/removed based on the current audit_logger.versioned_tables."""

    """ PG Functions """

    @Operations.register_operation("init_audit_logger_function")
    class InitAuditLoggerFunctionOp(MigrateOperation):
        def __init__(self, function_signature):
            self.function_signature = function_signature

        @classmethod
        def init_audit_logger_function(cls, operations, function_signature):
            op = InitAuditLoggerFunctionOp(function_signature)
            return operations.invoke(op)

        def reverse(self):
            return RemoveAuditLoggerFunctionOp(self.function_signature)

    @Operations.register_operation("remove_audit_logger_function")
    class RemoveAuditLoggerFunctionOp(MigrateOperation):
        def __init__(self, function_signature):
            self.function_signature = function_signature

        @classmethod
        def remove_audit_logger_function(cls, operations, function_signature):
            op = RemoveAuditLoggerFunctionOp(function_signature)
            return operations.invoke(op)

        def reverse(self):
            return InitAuditLoggerFunctionOp(self.function_signature)

    @Operations.implementation_for(InitAuditLoggerFunctionOp)
    def init_audit_logger_function(operations, operation):
        pg_func = audit_logger.functions_by_signature[operation.function_signature]
        operations.execute(pg_func.create_sql)

    @Operations.implementation_for(RemoveAuditLoggerFunctionOp)
    def remove_audit_logger_function(operations, operation):
        pg_func = audit_logger.functions_by_signature[operation.function_signature]
        operations.execute(pg_func.drop_sql)

    @renderers.dispatch_for(InitAuditLoggerFunctionOp)
    def render_init_audit_logger_function(autogen_context, op):
        return "op.init_audit_logger_function(%r)" % (op.function_signature,)

    @renderers.dispatch_for(RemoveAuditLoggerFunctionOp)
    def render_remove_audit_logger_function(autogen_context, op):
        return "op.remove_audit_logger_function(%r)" % (op.function_signature,)

    """ Table Triggers """

    @Operations.register_operation("init_audit_logger_triggers")
    class InitAuditLoggerTriggers(MigrateOperation):
        def __init__(
            self,
            table_name,
            excluded_columns=None,
            original_excluded_columns=None,
        ):
            self.table_name = table_name
            self.excluded_columns = excluded_columns or []
            self.original_excluded_columns = original_excluded_columns or []

        @classmethod
        def init_audit_logger_triggers(cls, operations, table_name, excluded_columns=None):
            op = InitAuditLoggerTriggers(table_name, excluded_columns=excluded_columns)
            return operations.invoke(op)

        def reverse(self):
            return RemoveAuditLoggerTriggers(
                self.table_name, excluded_columns=self.original_excluded_columns
            )

    @Operations.register_operation("remove_audit_logger_triggers")
    class RemoveAuditLoggerTriggers(MigrateOperation):
        def __init__(self, table_name, excluded_columns=None):
            self.table_name = table_name
            self.excluded_columns = excluded_columns or []

        @classmethod
        def remove_audit_logger_triggers(cls, operations, table_name, **kwargs):
            op = RemoveAuditLoggerTriggers(table_name, **kwargs)
            return operations.invoke(op)

        def reverse(self):
            return InitAuditLoggerTriggers(self.table_name, excluded_columns=self.excluded_columns)

    @Operations.implementation_for(InitAuditLoggerTriggers)
    def init_audit_logger_triggers(operations, operation):
        pg_triggers = audit_logger.pg_triggers_per_table.get(operation.table_name, [])
        for pg_trigger in pg_triggers:
            operations.execute(pg_trigger.create_sql)

    @Operations.implementation_for(RemoveAuditLoggerTriggers)
    def remove_audit_logger_triggers(operations, operation):
        pg_triggers = audit_logger.pg_triggers_per_table.get(operation.table_name, [])
        for pg_trigger in pg_triggers:
            operations.execute(pg_trigger.drop_sql)

    @renderers.dispatch_for(InitAuditLoggerTriggers)
    def render_init_audit_logger_triggers(autogen_context, op):
        if not op.excluded_columns:
            return "op.init_audit_logger_triggers(%r)" % (op.table_name,)
        return "op.init_audit_logger_triggers(%r, excluded_columns=%r)" % (
            op.table_name,
            op.excluded_columns,
        )

    @renderers.dispatch_for(RemoveAuditLoggerTriggers)
    def render_remove_audit_logger_triggers(autogen_context, op):
        return "op.remove_audit_logger_triggers(%r)" % (op.table_name)

    @comparators.dispatch_for("schema")
    def check_for_function_and_trigger_changes(autogen_context, upgrade_ops, schemas):
        check_functions(autogen_context, upgrade_ops, schemas)
        check_triggers(autogen_context, upgrade_ops, schemas)

    def check_functions(autogen_context, upgrade_ops, schemas):
        funcs_sql = text(
            f"""
            SELECT 
                format(
                    '%%s(%%s)',
                    replace(p.oid::regproc::TEXT, '{audit_logger.prefix}', ''),
                    pg_get_function_identity_arguments(p.oid)
                ) AS signature
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = '{audit_logger.schema}'
            ORDER  BY 1;
        """
        )

        funcs_in_db = {row.signature for row in autogen_context.connection.execute(funcs_sql)}

        funcs_in_app = set(audit_logger.functions_by_signature.keys())

        should_add = funcs_in_app - funcs_in_db
        should_remove = funcs_in_db - funcs_in_app

        for func in audit_logger.pg_functions:
            sig = func.signature
            if sig in should_add:
                upgrade_ops.ops.append(InitAuditLoggerFunctionOp(sig))
            if sig in should_remove:
                upgrade_ops.ops.append(RemoveAuditLoggerFunctionOp(sig))

    Trigger = namedtuple("Trigger", ["table", "trigger_name", "definition"])

    def check_triggers(autogen_context, upgrade_ops, schemas):
        triggers_sql = text(
            """
            SELECT event_object_table, trigger_name, action_statement
            FROM information_schema.triggers
            WHERE trigger_name LIKE 'audit_trigger%%'
        """
        )

        triggers_per_table = defaultdict(list)
        for row in autogen_context.connection.execute(triggers_sql):
            trigger = Trigger(*row)
            triggers_per_table[trigger.table].append(trigger)

        for table in audit_logger.versioned_tables:
            trigger = next((tr for tr in triggers_per_table[table.name]), None)
            excluded_columns_in_app = table.info["versioned"].get("exclude", [])

            if not trigger:
                upgrade_ops.ops.append(
                    InitAuditLoggerTriggers(
                        table.name,
                        excluded_columns=excluded_columns_in_app,
                    )
                )
            else:
                excluded_columns_in_db = _get_existing_excluded_columns(trigger.definition)

                if set(excluded_columns_in_db) != set(excluded_columns_in_app):
                    upgrade_ops.ops.append(
                        InitAuditLoggerTriggers(
                            table.name,
                            excluded_columns=excluded_columns_in_app,
                            original_excluded_columns=excluded_columns_in_db,
                        )
                    )

        for table_name, triggers in triggers_per_table.items():
            if table_name not in {t.name for t in audit_logger.versioned_tables}:
                upgrade_ops.ops.append(
                    RemoveAuditLoggerTriggers(
                        table_name,
                        excluded_columns=_get_existing_excluded_columns(triggers[0].definition),
                    )
                )


def _get_existing_excluded_columns(trigger_definition):
    matched = re.search(r"create_activity\('{(.+)}'\)", trigger_definition)

    if matched:
        return matched.group(1).split(",")

    return []
