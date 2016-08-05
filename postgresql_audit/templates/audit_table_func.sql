CREATE OR REPLACE FUNCTION
${schema_prefix}audit_table(target_table regclass, ignored_cols text[])
RETURNS void AS $$body$$
DECLARE
    stm_targets text = 'INSERT OR UPDATE OR DELETE OR TRUNCATE';
    query text;
    excluded_columns_text text = '';
BEGIN
    EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_row ON ' || target_table;

    IF array_length(ignored_cols, 1) > 0 THEN
        excluded_columns_text = ', ' || quote_literal(ignored_cols);
    END IF;
    query = 'CREATE TRIGGER audit_trigger_row AFTER INSERT OR UPDATE OR DELETE ON ' ||
             target_table || ' FOR EACH ROW ' ||
             E'WHEN (current_setting(\'session_replication_role\') ' ||
             E'<> \'local\')' ||
             ' EXECUTE PROCEDURE ${schema_prefix}create_activity(' ||
             excluded_columns_text ||
             ');';
    RAISE NOTICE '%', query;
    EXECUTE query;
    stm_targets = 'TRUNCATE';
END;
$$body$$
language 'plpgsql';


CREATE OR REPLACE FUNCTION ${schema_prefix}audit_table(target_table regclass) RETURNS void AS $$body$$
SELECT ${schema_prefix}audit_table($$1, ARRAY[]::text[]);
$$body$$ LANGUAGE SQL;
