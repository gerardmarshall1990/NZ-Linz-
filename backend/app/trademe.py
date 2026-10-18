"""Trade Me rentals connector, ready for keys (MASTER_SPEC Part 6 section 1, Part 4 section 2). Official API only: no scraping. It stays OFF until BOTH are true: the owner has read Trade Me's developer terms and set
`trademe.status: live` in config/listing_sources.yaml, and the keys are present as environment variables (TRADEME_CONSUMER_KEY, TRADEME_CONSUMER_SECRET, TRADEME_TOKEN, TRADEME_TOKEN_SECRET). Until then CSV import is the route.
UNVERIFIED against the live API (no keys, and api.trademe.co.nz is not reachable from the sandbox): the endpoint, parameters and field names below are from Trade Me's public documentation as I know it and must be checked
when keys arrive. Only structured facts are kept (address, rent, beds, baths, dates, URL); no photos or description text are stored. Requests are rate limited and identify the app."""
import os, time
from datetime import date
from fastapi import HTTPException
from . import listings

ENDPOINT = "https://api.trademe.co.nz/v1/Search/Property/Rental.json"
USER_AGENT = "nz-rest-home-screening/0.1 (owner use)"
MIN_INTERVAL_S = 2.0
_last = [0.0]
KEYS = ("TRADEME_CONSUMER_KEY", "TRADEME_CONSUMER_SECRET", "TRADEME_TOKEN", "TRADEME_TOKEN_SECRET")

def status() -> dict:
    src = listings.sources()["sources"].get("trademe", {}); have = {k: bool(os.environ.get(k)) for k in KEYS}
    ready = src.get("status") == "live" and all(have.values())
    return {"source_status": src.get("status"), "keys_present": have, "ready": ready,
            "blockers": ([] if src.get("status") == "live" else ["owner has not read the Trade Me developer terms and set trademe.status to live in config/listing_sources.yaml (BLOCKERS 2)"]) + [f"{k} not set" for k, v in have.items() if not v],
            "fallback": "CSV import (Import tab) works today", "unverified": "endpoint and field names unverified against the live API"}

def auth_header() -> str:
    """OAuth 1.0a with the PLAINTEXT signature method over HTTPS (as Trade Me documents it; verify when keys arrive)."""
    e = os.environ
    return ('OAuth oauth_consumer_key="%s", oauth_token="%s", oauth_signature_method="PLAINTEXT", oauth_signature="%s&%s"' % (e["TRADEME_CONSUMER_KEY"], e["TRADEME_TOKEN"], e["TRADEME_CONSUMER_SECRET"], e["TRADEME_TOKEN_SECRET"]))

def map_listing(x: dict) -> dict:
    """One API result -> the CSV row the importer takes. Structured facts only."""
    rent = x.get("RentPerWeek")
    lid = x.get("ListingId")
    return {"source_id": str(lid) if lid is not None else "", "address": x.get("Address") or "", "suburb": x.get("Suburb") or "", "rent_per_week": rent if isinstance(rent, (int, float)) else "",
            "bedrooms": x.get("Bedrooms") if x.get("Bedrooms") is not None else "", "bathrooms": x.get("Bathrooms") if x.get("Bathrooms") is not None else "", "listing_type": "rent",
            "url": f"https://www.trademe.co.nz/a/property/residential/rent/listing/{lid}" if lid is not None else ""}

def to_csv(results: list[dict]) -> str:
    import csv, io
    out = io.StringIO(); w = csv.DictWriter(out, fieldnames=["source_id", "address", "suburb", "rent_per_week", "bedrooms", "bathrooms", "listing_type", "url"]); w.writeheader()
    for x in results:
        row = map_listing(x)
        if row["source_id"] and row["address"]: w.writerow(row)
    return out.getvalue()

def fetch(params: dict, http=None) -> list[dict]:
    st = status()
    if not st["ready"]: raise HTTPException(503, {"trademe": "not ready", "blockers": st["blockers"], "fallback": st["fallback"]})
    wait = MIN_INTERVAL_S - (time.time() - _last[0])
    if wait > 0: time.sleep(wait)
    _last[0] = time.time()
    import httpx
    r = (http or httpx).get(ENDPOINT, params={**params, "region": params.get("region", 1)}, headers={"Authorization": auth_header(), "User-Agent": USER_AGENT}, timeout=30)
    if r.status_code != 200: raise HTTPException(502, f"Trade Me answered {r.status_code}")
    return r.json().get("List", [])

def sync(params: dict, http=None) -> dict:
    csv_text = to_csv(fetch(params, http))
    return listings.import_csv(csv_text, "trademe", dry_run=False, snapshot=True)
