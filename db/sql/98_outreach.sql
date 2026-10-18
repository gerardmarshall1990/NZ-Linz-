-- Autopilot F4-F7: field capture, audit log, offer letters, route plans. USER data. All features behind feature flags (config/feature_flags.yaml): off by default.
CREATE TABLE IF NOT EXISTS core.user_field_capture (id bigserial PRIMARY KEY, parcel_id bigint NOT NULL, rep_name text NOT NULL, permission_given_by text NOT NULL, permission_note text, gps jsonb, captured_at timestamptz NOT NULL,
  payload jsonb NOT NULL, status text NOT NULL DEFAULT 'pending_review' CHECK (status IN ('pending_review','confirmed','rejected')), photo_upload_ids bigint[] NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), reviewed_at timestamptz);
CREATE TABLE IF NOT EXISTS core.user_audit_log (id bigserial PRIMARY KEY, action text NOT NULL, subject_type text NOT NULL, subject_id bigint, detail jsonb, at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_offer_doc (id bigserial PRIMARY KEY, lead_id bigint, parcel_id bigint, scenario_id bigint, kind text NOT NULL CHECK (kind IN ('letter','email','one_page','terms_sheet')), version int NOT NULL, body_md text NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent_recorded')), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_route_plan (id bigserial PRIMARY KEY, name text NOT NULL, source text, stops jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.user_field_capture, core.user_audit_log, core.user_offer_doc, core.user_route_plan TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
END $$;
