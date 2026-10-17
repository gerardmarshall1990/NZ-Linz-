# Rules corpus (Auckland Unitary Plan, operative July 2026)

## What is loaded
| Table | Content | Count (2026-10-17) |
|---|---|---|
| `analytics.source_documents` | 99 official AUP chapter PDFs (C, D, E, H, J) with URL, SHA-256, plan index date | 99 |
| `analytics.rule_text_chunks` | citable text chunks: section ref, heading, page, full text, full-text index (heading weighted) | 2,166 (incl. 456 defined terms) |
| `analytics.rules` | structured rules: 156 numeric standards (verified quotes), 965 activity-table rows (P/C/RD/D/NC/Pr), 207 text-only standards | 1,328 |
| `analytics.plan_versions` | operative AUP, PC78, PC120 (proposed), Plan Stop | 4 |
`analytics.search_rules(query, zone_filter, limit)` returns section ref, heading, snippet, plan page, source URL, `last_verified`, plan version.

## Source and plan version
Index `https://unitaryplan.aucklandcouncil.govt.nz/data/operative/data.xml` (dated 16 Oct 2026); PDFs under `/images/Auckland Unitary Plan Operative/`.
The PDFs state "Auckland Unitary Plan July 2026"; Council: plan fully operative 23 July 2026. PC120 is proposed and **not applied**; margin notes
"PC 120 (see Modifications)" mark provisions it would change and are recorded as `PC 120 annotation` in each rule's `notes`.

## How rules get in (and why you can trust the numbers)
1. `ingest_aup.py` downloads the chapter PDFs and extracts text. 2. `ocr_aup.py` OCRs every page (Tesseract) because some pages' text layers drop
paragraphs, table cells and list numbers (62 pages badly, others partly). 3. `build_rule_chunks.py` splits by bold headings, uses OCR to repair gaps, numbers
unnumbered standards by position (H4 only) and validates that numbering against the chapter's own cross-references. 4. `extract_activity_tables.py` reads activity
tables by column position; row ids must be sequential. 5. `config/rules_seed/*.yaml` hold the numeric standards; **`load_rules.py` refuses to load any rule whose `quote`
does not occur verbatim in the extracted text for its section** (all 156 passed). 6. `report_rules_gate.py` writes `docs/RULES_STAGE3_GATE.md` for your spot-check.
Edit values only in the YAML, then `make rules`. Tests: `make test` (63 tests, run as the read-only `ai_readonly` role).

## Findings worth knowing
- Operative text: Single House Zone permits one dwelling per site, more than one is non-complying; Mixed Housing Suburban/Urban and Māori Purpose permit up to three, four or more is restricted discretionary; Terrace Housing and Apartment Buildings makes dwellings restricted discretionary.
- Subdivision minimum net site area for vacant sites (parent site under 1 ha): THAB 1,200 m2, MHU 300, MHS 400, SHZ 600, Large Lot 4,000, Rural and Coastal Settlement 2,500 (E38.8.2.3).
- Māori land (E20): papakāinga/marae activities up to 250 m2 GFA permitted; one dwelling per hectare (max 10 per site) permitted in rural zones; the less restrictive of E20 and zone rules applies.
- Supported residential care (rest homes) is defined as certified under the Health and Disability Services (Safety) Act 2001 (J1.4).

## Not covered yet
Precinct chapters (I), schedules (L), designations (K), appendices (M), H19 rural zone activity tables (multi-zone chapter), H7/H23/H26, Auckland-wide E27 (transport, parking, accessways)
and E36 (hazards) numeric standards (their text is searchable but not seeded), overlay numeric standards, Building Code/Building Act (MBIE), embeddings (no embedding provider key; the `embedding` column is empty, search is full-text).
