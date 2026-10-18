-- Part 7 step 3 leftovers: retrofit quote calibration loop, plan request tracking. USER data (core.rh_*).
CREATE TABLE IF NOT EXISTS core.rh_quote (
  id bigserial PRIMARY KEY, line text NOT NULL, description text, source text NOT NULL, quote_date date NOT NULL, region text NOT NULL DEFAULT 'Auckland',
  quantity numeric NOT NULL CHECK (quantity > 0), unit text, amount_ex_gst numeric NOT NULL CHECK (amount_ex_gst >= 0), parcel_id bigint, option_id bigint, note text,
  voided boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.rh_rate_calibration (
  id bigserial PRIMARY KEY, line text NOT NULL, old_rate jsonb, new_rate jsonb NOT NULL, n_quotes int NOT NULL, quote_ids bigint[] NOT NULL, applied_at timestamptz NOT NULL DEFAULT now(), note text);
CREATE TABLE IF NOT EXISTS core.rh_plan_request (
  id bigserial PRIMARY KEY, parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), kind text NOT NULL CHECK (kind IN ('owner_agent','council_file')), recipient text,
  sent_on date, follow_up_on date, status text NOT NULL DEFAULT 'drafted' CHECK (status IN ('drafted','sent','received','reviewed','closed')), note text, created_at timestamptz NOT NULL DEFAULT now());
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.rh_quote, core.rh_rate_calibration, core.rh_plan_request TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON core.rh_quote, core.rh_rate_calibration, core.rh_plan_request TO ai_readonly; END IF;
END $$;
