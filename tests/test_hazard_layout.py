"""Street-facing front edge, exclusion zones and the fine-grid packer used by the hazard report and the Develop tab."""
from shapely.geometry import box
from backend.app import devlayout, devrules, devscenarios

R0 = {"ols_ground_floor_min_area": {"v": 20.0, "unit": "m2", "section_ref": "T", "owner_verified": False, "last_verified": None},
      "ols_ground_floor_min_dimension": {"v": 4.0, "unit": "m", "section_ref": "T", "owner_verified": False, "last_verified": None}}

def test_front_edge_is_the_street_facing_edge_on_narrow_lots():
    s = devscenarios.load_site(5098060)                                             # 2 Parrish Road: 13 m wide, 40 m deep, address point near a side boundary
    assert s["front_from"].startswith("street-facing")
    B = devrules.classify_boundaries(s["poly"], s["front_point"]); assert 8 < sum(e.length for e in B["front"]) < 15       # the short street edge, not a 40 m side

def test_greedy_side_packing_fits_two_long_units_in_a_narrow_strip():
    strip = box(0, 0, 12, 40); unit = {"width_m": 4.0, "depth_m": 15.0, "height_m": 3.8, "gfa_m2": 60}
    placed = devlayout._pack_greedy(strip, unit, R0, 0.0, False, None, "side")
    assert len(placed) >= 4 and all(strip.buffer(1e-6).contains(u["footprint"].union(u["ols"])) for u in placed)
    assert all(not a["footprint"].union(a["ols"]).intersection(b["footprint"].union(b["ols"])).area > 1e-6 for i, a in enumerate(placed) for b in placed[i + 1:])
    assert all(u["ols"].area >= 20 - 1e-9 for u in placed)

def test_exclusion_zone_keeps_units_and_their_outdoor_space_out():
    strip = box(0, 0, 12, 40); unit = {"width_m": 4.0, "depth_m": 15.0, "height_m": 3.8, "gfa_m2": 60}
    free = devlayout._pack_greedy(strip, unit, R0, 0.0, False, None, "side"); block = box(0, 0, 12, 20)
    kept = devlayout._pack_greedy(strip, unit, R0, 0.0, False, block, "side")
    assert len(kept) < len(free) and all(not u["footprint"].intersects(block) and not u["ols"].intersects(block) for u in kept)
