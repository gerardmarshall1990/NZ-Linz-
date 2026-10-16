# Manual sources (files dropped in by hand)

Some official sources block scripted downloads (for example `www.health.govt.nz` serves a Cloudflare bot challenge). We do not bypass that.
Download the file in your browser and put it in the matching folder here, then run `python3 scripts/load_manual_sources.py`
(or `make manual`). Files are loaded as-is with their name, SHA-256 and load time recorded. Do not rename columns; do not edit files.
Dropped files are git-ignored (third-party documents); only this README and `.gitkeep` are committed.

| Folder | What goes here | Where to get it | Needed for |
|---|---|---|---|
| `healthcert/` | Export of the HealthCERT certified providers list for aged residential care (rest homes): CSV or XLSX with provider name, address, bed counts by care type, certification dates | Ministry of Health website (health.govt.nz), Regulation > Certification of health care services, certified providers / aged residential care. Take the downloadable list/spreadsheet if offered. If there is none, tell me and I will look for the same list on data.govt.nz | Stage 4 rest home provider layer, competitor density, rest home deal sheet |
| `standards/` | PDF of the Ngā Paerewa Health and Disability Services Standard (NZS 8134:2021) | Standards New Zealand, free to download via standards.govt.nz or the Ministry of Health page for Ngā Paerewa | Rest home compliance gaps (staffing, environment, safety clauses) |
| `council_forms/` | Auckland Council application PDFs: resource consent (land use, subdivision), building consent, pre-application meeting request, plus each form's checklist, and the current fee schedule | aucklandcouncil.govt.nz > Building and property > Resource consents / Building consents > Forms. I can usually download these myself (the site is reachable), so drop only those I report as missing | Consent packs (last step) |
| `tpk_maori_land/` | Any Te Puni Kōkiri or Māori Land Court public export of Māori freehold land blocks / trusts / incorporations (CSV or XLSX) | tpk.govt.nz Māori land data, and the Māori Land Court public information (maorilandcourt.govt.nz). Only public data; nothing behind a login | Stage 4 Māori land cross-check |
| `other/` | Anything else tabular, for example a rating-values extract if you obtain one under licence, or comparable sales | Your licensed supplier | Land cost, feasibility |

Not files, but needed from you: Watercare licence confirmation (SPEC 0.9), 10 or more parcels with known planning outcomes for the regression suite,
and `SPEC_RESTHOME_TOOL.md` (it was not in the uploads I can see).
