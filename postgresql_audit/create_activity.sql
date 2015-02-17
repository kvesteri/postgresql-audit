CREATE OR REPLACE FUNCTION audit.create_activity() RETURNS TRIGGER AS $body$
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
        RAISE EXCEPTION 'audit.create_activity() may only run as an AFTER trigger';
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
        nextval('audit.activity_id_seq'),               -- id
        TG_TABLE_SCHEMA::text,                          -- schema_name
        TG_TABLE_NAME::text,                            -- table_name
        TG_RELID,                                       -- relation OID for much quicker searches
        COALESCE(
            audit_row_values.issued_at,
            statement_timestamp()
        ),                                              -- issued_at
        COALESCE(
            audit_row_values.transaction_id,
            txid_current()
        ),                                              -- transaction ID
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
        audit_row.row_data = hstore(OLD.*) - excluded_cols;
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
        RAISE EXCEPTION '[audit.create_activity] - Trigger func added as trigger for unhandled case: %, %', TG_OP, TG_LEVEL;
        RETURN NULL;
    END IF;
    INSERT INTO audit.activity VALUES (audit_row.*);
    RETURN NULL;
END;
$body$
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public;


COMMENT ON FUNCTION audit.create_activity() IS $body$
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
