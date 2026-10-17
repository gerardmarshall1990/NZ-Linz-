# Plan currency check (2026-10-16)

## Verdict
**The loaded zone layer is current: it is the operative Auckland Unitary Plan, not out of date.** What is changing is a proposal (PC120) that is not in force.

| Item | Finding | Source |
|---|---|---|
| Operative plan | "We made the proposed Auckland Unitary Plan fully operative on 23 July 2026." Plan text site is titled "Auckland Unitary Plan July 2026". | aucklandcouncil.govt.nz (the-auckland-unitary-plan-operative-in-part.html), unitaryplan.aucklandcouncil.govt.nz |
| Zone layer we loaded | Service `Unitary_Plan_Base_Zone`, description "Auckland Unitary Plan July 2026", data last edited 2026-10-16, 139,490 features, VERSIONSTATUS 139,474 Operative / 12 Proposed / 4 Subject to Appeal | ArcGIS service metadata |
| 20-parcel sample | 20/20 of our `core.sites` zones equal Council's live base-zone service at the parcel point | live query, 10 where PC120 proposes a different zone, 10 where it does not |
| PC 120 Housing Intensification and Resilience | **Proposed, not in force.** Submissions closed 24 Sep 2026; amendments proposed Aug 2026 after April 2026 RMA changes. Proposed zones differ from operative for **213,218 of 524,524 sites with a PC120 record (40.6%)**; the largest change is 110,790 Mixed Housing Suburban to Mixed Housing Urban. | Council PC120 page; layers `RPC_PROD_Plan_Change_Property_Summary`, `PC120Revised_PROD_PropertySummary` |
| PC 78 Intensification | Council list shows PC78 as "Operative". Layer text: Metropolitan Centre Zone (H9) provisions from PC78 became operative May 2026. Which plan change introduced each residential rule is **not determined**; the operative rule text itself is loaded and cited in `analytics.rules`. The operative zone text (July 2026) already permits up to three dwellings per site in Mixed Housing Suburban/Urban and Māori Purpose zones (see docs/RULES.md); which plan change introduced it was not determined. Zone codes 70-72 exist in the layer's code list but no feature uses them. | Council proposed-plan-changes page; layers |
| Plan Stop | Proposed/draft plan changes must stop unless exempt (six exemption applications listed); PC120's fate is therefore uncertain. | Council page |

## What the tool does about it
- `analytics.plan_versions` holds the four rows above with source URLs and `last_verified`.
- `core.sites.pc120_proposed_zone` and `pc120_zone_differs` flag every site whose zone would change under PC120 (35,004 sites have no PC120 record: excluded areas or unmatched).
- `analytics.v_site_plan_status` returns a per-site note. Rule text (operative, July 2026) is now loaded (Stage 3). Density-dependent outputs are labelled "extracted standards awaiting owner spot-check" until you confirm `docs/RULES_STAGE3_GATE.md`. PC120 is never applied.
- Not covered: qualifying matters / overlays proposed by PC120, height variation controls, and PC78 centre height changes are not in `core.sites`.
