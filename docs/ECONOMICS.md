# Economics engine, retrofit cost and Offer Builder

API (all stored in `core.rh_scenario`): `POST /api/property/{pid}/retrofit?option_id=`, `POST .../economics`, `POST .../offers`, `GET /api/scenarios/{id}/proposal(.pdf)?mode=fixed|jv|hybrid`.

- **Inputs** live in `config/deal_assumptions.yaml` (the spec's four working figures are filled; everything else is blank), `config/rates.yaml` (all blank), `config/timeline_defaults.yaml`. Any unset input makes the dependent outputs `null` with a `needs_input` list. With the shipped config the tool therefore shows "needs input" everywhere; it never invents a cost or a profit. Fill the config (or pass `assumptions` / `retrofit` in the call) and the numbers appear.
- **Maths** (formulas printed in every response): stabilised net operating profit N, retrofit charge (I fund: amortised at cost of capital; owner funds: rent uplift), rent headroom, walk-away rent, break-even occupancy (solved numerically), sensitivity grid, N range (low/base/high), week-by-week operator cash with peak cash and full-timeline payback.
- **Offer modes**: A fixed rent (never above walk-away rent), B profit share (owner take at 60/80/100% occupancy and the downside cases; retrofit-recovery-first shown beside), C minimum payment plus share above a threshold. Flags: above walk-away (red), over cash limit (red), >30% allowances (red), share with no minimum payment (amber).
- **Worked example** from Part 6.4 (R0 1,000; N 5,000; s 50%; C 50,000) is a test and passes exactly: take 2,500 = 2.5 x; operator net 2,500; simple payback 20 weeks, stated to exclude conversion period, payments during it, fill ramp and pre-opening costs; the full-timeline version is shown beside it (cash required 74,000 with a 1,000/wk payment over 24 weeks; payback 54 weeks from lease start).
- **Proposal pack**: one page plus assumptions appendix, lawyer-review banner, downside cases always shown, wording scan tested ("minimum payment", no promise words).

## Limits
- Without the operating model attached, occupancy below stabilisation is scaled in proportion (this flatters the downside); the API attaches the real model so fixed staffing is respected. The response says which was used.
- Bed counts come from the layout option and ignore regulatory bed rules until they are sourced (BLOCKERS 18-19). A 4-bed option cannot cover a fixed roster even at 100% occupancy; the engine says so rather than hiding it.
- Roster step-up thresholds, supplies fixed/variable treatment, and pre-opening spread (over works and audit weeks) are stated assumptions to confirm.
