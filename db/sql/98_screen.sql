-- Autopilot F: bulk screening table (regenerable: rebuilt by `make screen`, not backed up), shortlists (user data).
CREATE TABLE IF NOT EXISTS analytics.rh_screen (
  parcel_id bigint PRIMARY KEY, address text, suburb text, zone text, title_type text, lon double precision, lat double precision, building_count int, footprint_m2 numeric, gfa_est_m2 numeric,
  beds_base int, beds_tier text NOT NULL, beds_source text NOT NULL, retrofit_est numeric, profit_before_rent_annual numeric, walk_away_rent numeric, min_beds_minimum int, min_beds_target int, too_small boolean,
  effort_points numeric, profit_per_effort numeric, hazard_flags text, uses_placeholders boolean NOT NULL DEFAULT false, needs_input text, inputs_hash text NOT NULL, last_computed timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS rh_screen_tier ON analytics.rh_screen (beds_tier); CREATE INDEX IF NOT EXISTS rh_screen_suburb ON analytics.rh_screen (suburb); CREATE INDEX IF NOT EXISTS rh_screen_beds ON analytics.rh_screen (beds_base DESC);
CREATE INDEX IF NOT EXISTS rh_screen_geo ON analytics.rh_screen (lon, lat);
CREATE TABLE IF NOT EXISTS analytics.rh_screen_run (id bigserial PRIMARY KEY, started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz, scope text, rows_seen int NOT NULL DEFAULT 0, rows_written int NOT NULL DEFAULT 0, rows_unchanged int NOT NULL DEFAULT 0, status text NOT NULL DEFAULT 'running', note text);
CREATE TABLE IF NOT EXISTS core.user_shortlist (id bigserial PRIMARY KEY, name text NOT NULL, filters jsonb NOT NULL, weights jsonb, notes text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_shortlist_run (id bigserial PRIMARY KEY, shortlist_id bigint NOT NULL REFERENCES core.user_shortlist(id) ON DELETE CASCADE, run_at timestamptz NOT NULL DEFAULT now(), parcel_ids bigint[] NOT NULL, ranks jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS core.user_shortlist_audit (id bigserial PRIMARY KEY, shortlist_id bigint, action text NOT NULL, detail jsonb, at timestamptz NOT NULL DEFAULT now());
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT USAGE ON SCHEMA analytics TO app_rw; GRANT SELECT ON analytics.rh_screen, analytics.rh_screen_run TO app_rw; GRANT INSERT, UPDATE, DELETE ON analytics.rh_screen, analytics.rh_screen_run TO app_rw;
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.user_shortlist, core.user_shortlist_run, core.user_shortlist_audit TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA analytics TO app_rw; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON analytics.rh_screen, analytics.rh_screen_run, core.user_shortlist TO ai_readonly; END IF;
END $$;
