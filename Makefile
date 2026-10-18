.PHONY: app-private backup-github backup-full owner-review-table bootstrap app-db app up down refresh refresh-linz refresh-auckland core backup manual rules test feeds feeds-status check-page validate demo-seed demo-clear preflight screen screen-bg
SHELL := /bin/bash
PSQL = set -a; . ./.env; set +a; PGPASSWORD=$$POSTGRES_PASSWORD psql -h $${PGHOST:-localhost} -U $$POSTGRES_USER -d $$POSTGRES_DB -v ON_ERROR_STOP=1 -q

up:
	docker compose up -d
down:
	docker compose down

refresh: refresh-linz refresh-auckland core rules

refresh-linz:
	python3 scripts/ingest_linz.py parcels buildings addresses titles facilities rail_stations
refresh-auckland:
	python3 scripts/ingest_auckland.py all
	python3 scripts/ingest_plan_changes.py
	python3 -I scripts/ingest_at_stops.py
core:
	$(PSQL) -f db/sql/10_zone_lookup.sql
	$(PSQL) -f db/sql/20_sites_base.sql
	$(PSQL) -f db/sql/30_sites_enrich.sql
	$(PSQL) -f db/sql/35_sites_amenities.sql
	$(PSQL) -f db/sql/40_sites_hazards.sql
	$(PSQL) -f db/sql/50_plan_versions.sql

# Run at the end of every stage: make backup STAGE=stage2
backup:
	bash scripts/backup_userdata.sh

# Full database dump (large, rarely needed: bootstrap rebuilds everything except user data)
backup-full:
	./scripts/backup.sh $(STAGE)

manual:
	python3 scripts/load_manual_sources.py

# Rules corpus: download operative AUP chapter PDFs, OCR-repair, chunk, load, extract activity tables, load verified rules, report
rules:
	python3 -I scripts/ingest_aup.py
	python3 -I scripts/ocr_aup.py
	python3 -I scripts/build_rule_chunks.py
	python3 -I scripts/extract_activity_tables.py
	python3 -I scripts/ingest_pc120.py
	python3 -I scripts/extract_pc120.py
	python3 scripts/load_rule_chunks.py
	python3 scripts/load_rules.py
	python3 scripts/check_extraction.py
	python3 scripts/report_rules_gate.py
	python3 scripts/build_key_standards_check.py

test:
	python3 -m pytest tests -q

feeds:
	$(PSQL) -f db/sql/70_feeds.sql

feeds-status:
	@python3 scripts/feeds_status.py

demo-seed:
	@python3 scripts/demo_seed.py

demo-clear:
	@python3 scripts/demo_seed.py --clear

preflight:
	@python3 scripts/preflight.py

screen:
	@python3 scripts/screen_bulk.py

screen-bg:
	@nohup python3 scripts/screen_bulk.py > bootstrap_screen.log 2>&1 &

validate:
	@python3 scripts/validate.py

app-db:
	bash scripts/create_app_role.sh
	$(PSQL) -f db/sql/80_rh_property.sql
	$(PSQL) -f db/sql/90_rh_step2.sql
	$(PSQL) -f db/sql/95_listings.sql
	$(PSQL) -f db/sql/96_settings.sql
	$(PSQL) -f db/sql/97_consent_pack.sql
	$(PSQL) -f db/sql/98_calibration_requests.sql
	$(PSQL) -f db/sql/98_workflow.sql
	$(PSQL) -f db/sql/98_digest_crm.sql
	$(PSQL) -f db/sql/98_dev.sql
	$(PSQL) -f db/sql/98_screen.sql
	$(PSQL) -f db/sql/98_outreach.sql
	python3 scripts/load_rh_requirements.py
	$(PSQL) -f db/sql/99_ai_grants.sql

app:
	python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Rebuild every regenerable layer from the original sources (target = POSTGRES_DB in .env)
bootstrap:
	bash scripts/bootstrap.sh

owner-review-table:
	$(PSQL) -f db/sql/85_owner_review_log.sql

# Encrypted user-data backup pushed to the separate PRIVATE backup repo (refuses if unencrypted). See docs/BACKUP.md
backup-github:
	bash scripts/backup_to_github.sh

# Private access over Tailscale (needs APP_PASSWORD and TS_AUTHKEY in the environment). See docs/ACCESS.md
app-private:
	bash scripts/start_private.sh
