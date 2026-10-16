.PHONY: up down refresh refresh-linz refresh-auckland core backup
SHELL := /bin/bash
PSQL = set -a; . ./.env; set +a; PGPASSWORD=$$POSTGRES_PASSWORD psql -h $${PGHOST:-localhost} -U $$POSTGRES_USER -d $$POSTGRES_DB -v ON_ERROR_STOP=1 -q

up:
	docker compose up -d
down:
	docker compose down

refresh: refresh-linz refresh-auckland core

refresh-linz:
	python3 scripts/ingest_linz.py parcels buildings addresses titles facilities rail_stations
refresh-auckland:
	python3 scripts/ingest_auckland.py all
core:
	$(PSQL) -f db/sql/10_zone_lookup.sql
	$(PSQL) -f db/sql/20_sites_base.sql
	$(PSQL) -f db/sql/30_sites_enrich.sql
	$(PSQL) -f db/sql/35_sites_amenities.sql
	$(PSQL) -f db/sql/40_sites_hazards.sql

# Run at the end of every stage: make backup STAGE=stage2
backup:
	./scripts/backup.sh $(STAGE)
