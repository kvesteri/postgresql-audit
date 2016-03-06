-- http://schinckel.net/2014/09/29/adding-json%28b%29-operators-to-postgresql/
CREATE OR REPLACE FUNCTION jsonb_subtract(
  "json" jsonb,
  "keys" TEXT[]
)
  RETURNS jsonb
  LANGUAGE sql
  IMMUTABLE
  STRICT
AS $$function$$
SELECT CASE WHEN "json" ?| "keys" THEN COALESCE(
  (SELECT ('{' || string_agg(to_json("key")::text || ':' || "value", ',') || '}')
     FROM jsonb_each("json")
    WHERE "key" <> ALL ("keys")),
  '{}'
)::jsonb
ELSE "json"
END
$$function$$;

DROP OPERATOR IF EXISTS - (jsonb, text[]);
CREATE OPERATOR - (
  LEFTARG = jsonb,
  RIGHTARG = text[],
  PROCEDURE = jsonb_subtract
);

CREATE OR REPLACE FUNCTION jsonb_subtract(
  "json" jsonb,
  "remove" jsonb
)
  RETURNS jsonb
  LANGUAGE sql
  IMMUTABLE
  STRICT
AS $$function$$
SELECT COALESCE(
  (
    SELECT ('{' || string_agg(to_json("key")::text || ':' || "value", ',') || '}')
    FROM jsonb_each("json")
    WHERE NOT
      ('{' || to_json("key")::text || ':' || "value" || '}')::jsonb <@ "remove"
      -- Note: updated using code from http://8kb.co.uk/blog/2015/01/16/wanting-for-a-hstore-style-delete-operator-in-jsonb/
  ),
  '{}'
)::jsonb
$$function$$;

DROP OPERATOR IF EXISTS - (jsonb, jsonb);

CREATE OPERATOR - (
  LEFTARG = jsonb,
  RIGHTARG = jsonb,
  PROCEDURE = jsonb_subtract
);

CREATE OR REPLACE FUNCTION jsonb_merge(data jsonb, merge_data jsonb)
RETURNS jsonb
IMMUTABLE
LANGUAGE sql
AS $$$$
    SELECT ('{'||string_agg(to_json(key)||':'||value, ',')||'}')::jsonb
    FROM (
        WITH to_merge AS (
            SELECT * FROM jsonb_each(merge_data)
        )
        SELECT *
        FROM jsonb_each(data)
        WHERE key NOT IN (SELECT key FROM to_merge)
        UNION ALL
        SELECT * FROM to_merge
    ) t;
$$$$;
