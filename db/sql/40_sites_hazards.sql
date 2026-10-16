\timing on
SET client_min_messages = warning;
-- Flood: Auckland Council flood plains / flood prone areas / flood sensitive areas. Share = % of parcel covered (union per parcel).
ALTER TABLE core.sites
  ADD COLUMN IF NOT EXISTS flood_plain boolean NOT NULL DEFAULT false, ADD COLUMN IF NOT EXISTS flood_prone boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS flood_sensitive boolean NOT NULL DEFAULT false, ADD COLUMN IF NOT EXISTS flood_cover_pct numeric(5,1),
  ADD COLUMN IF NOT EXISTS coastal_inundation boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS landslide_susceptibility int, ADD COLUMN IF NOT EXISTS liquefaction_vulnerability text,
  ADD COLUMN IF NOT EXISTS tsunami_zone text, ADD COLUMN IF NOT EXISTS hazard_flags text[] NOT NULL DEFAULT '{}';
UPDATE core.sites SET flood_plain=false, flood_prone=false, flood_sensitive=false, flood_cover_pct=NULL, coastal_inundation=false,
  landslide_susceptibility=NULL, liquefaction_vulnerability=NULL, tsunami_zone=NULL;

UPDATE core.sites s SET flood_plain = true FROM (SELECT DISTINCT s2.parcel_id FROM core.sites s2
  JOIN raw.sub_ac_hz_flood_plains o ON o.geom && s2.geom AND ST_Relate(o.geom, s2.geom, 'T********')) x WHERE x.parcel_id = s.parcel_id;
UPDATE core.sites s SET flood_prone = true FROM (SELECT DISTINCT s2.parcel_id FROM core.sites s2
  JOIN raw.sub_ac_hz_flood_prone o ON o.geom && s2.geom AND ST_Relate(o.geom, s2.geom, 'T********')) x WHERE x.parcel_id = s.parcel_id;
UPDATE core.sites s SET flood_sensitive = true FROM (SELECT DISTINCT s2.parcel_id FROM core.sites s2
  JOIN raw.sub_ac_hz_flood_sensitive o ON o.geom && s2.geom AND ST_Relate(o.geom, s2.geom, 'T********')) x WHERE x.parcel_id = s.parcel_id;
UPDATE core.sites s SET coastal_inundation = true FROM (SELECT DISTINCT s2.parcel_id FROM core.sites s2
  JOIN raw.sub_ac_hz_coastal_inundation o ON o.geom && s2.geom AND ST_Relate(o.geom, s2.geom, 'T********')) x WHERE x.parcel_id = s.parcel_id;

-- % of parcel covered by any flood layer (only for flagged parcels).
UPDATE core.sites s SET flood_cover_pct = LEAST(100, round((100 * x.a / NULLIF(s.area_m2,0))::numeric, 1)) FROM (
  SELECT s2.parcel_id, ST_Area(ST_Intersection(s2.geom, ST_UnaryUnion(ST_Collect(o.geom)), 0.01)) AS a
  FROM core.sites s2
  JOIN (SELECT geom FROM raw.sub_ac_hz_flood_plains UNION ALL SELECT geom FROM raw.sub_ac_hz_flood_prone UNION ALL SELECT geom FROM raw.sub_ac_hz_flood_sensitive) o
    ON o.geom && s2.geom AND ST_Intersects(o.geom, s2.geom)
  WHERE s2.flood_plain OR s2.flood_prone OR s2.flood_sensitive GROUP BY s2.parcel_id, s2.geom) x
WHERE x.parcel_id = s.parcel_id;

-- Landslide: max Auckland Council large-scale susceptibility code (1 Very Low .. 5 Very High). Regional model: a coarse screen only.
UPDATE core.sites s SET landslide_susceptibility = x.m FROM (
  SELECT s2.parcel_id, max(o.susceptibilitycode::int) m FROM core.sites s2
  JOIN raw.sub_ac_hz_landslide_large o ON o.geom && s2.geom AND ST_Relate(o.geom, s2.geom, 'T********')
  GROUP BY 1) x WHERE x.parcel_id = s.parcel_id;

-- Liquefaction: only assessed areas are covered; NULL means not assessed (not "safe").
UPDATE core.sites s SET liquefaction_vulnerability = x.v FROM (
  SELECT s2.parcel_id, (array_agg(o.vulnerability ORDER BY CASE o.vulnerability WHEN 'Possible' THEN 1 WHEN 'Undetermined' THEN 2
     WHEN 'Low' THEN 3 WHEN 'Unlikely' THEN 4 ELSE 5 END))[1] v
  FROM core.sites s2 JOIN raw.sub_ac_hz_liquefaction o ON o.geom && s2.geom AND ST_Relate(o.geom, s2.geom, 'T********')
  GROUP BY 1) x WHERE x.parcel_id = s.parcel_id;
UPDATE core.sites s SET tsunami_zone = x.z FROM (
  SELECT s2.parcel_id, min(o.zonetype) z FROM core.sites s2 JOIN raw.sub_ac_hz_tsunami o ON o.geom && s2.geom AND ST_Relate(o.geom, s2.geom, 'T********')
  GROUP BY 1) x WHERE x.parcel_id = s.parcel_id;

UPDATE core.sites SET hazard_flags = array_remove(ARRAY[
  CASE WHEN flood_plain THEN 'flood_plain' END, CASE WHEN flood_prone THEN 'flood_prone' END,
  CASE WHEN flood_sensitive THEN 'flood_sensitive' END, CASE WHEN coastal_inundation THEN 'coastal_inundation' END,
  CASE WHEN landslide_susceptibility >= 4 THEN 'landslide_high' END,
  CASE WHEN liquefaction_vulnerability = 'Possible' THEN 'liquefaction_possible' END,
  CASE WHEN tsunami_zone IS NOT NULL THEN 'tsunami_' || lower(tsunami_zone) END], NULL);
CREATE INDEX IF NOT EXISTS sites_hazard_gin ON core.sites USING gin (hazard_flags);
CREATE INDEX IF NOT EXISTS sites_overlay_gin ON core.sites USING gin (overlays);
CREATE INDEX IF NOT EXISTS sites_area_idx ON core.sites (area_m2);
GRANT USAGE ON SCHEMA core TO ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA core TO ai_readonly;
ANALYZE core.sites;
