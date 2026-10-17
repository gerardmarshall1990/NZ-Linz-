# Part 7 step 2: evidence gaps, layout options, compliance gaps, briefs

Run `make app-db` (adds tables and loads requirement slots), then `make app`.

## What it does (API; UI screens not built yet)
- `GET /api/property/{pid}/gaps`, `PUT .../gaps/{key}`: what plans cannot show (wall construction and fire ratings, structure, concealed services, roof/sub-floor, asbestos if built before 2000 or unknown, service capacity, existing fire systems, exits, unconfirmed or unscaled levels, plans vs as-built). Each is NEEDS_PROFESSIONAL with who confirms it; you can mark REQUESTED / RECEIVED.
- `POST /api/property/{pid}/layouts`: three options from the confirmed plan levels: conservative (existing ensuites only), base (add ensuites), max (also convert spare rooms). Room level only: each room is kept, converted, or gets a new-work item. Shows beds, the binding constraint, roles sacrificed when the building lacks an office, lounge, kitchen, laundry or store, and `below_target` under 50 beds.
- `GET /api/layouts/{id}/drawing.dxf|pdf?level=n`: demolition/new-work drawings (grey existing, orange change of use, blue new work). Every drawing carries the DRAFT stamp. A level with no scale gets no drawing.
- `POST /api/property/{pid}/compliance?option_id=`: PASS / FAIL / NEEDS_PROFESSIONAL / UNKNOWN / NOT_APPLICABLE for 18 requirement slots, plus the zone's related activity rows from the plan rules (a planner decides which applies). FAIL items carry quantities (for example ensuites to add) for step 3.
- `POST /api/property/{pid}/briefs` (fire, structural, accessibility, services): draft requests for the engineer built from recorded facts, the option, checks and gaps. They ask questions, state no conclusions, and list the professional's statement as an upload slot.

## Honest limits
- **The regulatory numbers are blank.** Ngā Paerewa and the Building Code Acceptable Solutions are behind bot challenges (BLOCKERS 18). So minimum room area, ensuite ratio, double occupancy, corridor and door widths and communal area per bed are not applied: a measured corridor width is NEEDS_PROFESSIONAL, never PASS. The option output names every rule not applied. Fill `config/bed_rules.yaml` and `config/rh_requirements.yaml` (with clause and date) and results change without code changes (tested: corridor 1.2 m against a 1.5 m value gives FAIL).
- Exits and escape routes, fire cells and wall moves are not modelled; they stay with the fire engineer and designer.
- Natural hazard data is never read in this step (decision 13); a test enforces it.
- Nothing produces a producer statement, signature, registration number or final report; tests scan outputs and code.
