\timing on
-- Repair raw overlay geometries (polygon layers).
SET client_min_messages = warning;
DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT table_name FROM information_schema.tables WHERE table_schema='raw' AND (table_name LIKE 'ac\_ov\_%' OR table_name LIKE 'ac\_hz\_%') LOOP
    EXECUTE format($q$UPDATE raw.%I SET geom = ST_Multi(ST_CollectionExtract(ST_MakeValid(geom),3))
                      WHERE GeometryType(geom) LIKE '%%POLYGON' AND NOT ST_IsValid(geom)$q$, t);
  END LOOP; END $$;


-- Subdivided copies (<=256 vertices/piece) of overlay + hazard layers: makes spatial tests fast on huge polygons.
CREATE OR REPLACE FUNCTION raw.make_sub(src text, cols text DEFAULT '') RETURNS void LANGUAGE plpgsql AS $f$
BEGIN
  EXECUTE format('DROP TABLE IF EXISTS raw.sub_%I', src);
  -- ST_Subdivide drops points, so point rows are copied through unchanged.
  EXECUTE format('CREATE TABLE raw.sub_%1$I AS SELECT ST_Subdivide(geom,256) AS geom%2$s FROM raw.%1$I WHERE GeometryType(geom) NOT LIKE ''%%POINT'' UNION ALL SELECT geom%2$s FROM raw.%1$I WHERE GeometryType(geom) LIKE ''%%POINT''', src, CASE WHEN cols='' THEN '' ELSE ', '||cols END);
  EXECUTE format('CREATE INDEX ON raw.sub_%I USING gist (geom)', src);
  EXECUTE format('ANALYZE raw.sub_%I', src);
END $f$;
DO $$ DECLARE t text; BEGIN
  FOR t IN SELECT table_name FROM information_schema.tables WHERE table_schema='raw' AND (table_name LIKE 'ac\_ov\_%' OR table_name LIKE 'ac\_hz\_%') LOOP
    PERFORM raw.make_sub(t, CASE t WHEN 'ac_hz_landslide_large' THEN 'susceptibilitycode' WHEN 'ac_hz_liquefaction' THEN 'vulnerability'
                             WHEN 'ac_hz_tsunami' THEN 'zonetype' ELSE '' END);
    RAISE WARNING 'subdivided %', t;
  END LOOP; END $$;

-- Precincts: any precinct covering >=5% of the parcel.
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS precincts text[] NOT NULL DEFAULT '{}';
UPDATE core.sites s SET precincts = x.p FROM (
  SELECT s2.parcel_id, array_agg(DISTINCT o.precinct) AS p
  FROM core.sites s2 JOIN raw.ac_precinct o ON o.geom && s2.geom AND ST_Intersects(o.geom, s2.geom)
  WHERE ST_Area(ST_Intersection(o.geom, s2.geom, 0.01)) >= 0.05 * s2.area_m2 GROUP BY 1) x
WHERE x.parcel_id = s.parcel_id;

-- Overlays: parcel interior intersects the overlay interior (edge-touching excluded).
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS overlays text[] NOT NULL DEFAULT '{}';
UPDATE core.sites SET overlays = '{}';
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('ac_ov_heritage_place','Historic Heritage Place'),('ac_ov_heritage_extent','Historic Heritage Extent of Place'),
    ('ac_ov_sea','Significant Ecological Area'),('ac_ov_special_character','Special Character Area'),
    ('ac_ov_volcanic_regional','Regionally Significant Volcanic Viewshaft'),('ac_ov_volcanic_local','Locally Significant Volcanic Viewshaft'),
    ('ac_ov_onl','Outstanding Natural Landscape'),('ac_ov_onf','Outstanding Natural Feature'),
    ('ac_ov_onc','Outstanding Natural Character'),('ac_ov_hnc','High Natural Character'),
    ('ac_ov_ridgeline','Ridgeline Protection'),('ac_ov_national_grid','National Grid Corridor'),
    ('ac_ov_notable_trees','Notable Tree'),('ac_ov_notable_tree_groups','Notable Tree Group'),
    ('ac_ov_aircraft_noise','Aircraft Noise'),('ac_ov_mana_whenua','Site of Significance to Mana Whenua'),
    ('ac_ov_waitakere','Waitakere Ranges Heritage Area'),('ac_ov_quarry_buffer','Quarry Buffer'),
    ('ac_ov_stream_mgmt','Natural Stream Management Area')) v(t,label) LOOP
    EXECUTE format($q$UPDATE core.sites s SET overlays = array_append(overlays, %L) WHERE EXISTS (
      SELECT 1 FROM raw.sub_%I o WHERE o.geom && s.geom AND ST_Relate(o.geom, s.geom, 'T********'))$q$, r.label, r.t);
    RAISE WARNING 'overlay done: %', r.label;
  END LOOP; END $$;

-- Buildings: assigned to the parcel containing the footprint's point-on-surface.
DROP TABLE IF EXISTS core.building_site;
CREATE TABLE core.building_site AS
SELECT b.building_id, s.parcel_id, ST_Area(b.geom)::numeric(12,1) AS footprint_m2, b."use" AS use, b.geom
FROM raw.linz_buildings b JOIN core.sites s ON ST_Intersects(s.geom, ST_PointOnSurface(b.geom));
CREATE INDEX ON core.building_site (parcel_id);
CREATE INDEX building_site_gix ON core.building_site USING gist (geom);
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS building_count int, ADD COLUMN IF NOT EXISTS total_footprint_m2 numeric(12,1),
  ADD COLUMN IF NOT EXISTS largest_footprint_m2 numeric(12,1), ADD COLUMN IF NOT EXISTS site_coverage_pct numeric(6,1);
UPDATE core.sites s SET building_count = 0, total_footprint_m2 = 0, largest_footprint_m2 = 0, site_coverage_pct = 0;
UPDATE core.sites s SET building_count = x.n, total_footprint_m2 = x.t, largest_footprint_m2 = x.m,
  site_coverage_pct = LEAST(100, round(100 * x.t / NULLIF(s.area_m2,0), 1))
FROM (SELECT parcel_id, count(*) n, sum(footprint_m2) t, max(footprint_m2) m FROM core.building_site GROUP BY 1) x
WHERE x.parcel_id = s.parcel_id;

-- Addresses: contained points; keep a representative address (lowest number, no unit preferred).
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS address text, ADD COLUMN IF NOT EXISTS address_count int NOT NULL DEFAULT 0, ADD COLUMN IF NOT EXISTS suburb text;
UPDATE core.sites s SET address = x.full_address, suburb = x.suburb_locality, address_count = x.n FROM (
  SELECT DISTINCT ON (s2.parcel_id) s2.parcel_id, a.full_address, a.suburb_locality,
         count(*) OVER (PARTITION BY s2.parcel_id) n
  FROM core.sites s2 JOIN raw.linz_addresses a ON ST_Intersects(s2.geom, a.geom)
  ORDER BY s2.parcel_id, (a.unit IS NOT NULL), a.address_number, a.address_id) x
WHERE x.parcel_id = s.parcel_id;

-- Titles: first title number on the parcel -> LINZ title type / estate.
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS title_no text, ADD COLUMN IF NOT EXISTS title_type text, ADD COLUMN IF NOT EXISTS estate_description text;
UPDATE core.sites s SET title_no = t.title_no, title_type = t.type, estate_description = t.estate_description
FROM raw.linz_titles t WHERE s.titles_raw IS NOT NULL AND t.title_no = split_part(s.titles_raw, ',', 1);

-- Council property record (no values are published; keys only).
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS ac_property_id text, ADD COLUMN IF NOT EXISTS ac_valuation_ref text;
-- Several Primary property polygons can contain a parcel's point (overlaps): pick deterministically (smallest polygon, then lowest id). An unordered UPDATE...FROM picked an arbitrary row,
-- so two builds could disagree (found by the slice bootstrap comparison).
UPDATE core.sites s SET ac_property_id = x.pid, ac_valuation_ref = x.vref
FROM (SELECT DISTINCT ON (s2.parcel_id) s2.parcel_id, p."propertyid" AS pid, p."valuationref" AS vref
      FROM core.sites s2 JOIN raw.ac_property p ON ST_Intersects(p.geom, ST_PointOnSurface(s2.geom)) AND p."addresstype" = 'Primary'
      ORDER BY s2.parcel_id, ST_Area(p.geom), p."propertyid") x
WHERE s.parcel_id = x.parcel_id;

-- Māori land indicators (partial: LINZ parcel intent + Māori Purpose zone). Entity link comes in Stage 4.
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS maori_land_linz boolean, ADD COLUMN IF NOT EXISTS zone_maori_purpose boolean;
UPDATE core.sites SET maori_land_linz = (parcel_intent = 'Maori'), zone_maori_purpose = (zone_code = 52);

-- Overlay lists in a fixed order (layers are appended in whatever order they were run).
UPDATE core.sites SET overlays = ARRAY(SELECT DISTINCT o FROM unnest(overlays) o ORDER BY o) WHERE overlays IS NOT NULL AND array_length(overlays,1) > 1;
