"""Confidence tiers. Every number inherits the lowest confidence of its inputs (Part 3 section 0)."""
ORDER = {"ESTIMATED": 0, "DOCUMENTED": 1, "CONFIRMED": 2}
BANNER_ESTIMATED = "Screening only: bedrooms/plans not confirmed"

def lowest(confidences):
    """Lowest tier among the inputs; None if there are no inputs (nothing to rank on)."""
    cs = [c for c in confidences if c]
    return min(cs, key=ORDER.__getitem__) if cs else None

def tier_for(facts: dict, required_fields: list) -> dict:
    """Tier of a computed result built from `required_fields` (names). A missing input makes the result 'needs input', never a guessed tier."""
    missing = [f for f in required_fields if f not in facts]
    if missing: return {"tier": None, "needs_input": missing, "banner": "needs input"}
    t = lowest(facts[f]["confidence"] for f in required_fields)
    return {"tier": t, "needs_input": [], "banner": BANNER_ESTIMATED if t == "ESTIMATED" else None}

def may_appear_in_tier(facts: dict, required_fields: list, tier: str) -> bool:
    """A property appears in the Confirmed tier only if every input is CONFIRMED (and so on down)."""
    r = tier_for(facts, required_fields)
    return r["tier"] is not None and ORDER[r["tier"]] >= ORDER[tier]
