# NZ property deal-sourcing tool (Auckland first)

Finds and screens rest home conversions of existing buildings: listings on a map with a verdict, bed layouts from a confirmed plan, compliance gaps, retrofit cost, economics and walk-away rent, the Offer Builder, a Deal Sheet PDF, and a draft building consent pack for your engineers. Development-site and Māori-land finders come later.
`MASTER_SPEC.md` is the single source of truth; `docs/STATUS.md` says what is done and what is blocked on you; `docs/BLOCKERS.md` is your to-do list. It is a **screening and preparation tool**: not planning, legal, engineering or financial advice. Council decides applications. Nothing it produces is a producer statement, signature, registration number or final fire report.

## Setup in 5 steps

**1. Get a working database (me, at the start of each cloud session).**
`make up` starts PostgreSQL/PostGIS (it stops between sessions). The data is rebuilt, not stored: `make bootstrap` rebuilds every regenerable layer from the public sources. Whole-of-Auckland takes about 3.5 to 4.5 hours (mostly downloads); for a quick run set `SLICE_BBOX=minE,minN,maxE,maxN` in `.env` (about 21 minutes for a 4,600-parcel slice). Then `make app-db` creates your own tables. Details and proofs: `docs/BOOTSTRAP.md`.
Needs a `.env` with `LINZ_API_KEY` and the database passwords (never committed; rotate the LINZ key, BLOCKERS 15).

**2. Set your secrets as environment variables (you, once).**
Claude app, the session's cloud environment menu, Edit, environment variables (use *Network secrets* if offered). Never put them in chat or in a file in this repo.
| Variable | What for |
|---|---|
| `APP_PASSWORD` | the app's login (16+ random characters; without it the app refuses to start) |
| `TS_AUTHKEY` | Tailscale key so your iPhone can reach the app privately |
| `BACKUP_PASSPHRASE` | encrypts the backups that go to your private backup repo (keep a copy in your password manager: lost means unreadable) |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | the plan reader's vision step and the chat agent (everything else works without them) |

**3. Drop in the files the official sites will not give to scripts (you).**
`docs/sources_manual/README.md` lists exactly which files, with the download page for each (Ngā Paerewa, Building Code documents, HealthCERT list, the Council's consent checklist and forms, the producer statement author register). Then `make manual`. Until then the numeric rules stay blank and the pack's "ready to lodge" stays blocked: the app says so rather than guessing.

**4. Open it on your iPhone (free, private, login required).**
Install Tailscale on the iPhone, allow the Tailscale domains for the sandbox, then in the session run `make app-private`. It refuses to start without `APP_PASSWORD` and `TS_AUTHKEY`, binds to localhost only, and prints a private address that works only on your tailnet. Steps and the domain list: `docs/ACCESS.md`. (`make app` runs it on `127.0.0.1:8000` for the sandbox itself.)

**5. Enter your numbers, then keep them safe (you).**
- **My inputs** and **Placeholders** tabs: your real running costs, rates and cash limit. Anything marked `placeholder: estimate` caps verdicts at AMBER and shows "Uses placeholder inputs: not decision-grade" until you replace it.
- **Quotes** tab: real QS quotes calibrate the retrofit rates; the count per line is shown.
- **Import** tab: your listings as CSV (Trade Me only through its official API once terms allow; realestate.co.nz has no lawful automated route).
- Backups: `make backup` (local), `make backup-github` (encrypted, to a separate PRIVATE repo; `docs/BACKUP.md`). Plans and uploads need a different route. The database lives only in the sandbox, so run a backup after each working session.

## Everyday use
Map: click a listing dot or search an address. **Parcel / Listing / Rest Home / Offer** tabs show the verdict, layout options, compliance screening, retrofit, economics, what-if sliders, the Deal Sheet PDF, the consent pack and engineer review packages. **Rank** orders properties by profit per effort point within each confidence tier.

## Checks
`make test` runs the test suite (215 tests). `make validate` regenerates `docs/VALIDATION.md`, the go/no-go report that must pass before you flip any outreach flag. Outreach, field capture and offer letters are **off** (`config/feature_flags.yaml`) and the routes answer 403; only you can turn them on, by editing that file.

## Where things are
`backend/app/` the API and engines; `backend/app/static/` the phone UI; `config/` rules, rates, assumptions, checklists; `db/sql/` schema; `scripts/` pipelines and backups; `docs/` explanations (start with `docs/STATUS.md`, `docs/BLOCKERS.md`, `docs/LIMITATIONS.md`).

## Safety rules the code enforces
Login on everything; keys server-side only; every number carries a source and confidence; natural hazard flags are information only for conversions; no numeric rule counts as verified until you confirm it; drawings and generated pack documents are stamped DRAFT; nothing is sent or lodged without you.
