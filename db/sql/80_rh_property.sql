-- Property Record, uploads, plan calibration and plan extraction (MASTER_SPEC Part 3 sections 1-2; Part 7 step 1). Re-runnable (IF NOT EXISTS; no drops).
SET client_min_messages = warning;
CREATE TABLE IF NOT EXISTS core.rh_property (
  parcel_id integer PRIMARY KEY REFERENCES core.sites(parcel_id), created_at timestamptz NOT NULL DEFAULT now(), created_by text,
  evidence_level text CHECK (evidence_level IN ('NONE','PLANS_ON_FILE','REMOTE_SCAN','SCAN_VISIT','ENGINEER_VISIT')) DEFAULT 'NONE', notes text);
-- every fact: {value, source, confidence, updated_at, note} (Part 3 section 1.1). Unknown facts simply have no row.
CREATE TABLE IF NOT EXISTS core.rh_property_fact (
  parcel_id integer NOT NULL REFERENCES core.rh_property(parcel_id), field text NOT NULL, value jsonb NOT NULL, source text NOT NULL,
  confidence text NOT NULL CHECK (confidence IN ('ESTIMATED','DOCUMENTED','CONFIRMED')), method text, note text, updated_at timestamptz NOT NULL DEFAULT now(), updated_by text,
  PRIMARY KEY (parcel_id, field));
CREATE TABLE IF NOT EXISTS core.rh_property_fact_history (
  id bigserial PRIMARY KEY, parcel_id integer NOT NULL, field text NOT NULL, old_value jsonb, new_value jsonb, old_confidence text, new_confidence text,
  source text, note text, changed_at timestamptz NOT NULL DEFAULT now(), changed_by text);
CREATE TABLE IF NOT EXISTS core.rh_upload (
  id serial PRIMARY KEY, parcel_id integer NOT NULL REFERENCES core.rh_property(parcel_id), kind text NOT NULL CHECK (kind IN ('plan','photo','document','scan','other')),
  original_name text NOT NULL, stored_name text NOT NULL, detected_type text NOT NULL, size_bytes bigint NOT NULL, sha256 text NOT NULL,
  uploaded_at timestamptz NOT NULL DEFAULT now(), uploaded_by text, source_note text, page_count int);
CREATE INDEX IF NOT EXISTS rh_upload_parcel_idx ON core.rh_upload (parcel_id);
CREATE TABLE IF NOT EXISTS core.rh_plan_calibration (
  id serial PRIMARY KEY, upload_id int NOT NULL REFERENCES core.rh_upload(id), page int NOT NULL DEFAULT 1,
  method text NOT NULL CHECK (method IN ('dxf_units','scale_bar','stated_scale','two_point')), metres_per_unit numeric NOT NULL CHECK (metres_per_unit > 0),
  unit text NOT NULL, residual_m numeric, detail jsonb, created_at timestamptz NOT NULL DEFAULT now(), created_by text);
CREATE TABLE IF NOT EXISTS core.rh_plan_extraction (
  id serial PRIMARY KEY, upload_id int NOT NULL REFERENCES core.rh_upload(id), page int NOT NULL DEFAULT 1, level_name text,
  source text NOT NULL CHECK (source IN ('dxf','vision','manual')), status text NOT NULL DEFAULT 'extracted' CHECK (status IN ('extracted','human_confirmed')),
  calibrated boolean NOT NULL DEFAULT false, calibration_id int REFERENCES core.rh_plan_calibration(id), model jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), created_by text, confirmed_at timestamptz, confirmed_by text, superseded_by int REFERENCES core.rh_plan_extraction(id));
CREATE TABLE IF NOT EXISTS core.rh_plan_edit (
  id bigserial PRIMARY KEY, extraction_id int NOT NULL REFERENCES core.rh_plan_extraction(id), edit jsonb NOT NULL, edited_at timestamptz NOT NULL DEFAULT now(), edited_by text);
-- app role (created by scripts/create_app_role.sh): read core/analytics, write only the rh_* tables
DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
  GRANT USAGE ON SCHEMA core, analytics TO app_rw; GRANT SELECT ON ALL TABLES IN SCHEMA core, analytics TO app_rw;
  GRANT INSERT, UPDATE, DELETE ON core.rh_property, core.rh_property_fact, core.rh_property_fact_history, core.rh_upload, core.rh_plan_calibration, core.rh_plan_extraction, core.rh_plan_edit TO app_rw;
  GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw;
END IF; END $$;
GRANT SELECT ON core.rh_property, core.rh_property_fact, core.rh_upload, core.rh_plan_extraction TO ai_readonly;
