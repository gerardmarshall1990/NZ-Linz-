# 48-hour sprint (started 2026-10-20)

**Goal by the end:** import real listings by CSV, get verdicts and offers, produce a Deal Sheet and a draft consent pack for one real property, on a server with encrypted backups.
**Rules:** full test suite green before every push (the pre-push gate enforces it); outreach and field-capture flags are not touched; nothing is marked owner-verified by me; after each block: at most 6 lines (done, running, blocked on you).

| Block | Hours | What gets done | What I need from you to finish it (only what blocks me) |
|---|---|---|---|
| 1 Real CSV import | 0 to 8 | Importer hardened for real exports: BOM, semicolon/tab, wage-style rent text (pw, pcm), price suffixes (k, m), per-row warnings in the dry run, header aliases, results shown on the phone | A real listings CSV (even 5 rows, from wherever you get them; remove names/phones if you like). Until then I use my own test files |
| 2 Verdicts and offers on real rows | 8 to 16 | Walk the real rows through verdicts, Quick answer and Offer; fix what looks wrong; placeholders you replace lift the AMBER cap | The 3 to 5 costs you can state (occupancy, supplies per bed, cook/cleaner hours, insurance, repairs). Optional: unanswered ones stay flagged placeholders |
| 3 One real property, end to end | 16 to 28 | Property Record, plan upload and reading, human review on the phone, layouts, compliance, Deal Sheet PDF, draft consent pack (AC1009) | The real property: address plus its floor plan (PDF, DXF or clear photos) and the plan scale. Optional: ANTHROPIC_API_KEY so the vision reader can read photos and scans (DXF needs no key) |
| 4 Server and encrypted backups (runs alongside 1 to 3) | 4 to 40 | Setup script, restore script, nightly encrypted backup with an off-server copy, restore drill on a copy, Tailscale address kept | A server account and server (Hetzner, about EUR 6 a month; steps in docs/HOSTING.md), a fresh Tailscale key for it, `BACKUP_PASSPHRASE` set as an environment variable, `LINZ_API_KEY`, and a decision on where the off-server backup copy goes |
| 5 Hardening and handover | 40 to 48 | Full tests, restore drill result, click-through script for your phone, known-gaps list | Your phone walk-through of the final script, in one message |

## While waiting on you
Fix list, tests, docs, hosting scripts, and the next unblocked item. Anything that cannot be finished without you is parked with the exact question.

## Not in this sprint
Outreach and field-capture flags (stay off), Trade Me/realestate.co.nz connectors, Ngā Paerewa and Building Code values (you type them on the Standards tab if you want them applied).

## Progress log
- **Block 1 (done, waiting on a real CSV):** importer reads Excel/Numbers exports (UTF-8, UTF-16, Windows-1252; comma, semicolon or tab), rent as pw/pcm/per fortnight, prices as k/m/POA, and lists every row that looks wrong in the dry run; shown on the phone.
- **Block 4 (scripts done, needs your server):** `deploy/server_setup.sh` and services, nightly encrypted backup with off-server copy, `scripts/restore_userdata.sh`, `scripts/restore_drill.sh` (PASS: 59 tables identical), pinned `requirements.txt`, `docs/SERVER.md`.
- **Block 3 rehearsal (synthetic plan, demo parcel, then cleaned up):** Plans page: upload DXF, read, confirm; then layouts (2 / 4 / 5 beds), compliance, Deal Sheet PDF, draft consent pack with 18 listed blockers, export zip: all worked. Found and fixed: the Plans page status line called an endpoint that no longer returned the site count (page error on every load); new test guards page-to-endpoint mismatches.
