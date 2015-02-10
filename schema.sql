-- An audit history is important on most tables. Provide an audit trigger that logs to
-- a dedicated audit table for the major relations.
--
-- This file should be generic and not depend on application roles or structures,
-- as it's being listed here:
--
--    https://wiki.postgresql.org/wiki/Audit_trigger_91plus
--
-- This trigger was originally based on
--   http://wiki.postgresql.org/wiki/Audit_trigger
-- but has been completely rewritten.
--
-- Should really be converted into a relocatable EXTENSION, with control and upgrade files.

CREATE EXTENSION IF NOT EXISTS hstore;

CREATE SCHEMA audit;
REVOKE ALL ON SCHEMA audit FROM public;

COMMENT ON SCHEMA audit IS 'Out-of-table audit/history logging tables and trigger functions';

--
-- Audited data. Lots of information is available, it's just a matter of how much
-- you really want to record. See:
--
--   http://www.postgresql.org/docs/9.1/static/functions-info.html
--
-- Remember, every column you add takes up more audit table space and slows audit
-- inserts.
--
-- Every index you add has a big impact too, so avoid adding indexes to the
-- audit table unless you REALLY need them. The hstore GIST indexes are
-- particularly expensive.
--
-- It is sometimes worth copying the audit table, or a coarse subset of it that
-- you're interested in, into a temporary table where you CREATE any useful
-- indexes and do your analysis.
--
CREATE TABLE audit.activity (
    event_id bigserial primary key,
    schema_name text,
    table_name text,
    relid oid,
    session_user_name text,
    issued_at TIMESTAMP WITH TIME ZONE,
    transaction_id bigint,
    application_name text,
    client_addr inet,
    client_port integer,
    verb TEXT,
    actor_id TEXT,
    object_id TEXT,
    target_id TEXT,
    row_data hstore,
    changed_fields hstore
);

REVOKE ALL ON audit.activity FROM public;

COMMENT ON TABLE audit.activity IS 'History of auditable actions on audited tables, from audit.if_modified_func()';
COMMENT ON COLUMN audit.activity.event_id IS 'Unique identifier for each auditable event';
COMMENT ON COLUMN audit.activity.schema_name IS 'Database schema audited table for this event is in';
COMMENT ON COLUMN audit.activity.table_name IS 'Non-schema-qualified table name of table event occured in';
COMMENT ON COLUMN audit.activity.relid IS 'Table OID. Changes with drop/create. Get with ''tablename''::regclass';
COMMENT ON COLUMN audit.activity.session_user_name IS 'Login / session user whose statement caused the audited event';
COMMENT ON COLUMN audit.activity.issued_at IS 'Statement start timestamp for tx in which audited event occurred';
COMMENT ON COLUMN audit.activity.transaction_id IS 'Identifier of transaction that made the change. May wrap, but unique paired with action_tstamp_tx.';
COMMENT ON COLUMN audit.activity.client_addr IS 'IP address of client that issued query. Null for unix domain socket.';
COMMENT ON COLUMN audit.activity.client_port IS 'Remote peer IP port address of client that issued query. Undefined for unix socket.';
COMMENT ON COLUMN audit.activity.application_name IS 'Application name set when this audit event occurred. Can be changed in-session by client.';
COMMENT ON COLUMN audit.activity.verb IS 'Action type, normally insert, update, delete or truncate';
COMMENT ON COLUMN audit.activity.row_data IS 'Record value. Null for statement-level trigger. For INSERT this is the new tuple. For DELETE and UPDATE it is the old tuple.';
COMMENT ON COLUMN audit.activity.changed_fields IS 'New values of fields changed by UPDATE. Null except for row-level UPDATE events.';

CREATE INDEX activity_relid_idx ON audit.activity(relid);
CREATE INDEX activity_issued_at_idx ON audit.activity(issued_at);
CREATE INDEX activity_verb_idx ON audit.activity(verb);

CREATE OR REPLACE FUNCTION audit.if_modified_func() RETURNS TRIGGER AS $body$
DECLARE
    audit_row audit.activity;
    audit_row_values audit.activity;
    include_values boolean;
    log_diffs boolean;
    h_old hstore;
    h_new hstore;
    excluded_cols text[] = ARRAY[]::text[];
    object_id text;
BEGIN
    IF TG_WHEN <> 'AFTER' THEN
        RAISE EXCEPTION 'audit.if_modified_func() may only run as an AFTER trigger';
    END IF;

    IF TG_ARGV[0] IS NOT NULL THEN
        IF TG_OP = 'DELETE' THEN
            object_id = array_to_string(
                hstore(OLD.*) -> TG_ARGV[0]::text[],
                ','
            );
        ELSE
            object_id = array_to_string(
                hstore(NEW.*) -> TG_ARGV[0]::text[],
                ','
            );
        END IF;
    END IF;

    BEGIN
        SELECT * FROM activity_values INTO audit_row_values LIMIT 1;
    EXCEPTION WHEN others THEN
    END;

    audit_row = ROW(
        nextval('audit.activity_event_id_seq'),         -- event_id
        TG_TABLE_SCHEMA::text,                          -- schema_name
        TG_TABLE_NAME::text,                            -- table_name
        TG_RELID,                                       -- relation OID for much quicker searches
        session_user::text,                             -- session_user_name
        COALESCE(
            audit_row_values.issued_at,
            statement_timestamp()
        ),                                              -- issued_at
        COALESCE(
            audit_row_values.transaction_id,
            txid_current()
        ),                                              -- transaction ID
        current_setting('application_name'),            -- client application
        inet_client_addr(),                             -- client_addr
        inet_client_port(),                             -- client_port
        COALESCE(audit_row_values.verb, LOWER(TG_OP)),  -- action
        audit_row_values.actor_id,                      -- actor_id
        COALESCE(
            audit_row_values.object_id,
            object_id
        ),                                              -- object_id
        audit_row_values.target_id,                     -- target_id
        NULL,                                           -- row_data
        NULL,                                           -- changed_fields
        'f'
    );

    IF TG_ARGV[1] IS NOT NULL THEN
        excluded_cols = TG_ARGV[1]::text[];
    END IF;

    IF (TG_OP = 'UPDATE' AND TG_LEVEL = 'ROW') THEN
        audit_row.row_data = hstore(OLD.*);
        audit_row.changed_fields =  (hstore(NEW.*) - audit_row.row_data) - excluded_cols;
        IF audit_row.changed_fields = hstore('') THEN
            -- All changed fields are ignored. Skip this update.
            RETURN NULL;
        END IF;
    ELSIF (TG_OP = 'DELETE' AND TG_LEVEL = 'ROW') THEN
        audit_row.row_data = hstore(OLD.*) - excluded_cols;
    ELSIF (TG_OP = 'INSERT' AND TG_LEVEL = 'ROW') THEN
        audit_row.row_data = hstore(NEW.*) - excluded_cols;
    ELSE
        RAISE EXCEPTION '[audit.if_modified_func] - Trigger func added as trigger for unhandled case: %, %',TG_OP, TG_LEVEL;
        RETURN NULL;
    END IF;
    INSERT INTO audit.activity VALUES (audit_row.*);
    RETURN NULL;
END;
$body$
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public;


COMMENT ON FUNCTION audit.if_modified_func() IS $body$
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
$body$;



CREATE OR REPLACE FUNCTION audit.audit_table(target_table regclass, ignored_cols text[]) RETURNS void AS $body$
DECLARE
    stm_targets text = 'INSERT OR UPDATE OR DELETE OR TRUNCATE';
    _q_txt text;
    _ignored_cols_snip text = '';
    primary_keys text[] = ARRAY[]::text[];
    primary_keys_q text;
BEGIN
    EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_row ON ' || target_table;
    EXECUTE 'DROP TRIGGER IF EXISTS audit_trigger_stm ON ' || target_table;

    primary_keys_q =
        'SELECT array_agg(pg_attribute.attname) ' ||
        'FROM pg_index, pg_class, pg_attribute WHERE ' ||
        E'pg_class.oid = \''||target_table||E'\'::regclass::oid AND '
        'indrelid = pg_class.oid AND '
        'pg_attribute.attrelid = pg_class.oid AND '
        'pg_attribute.attnum = any(pg_index.indkey) AND '
        'indisprimary';

    EXECUTE primary_keys_q INTO primary_keys;

    IF array_length(ignored_cols,1) > 0 THEN
        _ignored_cols_snip = ', ' || quote_literal(ignored_cols);
    END IF;
    _q_txt = 'CREATE TRIGGER audit_trigger_row AFTER INSERT OR UPDATE OR DELETE ON ' ||
             target_table ||
             ' FOR EACH ROW EXECUTE PROCEDURE audit.if_modified_func(' ||
             _ignored_cols_snip || ', ' ||
             quote_literal(primary_keys::text[]) ||
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
