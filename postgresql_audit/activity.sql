
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
    old_data JSONB,
    changed_data JSONB
);

REVOKE ALL ON audit.activity FROM public;
