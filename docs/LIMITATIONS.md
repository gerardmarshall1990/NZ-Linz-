# Limitations (running list)

- Zoning and overlay results are screens from Auckland Council open data, not planning advice. Confirm with a council planner.
- The base zone layer is the Operative Unitary Plan as published in the layer; plan changes (e.g. PC78 / MDRS intensification) may not be reflected. Verify per site.
- No rating values: Auckland Council does not openly publish capital/land/improvement values. Feasibility must use user-entered land cost.
- No slope yet; no bus stop / shop distances; wastewater/water network not loaded.
- Landslide field is a coarse regional model (codes 1-5). Liquefaction category 'Undetermined' covers about 161k sites.
- LINZ titles carry no owner names. Māori land trusts/incorporations must come from Te Puni Kōkiri / Māori Land Court public sources (Stage 4).
- Buildings have no age or storey data in the LINZ outline layer.

## Rules corpus (added 2026-10-17)
- Rule text is the operative AUP (July 2026). Several activity rows carry "legal effect under s86B(3)(f) RMA" / "PC 120 (see Modifications)" annotations: PC120 provisions with immediate legal effect may override operative text. The tool records these in `notes`; a planner must confirm. PC120 is not applied.
- The PDFs' text layers are incomplete in places; OCR repairs most gaps but OCR can misread characters (for example m2 shown as m?). Every numeric rule is checked against a verbatim quote, but non-numeric text-only rules rely on extraction quality: read the plan text.
- H4 standards are unnumbered in print; numbers are derived by position and validated (13 of 13 cross-references match).
- 4 H-chapter activity rows have no parsed status (flagged in `notes`); H19 (rural zones) activity tables are not parsed.
- Full-text search only: no embeddings (needs an embedding provider key).
- Standards not yet seeded numerically: E27 transport/accessways, E36 hazards, overlays, precincts, business and rural zone standards (activity statuses for 25 zones are loaded).
