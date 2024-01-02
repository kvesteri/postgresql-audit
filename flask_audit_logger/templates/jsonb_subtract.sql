CREATE OR REPLACE FUNCTION ${schema_prefix}jsonb_subtract(arg1 jsonb, arg2 jsonb)
RETURNS jsonb AS $$
SELECT
  COALESCE(json_object_agg(key, value), '{}')::jsonb
FROM
  jsonb_each(arg1)
WHERE
  (arg1 -> key) <> (arg2 -> key) OR (arg2 -> key) IS NULL
$$ LANGUAGE SQL;
