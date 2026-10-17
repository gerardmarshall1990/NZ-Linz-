"""Rest home layout options as room-level demolition / new-work actions over the as-built model (MASTER_SPEC 7.3 step 5).
Three options. They use only what the confirmed plans show (room types, areas, adjacency). Rules that are regulatory (min room area, ensuite ratio, double occupancy,
communal area per bed) apply only when filled in config/bed_rules.yaml; otherwise the option says the rule is not applied. Natural hazard data is never read here (decision 13).
Wall moves, structure, fire and services are the designer's work: this engine only decides what each existing room becomes."""
import json
from fastapi import HTTPException
from . import bedrules
from .db import conn
from .model_view import adjacency, confirmed_levels

SCENARIOS = {
    "conservative": "Keep what already works: only bedrooms that already have an adjacent ensuite become resident rooms.",
    "base": "Also add ensuites to bedrooms (convert an adjacent bathroom, else build one in the room).",
    "max": "As base, and convert spare non-essential rooms into resident rooms with new ensuites.",
}

def _plan(level: dict, scenario: str, d: dict, minarea) -> dict:
    rooms = {r["id"]: r for r in level["rooms"]}; adj = adjacency(level["rooms"], d["adjacency_distance_m"], d["min_shared_wall_m"])
    acts = {rid: {"room_id": rid, "label": r["label"], "type": r["type"], "action": "keep", "becomes": r["type"], "items": [], "note": None} for rid, r in rooms.items()}
    near = lambda rid, t: [o for o in adj.get(rid, ()) if rooms[o]["type"] == t]
    area_ok = lambda r: None if (minarea is None or r["area_m2"] is None) else r["area_m2"] >= minarea
    lost = {"too_small": 0, "no_ensuite": 0, "communal_roles": 0}
    resident = []
    beds_cands = [r for r in level["rooms"] if r["type"] == "bedroom"]
    for r in beds_cands:
        if area_ok(r) is False: lost["too_small"] += 1; acts[r["id"]]["note"] = f"below minimum room area {minarea} m2"; continue
        if near(r["id"], "ensuite"): resident.append(r["id"]); continue
        if scenario == "conservative": lost["no_ensuite"] += 1; acts[r["id"]]["note"] = "no adjacent ensuite: not counted in this option"; continue
        bath = near(r["id"], "bathroom")
        if bath: acts[bath[0]].update(action="convert", becomes="ensuite", items=["convert bathroom to private ensuite (new fixtures/door, designer to detail)"])
        else: acts[r["id"]]["items"].append("new ensuite built within the room: check remaining room area")
        resident.append(r["id"])
    if scenario == "max":
        seen = set()
        for r in level["rooms"]:
            role = "lounge" if r["type"] == "dining" else r["type"]      # dining counts as the lounge/dining role
            if role not in ("store", "other", "lounge", "office") or area_ok(r) is False: continue
            if role in d["required_roles"] and role not in seen: seen.add(role); continue   # keep the first of every required role on the level
            acts[r["id"]].update(action="convert", becomes="resident room", items=["change of use to resident room", "new ensuite (designer to locate)"]); resident.append(r["id"])
    # roles every rest home needs: sacrifice a resident room if the level has none (only when the whole building lacks it: handled in plan_option)
    return {"rooms": acts, "resident": resident, "lost": lost, "adj": {k: sorted(v) for k, v in adj.items()}}

def plan_option(parcel_id: int, scenario: str) -> dict:
    if scenario not in SCENARIOS: raise HTTPException(422, f"scenario must be one of {list(SCENARIOS)}")
    levels = confirmed_levels(parcel_id)
    if not levels: raise HTTPException(409, "no human-confirmed plan levels: confirm the plan reader output first")
    d = bedrules.design(); minarea = bedrules.reg("min_resident_room_m2")
    unscaled = [l["level_name"] for l in levels if not l["calibrated"]]
    plans = [_plan(l, scenario, d, minarea) for l in levels]
    all_types = {r["type"] for l in levels for r in l["rooms"]}
    roles_missing = [t for t in d["required_roles"] if t not in all_types and not (t == "lounge" and "dining" in all_types)]
    # sacrifice resident rooms (those that need the most work first) to create each missing role
    resident = [(i, rid) for i, p in enumerate(plans) for rid in p["resident"]]
    sacrificed = []
    for role in roles_missing:
        if not resident: break
        def cost(x): i, rid = x; return (len(plans[i]["rooms"][rid]["items"]), -(levels[i]["rooms"][[r["id"] for r in levels[i]["rooms"]].index(rid)]["area_m2"] or 0))
        i, rid = max(resident, key=cost)       # the room needing most new work (and the smallest) goes first
        resident.remove((i, rid)); plans[i]["resident"].remove(rid)
        plans[i]["rooms"][rid].update(action="convert", becomes=role, items=[f"change of use to {role} (required role missing from the building)"]); sacrificed.append({"room": rid, "level": levels[i]["level_name"], "role": role})
    occupancy = 2 if bedrules.reg("double_occupancy_allowed") is True else 1
    beds = len(resident) * occupancy
    # binding constraint: what the option lost
    lost_total = {k: sum(p["lost"][k] for p in plans) for k in ("too_small", "no_ensuite")}
    lost_total["communal_roles"] = len(sacrificed)
    bound = max(lost_total, key=lambda k: lost_total[k]); binding = (f"{bound.replace('_', ' ')} (cost {lost_total[bound]} candidate rooms)" if lost_total[bound] > 0
                                                                      else "none of the modelled constraints; exits, fire, corridor widths and room-size rules are not modelled here")
    new_items = sum(len(a["items"]) for p in plans for a in p["rooms"].values())
    return {"scenario": scenario, "description": SCENARIOS[scenario], "beds": beds, "resident_rooms": len(resident), "occupancy_per_room": occupancy,
            "levels": [{"extraction_id": l["extraction_id"], "level_name": l["level_name"], "calibrated": l["calibrated"], "rooms": list(p["rooms"].values()), "resident": p["resident"]} for l, p in zip(levels, plans)],
            "roles_missing": roles_missing, "sacrificed": sacrificed, "lost": lost_total, "binding_constraint": binding, "below_target": beds < d["target_beds"], "target_beds": d["target_beds"],
            "new_work_items": new_items, "unscaled_levels": unscaled,
            "rules_not_applied": bedrules.missing_regulatory(),
            "warnings": ["Room-level options only: wall moves, structure, fire, services and exits are for the designer and engineers.",
                         *([f"Regulatory rules not applied (not yet sourced): {', '.join(bedrules.missing_regulatory())}. Beds shown ignore them."] if bedrules.missing_regulatory() else []),
                         *([f"Levels without a scale: {', '.join(unscaled)}. Drawings cannot be produced for them."] if unscaled else []),
                         "Only levels with confirmed plans are counted; levels not uploaded are unknown."]}

def generate(parcel_id: int, by: str = "owner") -> list[dict]:
    levels = confirmed_levels(parcel_id); ids = [l["extraction_id"] for l in levels]
    out = []
    with conn() as c:
        c.execute("DELETE FROM core.rh_layout_option WHERE parcel_id = %s AND status = 'draft'", (parcel_id,))
        for s in SCENARIOS:
            o = plan_option(parcel_id, s)
            r = c.execute("""INSERT INTO core.rh_layout_option (parcel_id, scenario, beds, binding_constraint, below_target, option, extraction_ids, rules_snapshot, created_by)
                             VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s) RETURNING id""", (parcel_id, s, o["beds"], o["binding_constraint"], o["below_target"], json.dumps(o), ids, json.dumps(bedrules.load()), by)).fetchone()
            out.append({"id": r["id"], **o})
        c.commit()
    return out

def get_option(oid: int) -> dict:
    with conn() as c: r = c.execute("SELECT * FROM core.rh_layout_option WHERE id = %s", (oid,)).fetchone()
    if not r: raise HTTPException(404, "no such option")
    return {"id": r["id"], "parcel_id": r["parcel_id"], "status": r["status"], "created_at": r["created_at"].isoformat(), **r["option"]}

def list_options(parcel_id: int) -> list[dict]:
    with conn() as c: ids = [r["id"] for r in c.execute("SELECT id FROM core.rh_layout_option WHERE parcel_id = %s ORDER BY id", (parcel_id,)).fetchall()]
    return [get_option(i) for i in ids]
