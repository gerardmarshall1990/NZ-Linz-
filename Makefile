.PHONY: up down refresh
up:
	docker compose up -d
down:
	docker compose down
refresh:
	@echo "Ingest pipeline lands in Stage 1 once LINZ dataset IDs are verified." && exit 1
