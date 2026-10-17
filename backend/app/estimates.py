"""Auto-estimates for the Property Record (Part 3 section 1.2 step 1). Every value is ESTIMATED, with the method stated. Nothing is guessed:
storeys and bedrooms are NOT derivable from LINZ data, so storeys stay blank and 'bedrooms_total' is only offered as a unit-count proxy with a loud note."""
from .db import conn
from .facts import set_fact

def auto_estimates(parcel_id: int) -> list[dict]:
    done = []
    with conn() as c:
        s = c.execute("SELECT building_count, total_footprint_m2::float AS tf, largest_footprint_m2::float AS lf, address_count, title_type FROM core.sites WHERE parcel_id = %s", (parcel_id,)).fetchone()
        if not s: return done
        def put(field, value, method, note=None):
            if value is None: return
            if set_fact(c, parcel_id, field, value, "LINZ open data (auto-estimate)", "ESTIMATED", method, note, by="system"): done.append({"field": field, "value": value, "method": method})
        put("building_count", s["building_count"], "count of LINZ building outlines whose point-on-surface lies in the parcel", "outlines may include sheds and garages")
        if s["building_count"]:
            put("footprint_total_m2", s["tf"], "sum of LINZ building outline areas assigned to the parcel", "footprint is not floor area: storeys unknown")
            put("footprint_largest_m2", s["lf"], "largest LINZ building outline on the parcel")
        put("address_points_on_parcel", s["address_count"], "count of LINZ address points inside the parcel")
        if s["address_count"] and s["address_count"] >= 2:
            put("bedrooms_total", s["address_count"], "UNIT COUNT proxy: LINZ address points on the parcel",
                "NOT a bedroom count: motels often have one address point per unit but this is unverified. Replace with listing, council file or plan data.")
        if s["title_type"]: put("title_type", s["title_type"], "LINZ NZ Property Titles type via parcel title number")
        c.commit()
    return done
