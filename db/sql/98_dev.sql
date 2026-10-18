-- Autopilot E: development scenarios, manual site services, resource consent packs. USER data (named user_* so the backup includes them).
CREATE TABLE IF NOT EXISTS core.user_dev_run (id bigserial PRIMARY KEY, parcel_id bigint NOT NULL, inputs jsonb NOT NULL, result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), superseded_by bigint);
CREATE INDEX IF NOT EXISTS user_dev_run_parcel ON core.user_dev_run (parcel_id, id);
CREATE TABLE IF NOT EXISTS core.user_site_services (parcel_id bigint PRIMARY KEY, data jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_rc_pack (id bigserial PRIMARY KEY, run_id bigint NOT NULL REFERENCES core.user_dev_run(id), version int NOT NULL, status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','ready_to_lodge','superseded')),
  checklist_version text NOT NULL, fields jsonb NOT NULL DEFAULT '{}'::jsonb, uploads jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_maori_note (parcel_id bigint PRIMARY KEY, data jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now());
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.user_dev_run, core.user_site_services, core.user_rc_pack, core.user_maori_note TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON core.user_dev_run, core.user_site_services, core.user_rc_pack, core.user_maori_note TO ai_readonly; END IF;
END $$;
-- Map layers: read-only access to the Council zone and overlay layers for the app role (these are public open data, not user data).
DO $$ DECLARE t text; BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT USAGE ON SCHEMA raw TO app_rw;
    FOR t IN SELECT table_name FROM information_schema.tables WHERE table_schema='raw' AND (table_name = 'ac_zone' OR table_name = 'ac_precinct' OR table_name LIKE 'ac\_ov\_%' OR table_name LIKE 'ac\_hz\_%') LOOP
      EXECUTE format('GRANT SELECT ON raw.%I TO app_rw', t); END LOOP;
  END IF;
END $$;
