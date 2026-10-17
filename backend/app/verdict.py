"""Rest home potential verdict per listing (MASTER_SPEC Part 6.2) and house-scale minimum beds (Part 4 section 3.2). Pure functions.
GREEN / AMBER / RED / GREY are screening labels only: they never claim a conversion is cleared or certain to work. Natural hazard data is returned for information only and is never read by the logic (decision 13).
Without the economic inputs the label is GREY (not enough data), never a guess."""
import math
from . import economics as E
from .tiers import lowest

ACTIVITY_OK = {"permitted", "controlled", "restricted_discretionary", "discretionary"}     # a consent path exists
ACTIVITY_BLOCKED = {"non_complying", "prohibited"}

def per_bed_margin(p: dict) -> float:
    """Weekly net contribution of one extra bed at the stabilised occupancy (revenue - food - supplies - rostered staff share)."""
    return p["stabilised_occupancy"] * (p["fee_per_bed_per_week"] - p["food_per_occupied_bed_per_week"] - p["supplies_per_occupied_bed_per_week"]) - p["staff_positions_per_8_beds"] / 8 * p["staff_wage_per_week"] * p["roster_coverage_multiplier"]

def minimum_beds(p: dict) -> dict:
    """Smallest bed count that reaches the minimum acceptable profit and the target profit, with rent = 0 (rent is then tested against the walk-away rent).
    N(b) = b x margin - fixed other; retrofit charge = k x (retrofit per bed x b) where k is the weekly charge per dollar of retrofit. Solved in closed form (all terms are linear in beds)."""
    need = E.missing(p, E.OPEX_KEYS) + E.missing(p, ["stabilised_occupancy", "retrofit_cost_per_bed_screening", "minimum_acceptable_profit_per_year"])
    ch = E.retrofit_charge_weekly(1.0, p)
    need += ch["needs_input"]
    if need: return {"needs_input": sorted(set(need)), "minimum_beds": None, "target_beds": None}
    m = per_bed_margin(p); k = ch["weekly"]; fixed = E.operating(8, p["stabilised_occupancy"], p)["fixed_other"]
    net_per_bed = m - k * p["retrofit_cost_per_bed_screening"]
    def solve(profit_week): return None if net_per_bed <= 0 else max(1, math.ceil((fixed + profit_week) / net_per_bed))
    mn = solve(p["minimum_acceptable_profit_per_year"] / E.W); tg = solve(p["target_profit_per_year"] / E.W) if p.get("target_profit_per_year") is not None else None
    return {"needs_input": [], "minimum_beds": mn, "target_beds": tg, "net_per_extra_bed_per_week": net_per_bed, "fixed_other_per_week": fixed,
            "note": "None = no bed count reaches it (each extra bed loses money after its roster share and retrofit charge)."}

def at_beds(beds: int, p: dict) -> dict:
    """Walk-away rent and profit at a given bed count using the screening retrofit cost per bed."""
    need = E.missing(p, E.OPEX_KEYS) + E.missing(p, ["stabilised_occupancy", "retrofit_cost_per_bed_screening", "minimum_acceptable_profit_per_year"])
    ch = E.retrofit_charge_weekly(beds * p["retrofit_cost_per_bed_screening"], p) if not need else {"needs_input": [], "weekly": None}
    need += ch["needs_input"]
    if need: return {"needs_input": sorted(set(need))}
    N = E.operating(beds, p["stabilised_occupancy"], p)["net"]
    return {"needs_input": [], "N": N, "retrofit_charge": ch["weekly"], "retrofit_cost": beds * p["retrofit_cost_per_bed_screening"], "walk_away_rent": N - ch["weekly"] - p["minimum_acceptable_profit_per_year"] / E.W}

def zone_path(rows: list[dict]) -> tuple[str, str]:
    """('ok'|'blocked'|'unknown', text) from the related activity rows of the site's zone. Which activity a rest home falls under is a planner's call; this only says whether any consent path exists."""
    st = {r["status_class"] for r in rows}
    if not rows: return "unknown", "no related activity rows found for this zone"
    if st & ACTIVITY_OK: return "ok", "a consent path exists for related activities (planner to confirm which applies): " + ", ".join(sorted(st & ACTIVITY_OK))
    if st <= ACTIVITY_BLOCKED: return "blocked", "every related activity is non-complying or prohibited in this zone"
    return "unknown", "related activity statuses unclear"

def _verdict(listing: dict, site: dict | None, activity_rows: list[dict], p: dict, bedrooms_tier: str | None = "DOCUMENTED") -> dict:
    beds = listing.get("bedrooms"); rent = listing.get("rent_per_week"); reasons, flags, unknown = [], [], []
    out = {"verdict": None, "reasons": reasons, "flags": flags, "confidence": bedrooms_tier, "banner": "Screening only: bedrooms/plans not confirmed" if bedrooms_tier in (None, "ESTIMATED") else None,
           "label": "Screening label from the stated inputs. Not an approval and not a promise that it will work.", "hazard_info": (site or {}).get("hazard_flags"), "hazard_note": "Natural hazards are information only for conversions of existing buildings."}
    if not site or listing.get("parcel_id") is None or listing.get("match_confidence") in (None, "low", "none"):
        out["verdict"] = "GREY"; reasons.append("address not matched to a parcel with enough confidence"); return out
    if beds is None: out["verdict"] = "GREY"; reasons.append("bedrooms not stated"); return out
    out["depends_on_pc120"] = bool(site.get("pc120_depends"))
    red = []
    tt = (site.get("title_type") or "").lower()
    if not tt: unknown.append("title type unknown")
    elif "unit" in tt or "cross lease" in tt: red.append(f"title type '{site['title_type']}': several owners; legal path to certification needs a lawyer")
    zp, ztxt = zone_path(activity_rows); out["zone_path"] = {"state": zp, "text": ztxt, "zone": site.get("zone_name")}
    if zp == "blocked": red.append(ztxt)
    elif zp == "unknown": unknown.append(ztxt)
    mb = minimum_beds(p); out["minimum_beds"] = mb; out["beds_available"] = beds
    out["beds_note"] = "beds available = listed bedrooms: an upper bound until plans show rooms lost to office, communal space and ensuites"
    econ = at_beds(beds, p)
    if econ["needs_input"] or mb["needs_input"]:
        out["needs_input"] = sorted(set(econ["needs_input"]) | set(mb["needs_input"]))
        out["verdict"] = "RED" if red else "GREY"; reasons += red; reasons.append("economics cannot be judged: inputs not set (see needs_input)"); return out
    if mb["minimum_beds"] is None: red.append("no bed count reaches the minimum acceptable profit with these inputs")
    elif beds < mb["minimum_beds"]: red.append(f"too small: {beds} bedrooms vs {mb['minimum_beds']} needed for the minimum acceptable profit")
    wa = econ["walk_away_rent"]; out["economics"] = {**econ, "asking_rent": rent, "rent_multiple_possible": (wa / rent) if (rent and wa is not None and wa > 0) else None, "ceiling_note": ("no rent makes this work: it loses money before any rent is paid" if wa is not None and wa <= 0 else None),
                                                     "offer_ceiling": wa, "below_target": beds < 50}
    if rent is not None:
        out["offer_levels"] = [{"multiple": mu, "rent": rent * mu, "weekly_profit_after_rent": econ["N"] - econ["retrofit_charge"] - rent * mu, "above_ceiling": rent * mu > wa} for mu in (1.25, 1.5, 2.0)]
        if rent > wa: red.append(f"not viable at the asking rent: asking ${rent:,.0f}/wk is above the walk-away rent ${wa:,.0f}/wk")
    else: unknown.append("asking rent not stated")
    reasons += red
    if red: out["verdict"] = "RED"; return out
    if unknown or bedrooms_tier in (None, "ESTIMATED"): out["verdict"] = "AMBER"; reasons += unknown; reasons.append("economics positive at the asking rent but items above are unknown or only estimated"); return out
    out["verdict"] = "GREEN"; reasons.append(ztxt); reasons.append("economics positive at the asking rent; engineering items still need professionals (see Rest Home tab)"); return out


def verdict(listing: dict, site: dict | None, activity_rows: list[dict], p: dict, bedrooms_tier: str | None = "DOCUMENTED", placeholders: list[dict] | None = None) -> dict:
    """The verdict, then the placeholder rules: any result that rests on placeholder or estimated inputs carries the banner and the list of inputs that drove it, and can never be GREEN."""
    from .labels import PLACEHOLDER_BANNER
    out = _verdict(listing, site, activity_rows, p, bedrooms_tier)
    used = placeholders or []
    out["placeholders_used"] = used if out.get("economics") is not None else []
    out["placeholder_banner"] = PLACEHOLDER_BANNER if out["placeholders_used"] else None
    if out["placeholder_banner"] and out["verdict"] == "GREEN":
        out["verdict"] = "AMBER"
        out["reasons"].insert(0, "capped at AMBER: " + PLACEHOLDER_BANNER.lower() + " (" + ", ".join(x["label"] for x in out["placeholders_used"]) + ")")
    return out
