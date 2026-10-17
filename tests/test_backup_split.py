"""Every table is either user data (backed up) or regenerable (rebuilt by make bootstrap). A new table that is neither fails here, so user data can't silently go unbacked."""
import os
from pathlib import Path
import psycopg
for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
USER = ("core.rh_", "core.user_", "core.owner_")
REGENERABLE = {"core.auckland_boundary", "core.building_site", "core.feeds", "core.sites", "core.zone_group_lookup", "core.zone_lookup"}
def test_all_tables_classified():
    dsn = f"host=localhost dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
    with psycopg.connect(dsn, autocommit=True) as c:
        rows = [f"{s}.{t}" for s, t in c.execute("SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('raw','core','analytics')").fetchall()]
    unclassified = [t for t in rows if not (t.startswith(("raw.", "analytics.")) or t.startswith(USER) or t in REGENERABLE)]
    assert not unclassified, f"classify these as user data (name core.user_*/rh_*/owner_*) or add to REGENERABLE: {unclassified}"
