# Manual source files: exactly what I need from you

Several official sites refuse scripted downloads (a bot challenge or a `406`). I do not get around that. Open the page in your phone or computer browser, download the file, and drop it into the folder shown (the cloud session's file upload, or the repo's `docs/sources_manual/<folder>/`). Dropped files are git-ignored (third-party documents). Then run `make manual` or just tell me "files are in".

Page addresses below are the ones I found or know of; government sites move pages, so if a link is dead search the page title. **Nothing below has been opened by me**, so the "what to take" column is my best reading of what is on the page.

## A. Needed first (unblocks "ready to lodge" and the 17 requirement slots)

| # | File | Folder | Download page | What to take |
|---|---|---|---|---|
| 1 | **Ngā Paerewa Health and Disability Services Standard NZS 8134:2021** (the whole PDF) | `standards/` | Standards New Zealand (standards.govt.nz, search "NZS 8134:2021"); also the Ministry of Health page "Ngā Paerewa Health and disability services standard" on health.govt.nz | The full standard. Free to download. Needed for resident room size, ensuites, communal area per bed, double occupancy, nurse call and the environment clauses |
| 2 | **Building Code Acceptable Solutions and Verification Methods**: C/AS1 to C/AS7 (fire), D1/AS1 (access), F6 and F7 (lighting and warning systems), G1, G2, G3 (personal hygiene, laundering, food preparation), B1 and B2 | `standards/` | building.govt.nz, "Building Code compliance documents" (behind a bot challenge) | One PDF per document, original file names. Take the current version and note its amendment date |
| 3 | **MBIE guidance on changing the use of a building** (and the Building Act 2004 sections 114 and 115 text from legislation.govt.nz if easier) | `standards/` | building.govt.nz search "change the use of a building"; legislation.govt.nz "Building Act 2004" | The guidance PDF; the two sections |
| 4 | **HealthCERT certified providers list** for aged residential care | `healthcert/` | health.govt.nz, Regulation, "Certification of health care services", certified providers list (bot challenge). If there is only a web table, save it as CSV/XLSX or tell me and I look on data.govt.nz | Provider name, address, beds by care type, certification dates |

## B. Needed for the consent pack (so the pack can be reconciled with Council's own checklist)

| # | File | Folder | Download page | What to take |
|---|---|---|---|---|
| 5 | **AC1021 Building consent application pack 2 (commercial)** (AC1009 lodgement checklist v.21 June 2026: **received 2026-10-18, loaded**) | `council_forms/` | aucklandcouncil.govt.nz, Building and consents, Building consents, forms (direct link recorded in `docs/council_forms/README.md`; the Council site answers scripts with 406) | The PDF, which holds the Council's checklist |
| 6 | **AC2205 Change of use of existing buildings**, **AC1826 Fire protection guide**, **AC2154 Notification of proposed change of use** | `council_forms/` | same, links in `docs/council_forms/README.md` | PDFs |
| 7 | **Council's document file-naming page** and the **building consent fee schedule** | `council_forms/` | the file-naming page link is in `docs/council_forms/README.md`; the fee schedule is under Building consent fees on the Council site | Save each page as PDF (browser, Print, Save as PDF) |
| 8 | **The online application screens in order** (portal field order) | `council_forms/` | Start (do not submit) a building consent application in your Council online account and take screenshots of each screen, or save the Council's "how to apply online" guide as PDF | One screenshot per screen, numbered. Lets me put the data sheet in the portal's real order |
| 9 | **Producer statement author register** | `ps_register/` | The Council's "Find a producer statement author" search (links in `docs/council_forms/README.md`). There is no download list: email producerstatement@aucklandcouncil.govt.nz asking for an export, or search each author yourself and record the result in the app (Consent pack, then Register) | A CSV with columns `name, company, registration_no, valid_until` if the Council gives one. If not, nothing to drop: you record each check by hand and the app keeps who and when |

## C. Later (not needed for the current steps)

| File | Folder | Download page |
|---|---|---|
| Te Puni Kōkiri / Māori Land Court public exports of Māori freehold land (CSV/XLSX) | `tpk_maori_land/` | tpk.govt.nz Māori land data; maorilandcourt.govt.nz public information. Only for the Māori land finder |
| Rating values or comparable sales, if you buy them | `other/` | your licensed supplier |

## What I do when the files arrive

1. **Standards and Building Code (rows 1 to 3):** fill the 17 requirement slots in `config/rh_requirements.yaml` and the four regulatory values in `config/bed_rules.yaml`. Each gets the clause reference, the page, the document's amendment date and `last_verified`. A value I cannot find in the document stays blank and I say so. Then load them (`scripts/load_rh_requirements.py`), apply them in the compliance engine and the bed-yield engine (the layout options change when room size, ensuite and communal-area rules start to apply), and show you the first results side by side with the page crop for each figure.
2. **Nothing is marked verified until you confirm it** (decision 17). Extracted values are used and labelled "extracted, awaiting your confirmation", and screening results that depend on them stay capped as screening.
3. **Council documents (rows 5 to 9):** reconcile `config/building_consent_checklist.yaml` with the Council's own checklist (documents, names, folders, which are required for a change of use), put the data sheet in the portal's order, record URLs and `last_verified`. `council_verified` becomes true only after you tell me to; until then "ready to lodge" stays blocked.
4. **HealthCERT list:** load it as the rest home provider layer (competitor density, existing homes near a site).

Not files but still needed from you: see `docs/BLOCKERS.md`.
