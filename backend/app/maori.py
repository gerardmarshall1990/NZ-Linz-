"""Māori land module (MASTER_SPEC Part 2 section 10). Partnership-first: the tool NEVER describes Māori land as 'for sale'. It reports (1) whether the parcel is flagged Māori in LINZ or zoned Māori Purpose, (2) the gap between LINZ-flagged parcels and the Te Puni Kōkiri / Māori Land Court public data
(blank until you load an export), (3) the entity to approach where that data names one (otherwise unknown), (4) the approval route as a checklist for a lawyer experienced in Te Ture Whenua Māori Act to confirm, (5) zone rules and an indicative scheme via the layout engine, (6) a proposal outline with
[TO COMPLETE] sections, and (7) a transportable-homes note. Nothing is public-data scraped; restricted data is not accessed."""
from fastapi import HTTPException
from .db import conn
from .pack_pdf import md_to_pdf
from .stamp import STAMP

PATHWAY = ["Confirm the land's status and its governing body (trust, incorporation or owners) from the Māori Land Court record: the record, not this tool, is authoritative",
           "Identify the trustees or the owners' meeting that must resolve to enter any lease or joint venture, and what their governance documents require",
           "Check whether Māori Land Court involvement or confirmation is needed for the arrangement (a lawyer experienced in Te Ture Whenua Māori Act confirms the steps)",
           "Approach as a partner: introduce the intended use and the benefits to the owners; leave decisions and timing to them; no pressure and no price talk before they ask",
           "Agree the commercial structure (lease or joint venture) with legal advice on both sides; conditions precedent for consents and finance"]
NEVER = "This land is not described as 'for sale'. The route is a lease or a joint venture with the owners, led by their trustees or governing body."

def _tpk_table() -> bool:
    with conn() as c: return c.execute("SELECT to_regclass('raw.manual_maori_land') AS t").fetchone()["t"] is not None

def tpk_gap() -> dict:
    with conn() as c: n = c.execute("SELECT count(*) AS n FROM core.sites WHERE maori_land_linz").fetchone()["n"]
    return {"linz_flagged_parcels": n, "tpk_rows_loaded": 0 if not _tpk_table() else None,
            "note": "No Te Puni Kōkiri / Māori Land Court export is loaded, so the cross-check cannot be made. Drop a public export in docs/sources_manual/tpk_maori_land/ and run `make manual`." if not _tpk_table() else "export loaded: matching is by block name and is a human review"}

def get(parcel_id: int, unit: dict | None = None) -> dict:
    with conn() as c:
        s = c.execute("SELECT parcel_id, address, zone_name, area_m2::float AS area, maori_land_linz, title_type, appellation FROM core.sites WHERE parcel_id=%s", (parcel_id,)).fetchone()
        note = (c.execute("SELECT data FROM core.user_maori_note WHERE parcel_id=%s", (parcel_id,)).fetchone() or {}).get("data") or {}
    if not s: raise HTTPException(404, "no such parcel")
    maori_zone = "ori Purpose" in (s["zone_name"] or ""); flagged = bool(s["maori_land_linz"])
    out = {"parcel_id": parcel_id, "address": s["address"], "zone": s["zone_name"], "area_m2": s["area"], "linz_maori_flag": flagged, "maori_purpose_zone": maori_zone, "is_relevant": flagged or maori_zone, "never_for_sale": NEVER,
           "entity_to_approach": note.get("entity") or {"status": "unknown", "note": "Not in the loaded data. Find the owning trust or incorporation from the Māori Land Court public record and enter it here."},
           "approval_pathway": PATHWAY, "route": "lease or joint venture", "tpk_gap": tpk_gap(),
           "transportable_homes": {"relocation_rules": "UNKNOWN: not in the rules corpus (building consent and relocated building requirements: confirm with the Council)", "foundations": "NEEDS_PROFESSIONAL: engineer", "wastewater": "If the land is not reticulated, on-site wastewater (a TP58-type design by a qualified designer) is likely: confirm servicing"}}
    if unit and unit.get("width_m") and unit.get("depth_m"):
        from . import devscenarios
        r = devscenarios.run(parcel_id, {"typology": "transportable", "unit": unit, "finance": {}, "access_width_m": None})
        out["indicative_scheme"] = {"status": r.get("status"), "units": (r.get("scenarios") or [{}])[0].get("unit_count"), "binding": r.get("binding_constraint"), "badge": r.get("badge_label"), "note": "Concept layout from the zone rules; not a design. Rules for the Māori Purpose zone are used as loaded."}
    return out

def set_entity(parcel_id: int, name: str, role: str | None, source: str) -> dict:
    if not (name or "").strip() or not (source or "").strip(): raise HTTPException(422, "name and source (where you found it, for example the Māori Land Court public record) are required")
    import json
    with conn() as c: c.execute("INSERT INTO core.user_maori_note (parcel_id, data) VALUES (%s,%s::jsonb) ON CONFLICT (parcel_id) DO UPDATE SET data=EXCLUDED.data, updated_at=now()", (parcel_id, json.dumps({"entity": {"status": "entered by you", "name": name.strip(), "role": role, "source": source.strip()}}))); c.commit()
    return get(parcel_id)

def outline_md(parcel_id: int, unit: dict | None = None) -> str:
    d = get(parcel_id, unit); e = d["entity_to_approach"]
    L = [f"**{STAMP}**", "", f"# Proposal outline (partnership first): {d['address']}", "", f"_{NEVER}_", "", "## Who we would speak with", f"{e.get('name') or '[TO COMPLETE: owning trust or governing body, from the Māori Land Court record]'}",
         "", "## Why this land and this use", "[TO COMPLETE: intended use and why it suits the land and the owners]", "", "## Benefits to the owners", "[TO COMPLETE: income, employment, retained ownership, kaitiakitanga considerations, as discussed with the owners]", "",
         "## Indicative scheme"]
    sch = d.get("indicative_scheme"); L += [f"Concept only: {sch['units']} units fit under the zone rules as loaded ({sch['badge']})." if sch and sch.get("units") else "[TO COMPLETE: run the indicative scheme with a unit size]"]
    L += ["", "## Servicing", "[TO COMPLETE: water, wastewater, power; capacity is unknown until confirmed in writing by the providers]", "", "## Timelines", "[TO COMPLETE: in broad terms, agreed with the owners' pace]", "",
          "## Who approves", "\n".join(f"{i}. {p}" for i, p in enumerate(d["approval_pathway"], 1)), "", "## Next step", "[TO COMPLETE: an introduction through the trustees]"]
    return "\n".join(L)
