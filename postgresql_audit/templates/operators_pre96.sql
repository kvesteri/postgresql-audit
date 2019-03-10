CREATE OR REPLACE FUNCTION current_setting (setting_name TEXT, missing_ok BOOL)
RETURNS TEXT AS $$
BEGIN
    BEGIN
        RETURN current_setting(setting_name);
    EXCEPTION WHEN OTHERS THEN
        IF (missing_ok) THEN
            RETURN NULL;
        ELSE
            RAISE;
        END IF;
    END;
END;
$$ LANGUAGE 'plpgsql';
