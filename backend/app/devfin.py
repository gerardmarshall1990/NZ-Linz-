"""Development financial engine (MASTER_SPEC Part 2 section 5): pure functions, every input is the owner's and blank by default ('needs input', never a number). Formulas are shown with every result.
Comparable sales are not available (no licensed feed): price per unit is an input. Nothing here is advice."""
REQUIRED = ["price_per_unit", "build_cost_per_m2", "site_works_allowance", "contingency_pct", "land_cost", "consent_professional_fees", "development_contributions", "holding_months", "interest_rate_pct", "selling_costs_pct"]
OPTIONAL = ["target_margin_pct"]
LABELS = {"price_per_unit": "Sale price per unit or lot", "build_cost_per_m2": "Build cost per m2 of gross floor area", "site_works_allowance": "Site works allowance (whole site)", "contingency_pct": "Contingency % of build cost",
          "land_cost": "Land cost", "consent_professional_fees": "Consent, professional and council fees", "development_contributions": "Development contributions / growth charges", "holding_months": "Holding period (months)",
          "interest_rate_pct": "Interest rate % per year", "selling_costs_pct": "Selling costs % of revenue", "target_margin_pct": "Target margin % on cost"}
FORMULAS = ["revenue = units x price per unit", "build = units x gross floor area x build cost per m2 x (1 + contingency)", "holding = land x rate x months/12 + 0.5 x (build + site works) x rate x months/12 (average drawn balance is half)",
            "selling = revenue x selling costs %", "total cost = land + site works + build + fees + contributions + holding + selling", "profit = revenue - total cost; margin on cost = profit / total cost; margin on revenue = profit / revenue",
            "peak funding (approximate) = land + site works + build + fees + contributions + holding (everything before the first sale)", "break-even price = (total cost - selling) / (units x (1 - selling %))"]

def needs(inputs: dict) -> list[str]: return [k for k in REQUIRED if inputs.get(k) is None]

def feasibility(units: int, gfa_each: float, inputs: dict) -> dict:
    miss = needs(inputs)
    if miss or units <= 0: return {"status": "needs_input", "needs_input": [LABELS[k] for k in miss] or ["at least one unit"], "formulas": FORMULAS}
    g = inputs; rate = g["interest_rate_pct"] / 100; m = g["holding_months"]
    revenue = units * g["price_per_unit"]; build = units * gfa_each * g["build_cost_per_m2"] * (1 + g["contingency_pct"] / 100)
    holding = g["land_cost"] * rate * m / 12 + 0.5 * (build + g["site_works_allowance"]) * rate * m / 12; selling = revenue * g["selling_costs_pct"] / 100
    pre_sale = g["land_cost"] + g["site_works_allowance"] + build + g["consent_professional_fees"] + g["development_contributions"] + holding
    total = pre_sale + selling; profit = revenue - total
    out = {"status": "ok", "units": units, "revenue": revenue, "costs": {"land": g["land_cost"], "site_works": g["site_works_allowance"], "build": build, "fees": g["consent_professional_fees"], "contributions": g["development_contributions"], "holding": holding, "selling": selling},
           "total_cost": total, "profit": profit, "margin_on_cost_pct": profit / total * 100 if total else None, "margin_on_revenue_pct": profit / revenue * 100 if revenue else None, "profit_per_unit": profit / units, "cost_per_unit": total / units,
           "peak_funding_approx": pre_sale, "break_even_price_per_unit": (total - selling) / (units * (1 - g["selling_costs_pct"] / 100)) if g["selling_costs_pct"] < 100 else None,
           "annualised_simple_return_on_cost_pct": (profit / total) / (m / 12) * 100 if total and m else None, "formulas": FORMULAS}
    tm = g.get("target_margin_pct")
    if tm is not None: out["meets_target_margin"] = out["margin_on_cost_pct"] >= tm
    return out

def break_even_build_cost(units: int, gfa_each: float, inputs: dict) -> float | None:
    if needs(inputs) or units <= 0 or not gfa_each: return None
    p0 = feasibility(units, gfa_each, {**inputs, "build_cost_per_m2": 0})["profit"]; p1 = feasibility(units, gfa_each, {**inputs, "build_cost_per_m2": 1})["profit"]
    slope = p1 - p0
    return -p0 / slope if slope else None

def sensitivity(units: int, gfa_each: float, inputs: dict) -> dict:
    if needs(inputs) or units <= 0: return {"status": "needs_input"}
    base = feasibility(units, gfa_each, inputs)["profit"]; grid = {"base": base}
    def p(**kw): return feasibility(units, gfa_each, {**inputs, **kw})["profit"]
    grid["build_cost_minus_10pct"] = p(build_cost_per_m2=inputs["build_cost_per_m2"] * 0.9); grid["build_cost_plus_10pct"] = p(build_cost_per_m2=inputs["build_cost_per_m2"] * 1.1)
    grid["price_minus_10pct"] = p(price_per_unit=inputs["price_per_unit"] * 0.9); grid["price_plus_10pct"] = p(price_per_unit=inputs["price_per_unit"] * 1.1)
    grid["interest_minus_2pts"] = p(interest_rate_pct=max(0, inputs["interest_rate_pct"] - 2)); grid["interest_plus_2pts"] = p(interest_rate_pct=inputs["interest_rate_pct"] + 2)
    grid["delay_plus_3_months"] = p(holding_months=inputs["holding_months"] + 3)
    return {"status": "ok", "profit": grid, "note": "profit under each change, one at a time"}
