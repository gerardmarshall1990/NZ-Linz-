-- Part 7 step 2: requirement slots, layout options, compliance runs, briefs, evidence-gap statuses.
CREATE TABLE IF NOT EXISTS analytics.rh_requirements (
  id text PRIMARY KEY, topic text, check_kind text, fact text, operator text, unit text, value_num numeric, clause text, source text, source_url text, last_verified date,
  signs_off text, evidence_needed text, loaded_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS core.rh_layout_option (
  id bigserial PRIMARY KEY, parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), scenario text NOT NULL, beds int, binding_constraint text, below_target boolean,
  option jsonb NOT NULL, extraction_ids int[] NOT NULL, rules_snapshot jsonb, status text NOT NULL DEFAULT 'draft', created_at timestamptz NOT NULL DEFAULT now(), created_by text);
CREATE TABLE IF NOT EXISTS core.rh_check_run (
  id bigserial PRIMARY KEY, parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), option_id bigint REFERENCES core.rh_layout_option(id), results jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.rh_brief (
  id bigserial PRIMARY KEY, parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), option_id bigint REFERENCES core.rh_layout_option(id), kind text NOT NULL, body_md text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.rh_evidence_gap_status (
  parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), gap_key text NOT NULL, status text NOT NULL CHECK (status IN ('NEEDS_PROFESSIONAL','REQUESTED','RECEIVED','NOT_RELEVANT')), note text, updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (parcel_id, gap_key));
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT ON analytics.rh_requirements, core.rh_layout_option, core.rh_check_run, core.rh_brief, core.rh_evidence_gap_status TO app_rw;
    GRANT INSERT, UPDATE, DELETE ON core.rh_layout_option, core.rh_check_run, core.rh_brief, core.rh_evidence_gap_status TO app_rw;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN
    GRANT SELECT ON analytics.rh_requirements, core.rh_layout_option, core.rh_check_run, core.rh_brief, core.rh_evidence_gap_status TO ai_readonly;
  END IF;
END $$;
