.PHONY: up down refresh refresh-linz refresh-auckland core backup manual rules test
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
	./scripts/backup.sh $(STAGE)

manual:
	python3 scripts/load_manual_sources.py

# Rules corpus: download operative AUP chapter PDFs, OCR-repair, chunk, load, extract activity tables, load verified rules, report
rules:
	python3 -I scripts/ingest_aup.py
	python3 -I scripts/ocr_aup.py
	python3 -I scripts/build_rule_chunks.py
	python3 -I scripts/extract_activity_tables.py
	python3 scripts/load_rule_chunks.py
	python3 scripts/load_rules.py
	python3 scripts/report_rules_gate.py

test:
	python3 -m pytest tests -q
