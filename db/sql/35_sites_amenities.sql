\timing on
-- Amenity distances (m, NZTM) from parcel centroid to the nearest hospital / school (LINZ NZ Facilities) and rail station (LINZ Topo50).
-- Bus stops and shops are NOT included yet (no open source reachable); see docs/DATA_SOURCES.md.
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS dist_hospital_m int, ADD COLUMN IF NOT EXISTS dist_school_m int, ADD COLUMN IF NOT EXISTS dist_rail_m int;
UPDATE core.sites s SET dist_hospital_m = (SELECT round(ST_Distance(f.geom, ST_Centroid(s.geom))) FROM raw.linz_facilities f
  WHERE f."use" = 'Hospital' ORDER BY f.geom <-> ST_Centroid(s.geom) LIMIT 1);
UPDATE core.sites s SET dist_school_m = (SELECT round(ST_Distance(f.geom, ST_Centroid(s.geom))) FROM raw.linz_facilities f
  WHERE f."use" = 'School' ORDER BY f.geom <-> ST_Centroid(s.geom) LIMIT 1);
UPDATE core.sites s SET dist_rail_m = (SELECT round(ST_Distance(f.geom, ST_Centroid(s.geom))) FROM raw.linz_rail_stations f
  ORDER BY f.geom <-> ST_Centroid(s.geom) LIMIT 1);
