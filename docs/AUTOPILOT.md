# AUTOPILOT checklist (read this first in a new session, then continue from the first unchecked item)

Rules (owner's autopilot instruction, 2026-10-18): never stop to ask; decide the safest conservative option and log one line in `docs/DECISIONS.md`; a value only the owner can give becomes a flagged placeholder or a PENDING line in `docs/BLOCKERS.md`; tests must pass before an item is done; no invented rules, rates or numbers; DRAFT stamps; nothing sent or lodged without an approval record; outreach behind feature flags (all off); commit after every item; milestone report of at most 8 lines (iPhone, test counts, blocked on owner).
Start of session: read MASTER_SPEC.md, this file, docs/STATUS.md. `bash scripts/db_up.sh` (Postgres stops between sessions). Tests: `python -m pytest -q` (run long ones in the background).

Status key: [x] done, [~] partly done (what is left in the note), [ ] not started, [P] pending on the owner.

## A. Make the app testable on the iPhone
- [x] A1 docs/IPHONE_TEST.md: setup steps, login, 3 DEMO listings, 10-step test script (done)
- [x] A2 `make demo-seed` / `make demo-clear`, DEMO badge, `make preflight` (done; opening on the iPhone itself is [P] on APP_PASSWORD + TS_AUTHKEY)

## B. Part 7 steps 4 and 5, plan request pack
- [x] B1 Consent pack, review workflow, completeness against AC1009 (151 lines), DRAFT stamps, upload slots, PS validity (90 days, register)  (done 2026-10-18)
- [x] B2 Plan request pack (email, Council LIM guidance, site visit form, request log)  (done)
- [ ] B3 Approval records (nothing sent or lodged without one): table + API, used by review send and "lodged" marker
- [ ] B4 Capture Guide generator (remote phone capture instructions for the owner/agent)
- [ ] B5 RFI tracker (Council requests for information: logged, due dates, responses)
- [ ] B6 Timeline widget (consent, works, audit; parallel tracks) and metrics (human minutes per step)

## C. Part 3
- [x] C1 Retrofit calibration loop (done)
- [x] C2 Deal Sheet PDF (done)
- [x] C3 Ranking and what-if sliders (done)
- [ ] C4 Timeline scenarios (best / base / delay) feeding the Offer Builder
- [ ] C5 Certification checklist (HealthCERT / Ngā Paerewa pathway; clause values PENDING the standard)

## D. Part 6
- [ ] D1 Digest and alerts (listing changes, follow-ups due, RFIs due; in-app only, no sending)
- [ ] D2 CRM link (listing to owner contact record; behind outreach flag, off)
- [ ] D3 Trade Me connector ready for keys (CSV until then; status pending_licence)

## E. Part 2 (development sites, Māori land)
- [ ] E1 Rules evaluator
- [ ] E2 Development layout engine, fit_units, subdivision_yield
- [ ] E3 Services module (licence rules respected)
- [ ] E4 Site Panel buttons 1 to 3 for development sites
- [ ] E5 Resource consent pack
- [ ] E6 Best Use tab
- [ ] E7 Zone / overlay / Māori map layers
- [ ] E8 Māori land module
- [ ] E9 Apartment playbook

## F. Part 4
- [ ] F1 Bulk Auckland screening with map layers
- [ ] F2 House-scale and portfolio economics
- [ ] F3 Suburb analytics
- [ ] F4 Field capture app (behind flag)
- [ ] F5 CRM (behind flag)
- [ ] F6 Route planning (behind flag)
- [ ] F7 Offer generator (behind flag)

## G. Part 8
- [ ] G1 Approval Queue
- [ ] G2 Dashboard
- [ ] G3 Capture portal
- [ ] G4 Playbooks and delta view
- [ ] G5 Batch engineer workflow
- [ ] G6 Capacity planner

## H. Part 5 and close-out
- [ ] H1 Feeds admin page, importers, CONFLICTS.md
- [x] H2 Feature flags and validation report (done; re-run `make validate` at the end)
- [ ] H3 README refreshed, final backup, STATUS.md final

## Owner-blocked inputs (do not wait for these; see docs/BLOCKERS.md)
APP_PASSWORD, TS_AUTHKEY, BACKUP_PASSPHRASE + private backup repo, ANTHROPIC_API_KEY/MODEL, Ngā Paerewa and Building Code documents, HealthCERT list, AC1021 / portal screens / fee schedule, PS author register export, real costs and QS quotes, standards spot-checks, tolerance and chosen validation properties.
