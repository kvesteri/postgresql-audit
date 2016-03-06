CREATE OR REPLACE FUNCTION jsonb_change_key_name(data jsonb, old_key text, new_key text)
RETURNS jsonb
IMMUTABLE
LANGUAGE sql
AS $$$$
    SELECT ('{'||string_agg(to_json(CASE WHEN key = old_key THEN new_key ELSE key END)||':'||value, ',')||'}')::jsonb
    FROM (
        SELECT *
        FROM jsonb_each(data)
    ) t;
$$$$;

CREATE OR REPLACE FUNCTION ${schema_prefix}create_activity() RETURNS TRIGGER AS $$body$$
DECLARE
    audit_row ${schema_prefix}activity;
    audit_row_values ${schema_prefix}activity;
    excluded_cols text[] = ARRAY[]::text[];
BEGIN
    IF TG_WHEN <> 'AFTER' THEN
        RAISE EXCEPTION '${schema_prefix}create_activity() may only run as an AFTER trigger';
    END IF;

    BEGIN
        SELECT * FROM activity_values INTO audit_row_values LIMIT 1;
    EXCEPTION WHEN others THEN
    END;

    audit_row.id = nextval('${schema_prefix}activity_id_seq');
    audit_row.schema_name = TG_TABLE_SCHEMA::text;
    audit_row.table_name = TG_TABLE_NAME::text;
    audit_row.relid = TG_RELID;
    audit_row.issued_at = COALESCE(
        audit_row_values.issued_at,
        statement_timestamp()
    );
    audit_row.transaction_id = COALESCE(
        audit_row_values.transaction_id,
        txid_current()
    );
    audit_row.client_addr = COALESCE(
        audit_row_values.client_addr,
        inet_client_addr()
    );
    audit_row.verb = COALESCE(audit_row_values.verb, LOWER(TG_OP));
    audit_row.actor_id = audit_row_values.actor_id;
    audit_row.target_id = audit_row_values.target_id;
    audit_row.old_data = NULL;
    audit_row.changed_data = NULL;

    IF TG_ARGV[0] IS NOT NULL THEN
        excluded_cols = TG_ARGV[0]::text[];
    END IF;

    IF (TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW') THEN
        audit_row.old_data = row_to_json(OLD.*)::jsonb - excluded_cols;
        audit_row.changed_data = (
            row_to_json(NEW.*)::jsonb - audit_row.old_data - excluded_cols
        );
        IF audit_row.changed_data = '{}'::jsonb THEN
            -- All changed fields are ignored. Skip this update.
            RETURN NULL;
        END IF;
    ELSIF (TG_OP = 'DELETE' AND TG_LEVEL = 'ROW') THEN
        audit_row.old_data = row_to_json(OLD.*)::jsonb - excluded_cols;
    ELSIF (TG_OP = 'INSERT' AND TG_LEVEL = 'ROW') THEN
        audit_row.changed_data = row_to_json(NEW.*)::jsonb - excluded_cols;
    ELSE
        RAISE EXCEPTION '[${schema_prefix}create_activity] - Trigger func added as trigger for unhandled case: %, %', TG_OP, TG_LEVEL;
        RETURN NULL;
    END IF;
    INSERT INTO ${schema_prefix}activity VALUES (audit_row.*);
    RETURN NULL;
END;
$$body$$
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public;


COMMENT ON FUNCTION ${schema_prefix}create_activity() IS $$body$$
Track changes to a table at the statement and/or row level.

Optional parameters to trigger in CREATE TRIGGER call:

param 0: boolean, whether to log the query text. Default 't'.

param 1: text[], columns to ignore in updates. Default [].

         Updates to ignored cols are omitted from changed_fields.

         Updates with only ignored cols changed are not inserted
         into the audit log.

         Almost all the processing work is still done for updates
         that ignored. If you need to save the load, you need to use
         WHEN clause on the trigger instead.

         No warning or error is issued if ignored_cols contains columns
         that do not exist in the target table. This lets you specify
         a standard set of ignored columns.

There is no parameter to disable logging of values. Add this trigger as
a 'FOR EACH STATEMENT' rather than 'FOR EACH ROW' trigger if you do not
want to log row values.

Note that the user name logged is the login role for the session. The audit trigger
cannot obtain the active role because it is reset by the SECURITY DEFINER invocation
of the audit trigger its self.
$$body$$;
