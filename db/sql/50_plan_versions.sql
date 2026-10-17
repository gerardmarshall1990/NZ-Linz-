-- Plan currency (SPEC 0.8). Facts below were read from Auckland Council's own pages/layers on 2026-10-16 (see docs/PLAN_CURRENCY.md).
SET client_min_messages = warning;
CREATE SCHEMA IF NOT EXISTS analytics;
DROP TABLE IF EXISTS analytics.plan_versions CASCADE;
CREATE TABLE analytics.plan_versions (
  id serial PRIMARY KEY, council text NOT NULL, plan_name text NOT NULL, status text NOT NULL, version_label text,
  effective_date date, source_url text NOT NULL, notes text, last_verified date NOT NULL);
INSERT INTO analytics.plan_versions (council, plan_name, status, version_label, effective_date, source_url, notes, last_verified) VALUES
('Auckland Council','Auckland Unitary Plan','operative','July 2026 (fully operative)','2026-07-23',
 'https://www.aucklandcouncil.govt.nz/en/plans-policies-bylaws-reports-projects/our-plans-strategies/unitary-plan/the-auckland-unitary-plan-operative-in-part.html',
 'Council: "We made the proposed Auckland Unitary Plan fully operative on 23 July 2026." Plan text site https://unitaryplan.aucklandcouncil.govt.nz/ shows "Auckland Unitary Plan July 2026". Zone layer Unitary_Plan_Base_Zone service description: "Auckland Unitary Plan July 2026".', '2026-10-16'),
('Auckland Council','PC 78: Intensification','operative (per Council list); residential intensification status not verified','n/a',NULL,
 'https://www.aucklandcouncil.govt.nz/en/plans-policies-bylaws-reports-projects/our-plans-strategies/unitary-plan/auckland-unitary-plan-modifications/proposed-plan-changes.html',
 'Council plan-change list shows PC 78 as "Operative". PC120 map text says Metropolitan Centre Zone (H9) provisions from PC78 became operative May 2026. The operative zone text (July 2026) shows: Single House Zone permits one dwelling per site and makes more than one non-complying (H3.4.1 A3, A6); Mixed Housing Suburban and Urban and Māori Purpose permit up to three dwellings per site and make four or more restricted discretionary (H4.4.1 A3-A4, H5.4.1 A3-A4, H27.4.1 A4-A5); Terrace Housing and Apartment Buildings makes dwellings restricted discretionary (H6.4.1 A3). Which plan change introduced each of these was not determined. Zone codes 70-72 exist in the layer code list but no feature uses them.', '2026-10-16'),
('Auckland Council','PC 120: Housing Intensification and Resilience','proposed (not in force)','Notified 3 Nov 2025; partially withdrawn and amended 27 Aug 2026',NULL,
 'https://www.aucklandcouncil.govt.nz/en/plans-policies-bylaws-reports-projects/our-plans-strategies/unitary-plan/auckland-unitary-plan-modifications/proposed-plan-changes/pc-120-housing-intensification-resilience.html',
 'Council status page (read 2026-10-17): notified 3 November 2025; submissions closed 19 December 2025; summary of decisions requested 14 May 2026; PC120 withdrawn in part and proposed amendments publicly notified 27 August 2026; second submission period (no further submissions) closed 24 September 2026 5pm; hearings follow. Some PC120 rules had immediate legal effect under s86B(3) RMA from 3 November 2025 (for example Single House Zone rezoning for natural hazards). Aug 2026 information sheets say standards changes proposed in Nov 2025 still apply even where rezoning was withdrawn. Proposed zones differ from the operative zone for ~41% of joined properties. Proposed rules are stored in analytics.rules with status = proposed, plan_change_id = PC120, never merged with operative rows.','2026-10-17'),
('Auckland Council','Plan Stop (government legislation)','constraint','2025-26',NULL,
 'https://www.aucklandcouncil.govt.nz/en/plans-policies-bylaws-reports-projects/our-plans-strategies/unitary-plan/auckland-unitary-plan-modifications/proposed-plan-changes.html',
 'Proposed and draft plan changes must stop unless exempt; Council lists six exemption applications (status on that page). Whether PC120 proceeds as notified is therefore uncertain.','2026-10-16');

-- Per-site flag: does the PC120 proposal change this site's zone?
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS pc120_proposed_zone text, ADD COLUMN IF NOT EXISTS pc120_zone_differs boolean,
  ADD COLUMN IF NOT EXISTS plan_version_id int;
UPDATE core.sites SET pc120_proposed_zone = NULL, pc120_zone_differs = NULL;
UPDATE core.sites s SET pc120_proposed_zone = regexp_replace(t.zone1,'^- ',''),
  pc120_zone_differs = (regexp_replace(t.zone1,'^- ','') <> s.zone_name)
FROM raw.ac_pc120_notified t WHERE t.propertyid = split_part(s.ac_property_id,'-',1) AND t.zone1 <> '';
UPDATE core.sites SET plan_version_id = (SELECT id FROM analytics.plan_versions WHERE plan_name = 'Auckland Unitary Plan');
-- "Depends on PC120" (decision 16): true when PC120 would change the site's zone, or changes standards in the site's zone (assessed for the four main residential zones:
-- Single House 19, Mixed Housing Suburban 18, Mixed Housing Urban 60, Terrace Housing and Apartment Buildings 8). NULL = PC120 effect not assessed for this zone yet.
ALTER TABLE core.sites ADD COLUMN IF NOT EXISTS pc120_depends boolean, ADD COLUMN IF NOT EXISTS pc120_depends_reasons text[];
UPDATE core.sites SET
  pc120_depends_reasons = array_remove(ARRAY[CASE WHEN pc120_zone_differs THEN 'zone_would_change' END, CASE WHEN zone_code IN (19,18,60,8) THEN 'zone_standards_change' END,
                                             CASE WHEN zone_code NOT IN (19,18,60,8) AND coalesce(pc120_zone_differs,false) = false THEN 'not_assessed' END], NULL),
  pc120_depends = CASE WHEN pc120_zone_differs OR zone_code IN (19,18,60,8) THEN true WHEN pc120_zone_differs IS NULL AND zone_code IS NULL THEN NULL ELSE NULL END;
DROP VIEW IF EXISTS analytics.v_site_plan_status;
CREATE VIEW analytics.v_site_plan_status AS
SELECT s.parcel_id, s.zone_name, v.version_label AS operative_plan, s.pc120_proposed_zone, s.pc120_zone_differs, s.pc120_depends, s.pc120_depends_reasons,
  CASE WHEN s.pc120_depends THEN 'depends on PC120' ELSE 'PC120 effect not assessed for this zone' END AS verdict_dependency,
  CASE WHEN s.pc120_zone_differs THEN 'Operative zone shown. PC120 (proposed, not in force) would change this site''s zone and standards: verdict depends on PC120.'
       WHEN s.pc120_depends THEN 'Operative zone shown. PC120 (proposed, not in force) would change standards in this zone: verdict depends on PC120.'
       ELSE 'Operative zone shown. PC120 effect not assessed for this zone.' END AS plan_note,
  'Operative AUP July 2026 rules shown; PC120 (proposed) shown separately, never merged; numeric standards quote-matched but awaiting owner spot-check' AS density_outputs_label
FROM core.sites s JOIN analytics.plan_versions v ON v.id = s.plan_version_id;
-- narrow covering index: status counts must not scan the wide geometry table (they ran ~14 s against the agent's 15 s limit)
CREATE INDEX IF NOT EXISTS sites_plan_status_idx ON core.sites (plan_version_id, pc120_depends, pc120_zone_differs);
GRANT USAGE ON SCHEMA analytics TO ai_readonly; GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ai_readonly; GRANT SELECT ON ALL TABLES IN SCHEMA core TO ai_readonly;
