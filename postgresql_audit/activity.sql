
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
    id BIGSERIAL primary key,
    schema_name TEXT,
    table_name TEXT,
    relid OID,
    issued_at TIMESTAMP WITH TIME ZONE,
    transaction_id BIGINT,
    client_addr INET,
    client_port INTEGER,
    verb TEXT,
    actor_id TEXT,
    object_id TEXT,
    target_id TEXT,
    row_data HSTORE,
    changed_fields HSTORE
);

REVOKE ALL ON audit.activity FROM public;

COMMENT ON TABLE audit.activity IS 'History of auditable actions on audited tables, from audit.create_activity()';
COMMENT ON COLUMN audit.activity.id IS 'Unique identifier for each auditable event';
COMMENT ON COLUMN audit.activity.schema_name IS 'Database schema audited table for this event is in';
COMMENT ON COLUMN audit.activity.table_name IS 'Non-schema-qualified table name of table event occured in';
COMMENT ON COLUMN audit.activity.relid IS 'Table OID. Changes with drop/create. Get with ''tablename''::regclass';
COMMENT ON COLUMN audit.activity.issued_at IS 'Statement start timestamp for tx in which audited event occurred';
COMMENT ON COLUMN audit.activity.transaction_id IS 'Identifier of transaction that made the change. May wrap, but unique paired with action_tstamp_tx.';
COMMENT ON COLUMN audit.activity.client_addr IS 'IP address of client that issued query. Null for unix domain socket.';
COMMENT ON COLUMN audit.activity.client_port IS 'Remote peer IP port address of client that issued query. Undefined for unix socket.';
COMMENT ON COLUMN audit.activity.verb IS 'Action type, normally insert, update, delete or truncate';
COMMENT ON COLUMN audit.activity.row_data IS 'Record value. Null for statement-level trigger. For INSERT this is the new tuple. For DELETE and UPDATE it is the old tuple.';
COMMENT ON COLUMN audit.activity.changed_fields IS 'New values of fields changed by UPDATE. Null except for row-level UPDATE events.';
