"""Tools for the chat agent (MASTER_SPEC Stage 5, scoped to the rest home flow). Every tool returns JSON with its sources; the SQL tool is validated and runs as the read-only database role.
LATER and not implemented: fit_units, subdivision_yield, feasibility (development finder), map_highlight, consent_path. The agent is told so."""
import json
import psycopg
import sqlglot
from sqlglot import exp
from psycopg.rows import dict_row
from . import listings
from .config import ai_dsn

ROW_CAP = 200
ALLOWED_SCHEMAS = {"core", "analytics"}
DENY_FUNCS = {"pg_sleep", "pg_sleep_for", "pg_sleep_until", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file", "dblink", "dblink_exec", "set_config", "lo_import", "lo_export",
              "lo_open", "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf", "pg_advisory_lock", "pg_notify", "nextval", "setval", "txid_current", "current_setting", "pg_file_write",
              "query_to_xml", "xpath", "pg_read_server_files", "copy"}
BAD_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Merge, exp.Set, exp.Into, exp.Lock, exp.Transaction, exp.Commit, exp.Rollback, exp.TruncateTable, exp.Use, exp.Copy)

class Rejected(ValueError): pass

def validate_sql(query: str) -> str:
    """Return the query if it is one plain SELECT over core/analytics tables; raise Rejected otherwise. (The database role is the second line of defence.)"""
    q = (query or "").strip().rstrip(";").strip()
    if not q: raise Rejected("empty query")
    if len(q) > 6000: raise Rejected("query too long")
    try: trees = sqlglot.parse(q, read="postgres")
    except sqlglot.errors.SqlglotError as e: raise Rejected(f"could not parse as SQL: {str(e)[:120]}")
    trees = [t for t in trees if t is not None]
    if len(trees) != 1: raise Rejected("exactly one statement is allowed")
    t = trees[0]
    if not isinstance(t, (exp.Select, exp.Union, exp.Subquery)) : raise Rejected("only SELECT queries are allowed")
    for n in t.walk():
        node = n[0] if isinstance(n, tuple) else n
        if isinstance(node, BAD_NODES): raise Rejected(f"{type(node).__name__} is not allowed")
        if isinstance(node, exp.Lock): raise Rejected("row locking is not allowed")
        if isinstance(node, (exp.Func, exp.Anonymous)):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
            if name in DENY_FUNCS: raise Rejected(f"function {name} is not allowed")
    ctes = {c.alias_or_name.lower() for c in t.find_all(exp.CTE)}
    for tb in t.find_all(exp.Table):
        sch = (tb.args.get("db").name.lower() if tb.args.get("db") else "")
        if tb.args.get("catalog"): raise Rejected("cross-database references are not allowed")
        if not sch:
            if tb.name.lower() in ctes: continue
            raise Rejected(f"qualify the table with its schema (core or analytics): {tb.name}")
        if sch not in ALLOWED_SCHEMAS: raise Rejected(f"schema {sch} is not readable (only core and analytics)")
        if isinstance(tb.this, exp.Func): raise Rejected("table functions are not allowed")
    return q

def _trim(v):
    if isinstance(v, (bytes, memoryview)): return "<binary>"
    if isinstance(v, str) and len(v) > 400: return v[:400] + "...(truncated)"
    if hasattr(v, "isoformat"): return v.isoformat()
    if hasattr(v, "as_tuple"): return float(v)
    return v

def run_sql(query: str, limit: int = 50) -> dict:
    limit = max(1, min(int(limit or 50), ROW_CAP))
    try: q = validate_sql(query)
    except Rejected as e: return {"error": f"query rejected: {e}", "hint": "one SELECT over core.* or analytics.* only; call describe_schema first"}
    try:
        with psycopg.connect(ai_dsn(), row_factory=dict_row, autocommit=False) as c:
            c.execute("SET LOCAL statement_timeout = '15s'")
            rows = c.execute(f"SELECT * FROM ({q}) AS _agent LIMIT {limit + 1}").fetchall()
    except psycopg.Error as e: return {"error": f"database error: {str(e).splitlines()[0][:200]}"}
    more = len(rows) > limit; rows = rows[:limit]
    return {"rows": [{k: _trim(v) for k, v in r.items()} for r in rows], "row_count": len(rows), "truncated": more, "row_cap": limit, "source": "database query (core/analytics, read-only)"}

DESCRIPTIONS = {"core.sites": "one row per Auckland parcel: zone, area, title type, overlays, hazard flags (information only for conversions), PC120 flags, distances. Source: LINZ + Auckland Council open data",
                "analytics.rules": "planning rules and activity statuses with citations; status operative or proposed (PC120, never merged); owner_verified false until the owner confirms",
                "analytics.rule_text_chunks": "plan text with section references", "core.user_listing": "listings the owner imported (CSV/manual)", "core.rh_property": "Property Records (rest home candidates)",
                "core.rh_property_fact": "facts with source and confidence (ESTIMATED/DOCUMENTED/CONFIRMED)", "core.rh_layout_option": "rest home layout options with beds and binding constraint"}

def describe_schema() -> dict:
    with psycopg.connect(ai_dsn(), row_factory=dict_row) as c:
        cols = c.execute("""SELECT table_schema||'.'||table_name AS t, column_name, data_type FROM information_schema.columns WHERE table_schema IN ('core','analytics') AND column_name <> 'geom' ORDER BY 1, ordinal_position""").fetchall()
    out = {}
    for r in cols: out.setdefault(r["t"], []).append(f"{r['column_name']}:{r['data_type']}")
    return {"tables": {t: {"columns": c_, "about": DESCRIPTIONS.get(t)} for t, c_ in out.items()}, "note": "geom columns are omitted (EPSG:2193); read-only, core and analytics only"}

def search_rules(query: str, zone: str | None = None, limit: int = 6) -> dict:
    with psycopg.connect(ai_dsn(), row_factory=dict_row) as c:
        rows = c.execute("SELECT * FROM analytics.search_rules(%s, %s, %s)", (query, zone, max(1, min(int(limit or 6), 12)))).fetchall()
    return {"results": [{k: _trim(v) for k, v in r.items()} for r in rows], "note": "Quote section references. Operative and proposed (PC120) rules are separate. Confirm with a council planner.", "source": "Auckland Unitary Plan (operative July 2026) and PC120 documents"}

def site_info(parcel_id: int) -> dict:
    with psycopg.connect(ai_dsn(), row_factory=dict_row) as c:
        s = c.execute("""SELECT parcel_id, address, suburb, area_m2::float AS area_m2, zone_name, title_type, building_count, overlays, hazard_flags, pc120_depends, pc120_proposed_zone, maori_land_linz
                         FROM core.sites WHERE parcel_id = %s""", (int(parcel_id),)).fetchone()
        if not s: return {"error": "no such parcel"}
        facts = c.execute("SELECT field, value, confidence, source FROM core.rh_property_fact WHERE parcel_id = %s ORDER BY field", (int(parcel_id),)).fetchall()
    return {"site": {k: _trim(v) for k, v in s.items()}, "property_facts": [{k: _trim(v) for k, v in f.items()} for f in facts], "hazard_note": "Hazard flags are information only for conversions of existing buildings and never change the verdict.",
            "source": "core.sites (LINZ, Auckland Council); core.rh_property_fact", "last_verified_note": "Zoning results are screens, not planning advice: confirm with a council planner."}

def listings_search(filters: dict | None = None) -> dict:
    f = {k: v for k, v in (filters or {}).items() if k in ("min_beds", "max_beds", "min_rent", "max_rent", "suburb", "verdict", "source")}
    r = listings.search(f)
    rows = [{"listing_id": o["listing"]["id"], "address": o["listing"]["raw_address"], "bedrooms": o["listing"]["bedrooms"], "rent_per_week": o["listing"]["rent_per_week"], "verdict": o["verdict"], "confidence": o["confidence"],
             "reasons": o["reasons"][:4], "needs_input": o.get("needs_input"), "walk_away_rent": (o.get("economics") or {}).get("offer_ceiling"), "parcel_id": o["listing"]["parcel_id"]} for o in r["listings"][:50]]
    return {"count": r["count"], "verdict_counts": r["verdict_counts"], "listings": rows, "source_coverage": r["source_coverage"], "source": "owner-imported listings (CSV/manual) + verdict engine"}

TOOLS = [
    {"name": "describe_schema", "description": "List the tables and columns the agent may query (core and analytics), with what each table holds.", "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "run_sql", "description": "Run ONE read-only SELECT over core.* or analytics.* (qualify every table). Rows are capped. Use describe_schema first. Never answer numbers from memory.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": ROW_CAP}}, "required": ["query"], "additionalProperties": False}},
    {"name": "search_rules", "description": "Search the planning rule text and rows; returns wording with section references. Optionally restrict to a zone name.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "zone": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 12}}, "required": ["query"], "additionalProperties": False}},
    {"name": "site_info", "description": "Zone, overlays, title type, hazards (information only), PC120 flags and recorded Property Record facts with confidence for one parcel.",
     "input_schema": {"type": "object", "properties": {"parcel_id": {"type": "integer"}}, "required": ["parcel_id"], "additionalProperties": False}},
    {"name": "listings_search", "description": "Search the owner's imported listings with rest home verdicts (GREEN/AMBER/RED/GREY), reasons, confidence, walk-away rent and what inputs are missing. Filters: min_beds, max_beds, min_rent, max_rent, suburb, verdict, source.",
     "input_schema": {"type": "object", "properties": {"filters": {"type": "object", "properties": {"min_beds": {"type": "integer"}, "max_beds": {"type": "integer"}, "min_rent": {"type": "number"}, "max_rent": {"type": "number"}, "suburb": {"type": "string"}, "verdict": {"type": "string", "enum": ["GREEN", "AMBER", "RED", "GREY"]}, "source": {"type": "string"}}, "additionalProperties": False}}, "additionalProperties": False}},
]
DISPATCH = {"describe_schema": lambda a: describe_schema(), "run_sql": lambda a: run_sql(a["query"], a.get("limit", 50)), "search_rules": lambda a: search_rules(a["query"], a.get("zone"), a.get("limit", 6)),
            "site_info": lambda a: site_info(a["parcel_id"]), "listings_search": lambda a: listings_search(a.get("filters"))}

def call(name: str, args: dict) -> dict:
    import jsonschema
    spec = next((t for t in TOOLS if t["name"] == name), None)
    if not spec: return {"error": f"unknown tool {name}"}
    try: jsonschema.validate(args, spec["input_schema"])
    except jsonschema.ValidationError as e: return {"error": f"invalid input: {e.message[:150]}"}
    try: return DISPATCH[name](args)
    except Exception as e: return {"error": f"{type(e).__name__}: {str(e)[:150]}"}
