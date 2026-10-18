"""Retrofit calibration loop (MASTER_SPEC Part 3 section 5.3): the owner enters real quotes or invoices per rate line; the tool compares each with the current model rate, stores the variance, and can re-base a line's
low/base/high from the quotes (min / median / max of the quoted unit rates) with the quote count as its source. Percentage lines (preliminaries, fees, contingency) are not calibrated from line quotes.
A single quote gives no range: applying it needs an explicit accept, and low=base=high is then flagged. Applying writes through settings.set_rates, so it is in the change history and can be undone by re-entering a rate."""
import statistics
from datetime import date
from fastapi import HTTPException
from . import retrofit, settings
from .db import conn

def _lines() -> dict: return retrofit.rates()["lines"]

def add_quote(line: str, source: str, quote_date: date, quantity: float, amount_ex_gst: float, description: str | None = None, unit: str | None = None, region: str = "Auckland",
              parcel_id: int | None = None, option_id: int | None = None, note: str | None = None) -> dict:
    if line not in _lines(): raise HTTPException(422, f"unknown rate line {line!r}")
    if not (source or "").strip(): raise HTTPException(422, "a quote needs a source (supplier / QS / invoice number)")
    if quote_date > date.today(): raise HTTPException(422, "quote date is in the future")
    if quantity <= 0 or amount_ex_gst < 0: raise HTTPException(422, "quantity must be positive and the amount not negative")
    unit = unit or _lines()[line]["unit"]
    with conn() as c:
        r = c.execute("""INSERT INTO core.rh_quote (line, description, source, quote_date, region, quantity, unit, amount_ex_gst, parcel_id, option_id, note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                      (line, description, source.strip(), quote_date, region, quantity, unit, amount_ex_gst, parcel_id, option_id, note)).fetchone(); c.commit()
    return summary_for(line)

def void_quote(qid: int) -> dict:
    with conn() as c:
        r = c.execute("UPDATE core.rh_quote SET voided = true WHERE id=%s RETURNING line", (qid,)).fetchone(); c.commit()
    if not r: raise HTTPException(404, "no such quote")
    return summary_for(r["line"])

def _quotes(line: str | None = None) -> list[dict]:
    with conn() as c:
        return c.execute("SELECT * FROM core.rh_quote WHERE NOT voided" + (" AND line = %s" if line else "") + " ORDER BY quote_date, id", (line,) if line else ()).fetchall()

def _unit_rate(q) -> float: return float(q["amount_ex_gst"]) / float(q["quantity"])

def summary_for(line: str) -> dict:
    cfg = settings.rates_cfg()["lines"][line]; qs = _quotes(line); model = cfg.get("base")
    rows = [{"id": q["id"], "source": q["source"], "date": q["quote_date"].isoformat(), "region": q["region"], "quantity": float(q["quantity"]), "unit": q["unit"], "amount_ex_gst": float(q["amount_ex_gst"]),
             "unit_rate": round(_unit_rate(q), 2), "variance_vs_model_pct": round((_unit_rate(q) - model) / model * 100, 1) if model else None, "description": q["description"]} for q in qs]
    rates = [r["unit_rate"] for r in rows]
    prop = None
    if rates:
        prop = {"low": min(rates), "base": round(statistics.median(rates), 2), "high": max(rates), "n_quotes": len(rates), "single_quote": len(rates) == 1}
    return {"line": line, "unit": cfg["unit"], "model_rate": {k: cfg.get(k) for k in ("low", "base", "high", "source", "date")}, "n_quotes": len(rows), "quotes": rows, "proposed": prop,
            "model_vs_quotes_variance_pct": round((statistics.median(rates) - model) / model * 100, 1) if rates and model else None}

def overview() -> dict:
    lines = {k: summary_for(k) for k in _lines()}
    return {"lines": {k: {"unit": v["unit"], "n_quotes": v["n_quotes"], "model_base": v["model_rate"]["base"], "median_quote_rate": v["proposed"]["base"] if v["proposed"] else None, "variance_pct": v["model_vs_quotes_variance_pct"]} for k, v in lines.items()},
            "note": "n_quotes is how many real quotes calibrate each line. Zero means the line still rests on the rate you typed (or is blank)."}

def apply(line: str, accept_single_quote: bool = False, note: str | None = None) -> dict:
    s = summary_for(line); p = s["proposed"]
    if not p: raise HTTPException(409, "no quotes for this line")
    if p["single_quote"] and not accept_single_quote: raise HTTPException(409, "only one quote: it gives no low/high range. Add another quote, or apply with accept_single_quote to set low = base = high")
    ids = [q["id"] for q in s["quotes"]]; dates = [q["date"] for q in s["quotes"]]
    src = f"calibrated from {p['n_quotes']} quote(s): " + "; ".join(sorted({q['source'] for q in s['quotes']}))[:200]
    new = {"low": p["low"], "base": p["base"], "high": p["high"], "source": src, "date": max(dates)}
    old = settings.rates_cfg()["lines"][line]
    settings.set_rates({line: new}, None)
    with conn() as c:
        c.execute("INSERT INTO core.rh_rate_calibration (line, old_rate, new_rate, n_quotes, quote_ids, note) VALUES (%s,%s::jsonb,%s::jsonb,%s,%s,%s)",
                  (line, __import__("json").dumps({k: old.get(k) for k in ("low", "base", "high", "source", "date")}), __import__("json").dumps(new), p["n_quotes"], ids, note)); c.commit()
    return {"applied": new, "single_quote": p["single_quote"], **summary_for(line)}

def history() -> list[dict]:
    with conn() as c: rows = c.execute("SELECT id, line, old_rate, new_rate, n_quotes, applied_at, note FROM core.rh_rate_calibration ORDER BY id DESC LIMIT 200").fetchall()
    return [{**r, "applied_at": r["applied_at"].isoformat()} for r in rows]
