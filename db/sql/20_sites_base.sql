\timing on
-- Repair invalid geometries in raw layers (idempotent).
UPDATE raw.linz_parcels   SET geom = ST_Multi(ST_CollectionExtract(ST_MakeValid(geom),3)) WHERE NOT ST_IsValid(geom);
UPDATE raw.ac_zone        SET geom = ST_Multi(ST_CollectionExtract(ST_MakeValid(geom),3)) WHERE NOT ST_IsValid(geom);
UPDATE raw.ac_precinct    SET geom = ST_Multi(ST_CollectionExtract(ST_MakeValid(geom),3)) WHERE NOT ST_IsValid(geom);
UPDATE raw.ac_boundary_local_board SET geom = ST_Multi(ST_CollectionExtract(ST_MakeValid(geom),3)) WHERE NOT ST_IsValid(geom);

DROP TABLE IF EXISTS core.auckland_boundary;
CREATE TABLE core.auckland_boundary AS
  SELECT ST_Multi(ST_Union(geom))::geometry(MultiPolygon,2193) AS geom FROM raw.ac_boundary_local_board;
CREATE INDEX ON core.auckland_boundary USING gist (geom);

DROP TABLE IF EXISTS core.sites CASCADE;
CREATE TABLE core.sites AS
SELECT p.id AS parcel_id, p.appellation, p.parcel_intent, p.land_district, p.titles AS titles_raw,
       ST_Multi(p.geom)::geometry(MultiPolygon,2193) AS geom,
       ST_Area(p.geom)::numeric(14,1) AS area_m2,
       (p.parcel_intent LIKE 'Vesting on Deposit%') AS is_reserve
FROM raw.linz_parcels p
JOIN core.auckland_boundary b ON ST_Intersects(b.geom, ST_PointOnSurface(p.geom))
WHERE p.parcel_intent NOT IN ('Road','Hydro','Railway','Erosion','Legalisation','Streambed','Accretion','Reclamation Area',
      'Common Marine and Coastal Area (Sec 237A(1)(b) RM Act)','Marginal Strip - Movable','Marginal Strip - Fixed',
      'Licence/Permit','UNKN','Vesting on Deposit for Road');
ALTER TABLE core.sites ADD PRIMARY KEY (parcel_id);
CREATE INDEX sites_geom_gix ON core.sites USING gist (geom);
ANALYZE core.sites;

-- Dominant (largest-overlap) base zone per parcel.
ALTER TABLE core.sites ADD COLUMN zone_code int, ADD COLUMN zone_name text, ADD COLUMN zone_group text,
  ADD COLUMN zone_share numeric(5,3), ADD COLUMN zone_count int;
WITH z AS (
  SELECT s.parcel_id, o.zone::int AS zone_code, ST_Area(ST_Intersection(s.geom, o.geom, 0.01)) AS a,
         row_number() OVER (PARTITION BY s.parcel_id ORDER BY ST_Area(ST_Intersection(s.geom, o.geom, 0.01)) DESC) AS rn,
         count(*) OVER (PARTITION BY s.parcel_id) AS n
  FROM core.sites s JOIN raw.ac_zone o ON o.geom && s.geom AND ST_Intersects(o.geom, s.geom)
)
UPDATE core.sites s SET zone_code = z.zone_code, zone_share = LEAST(1, z.a / NULLIF(s.area_m2,0)), zone_count = z.n
FROM z WHERE z.parcel_id = s.parcel_id AND z.rn = 1;
UPDATE core.sites s SET zone_name = l.zone_name FROM core.zone_lookup l WHERE l.code = s.zone_code;
UPDATE core.sites s SET zone_group = g.group_name
  FROM (SELECT DISTINCT ON (zone::int) zone::int AS zc, groupzone::int AS gc FROM raw.ac_zone ORDER BY zone::int, ogc_fid) x
  JOIN core.zone_group_lookup g ON g.code = x.gc WHERE x.zc = s.zone_code;
CREATE INDEX sites_zone_idx ON core.sites (zone_code);
