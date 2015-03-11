CREATE OR REPLACE FUNCTION audit.audit_table(target_table regclass, ignored_cols text[]) RETURNS void AS $body$
DECLARE
    stm_targets text = 'INSERT OR UPDATE OR DELETE OR TRUNCATE';
    _q_txt text;
    _ignored_cols_snip text = '';
BEGIN
    EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_row ON ' || target_table;
    EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_stm ON ' || target_table;

    IF array_length(ignored_cols, 1) > 0 THEN
        _ignored_cols_snip = ', ' || quote_literal(ignored_cols);
    END IF;
    _q_txt = 'CREATE TRIGGER audit_trigger_row AFTER INSERT OR UPDATE OR DELETE ON ' ||
             target_table ||
             ' FOR EACH ROW EXECUTE PROCEDURE audit.create_activity(' ||
             _ignored_cols_snip ||
             ');';
    RAISE NOTICE '%',_q_txt;
    EXECUTE _q_txt;
    stm_targets = 'TRUNCATE';
END;
$body$
language 'plpgsql';

COMMENT ON FUNCTION audit.audit_table(regclass, text[]) IS $body$
Add auditing support to a table.

Arguments:
   target_table:     Table name, schema qualified if not on search_path
   ignored_cols:     Columns to exclude from update diffs, ignore updates that change only ignored cols.
$body$;


CREATE OR REPLACE FUNCTION audit.audit_table(target_table regclass) RETURNS void AS $body$
SELECT audit.audit_table($1, ARRAY[]::text[]);
$body$ LANGUAGE SQL;


COMMENT ON FUNCTION audit.audit_table(regclass) IS $body$
Add auditing support to the given table. Row-level changes will be logged with full client query text. No cols are ignored.
$body$;
