-- http://schinckel.net/2014/09/29/adding-json%28b%29-operators-to-postgresql/
CREATE OR REPLACE FUNCTION jsonb_subtract(
  "json" jsonb,
  "keys" TEXT[]
)
  RETURNS jsonb
  LANGUAGE SQL
  IMMUTABLE
  STRICT
AS $$
SELECT CASE WHEN "json" ?| "keys" THEN COALESCE(
  (SELECT ('{' || string_agg(to_json("key")::text || ':' || "value", ',') || '}')
     FROM jsonb_each("json")
    WHERE "key" <> ALL ("keys")),
  '{}'
)::jsonb
ELSE "json"
END
$$;

DROP OPERATOR IF EXISTS - (jsonb, text[]);
CREATE OPERATOR - (
  LEFTARG = jsonb,
  RIGHTARG = text[],
  PROCEDURE = jsonb_subtract
);

-- http://coussej.github.io/2016/05/24/A-Minus-Operator-For-PostgreSQLs-JSONB/
CREATE OR REPLACE FUNCTION jsonb_subtract(arg1 jsonb, arg2 jsonb)
RETURNS jsonb AS $$
SELECT
  COALESCE(json_object_agg(key, value), '{}')::jsonb
FROM
  jsonb_each(arg1)
WHERE
  (arg1 -> key) <> (arg2 -> key) OR (arg2 -> key) IS NULL
$$ LANGUAGE SQL;

DROP OPERATOR IF EXISTS - (jsonb, jsonb);

CREATE OPERATOR - (
  LEFTARG = jsonb,
  RIGHTARG = jsonb,
  PROCEDURE = jsonb_subtract
);
