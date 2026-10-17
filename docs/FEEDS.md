# External feeds register
The live register is the table `core.feeds` (`db/sql/70_feeds.sql`). Run `make feeds-status` for status, last refresh, row counts, licence and what is blocked. Owner actions are in `docs/BLOCKERS.md`.
Statuses: `live`, `manual`, `pending_licence`, `pending_purchase`, `blocked`, `not_started`. Rules for every feed: importer + schema + validation report on first load + licence note in `docs/DATA_SOURCES.md`; never scrape; never bulk-load restricted data; nothing silently defaulted when a feed is missing.
