"""Vehicle access (AUP E27): every quoted figure must occur verbatim in the extracted Council text, and the width check follows the table."""
import re, pytest
from shapely.geometry import box
from backend.app import transport
from backend.app.config import ROOT

def norm(t): return re.sub(r"\s+", " ", t.replace("–", "-")).strip()

def test_every_quote_is_in_the_council_text():
    txt = norm(next((ROOT / "data/aup/txt").rglob("E27 Transport.txt")).read_text()); R = transport.rules()
    quotes = [r["quote"] for r in R["width_rows"]] + [R["passing_bay"]["quote"], R["gradient"]["rear_site"]["quote"], R["gradient"]["other_residential"]["quote"]]
    for q in quotes: assert norm(q) in txt, q
    assert norm(R["crossing_note"]) in txt
    assert [r["corridor_clear_m"] for r in R["width_rows"]] == [3.0, 3.5, 5.5]

def test_width_check():
    ok = transport.check(2, box(0, 0, 3.5, 20)); assert ok["status"] == "NEEDS_PROFESSIONAL" and ok["measured"] == 3.5 and ok["required"] == 3.5 and "gradient" in ok["note"].lower()      # 4 spaces -> 3 to 9 row
    two = transport.check(1, box(0, 0, 3.0, 20)); assert two["required"] == 3.0 and two["status"] == "NEEDS_PROFESSIONAL"
    bad = transport.check(2, box(0, 0, 3.0, 20)); assert bad["status"] == "FAIL" and bad["required"] == 3.5
    big = transport.check(6, box(0, 0, 4.0, 20)); assert big["status"] == "FAIL" and big["required"] == 5.5                # 12 spaces -> two-way
    none = transport.check(1, None); assert none["status"] == "NEEDS_PROFESSIONAL" and "Auckland Transport" in none["note"]

def test_driveway_drawn_at_exactly_the_required_width_passes_despite_rounding():
    assert transport.check(3, box(0, 0, 3.4999999, 20))["status"] == "NEEDS_PROFESSIONAL"        # 6 spaces -> 3.5 m corridor
    assert transport.check(3, box(0, 0, 3.4, 20))["status"] == "FAIL"
