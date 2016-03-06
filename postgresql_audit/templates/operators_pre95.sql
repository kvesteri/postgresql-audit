CREATE OR REPLACE FUNCTION jsonb_subtract(
  "json" jsonb,
  "key_to_remove" TEXT
)
  RETURNS jsonb
  LANGUAGE sql
  IMMUTABLE
  STRICT
AS $$function$$
SELECT CASE WHEN "json" ? "key_to_remove" THEN COALESCE(
  (SELECT ('{' || string_agg(to_json("key")::text || ':' || "value", ',') || '}')
     FROM jsonb_each("json")
    WHERE "key" <> "key_to_remove"),
  '{}'
)::jsonb
ELSE "json"
END
$$function$$;

DROP OPERATOR IF EXISTS - (jsonb, text);
CREATE OPERATOR - (
  LEFTARG = jsonb,
  RIGHTARG = text,
  PROCEDURE = jsonb_subtract
);
