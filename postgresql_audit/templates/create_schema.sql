CREATE SCHEMA ${schema_name};
REVOKE ALL ON SCHEMA ${schema_name} FROM public;

COMMENT ON SCHEMA ${schema_name} IS 'Out-of-table audit/history logging tables and trigger functions';