import re

from alembic.autogenerate import comparators, rewriter
from alembic.operations import ops

from postgresql_audit.alembic.init_activity_table_triggers import (
    InitActivityTableTriggersOp,
    RemoveActivityTableTriggersOp
)
from postgresql_audit.alembic.migration_ops import (
    AddColumnToActivityOp,
    RemoveColumnFromRemoveActivityOp
)
from postgresql_audit.alembic.register_table_for_version_tracking import (
    DeregisterTableForVersionTrackingOp,
    RegisterTableForVersionTrackingOp
)


@comparators.dispatch_for('schema')
def compare_timestamp_schema(autogen_context, upgrade_ops, schemas):
    routines = set()
    for schema in schemas:
        schema_name = (
            autogen_context.dialect.default_schema_name if schema is None
            else schema
        )
        routines.update([
            (schema, *row) for row in autogen_context.connection.execute(f'''
                SELECT routine_name, routine_definition
                FROM information_schema.routines
                WHERE routines.specific_schema='{schema_name}'
            ''')
        ])

    for schema in schemas:
        should_track_versions = any(
            'versioned' in table.info
            for table in autogen_context.sorted_tables
            if table.info and table.schema == schema
        )
        schema_prefix = f'{schema}.' if schema else ''
        tracked = f'{schema_prefix}audit_table' in [
            routine[1] for routine in routines if routine[0] == schema
        ]

        if should_track_versions:
            if not tracked:
                upgrade_ops.ops.insert(
                    0,
                    InitActivityTableTriggersOp(False, schema=schema)
                )
        else:
            if tracked:
                upgrade_ops.ops.append(
                    RemoveActivityTableTriggersOp(False, schema=schema)
                )


@comparators.dispatch_for('table')
def compare_timestamp_table(
    autogen_context,
    modify_ops,
    schemaname,
    tablename,
    conn_table,
    metadata_table
):
    if metadata_table is None:
        return
    meta_info = metadata_table.info or {}
    schema_name = (
        autogen_context.dialect.default_schema_name
        if schemaname is None else schemaname
    )

    triggers = [row for row in autogen_context.connection.execute(
        'SELECT event_object_schema AS table_schema,'
        'event_object_table AS table_name,'
        'trigger_schema,'
        'trigger_name,'
        'STRING_AGG(event_manipulation, ',') AS event,'
        'action_timing AS activation,'
        'action_condition AS condition,'
        'action_statement AS definition '
        'FROM information_schema.triggers '
        f"WHERE event_object_table = '{tablename}' "
        f"AND trigger_schema = '{schema_name}' "
        'GROUP BY 1,2,3,4,6,7,8 '
        'ORDER BY table_schema, table_name'
    )]

    trigger_name = 'audit_trigger'

    if 'versioned' in meta_info:
        excluded_columns = (
            metadata_table.info['versioned'].get('exclude', tuple())
        )
        trigger = next(
            (trigger for trigger in triggers if trigger_name in trigger[3]),
            None
        )
        original_excluded_columns = __get_existing_excluded_columns(trigger)

        if trigger and set(original_excluded_columns) == set(excluded_columns):
            return

        modify_ops.ops.insert(
            0,
            RegisterTableForVersionTrackingOp(
                tablename,
                excluded_columns,
                original_excluded_columns,
                schema=schema_name
            )
        )
    else:
        trigger = next(
            (trigger for trigger in triggers if trigger_name in trigger[3]),
            None
        )
        original_excluded_columns = __get_existing_excluded_columns(trigger)

        if trigger:
            modify_ops.ops.append(
                DeregisterTableForVersionTrackingOp(
                    tablename,
                    original_excluded_columns,
                    schema=schema_name
                )
            )


def __get_existing_excluded_columns(trigger):
    original_excluded_columns = ()
    if trigger:
        arguments_match = re.search(
            r"EXECUTE FUNCTION create_activity\('{(.+)}'\)",
            trigger[7]
        )
        if arguments_match:
            original_excluded_columns = arguments_match.group(1).split(',')
    return original_excluded_columns


writer = rewriter.Rewriter()


@writer.rewrites(ops.AddColumnOp)
def add_column_rewrite(context, revision, op):
    table_info = op.column.table.info or {}
    if (
        'versioned' in table_info
        and op.column.name not in table_info['versioned'].get('exclude', [])
    ):
        return [
            op,
            AddColumnToActivityOp(
                op.table_name,
                op.column.name,
                schema=op.column.table.schema,
            ),
        ]
    else:
        return op


@writer.rewrites(ops.DropColumnOp)
def drop_column_rewrite(context, revision, op):
    column = op._orig_column
    table_info = column.table.info or {}
    if (
        'versioned' in table_info
        and column.name not in table_info['versioned'].get('exclude', [])
    ):
        return [
            op,
            RemoveColumnFromRemoveActivityOp(
                op.table_name,
                column.name,
                schema=column.table.schema,
            ),
        ]
    else:
        return op
