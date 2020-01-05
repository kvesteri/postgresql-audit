from alembic.autogenerate import renderers
from alembic.operations import Operations, MigrateOperation

from postgresql_audit.utils import render_tmpl, create_audit_table, create_operators


@Operations.register_operation("init_activity_table_triggers")
class InitActivityTableTriggersOp(MigrateOperation):
    """Initialize Activity Table Triggers"""

    def __init__(self, use_statement_level_triggers, schema=None):
        self.schema = schema
        self.use_statement_level_triggers = use_statement_level_triggers

    @classmethod
    def init_activity_table_triggers(cls, operations, use_statement_level_triggers, **kwargs):
        op = InitActivityTableTriggersOp(use_statement_level_triggers, **kwargs)
        return operations.invoke(op)

    def reverse(self):
        # only needed to support autogenerate
        return RemoveActivityTableTriggersOp(schema=self.schema)

@Operations.register_operation("remove_activity_table_triggers")
class RemoveActivityTableTriggersOp(MigrateOperation):
    """Drop Activity Table Triggers"""

    def __init__(self, use_statement_level_triggers, schema=None):
        self.schema = schema
        self.use_statement_level_triggers = use_statement_level_triggers


    @classmethod
    def remove_activity_table_triggers(cls, operations, use_statement_level_triggers, **kwargs):
        op = RemoveActivityTableTriggersOp(use_statement_level_triggers, **kwargs)
        return operations.invoke(op)

    def reverse(self):
        # only needed to support autogenerate
        return InitActivityTableTriggersOp(self.use_statement_level_triggers, schema=self.schema)


@Operations.implementation_for(InitActivityTableTriggersOp)
def init_activity_table_triggers(operations, operation):
    conn = operations.connection

    if operation.schema:
        conn.execute(render_tmpl('create_schema.sql', operation.schema))

    conn.execute(render_tmpl('jsonb_change_key_name.sql', operation.schema))
    create_audit_table(None, conn, operation.schema, operation.use_statement_level_triggers)
    create_operators(None, conn, operation.schema)


@Operations.implementation_for(RemoveActivityTableTriggersOp)
def remove_activity_table_triggers(operations, operation):
    conn = operations.connection
    bind = conn.bind

    if operation.schema:
        conn.execute(render_tmpl('drop_schema.sql', operation.schema))

    conn.execute("DROP FUNCTION jsonb_change_key_name(data jsonb, old_key text, new_key text)")
    schema_prefix = f"{operation.schema}." if operation.schema else ""

    conn.execute(f"DROP FUNCTION {schema_prefix}audit_table(target_table regclass, ignored_cols text[])")
    conn.execute(f"DROP FUNCTION {schema_prefix}create_activity()")


    if bind.dialect.server_version_info < (9, 5, 0):
        conn.execute(f"""DROP FUNCTION jsonb_subtract(jsonb,  TEXT)""")
        conn.execute(f"""DROP OPERATOR IF EXISTS - (jsonb, text);""")
        conn.execute(f"""DROP FUNCTION jsonb_merge(jsonb, jsonb)""")
        conn.execute(f"""DROP OPERATOR IF EXISTS || (jsonb, jsonb);""")
    if bind.dialect.server_version_info < (9, 6, 0):
        conn.execute(f"""DROP FUNCTION current_setting(TEXT, BOOL)""")
    if bind.dialect.server_version_info < (10, 0):
        conn.execute(f"""DROP FUNCTION jsonb_subtract(jsonb, TEXT[])""")
        conn.execute(f"""DROP OPERATOR IF EXISTS - (jsonb, text[])""")

    conn.execute(f"""DROP FUNCTION jsonb_subtract(jsonb,jsonb)""")
    conn.execute(f"""DROP OPERATOR IF EXISTS - (jsonb, jsonb)""")
    conn.execute(f"""DROP FUNCTION get_setting(text, text)""")


@renderers.dispatch_for(InitActivityTableTriggersOp)
def render_init_activity_table_triggers(autogen_context, op):
    return "op.init_activity_table_triggers(%r, **%r)" % (
        op.use_statement_level_triggers,
        {"schema": op.schema}
    )

@renderers.dispatch_for(RemoveActivityTableTriggersOp)
def render_remove_activity_table_triggers(autogen_context, op):
    return "op.remove_activity_table_triggers(**%r)" % (
        {"schema": op.schema}
    )
