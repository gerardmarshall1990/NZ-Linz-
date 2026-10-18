"""Call sheets, route plans and one-page briefs (MASTER_SPEC Part 4 section 5.3; behind the outreach flag). From a shortlist or a parcel list: stops are clustered by suburb and ordered by nearest neighbour from a start point.
DISTANCES ARE STRAIGHT-LINE: no routing engine (OSRM / pgRouting with an NZ extract) is installed, so no drive times are claimed. The counterparty is the landlord or managing agent, never a tenant. Briefs ask honest questions and make no promises.
Objection answers are yours to write ([TO COMPLETE]): nothing is scripted for you."""
import json, math
from fastapi import HTTPException
from . import audit, screenapi
from .db import conn
from .pack_pdf import md_to_pdf

def hav(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b; p = math.pi / 180; x = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(x))

def order(stops: list[dict], start: tuple | None = None) -> list[dict]:
    rest = list(stops); out = []; cur = start or ((rest[0]["lat"], rest[0]["lon"]) if rest else None)
    while rest:
        nxt = min(rest, key=lambda s: hav(cur, (s["lat"], s["lon"]))); out.append({**nxt, "leg_km": round(hav(cur, (nxt["lat"], nxt["lon"])), 2)}); cur = (nxt["lat"], nxt["lon"]); rest.remove(nxt)
    return out

def brief_md(row: dict) -> str:
    walk = row.get("walk_away_rent"); return "\n".join([f"### {row['address'] or row['parcel_id']} ({row['suburb'] or ''})", f"- Why it may fit: zone {row['zone']}; {row['beds_base']} beds estimated; title {row['title_type'] or 'unknown'}", f"- Bedrooms and confidence: {row['beds_base']} ({row['beds_tier']}: {row['beds_source']})",
        "- Layout status: " + ("known (confirmed plan)" if row["beds_tier"] == "CONFIRMED" else "unknown: request plans or capture on site with permission"),
        f"- Indicative offer ceiling (walk-away rent): {'needs input' if walk is None else '$%s per week' % format(round(float(walk)), ',')} (screening; uses placeholders: {row['uses_placeholders']})",
        "- Pitch points (honest): income during the conversion where agreed, a professional operator, the owner keeps the building; consents and certification are conditions that may not be met",
        "- Objections and answers: [TO COMPLETE: your answers]", "- Ask for: floor plans, consent history, current lease terms, compliance schedule", "- Counterparty: the landlord or managing agent as published. Never the tenant.", ""])

def build(parcel_ids: list[int], name: str, start: tuple | None = None, save: bool = True) -> dict:
    if not parcel_ids: raise HTTPException(422, "no parcels")
    rows = []
    for pid in parcel_ids:
        e = screenapi.explain_parcel(pid)
        if e["candidate"]: rows.append(e["row"])
    if not rows: raise HTTPException(409, "none of these parcels is a screening candidate")
    clusters = {}
    for r in rows: clusters.setdefault(r["suburb"] or "unknown suburb", []).append(r)
    plan = []; L = [f"# Call sheet: {name}", "Draft for your use. Straight-line distances only (no routing engine installed). Never approach tenants. Outreach rules apply: confirm source and lawful basis before any contact.", ""]
    for sub, rs in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        o = order(rs, start); plan.append({"suburb": sub, "stops": [{"parcel_id": s["parcel_id"], "address": s["address"], "leg_km": s["leg_km"], "lat": s["lat"], "lon": s["lon"]} for s in o]})
        L += [f"## {sub} ({len(o)} stops, about {round(sum(s['leg_km'] for s in o), 1)} km straight-line)"] + [f"{i}. {s['address'] or s['parcel_id']} (+{s['leg_km']} km)" for i, s in enumerate(o, 1)] + [""] + [brief_md(s) for s in o]
    md = "\n".join(L); rid = None
    if save:
        with conn() as c: rid = c.execute("INSERT INTO core.user_route_plan (name, source, stops) VALUES (%s,%s,%s::jsonb) RETURNING id", (name, "parcel list", json.dumps(plan))).fetchone()["id"]; c.commit()
    audit.log("call_sheet", "route_plan", rid, {"stops": len(rows)})
    return {"id": rid, "name": name, "plan": plan, "markdown": md, "distance_basis": "straight-line"}

def pdf(md: str) -> bytes: return md_to_pdf(md, "", stamp="Call sheet: draft")
