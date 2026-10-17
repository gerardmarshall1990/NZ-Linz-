"""Stage 3 gate tests for the rules corpus. Needs the local database loaded (`make rules`).
Expected numbers were recorded by reading the plan PDFs (several by looking at the rendered page images), independent of the YAML seeds."""
import os
from pathlib import Path
import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1); os.environ.setdefault(k, v)

@pytest.fixture(scope="module")
def cur():
    # the read-only agent role: proves the corpus is readable by `ai_readonly`
    dsn = f"host=localhost dbname={os.environ['POSTGRES_DB']} user=ai_readonly password={os.environ['AI_READONLY_PASSWORD']}"
    with psycopg.connect(dsn) as con, con.cursor() as c:
        yield c

def val(cur, zone, param):
    cur.execute("SELECT value_num FROM analytics.rules WHERE zone = %s AND parameter = %s", (zone, param)); r = cur.fetchall()
    assert len(r) == 1, f"{zone} {param}: {len(r)} rows"; return float(r[0][0])

SHZ, MHS, MHU, THAB = ("Residential - Single House Zone", "Residential - Mixed Housing Suburban Zone", "Residential - Mixed Housing Urban Zone",
                       "Residential - Terrace Housing and Apartment Building Zone")
EXPECTED = [  # (zone, parameter, value)
    (SHZ, "building_height_max", 8), (MHS, "building_height_max", 8), (MHU, "building_height_max", 11), (THAB, "building_height_max", 16),
    (SHZ, "hirb_start_height", 2.5), (MHS, "hirb_start_height", 2.5), (MHU, "hirb_start_height", 3), (THAB, "hirb_start_height", 3),
    (SHZ, "yard_front_min", 3), (MHS, "yard_front_min", 3), (MHU, "yard_front_min", 2.5), (THAB, "yard_front_min", 1.5),
    (SHZ, "impervious_max_pct", 60), (MHS, "impervious_max_pct", 60), (MHU, "impervious_max_pct", 60), (THAB, "impervious_max_pct", 70),
    (SHZ, "building_coverage_max_pct", 35), (MHS, "building_coverage_max_pct", 40), (MHU, "building_coverage_max_pct", 45), (THAB, "building_coverage_max_pct", 50),
    (SHZ, "landscaped_min_pct", 40), (MHS, "landscaped_min_pct", 40), (MHU, "landscaped_min_pct", 35), (THAB, "landscaped_min_pct", 30),
    (MHS, "dwelling_min_net_floor_area_studio", 30), (MHU, "dwelling_min_net_floor_area_1br_plus", 45), (THAB, "dwelling_min_net_floor_area_1br_plus", 45),
    (SHZ, "min_net_site_area_vacant_site_parent_lt_1ha", 600), (MHS, "min_net_site_area_vacant_site_parent_lt_1ha", 400),
    (MHU, "min_net_site_area_vacant_site_parent_lt_1ha", 300), (THAB, "min_net_site_area_vacant_site_parent_lt_1ha", 1200),
]

@pytest.mark.parametrize("zone,param,expected", EXPECTED)
def test_numeric_standard(cur, zone, param, expected):
    if param.startswith("min_net_site_area"):
        cur.execute("SELECT value_num FROM analytics.rules WHERE topic = 'subdivision' AND parameter = %s AND applies_if->>'zone_code' = "
                    "(SELECT code::text FROM core.zone_lookup WHERE zone_name = %s OR zone_name = replace(%s, 'Buildings', 'Building'))", (param, zone, zone))
        r = cur.fetchall(); assert len(r) == 1; assert float(r[0][0]) == expected
    else:
        assert val(cur, zone, param) == expected

ACTIVITY = [  # (zone, activity text prefix, status)
    (SHZ, "One dwelling per site", "P"), (SHZ, "More than one dwelling per site", "NC"),
    (MHS, "Up to three dwellings per site", "P"), (MHS, "Four or more dwellings per site", "RD"),
    (MHU, "Up to three dwellings per site", "P"), (MHU, "Four or more dwellings per site", "RD"),
    (THAB, "Dwellings", "RD"),
]

@pytest.mark.parametrize("zone,prefix,status", ACTIVITY)
def test_activity_status(cur, zone, prefix, status):
    cur.execute("SELECT value_text FROM analytics.rules WHERE topic = 'activity_status' AND zone = %s AND activity ILIKE %s ORDER BY id LIMIT 1", (zone, prefix + "%"))
    r = cur.fetchone(); assert r and r[0] == status

SEARCH = [  # (query, zone filter, expected section_ref within top 3)
    ("building coverage maximum", "H4", "H4.6.9"), ("building coverage maximum", "H3", "H3.6.10"), ("building coverage", "H5", "H5.6.10"), ("building coverage", "H6", "H6.6.11"),
    ("height in relation to boundary recession plane", "H5", "H5.6.5"), ("building height", "H6", "H6.6.5"), ("yards front side rear riparian lakeside", "H3", "H3.6.8"),
    ("outdoor living space balcony", "H6", "H6.6.15"), ("maximum impervious area", "H4", "H4.6.8"), ("minimum dwelling size studio", "H5", "H5.6.16"),
    ("minimum net site area vacant sites subdivision", None, "E38.8.2.3"), ("access to rear sites legal width formed width", None, "E38.8.1.2"),
    ("site shape factor rectangle vacant sites", None, "E38.8.1.1"),
]

@pytest.mark.parametrize("q,zone,ref", SEARCH)
def test_search_rules_returns_citation(cur, q, zone, ref):
    cur.execute("SELECT section_ref, source_url, last_verified, plan_version FROM analytics.search_rules(%s, %s, 3)", (q, zone))
    rows = cur.fetchall()
    assert ref in [r[0] for r in rows], f"{q!r} {zone}: got {[r[0] for r in rows]}"
    for r in rows: assert r[1].startswith("https://unitaryplan.aucklandcouncil.govt.nz/") and r[2] and r[3]

def test_every_numeric_rule_has_provenance(cur):
    cur.execute("SELECT count(*) FROM analytics.rules WHERE topic NOT IN ('activity_status','standard_text') AND (quote IS NULL OR source_url IS NULL OR last_verified IS NULL OR section_ref IS NULL OR chunk_id IS NULL OR plan_version_id IS NULL)")
    assert cur.fetchone()[0] == 0

def test_plan_version_recorded(cur):
    cur.execute("SELECT status FROM analytics.plan_versions WHERE plan_name = 'Auckland Unitary Plan'"); assert cur.fetchone()[0] == "operative"


MAORI = [("Special Purpose - Māori Purpose Zone", "building_height_max", 8), ("Special Purpose - Māori Purpose Zone", "maori_cultural_buildings_height_max", 10),
         ("Special Purpose - Māori Purpose Zone", "building_coverage_max_pct", 50), ("Special Purpose - Māori Purpose Zone", "impervious_max_pct", 60),
         ("Māori land (Auckland-wide, E20)", "building_coverage_max_pct_rural_zones_maori_land", 20)]

@pytest.mark.parametrize("zone,param,expected", MAORI)
def test_maori_numeric(cur, zone, param, expected):
    assert val(cur, zone, param) == expected

def test_maori_purpose_dwelling_activity_statuses(cur):
    for prefix, st in (("Up to three dwellings per site", "P"), ("Four or more dwellings per site", "RD"), ("Marae", "P")):
        cur.execute("SELECT value_text FROM analytics.rules WHERE topic = 'activity_status' AND zone = 'Special Purpose - Māori Purpose Zone' AND activity ILIKE %s ORDER BY id LIMIT 1", (prefix + "%",))
        assert cur.fetchone()[0] == st

def test_e20_papakainga_statuses(cur):
    cur.execute("SELECT parameter, value_text FROM analytics.rules WHERE zone = 'Māori land (Auckland-wide, E20)' AND topic = 'activity_status'")
    got = dict(cur.fetchall()); assert got["A1"] == "P" and got["A2"] == "RD" and got["A3"] == "P" and got["A4"] == "RD" and got["A6"] == "NC"

def test_rest_home_definition_searchable(cur):
    cur.execute("SELECT section_ref, snippet FROM analytics.search_rules('supported residential care rest home certified Health and Disability Services', 'J1', 5)")
    rows = cur.fetchall(); assert any(r[0] == "J1.4 Supported residential care" for r in rows), [r[0] for r in rows]

def test_maori_land_search(cur):
    cur.execute("SELECT section_ref FROM analytics.search_rules('papakāinga marae dwellings Māori land activity table', 'E20', 3)")
    assert "E20.4" in [r[0] for r in cur.fetchall()]

def test_read_only_role_cannot_write(cur):
    with pytest.raises(psycopg.errors.Error):
        cur.execute("DELETE FROM analytics.rules")
