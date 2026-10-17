-- Owner inputs entered in the app ("My inputs"): deal assumptions and retrofit rates. USER DATA (core.user_*): included in the user-data backup; they override the blank config files.
CREATE TABLE IF NOT EXISTS core.user_setting (key text PRIMARY KEY, value jsonb, updated_at timestamptz NOT NULL DEFAULT now(), updated_by text);
CREATE TABLE IF NOT EXISTS core.user_setting_history (id bigserial PRIMARY KEY, key text NOT NULL, old_value jsonb, new_value jsonb, changed_at timestamptz NOT NULL DEFAULT now());
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.user_setting, core.user_setting_history TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON core.user_setting, core.user_setting_history TO ai_readonly; END IF;
END $$;
