-- Listings (MASTER_SPEC Part 4 section 2.2, Part 6). User data: entered or imported by the owner, so named core.user_* and included in the user-data backup.
CREATE TABLE IF NOT EXISTS core.user_listing (
  id bigserial PRIMARY KEY, source text NOT NULL, source_id text NOT NULL, listing_type text NOT NULL CHECK (listing_type IN ('rent','sale')),
  raw_address text NOT NULL, address_id integer, parcel_id bigint, match_confidence text NOT NULL DEFAULT 'none' CHECK (match_confidence IN ('high','medium','low','none')), match_method text, match_reviewed boolean NOT NULL DEFAULT false,
  suburb text, rent_per_week numeric, price numeric, bedrooms int, bathrooms int, property_type text, floor_area_m2 numeric, parking int, available_from date, listed_date date,
  first_seen date NOT NULL DEFAULT current_date, last_seen date NOT NULL DEFAULT current_date, status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','removed')),
  agent_name text, agent_business_contact text, url text, description_hash text, has_floor_plan boolean, has_photos boolean, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, source_id));
CREATE TABLE IF NOT EXISTS core.user_listing_history (
  id bigserial PRIMARY KEY, listing_id bigint NOT NULL REFERENCES core.user_listing(id) ON DELETE CASCADE, changed_on date NOT NULL DEFAULT current_date, field text NOT NULL, old_value text, new_value text);
CREATE INDEX IF NOT EXISTS user_listing_parcel_idx ON core.user_listing (parcel_id);
-- address lookup used by the matcher (rebuilt with the data by make app-db)
CREATE INDEX IF NOT EXISTS linz_addr_lookup_idx ON raw.linz_addresses (address_number, lower(full_road_name_ascii));
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT ON core.user_listing, core.user_listing_history TO app_rw; GRANT INSERT, UPDATE, DELETE ON core.user_listing, core.user_listing_history TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw;
    GRANT SELECT ON raw.linz_addresses TO app_rw; GRANT USAGE ON SCHEMA raw TO app_rw;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON core.user_listing, core.user_listing_history TO ai_readonly; END IF;
END $$;
