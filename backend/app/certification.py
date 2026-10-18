"""Certification checklist and conditional-lease checklist per property (MASTER_SPEC Part 3 section 8). Status is the owner's; the app invents no Ministry step and no lead time.
Policy and document templates are skeletons marked [TO COMPLETE]: never a final policy."""
from functools import lru_cache
import yaml
from fastapi import HTTPException
from .config import ROOT
from .db import conn
from .facts import get_property
from .stamp import STAMP

@lru_cache
def cfg() -> dict: return yaml.safe_load((ROOT / "config" / "certification_checklist.yaml").read_text())

STATUSES = ("not_started", "in_progress", "done", "not_applicable")

def view(parcel_id: int) -> dict:
    get_property(parcel_id)
    with conn() as c: st = {r["key"]: r for r in c.execute("SELECT key, status, note FROM core.rh_cert_item WHERE parcel_id=%s", (parcel_id,)).fetchall()}
    def rows(items): return [{**i, "status": (st.get(i["key"]) or {}).get("status", "not_started"), "note": (st.get(i["key"]) or {}).get("note")} for i in items]
    cert, lease = rows(cfg()["certification"]), rows(cfg()["lease_conditions"])
    done = lambda r: sum(1 for x in r if x["status"] in ("done", "not_applicable"))
    return {"parcel_id": parcel_id, "source": cfg()["source"], "certification": cert, "lease_conditions": lease, "certification_done": f"{done(cert)}/{len(cert)}", "lease_done": f"{done(lease)}/{len(lease)}",
            "warning": "The Ministry's actual HealthCERT steps are not yet loaded (health.govt.nz blocks scripts). Confirm every step with the Ministry and your auditing agency."}

def set_status(parcel_id: int, key: str, status: str, note: str | None) -> dict:
    keys = {i["key"] for i in cfg()["certification"] + cfg()["lease_conditions"]}
    if key not in keys: raise HTTPException(404, "unknown checklist item")
    if status not in STATUSES: raise HTTPException(422, f"status must be one of {list(STATUSES)}")
    get_property(parcel_id)
    with conn() as c:
        c.execute("""INSERT INTO core.rh_cert_item (parcel_id, key, status, note) VALUES (%s,%s,%s,%s) ON CONFLICT (parcel_id, key) DO UPDATE SET status=EXCLUDED.status, note=EXCLUDED.note, updated_at=now()""", (parcel_id, key, status, note)); c.commit()
    return view(parcel_id)

def template(key: str) -> str:
    it = next((i for i in cfg()["certification"] if i["key"] == key), None)
    if not it: raise HTTPException(404, "no such certification item")
    return "\n".join([f"**TEMPLATE ONLY: NOT A POLICY. {STAMP}**", "", f"# {it['title']}", "", "This is a skeleton for the operator's clinical lead to complete. It contains no policy content.", "",
                      "## Purpose", "[TO COMPLETE: purpose]", "", "## Scope", "[TO COMPLETE: scope]", "", "## Requirement it responds to", "[TO COMPLETE: clause of Ngā Paerewa NZS 8134:2021 (standard not yet loaded)]", "",
                      "## Procedure", "[TO COMPLETE: steps]", "", "## Responsible person", "[TO COMPLETE: role]", "", "## Review date", "[TO COMPLETE: date]", "", "## Signed off by", "[TO COMPLETE: name, role, date]"])
