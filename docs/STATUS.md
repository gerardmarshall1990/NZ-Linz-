# Status (2026-10-17)

## Done
- Stage 1 LINZ ingest, Stage 2 `core.sites` (559,528 Auckland parcels with zone, overlays, hazards, buildings, amenity distances incl. AT bus stops): passed.
- Plan currency: zone layer = operative AUP (fully operative 23 Jul 2026). PC120 is proposed and differs from the operative zone for 40.6% of sites; flagged per site. See docs/PLAN_CURRENCY.md.
- Stage 3 rules corpus: 99 official AUP chapter PDFs -> 2,166 citable chunks, 1,328 structured rules (156 numeric standards each verified against a verbatim quote, 965 activity-table rows, 207 text-only), `analytics.search_rules`, 63 passing tests. Gate table for your spot-check: docs/RULES_STAGE3_GATE.md.
- Manual sources folder + loader (docs/sources_manual/) ready for HealthCERT, Ngā Paerewa, council forms, TPK files.

## Waiting on you
1. Spot-check docs/RULES_STAGE3_GATE.md (15 standards x 4 zones against the Council plan) and tell me anything wrong.
2. SPEC_RESTHOME_TOOL.md was never uploaded (only CLAUDE.md and SPEC_SITE_FLOW.md): please attach it.
3. HealthCERT list / Ngā Paerewa PDF into docs/sources_manual/ (see README there) or attach them in chat.
4. download.geofabrik.de is still blocked (OSM motel tags skipped as instructed); Watercare licence decision (SPEC 0.9); 10+ known-outcome parcels for the regression suite.

## Next
Stage 4: Māori land cross-check (LINZ 'Maori' parcels vs Te Puni Kōkiri / Māori Land Court public data, report the gap) and the rest home layer from the manual HealthCERT file; then Stage 5 agent, Stage 6 calculators; slope (candidate parcels only) before the layout engine.
