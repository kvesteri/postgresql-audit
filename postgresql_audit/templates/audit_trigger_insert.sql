CREATE OR REPLACE TRIGGER audit_trigger_insert AFTER INSERT ON ${table_name}
REFERENCING NEW TABLE AS new_table FOR EACH STATEMENT
WHEN (${schema_prefix}get_setting('postgresql_audit.enable_versioning', 'true')::bool)
EXECUTE PROCEDURE ${schema_prefix}create_activity(${excluded_columns})
