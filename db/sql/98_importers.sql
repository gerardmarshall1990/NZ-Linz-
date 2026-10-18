-- Autopilot H: importers for pending feeds (licensed attributes and sales, census, rest homes). User-supplied data (named user_*: backed up).
CREATE TABLE IF NOT EXISTS core.user_property_attribute (parcel_id bigint PRIMARY KEY, address_raw text, bedrooms int, bathrooms int, floor_area_m2 numeric, storeys int, build_year int, construction_type text, land_use text, source text NOT NULL, file_sha256 text NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_sale (id bigserial PRIMARY KEY, parcel_id bigint, address_raw text, sale_date date, price numeric, source text NOT NULL, file_sha256 text NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_demographic (area_name text NOT NULL, year int, population_75_plus int, source text NOT NULL, file_sha256 text NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (area_name, year));
CREATE TABLE IF NOT EXISTS core.user_rest_home (id bigserial PRIMARY KEY, name text NOT NULL, address_raw text, parcel_id bigint, beds int, lon double precision, lat double precision, source text NOT NULL, file_sha256 text NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_import_log (id bigserial PRIMARY KEY, kind text NOT NULL, file_sha256 text NOT NULL, filename text, rows int, applied int, rejected int, match_rate numeric, dry_run boolean NOT NULL, at timestamptz NOT NULL DEFAULT now());
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.user_property_attribute, core.user_sale, core.user_demographic, core.user_rest_home, core.user_import_log TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
END $$;
