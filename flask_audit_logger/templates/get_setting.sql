CREATE OR REPLACE FUNCTION ${schema_prefix}get_setting(setting text, fallback text)
RETURNS text AS $$
    SELECT coalesce(
        nullif(current_setting(setting, 't'), ''),
        fallback
    );
$$ LANGUAGE SQL;
