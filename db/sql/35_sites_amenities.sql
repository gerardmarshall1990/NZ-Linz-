\timing on
-- Amenity distances (m, NZTM) from parcel centroid to the nearest hospital / school (LINZ NZ Facilities) and rail station (LINZ Topo50).
-- Bus distances are added at the end of this file (AT GTFS). Shops are not loaded yet; see docs/DATA_SOURCES.md.
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS dist_hospital_m int, ADD COLUMN IF NOT EXISTS dist_school_m int, ADD COLUMN IF NOT EXISTS dist_rail_m int;
UPDATE core.sites s SET dist_hospital_m = (SELECT round(ST_Distance(f.geom, ST_Centroid(s.geom))) FROM raw.linz_facilities f
  WHERE f."use" = 'Hospital' ORDER BY f.geom <-> ST_Centroid(s.geom) LIMIT 1);
UPDATE core.sites s SET dist_school_m = (SELECT round(ST_Distance(f.geom, ST_Centroid(s.geom))) FROM raw.linz_facilities f
  WHERE f."use" = 'School' ORDER BY f.geom <-> ST_Centroid(s.geom) LIMIT 1);
UPDATE core.sites s SET dist_rail_m = (SELECT round(ST_Distance(f.geom, ST_Centroid(s.geom))) FROM raw.linz_rail_stations f
  ORDER BY f.geom <-> ST_Centroid(s.geom) LIMIT 1);

-- Bus stops: nearest Auckland Transport stop served by a bus route (GTFS route_type 3) with at least one scheduled trip in the feed.
-- Source: AT static GTFS (raw.at_stops, scripts/ingest_at_stops.py). Shops are still not loaded.
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS dist_bus_m int;
UPDATE core.sites s SET dist_bus_m = (SELECT round(ST_Distance(f.geom, ST_Centroid(s.geom))) FROM raw.at_stops f
  WHERE f.route_types LIKE '%3%' AND f.n_trips > 0 ORDER BY f.geom <-> ST_Centroid(s.geom) LIMIT 1);
