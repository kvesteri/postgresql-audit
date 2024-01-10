CREATE OR REPLACE TRIGGER audit_trigger_update AFTER UPDATE ON "${table_name}"
REFERENCING NEW TABLE AS new_table OLD TABLE AS old_table FOR EACH STATEMENT
WHEN (${schema_prefix}get_setting('flask_audit_logger.enable_versioning', 'true')::bool)
EXECUTE PROCEDURE ${schema_prefix}create_activity(${excluded_columns})
