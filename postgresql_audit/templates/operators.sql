-- http://coussej.github.io/2016/05/24/A-Minus-Operator-For-PostgreSQLs-JSONB/
DROP FUNCTION IF EXISTS jsonb_subtract(jsonb,jsonb) CASCADE;
CREATE FUNCTION jsonb_subtract(arg1 jsonb, arg2 jsonb)
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


DROP FUNCTION IF EXISTS get_setting(text, text) CASCADE;
CREATE FUNCTION get_setting(setting text, default_value text)
RETURNS text AS $$
    SELECT coalesce(
        nullif(current_setting(setting, 't'), ''),
        default_value
    );
$$ LANGUAGE SQL;
