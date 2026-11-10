"""Engineering_Flood_Report.docx: parametric, screening-level completion of the owner's draft specification."""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
from docx_lib import *
from docx.enum.section import WD_ORIENT
P = jload(DATA / "pack_data.json"); E = jload(DATA / "eng_results.json"); RUNS = jload(DATA / "scenario_runs.json")
LOT = {NUM[i]: P["lots"][str(i)] for i in IDS}; GMIN = E["lots_ground_min"]; U = E["units"]; BYLOT = {n: [u for u in U if u["lot"] == n] for n in "2468"}
D = [str(x) for x in DEPTHS]; V = ["0.5", "1.0", "2.0"]
f1 = lambda x: f"{x:.1f}"; f2 = lambda x: f"{x:.2f}"
d = new_doc()
d.add_heading("2-8 Parrish Road – Flood Mitigation & Relocatable Foundation Specification (Draft for CPEng)", 0)
para(d, f"Nov 10, 2026   ·   @GERARD   ·   Completed from the project app on {TODAY}. Parametric screening report: working unit 60 m² (4 m × 15 m) relocatable.", italic=True)
# ---- colour legend
para(d, "How to read this document", bold=True, size=11)
table(d, ["Marking", "Meaning"], [(("Yellow cell or paragraph", YEL), "Information the owner, engineer or Council must supply (left blank, or needs a signature)."), (("Orange cell or paragraph", ORG), "Confirm: an ASSUMED value, an UNVERIFIED rule or source, or an [ENGINEER] item. Do not rely on it until confirmed."), ("White / grey", "DATA read from a named source, or CALCULATED from DATA and stated assumptions."),
    ("Tags", "DATA = read from a source. CALCULATED = arithmetic on DATA / ASSUMED values (method stated). ASSUMED = adopted by this pack, not sourced. UNVERIFIED = a rule, clause or fact I could not read in its official text. Source IDs S1–S15 are in Section 'Sources' and in data_sources.md.")], widths=[4.2, 13], rule=False)
# ---- Purpose and status
d.add_heading("Purpose and status", 1)
para(d, "The design intent is to lift every relocatable above the 1% AEP flood level on piles, keep the overland flow paths open, and place no fill in the floodplain, so the site loses no flood storage and keeps maximum density.")
para(d, "This is a draft design brief and specification, not a certified engineering report. A CPEng must verify every item marked [ENGINEER] before Council or a financier relies on it. Nothing in this document states that the design complies with any rule: it states what the design is designed to meet and what remains to be shown.", fill=ORG)
bullets(d, [("Site: 2, 4, 6 and 8 Parrish Road, Sandringham. LINZ titles total 2,006.9 m² (467.4 + 536.0 + 463.6 + 539.9) against 2,006 m² in the owner's documents and listing (DATA S1; listing UNVERIFIED). Freehold, listed by Bayleys #1657716 (S12).", None),
    ("Zoning, operative AUP: Terrace Housing & Apartment Building on 2 and 4; Mixed Housing Urban on 6 and 8 (DATA S1, S9). PC120 changes this: lot 2 was rezoned Single House and lot 4 Mixed Housing Urban with immediate legal effect from 3 Nov 2025 (s86B(3)(f) RMA), and Council's August 2026 amendments propose Single House Zone on all four lots (DATA S8, S9; not operative).", ORG),
    ("Hazards on the listing: overland flow paths, flood prone, flood plain. Confirmed in Council layers: all four titles are 100% inside the 1% AEP Flood Plain (Meola model, URS 2017, climate-change adjusted) and inside Flood Prone Area 30836607 (DATA S2, S3). An overland flow path crosses lot 2 only (18.6 m inside the title; DATA S5). Flood sensitive area: none mapped (S4).", None)])
para(d, "What this completed draft adds", bold=True)
bullets(d, ["Every table in the original brief is kept in order. Blank engineering inputs are replaced by LiDAR DATA and by lookup tables over flood depths 0.3, 0.6, 0.9 and 1.2 m and velocities 0.5, 1.0 and 2.0 m/s, so the report is parametric until the engineer's model and geotechnical report are in.",
    ("Headline flag: the published Council Flood Prone Area layer gives a 1% AEP spill level of 37.03 m RL (NZVD2016) with the note 'Spills – specific calculation is required'. If the lot depressions filled to that level, depth over the lots would be 2.9 to 4.8 m, far above the 0.3 to 1.2 m lookup range (DATA S3, CALCULATED). The lookup range is an ASSUMED planning range chosen to match the brief, not a Council figure. Confirmed Input 1 decides whether piled relocatables are viable at all.", ORG),
    "Indicative layout: 8 units (4 on each of two amalgamated groups, 2+4 and 6+8) under operative zoning; 6 units on four separate titles under the current legal position (Zoning_Feasibility.xlsx). Pile positions, stairs, ramps and parking tests below use the 8-unit scheme; any subset reads from the same lookup tables."])
# ---- What financier signs off
d.add_heading("What the financier signs off", 1)
para(d, "The technical risk is covered by one chartered engineer's report and producer statement, so the financier relies on a single sign-off. The consents are approvals to track as conditions, not extra reports.")
table(d, ["Item", "Position"], [
 ("Hazard", "Floodplain and overland flow paths on all four titles, per the listing. Confirmed in Council layers: 100% flood plain and flood prone area on every title; one overland flow path across lot 2 (DATA S2, S3, S5)."),
 ("Mitigation", "Units designed to be raised on piles to the 1% AEP flood level plus 500 mm. Open sub-floor, no fill, flow paths kept clear. Pile height, stair and ramp lengths per unit and depth are in Tables 6 to 8 (CALCULATED, ASSUMED depths)."),
 ("Compliance", "Eighteen rules mapped to the design in the compliance matrix across the Unitary Plan, Building Act and Building Code. Rows 1 to 13 were checked against the operative AUP text (July 2026); rows 14 to 18 are UNVERIFIED because the official Act, Code and Council texts could not be retrieved."),
 ("Technical sign-off", "One CPEng: flood hazard assessment, structural design and PS1. Not yet appointed."),
 ("Approvals to track", "One restricted discretionary resource consent for the floodplain, then a building consent per unit. A density consent is also needed under the zone rules (Zoning_Feasibility.xlsx)."),
 ("Inputs the engineer commissions", "Topographic survey and geotechnical report. Council flood model depth and velocity for the 1% AEP and climate change cases."),
 ("Residual risks", "A s73 title notice is possible. Plan Change 120 is rewriting E36 and has rezoned lots 2 and 4 with immediate legal effect; the August 2026 amendments propose Single House Zone on all four lots. The flood model may reduce the unit count. No public stormwater pipe within about 157 m and a Combined Wastewater Network Control qualifying matter on all four lots (PC120).")], widths=[4.5, 12.7], first_col_bold=True)
# ---- Engineer sign-off (blank)
d.add_heading("Engineer sign-off", 1)
table(d, ["Field", "Entry"], [("Engineer name", ""), ("CPEng number", ""), ("Report reference", ""), ("Date", ""), ("Signature", "")], widths=[5, 12.2], first_col_bold=True)
para(d, "Left blank on purpose. This pack does not state, and must not be read as stating, that any engineer has checked, certified or accepted it. PS1 and PS4 are not drafted.", italic=True)
# ---- Confirmed inputs
d.add_heading("Confirmed Inputs: the three items the engineer supplies", 1)
para(d, "Everything in the lookup tables depends on three engineer-supplied items. They are pre-filled below with ASSUMED ranges so the report is complete but parametric. Replace the orange values with the engineer's confirmed values; the numbers in Tables 5 to 12 then rerun from the same method (scripts/parrish_pack/calc.py).")
gm = {n: GMIN[n] for n in "2468"}
rng = lambda n: f"RL {f2(gm[n] + .3)} to {f2(gm[n] + 1.2)} m (depth 0.3 to 1.2 m on lowest lot ground {f2(gm[n])})"
fp = {n: LOT[n]["depth_if_filled_to_published_level"] for n in "2468"}
table(d, ["Confirmed input", "Lot 2", "Lot 4", "Lot 6", "Lot 8", "Source / status"], [
 ("1. 1% AEP flood level and peak depth (m RL; m). Used as the level on the lowest ground of each lot.", rng("2"), rng("4"), rng("6"), rng("8"), "ASSUMED range. Engineer's model (Council baseline plus site refinement) replaces it. Datum must be confirmed (see below)."),
 ("1b. Council published level for comparison (DATA S3)", f"37.03 m RL NZVD2016, 'Spills – specific calculation is required'. Depth if filled to that level: {fp['2']['min_depth_m']} to {fp['2']['max_depth_m']} m", f"{fp['4']['min_depth_m']} to {fp['4']['max_depth_m']} m", f"{fp['6']['min_depth_m']} to {fp['6']['max_depth_m']} m", f"{fp['8']['min_depth_m']} to {fp['8']['max_depth_m']} m", "DATA (S3) and CALCULATED against LiDAR (S6). This is a ponding spill level for the whole flood prone area, not a modelled depth at the lot. UNVERIFIED whether the lots actually reach it: that is exactly what the engineer's model must show."),
 ("1c. Climate change level (m RL)", "", "", "", "", "Engineer, per Council requirements. The Council Flood Plains layer is flagged climate-change adjusted (S2) but publishes no level or depth. UNVERIFIED."),
 ("2. Geotechnical parameters: soil type; allowable bearing; scour depth to fixity; groundwater", "Soil type UNVERIFIED (no geotech and no geology read). Bearing 100 to 300 kPa ASSUMED range (not used in calcs). Scour 0.3 to 1.0 m ASSUMED range (0.5 m used). Groundwater ASSUMED at surface in flood.", "Same", "Same", "Same", "ASSUMED ranges. Geotechnical report replaces them. Embedment, bearing and lateral capacity are NOT checked in this pack."),
 ("3. Peak flow velocity (m/s) and depth × velocity (m²/s)", "0.5, 1.0 and 2.0 m/s (ASSUMED). D×V 0.15 to 2.4 m²/s (CALCULATED).", "Same", "Same", "Same", "ASSUMED. Council or engineer model replaces them. The layer for overland flow paths has centrelines only (S5): no velocity.")], widths=[4, 3.6, 2.6, 2.6, 2.6, 3.8])
para(d, "Datum note: LiDAR levels are NZ Elevation 2024 (S6), assumed NZVD2016. Council flood layers are NZVD2016 (S3); the overland flow path layer is NZVD1946 (S5). The offset between the two is not applied: UNVERIFIED; confirm with Healthy Waters and show the datum on every drawing.", fill=ORG)
# ---- Site inputs
d.add_heading("Site inputs to confirm", 1)
para(d, "Every floor level and pile length below depends on these inputs, so none of the design values can be finalised until they are filled in. Take them from Council's flood model, LiDAR and a surveyor's topo, then have the engineer verify them.")
def gr(n): return "; ".join(f"{u['id']} {f2(u['ground_min_RL'])} to {f2(u['ground_max_RL'])} (mean {f2(u['ground_mean_RL'])})" for u in BYLOT[n])
def ofp(n):
    l = LOT[n]; loc = l.get("flow_path_location_in_lot") or []
    if loc: return f"Council centreline {sum(x['length_m'] for x in loc):.1f} m inside the lot, from the street frontage up to {loc[0]['depth_from_street_m'][1]} m in, drifting {loc[0]['u_from_to_m'][1]} m across (DATA S5, lot frame). Width and flow direction not in the layer: UNVERIFIED."
    nn = [x for x in l["overland_flow_paths"] if x["inside_lot_m"] == 0][:2]
    return "None inside the lot. " + "; ".join(f"path {x['objectid']} is {x['distance_m']} m away" for x in nn) + " (DATA S5). 2 m planning offset corridor on the lot: " + f"{l['usable_after_clearance']['2m_each_side']['corridor_m2']} m²."
table(d, ["Input", "Lot 2", "Lot 4", "Lot 6", "Lot 8", "Source"], [
 ("1% AEP flood level (m RL)", "ASSUMED " + f"{f2(gm['2']+.3)}–{f2(gm['2']+1.2)}", "ASSUMED " + f"{f2(gm['4']+.3)}–{f2(gm['4']+1.2)}", "ASSUMED " + f"{f2(gm['6']+.3)}–{f2(gm['6']+1.2)}", "ASSUMED " + f"{f2(gm['8']+.3)}–{f2(gm['8']+1.2)}", "Council flood model, GeoMaps, engineer's model. Pre-filled from Confirmed Input 1."),
 ("Flood level with climate change (m RL)", "", "", "", "", "Engineer, per Council requirements"),
 ("Existing ground level at each unit (m RL)", gr("2"), gr("4"), gr("6"), gr("8"), "DATA LiDAR 1 m DEM (S6), min to max under footprint. Surveyor topo to replace."),
 ("Peak flood depth (m)", "ASSUMED 0.3 to 1.2", "ASSUMED 0.3 to 1.2", "ASSUMED 0.3 to 1.2", "ASSUMED 0.3 to 1.2", "Engineer's model"),
 ("Peak flow velocity (m/s)", "ASSUMED 0.5 to 2.0", "ASSUMED 0.5 to 2.0", "ASSUMED 0.5 to 2.0", "ASSUMED 0.5 to 2.0", "Engineer's model"),
 ("Depth × velocity (m²/s)", "CALCULATED 0.15 to 2.4", "CALCULATED 0.15 to 2.4", "CALCULATED 0.15 to 2.4", "CALCULATED 0.15 to 2.4", "Calculated: depth × velocity"),
 ("Overland flow path width and direction", ofp("2"), ofp("4"), ofp("6"), ofp("8"), "Council overlay (S5), survey"),
 ("Flood-sensitive area status", "None mapped (DATA S4)", "None mapped (DATA S4)", "None mapped (DATA S4)", "None mapped (DATA S4)", "Council overlay"),
 ("Soil type, bearing capacity, scour depth", "", "", "", "", "Geotechnical report. See Confirmed Input 2.")], widths=[3.4, 3.2, 3, 3, 3, 3.2], size=7.5)
# ---- Compliance matrix
d.add_heading("Compliance matrix", 1)
para(d, "Each mitigation measure below is tied to the rule it satisfies. Clause numbers are from the operative Auckland Unitary Plan chapter E36, the Building Act 2004 and the Building Code. Plan Change 120 is rewriting E36, so the engineer confirms the version in force at lodgement. [ENGINEER]", fill=ORG)
para(d, "Re-verified 10 Nov 2026: rows 1 to 13 against the AUP operative text dated July 2026 (S7) and, where marked, PC120 proposed E36 (S8). Rows 14 to 18: the official Building Act, Building Code and Council Code of Practice texts could not be retrieved (official sites blocked); only search snippets were read (S13), so those rows are UNVERIFIED. 'Designed to meet' means the design is intended to satisfy the rule; nothing is certified.", size=9)
CM = [
 (1, "Resource consent for new dwellings in the 1% AEP floodplain", "E36.4.1 A37 and A38, restricted discretionary. A42 as well for any building in an overland flow path.", "One consent application is designed to cover all four lots. Council's discretion is limited to the matters in E36.8.1(9), (10) and (13), each answered below.", "4", "VERIFIED: rows A37, A38 (RD) and A42 (RD) and matters E36.8.1(9), (10), (13) read in S7. PC120 proposes new rows A87 to A102; A98 is RD for other buildings in the 1% AEP floodplain and flood prone areas, with Very high/High, Medium and Low hazard columns. The property's hazard category is not in the app: UNVERIFIED."),
 (2, "Hazard risk assessment lodged with the application", "E36.9(1)–(2), items (a)–(l)", "The flood hazard assessment is designed to follow the (a)–(l) headings so Council can tick each off (outline below).", "4", "VERIFIED: E36.9(1)–(2); (2) timeframe at least the next 100 years; item (f) is coastal."),
 (3, "Flood water can pass under buildings", "E36.8.2(9)(b), clear under-croft", "Open piled sub-floor, no solid skirts, designed to let flood water pass.", "3, 5", "VERIFIED: E36.8.2(9)(a)–(d) read. It is an assessment criterion, not a permitted standard."),
 (4, "Buildings resilient to flooding", "E36.8.2(9)(c); policy E36.3(25)", "Services above FFL, water-resistant underfloor, non-return valves, flood-proof utility connections.", "5", "VERIFIED: E36.8.2(9)(c); policy E36.3(25)."),
 (5, "No floatable items leaving the site", "E36.8.2(9)(d); storage E36.6.1.6", "Bins and stored goods secured. Cars parked on ground that meets row 6.", "4", "VERIFIED: E36.8.2(9)(d); E36.6.1.6."),
 (6, "Surface parking location", "E36.6.1.7: depth must not exceed 200mm in a 1% AEP event. Deeper, up to 500mm, is a controlled activity if vehicles are contained (A25, E36.6.2.1).", "Parking is designed to sit only on cells at or under 200 mm depth, from the flood model. At the ASSUMED depths in Table 11 lots 6 and 8 cannot meet this from 0.6 m, and lot 2 at 1.2 m.", "3, 4", "VERIFIED: E36.6.1.7 (≤200 mm); E36.6.2.1 (≤500 mm, vehicles contained); A24 permitted, A25 controlled."),
 (7, "Shared accessway", "E36.6.1.8: where it serves more than two lots, depth must not exceed 200mm", "Shared access is designed to sit where the model shows 200 mm or less. In the indicative scheme each driveway serves two lots, so the standard is not triggered; one accessway serving all four lots would be.", "3, 7", "VERIFIED: E36.6.1.8 (accessway serving more than 2 lots, depth ≤200 mm)."),
 (8, "No worse flooding for neighbours", "Policy E36.3(21); E36.8.1(10)(g); E36.8.2(10)(d)", "Pre and post development modelling is designed to show no increase in level, depth or velocity at the boundaries. Not yet modelled.", "3, 4, 6", "VERIFIED: policy E36.3(21); E36.8.1(10)(g) exacerbation; E36.8.2(10)(d)."),
 (9, "Buildings stay structurally sound in a flood", "E36.8.2(10)(e)", "Foundations and chassis connections are designed for flood, debris and uplift loads, with a PS1. Preliminary only here.", "5, 8", "VERIFIED: E36.8.2(10)(e)."),
 (10, "Safe evacuation or refuge", "Policy E36.3(13)(b); E36.8.1(10)(f) and (13)(c)", "Floors above flood level are designed to give refuge. Raised walkways, an assessed egress route and a tenancy flood plan.", "7", "VERIFIED: policy E36.3(13)(b); E36.8.1(10)(f) safe egress; (13)(c) access design. (13) applies to buildings within an overland flow path (lot 2 on the Council layer)."),
 (11, "Overland flow paths kept working", "Policy E36.3(29)–(30); A41 and A42 restricted discretionary; fences E36.6.1.10", "Flow paths are designed to be left open and not piped or diverted. Fences open. Ponding must not extend beyond the site: not yet shown.", "3, 4", "VERIFIED: policy E36.3(29)–(30); A41, A42; E36.6.1.10. PC120 proposes A100 (permitted, catchment under 4,000 m²) and A101 (RD, over 4,000 m²) for flow-path buildings; catchment size per path is in the layer (path 852976: group 4) but the threshold test is UNVERIFIED."),
 (12, "Fences pass flood water", "E36.6.1.5: must let water through where deeper than 300mm. Railing fences at least 70% non-solid comply.", "Open fencing at least 70% void is specified.", "5", "VERIFIED: E36.6.1.5 and Note 1 (70% non-solid)."),
 (13, "Earthworks in the floodplain", "Policy E36.3(20)", "No fill. Any cut and fill balanced on site.", "3, 6", "VERIFIED: policy E36.3(20)."),
 (14, "Building Act natural hazard provisions", "Building Act ss71–73", "The report is designed to show adequate provision for the hazard and no worsening of it, so consent can issue normally. If Council still grants under s72, consent carries a s73 notice on the titles.", "4", "UNVERIFIED: official text of ss71–74 not retrievable (legislation.govt.nz blocked); MBIE guidance read only as search snippets (S13)."),
 (15, "Flood water must not enter housing", "Building Code E1.3.2: 2% AEP event", "FFL at the 1% AEP level plus 500 mm is designed to sit above the 2% AEP level. 2% AEP level not available: Council layers do not publish it.", "3, 4", "UNVERIFIED: E1.3.2 wording seen only in an MBIE determination snippet (S13)."),
 (16, "Water concentrated by buildings and sitework", "Building Code E1.3.1: 10% AEP event, no damage or nuisance to other property", "Stormwater management plan (Section 'Stormwater').", "6", "UNVERIFIED: E1.3.1 not read in the official Code text (S13 snippet only)."),
 (17, "Structure and durability", "Building Code B1, B2", "Specific engineering design, durable materials in the wetting zone.", "5", "UNVERIFIED: B1 and B2 not read officially; B2.3.1 50-year tier is from a BRANZ snippet (S13)."),
 (18, "Floor level freeboard", "Council Stormwater Code of Practice: 500mm above flood level. E36 sets no numeric freshwater floor level.", "FFL = 1% AEP flood level + 0.5 m. Datum to be confirmed with Healthy Waters.", "3", "E36 point VERIFIED: searched E36 operative text, no numeric freeboard. Code of Practice 500 mm: UNVERIFIED (Council site blocked; snippet only, S13).")]
table(d, ["#", "Requirement", "Rule", "How this design is designed to meet it", "Report item", "Check made 10 Nov 2026"], [(a, b, c, e, f, g) for a, b, c, e, f, g in CM], widths=[0.7, 2.8, 3.4, 4.1, 1.2, 5.3], size=7.5, fills={(i, 5): (ORG if CM[i][5].startswith(("UNVERIFIED", "E36 point")) or "UNVERIFIED" in CM[i][5] else None) for i in range(18)})
para(d, "Row 14 is the one to flag to a financier: a s73 notice on the title is possible even with a strong report, because the Council decides whether provision is adequate. The 2024/053 determination is cited in the owner's draft as an example of s72 applied to flood land (not read here: UNVERIFIED).")
para(d, "Additional items found while re-verifying (not in the original eighteen)", bold=True)
bullets(d, [("PC120 immediate legal effect: the rezoning of lot 2 to Single House Zone and lot 4 to Mixed Housing Urban Zone applies now (s86B(3)(f) RMA). Amended rules for Single House Zone allow one dwelling plus one minor dwelling (≤65 m², H3.6.4) per site; more than that is non-complying (H3.4.1 A6). See Zoning_Feasibility.xlsx.", None),
    ("PC120 proposed E36 hazard-category columns (Very high/High, Medium, Low) decide whether dwellings are discretionary or non-complying. The category per lot is not in the app: UNVERIFIED. Obtain from Council's PC120 property map.", ORG),
    ("PC120 proposes a Combined Wastewater Network Control standard (H3.6.3A for Single House; equivalent in other zones): development must connect to an existing separated local public stormwater pipe and the wastewater provider must confirm capacity. All four lots carry this qualifying matter (S9) and the nearest public stormwater pipe is 157 to 173 m away (DATA S10). UNVERIFIED how Council would apply it.", ORG),
    ("E27 vehicle access width test (3.5 m shared drive) is used in the layout (config/transport_rules.yaml, S15). Gradient and crossing details need a professional.", None),
    ("Stormwater Management Area Flow (SMAF) overlay: not mapped at the lots (point test, S11).", None)])
# ---- Floor level and setout
d.add_heading("Floor level and setout", 1)
para(d, "Each unit's finished floor level (FFL) is set at the 1% AEP flood level plus 500mm freeboard, so the pile height above existing ground is the flood depth plus 0.5m.")
para(d, "FFL = Q(1% AEP) + 0.5 m", bold=True, italic=True)
table(d, ["Flood depth at unit", "Floor height above existing ground", "Basis"], [("0.3 m", "0.8 m", "CALCULATED: depth + 0.5"), ("0.6 m", "1.1 m", "CALCULATED"), ("0.9 m", "1.4 m", "CALCULATED"), ("1.2 m", "1.7 m", "CALCULATED (added)")], widths=[4, 6, 5])
para(d, "Above about 1.1 m, access stairs and ramps start to take real footprint, so the engineer's depth map sets the true unit count. Confirm the FFL datum (top of floor or underside of joists) and any climate change allowance with Council Healthy Waters before the layout is fixed. [ENGINEER]", fill=ORG)
para(d, "Method used for the unit tables (CALCULATED, ASSUMED inputs): design flood level on a lot = lowest LiDAR ground on that lot + depth d (a flat level across the lot, as in a ponded depression); FFL = level + 0.5 m; chassis underside = FFL − 0.30 m (ASSUMED floor frame depth); exposed pile height at each pile = chassis underside − LiDAR ground at that pile (bilinear, 1 m DEM). A negative value means the ground is above the chassis underside at that pile: the engineer must cut or raise the unit.")
def hdrs(first): return [first] + [f"{x} m" for x in D]
d.add_heading("Table 6: FFL (m RL) per unit, by flood depth on the lowest lot ground", 3)
table(d, ["Unit", "Mean ground (m RL)"] + [f"FFL @ {x} m" for x in D], [(u["id"], f2(u["ground_mean_RL"])) + tuple(f2(u["levels"][x]["ffl_RL"]) for x in D) for u in U], widths=[2.2, 3, 2.9, 2.9, 2.9, 2.9], rule=False)
d.add_heading("Table 7: exposed pile height (m) under each unit, min to max across 10 piles", 3)
table(d, ["Unit"] + [f"@ {x} m" for x in D], [(u["id"],) + tuple(f"{f2(u['levels'][x]['pile_exposed_min_m'])} to {f2(u['levels'][x]['pile_exposed_max_m'])}" for x in D) for u in U], widths=[2.4, 3.7, 3.7, 3.7, 3.7], rule=False)
d.add_heading("Table 8: stairs and ramps (CALCULATED from door-end ground; ASSUMED riser 0.175 m, going 0.28 m, landing 1.2 m, ramp 1:12)", 3)
rows = []
for u in U:
    r = [u["id"], f2(u["ground_door_RL"])]
    for x in D: l = u["levels"][x]; r.append(f"{l['stair_risers']} risers, run {l['stair_run_m']} m; ramp {max(l['ramp_length_m'], 0):.1f} m")
    rows.append(tuple(r))
table(d, ["Unit", "Door-end ground RL"] + [f"@ {x} m" for x in D], rows, widths=[1.7, 2, 3.4, 3.4, 3.4, 3.4], size=7.5, rule=False)
para(d, "Stair and ramp footprint is ASSUMED to sit within each lot and outside the 4 x 15 m unit footprint; the layout packing did not reserve space for it. At 1.2 m depth, ramps of 15 to 17 m would be needed on the higher-ground lots: an accessible route to every unit is not achievable inside the layout used. Confirm with the architect whether an accessible route is required (Brief item).", fill=ORG)
# ---- Foundation spec
d.add_heading("Foundation and pile specification", 1)
para(d, "Use an open piled sub-floor with no solid skirting, so floodwater passes under the units and no flood storage is lost. All values are design targets for the engineer to confirm. [ENGINEER]", fill=ORG)
table(d, ["Item", "Specification", "Value used in this pack"], [
 ("Pile type", "Concrete piers or galvanised steel screw piles preferred below flood level. H5 treated timber poles only if the engineer accepts them for repeated wetting.", "ASSUMED 300 × 300 mm concrete pier (drag area, square) or 114.3 mm OD CHS (round) for the drag calculation; availability of section sizes UNVERIFIED"),
 ("Embedment", "Below the scour depth from the geotech report, and sized for the lateral flood load plus bearing.", "ASSUMED scour-to-fixity 0.5 m. Embedment depth and bearing not calculated: needs geotech."),
 ("Lateral flood load", "Hydrodynamic force on each pile and unit, calculated from the peak velocity at that unit.", "CALCULATED, Table 9 (ASSUMED Cd, blockage, velocity)"),
 ("Bracing", "Engineered diagonal bracing between piles, designed for flood flow direction.", "ASSUMED tension-only diagonals at 45°; axial force Table 9"),
 ("Underfloor", "Open lattice at least 90% void, or engineered breakaway panels. No solid skirts.", "Specification unchanged. Hydrostatic load if a skirt were solid is in Table 10 for comparison."),
 ("Clearance", "Set from the model: enough for flow and debris to pass, and for inspection.", "Chassis underside = FFL − 0.30 m (ASSUMED). Clear height above ground varies per pile (Table 7). Engineer sets the minimum from the model."),
 ("Uplift", "Tie-downs from chassis to piles, designed in case a flood exceeds the design event.", "CALCULATED, Table 10 (ASSUMED unit weight 120 kg/m²)")], widths=[2.6, 7, 7.6], size=8)
para(d, "F_d = ½ · ρ · C_d · A · v²", bold=True, italic=True)
para(d, "F_d is the drag force from flood flow, ρ is water density, C_d the drag coefficient, A the area facing the flow and v the velocity. The engineer also allows for debris impact and a blockage factor on the piles.")
A = E["assumptions"]
para(d, "Inputs used: ρ = 1,000 kg/m³ (ASSUMED clear water; sediment-laden flood water can be 1,100 to 1,200); C_d = 2.0 for a square pile and 1.2 for a round pile (ASSUMED; ASCE 7 Chapter 5 not read: UNVERIFIED); blockage factor 1.5 on projected pile area (ASSUMED); wetted height = design depth above ground at the pile; moment arm = half the wetted height plus 0.5 m scour-to-fixity. Debris impact is NOT calculated: [ENGINEER].", fill=ORG)
d.add_heading("Table 9: flood loads (worst unit in the scheme, CALCULATED; PRELIMINARY)", 3)
rows = []
for dd in D:
    for vv in V:
        L = E["lookup"][f"{dd}|{vv}"]; ch = L["chs_pick"]
        rows.append((dd, vv, f"{L['dxv_max']:.2f}", f"{L['worst_unit']}", f"{L['unit_total_drag_kN_max']:.1f}", f"{L['max_pile_moment_kNm']:.2f}", f"{L['Z_required_cm3']:.1f}", f"{ch['OD_mm']} × {ch['t_mm']} CHS (Z {ch['Z_cm3']} cm³)", f"{L['brace_axial_kN']:.1f}"))
table(d, ["Depth (m)", "Velocity (m/s)", "D×V (m²/s)", "Worst unit", "Unit drag (kN, square piles)", "Max pile moment (kNm, round)", "Z req (cm³)", "PRELIMINARY CHS pick", "Brace axial (kN)"], rows, widths=[1.3, 1.6, 1.4, 1.6, 2.2, 2.2, 1.5, 3.6, 1.8], size=7.5, rule=False)
para(d, "PRELIMINARY: the flood drag moments are small, so the section is governed by vertical load (about 22 kN per pile, Table 10), buckling over the exposed height, connection detailing, durability and debris impact, none of which are checked here. Treat the CHS pick as a placeholder, not a design: [ENGINEER].", fill=ORG)
d.add_heading("Table 10: uplift, gravity and hydrostatic checks (CALCULATED, ASSUMED inputs)", 3)
rows = [(f"{u['water_above_design_level_m']}", f"{u['water_above_floor_underside_m']}", f"{u['buoyancy_kN']}", f"{u['dead_kN']}", f"{u['net_uplift_kN']}", f"{u['per_pile_kN']}") for u in E["uplift"]]
table(d, ["Water above design level (m)", "Water above floor underside (m)", "Buoyancy on 60 m² floor (kN)", "Dead load (kN)", "Net uplift (kN)", "Per pile, 10 piles (kN)"], rows, widths=[3, 3, 3, 2.5, 2.5, 3], rule=False)
para(d, f"Gravity: {E['gravity']['uls_kPa']} kPa ULS and {E['gravity']['per_pile_kN']} kN per pile (CALCULATED; 1.2G + 1.5Q on 6 m² tributary area, ASSUMED G 120 kg/m² and Q 1.5 kPa; AS/NZS 1170.0 combinations not read: UNVERIFIED). Hydrostatic load per metre length of a SOLID skirt (kN/m) at depth 0.3 / 0.6 / 0.9 / 1.2 m: " + " / ".join(str(E['hydrostatic_per_m_solid_kN'][x]) for x in D) + " (CALCULATED ½ρgh²). The brief requires open lattice, so this is the load that open lattice is avoiding.")
# ---- Relocatable structure
d.add_heading("Relocatable structure and connections", 1)
para(d, "A relocatable was built to sit on its own supports, so the engineer must re-check the chassis and floor frame for the new pile support points and the flood load path. Get the manufacturer's structural drawings for every unit before design starts.")
table(d, ["Check", "What the engineer confirms", "Status"], [
 ("Chassis and floor frame", "Capacity at the new pile positions, point loads and spans.", "[ENGINEER] Not calculable: no manufacturer drawings. Pile grid used: 5 rows × 2 (ASSUMED)."),
 ("Chassis-to-pile connection", "Fixings designed for lateral flood load and uplift.", "[ENGINEER] Loads per pile in Tables 9 and 10."),
 ("Lateral stability", "Bracing and diaphragm action under flood flow and wind.", "[ENGINEER] Wind and seismic not calculated (AS/NZS 1170.2, NZS 1170.5 not read)."),
 ("Durability", "Galvanised or stainless fixings and steelwork in the wetting zone (B2).", "[ENGINEER]"),
 ("Relocation condition", "Existing damage, repairs and compliance of each unit for a relocated-building consent.", ""),
 ("Debris impact", "Allowance on the upstream face of the units and piles.", "[ENGINEER] Not calculated.")], widths=[3.6, 7, 6.6])
# ---- Materials
d.add_heading("Flood-resilient materials and services", 1)
para(d, "Everything that can be damaged by water goes above the FFL, and anything that must sit below it is built to survive wetting.")
bullets(d, [("Electrical: switchboard, meters, power points and the main feed above the FFL, with cables entering from above.", None), ("Plant: hot water cylinder, heat pump units and any gas bottles above the FFL and strapped down.", None), ("Plumbing and drainage: non-return valves on wastewater and stormwater connections, flexible connections where the units meet the ground.", None), ("Underfloor: water-resistant, closed-cell insulation and lining, or none below the floor frame.", None), ("Fixings and steel: hot-dip galvanised or stainless below the flood line.", None),
 ("Utility connections: Watercare, power and telco connections routed on a raised service spine, not through the flow path. Watercare network data is not in the app: UNVERIFIED connection points. Nearest public stormwater pipe (225 mm concrete, owner Stormwater) is 157 to 173 m away; Council stormwater connections owned by Transport are 4.8 to 28 m from the lots (DATA S10).", ORG)])
# ---- Layout rules
d.add_heading("Layout rules for maximum density", 1)
para(d, "Place units on the lowest-hazard ground and treat the flow paths as shared open space, so density is limited by hazard and zoning rather than by lost flood storage.")
numbered(d, ["Keep every overland flow path clear of buildings, solid fences and stored material. Applied: a 2 m offset each side of the Council centreline is excluded from the layout (ASSUMED planning figure); only lot 2 has a path inside it (73 m² corridor) and no unit count changed.",
 "Orient each unit with its narrow end facing the flow, to reduce obstruction. Units are laid long axis from street to rear; flow direction is UNVERIFIED (not in the layer).",
 "Cluster units on the cells with the lowest depth × velocity from the model. Not possible without the model: [ENGINEER].",
 "Leave gaps between units wide enough to pass flow, with the width set from the model. [ENGINEER] Gaps in the indicative layout are the yard and driveway spaces (2 to 7 m).",
 "Put carparks only on ground where the 1% AEP depth is 200mm or less (E36.6.1.7), and use the deeper zones for landscaping and the flow path. Result: Table 11.",
 "Count stairs, ramps and walkways as obstructions in the flood model. Not yet modelled.",
 "Use open fencing, at least 70% void, inside the floodplain (E36.6.1.5).",
 "Avoid retaining walls and level pads that would need fill. None used.",
 "Treat 2, 4, 6 and 8 as one coordinated layout, with the flow path solved once across the whole site. The indicative scheme pools 2+4 and 6+8; whole-site amalgamation and the effect of zoning on the count are in Zoning_Feasibility.xlsx."])
d.add_heading("Table 11: parking tests (E36.6.1.7), spaces available vs required (2 per unit, ASSUMED), by design depth on the lowest lot ground", 3)
rows = []
for n in "2468":
    p = E["parking"][n]; r = [f"Lot {n}", str(p["0.3"]["required_spaces"])]
    for x in D: r.append(f"≤200 mm: {p[x]['le200mm']['spaces']} ({p[x]['le200mm']['area_ok_pct']}% of lot); ≤500 mm: {p[x]['le500mm']['spaces']}")
    rows.append(tuple(r))
table(d, ["Lot", "Required"] + [f"@ {x} m" for x in D], rows, widths=[1.5, 1.7, 3.5, 3.5, 3.5, 3.5], size=7.5, rule=False)
para(d, "CALCULATED: a flat water level across each lot; cells where (level − ground) ≤ 0.2 m (or ≤ 0.5 m) are eligible; spaces 2.5 × 5.0 m (ASSUMED) packed on the eligible area outside the units and driveway. Result: lot 4 meets 4 spaces at 200 mm or less at every depth; lot 2 fails only at 1.2 m (2 spaces); lot 6 fails from 0.6 m (2 spaces) and has none at 0.9 m; lot 8 fails from 0.6 m (none at 200 mm or less). Where only the 500 mm count passes (lot 2 at 1.2 m: 4; lot 6 at 0.6 m: 4; lot 8 at 0.6 m: 5), a controlled activity (A25) with vehicles contained (E36.6.2.1) would be needed.", fill=ORG)
d.add_heading("Table 12: shared accessway depth (E36.6.1.8 applies only where an accessway serves more than two lots)", 3)
acc = E["accessway"]
table(d, ["Driveway", "Area (m²)", "Ground RL min to max", "Lots served", "Max depth at 0.3 / 0.6 / 0.9 / 1.2 m design depth", "E36.6.1.8 (≤200 mm if >2 lots)"], [(k, a["area_m2"], f"{a['ground_min']} to {a['ground_max']}", ", ".join(a["lots_served"]), " / ".join(str(a["max_depth_by_peak_depth"][x]) for x in D), "Not triggered (serves 2 lots). If it served >2 lots: exceeds 200 mm at every ASSUMED depth, because it crosses the lowest ground.") for k, a in acc.items()], widths=[3.2, 1.5, 2.6, 1.6, 3.8, 4.5], size=7.5, rule=False)
# ---- Access/egress
d.add_heading("Access, egress and emergency plan", 1)
para(d, "Residents must be able to reach every unit and leave the site safely in the design flood, so the access route is designed as carefully as the foundations.")
bullets(d, [("Hazard classification: the engineer rates depth × velocity along the access route and the street frontage against a recognised hazard scale, and confirms which one Council accepts. [ENGINEER] D×V values at the ASSUMED depths and velocities are in Table 9; no hazard scale has been applied (none verified).", ORG),
 ("Raised walkways: a raised path at or near FFL linking the units to the street and any dry refuge. Not drawn; lengths follow Table 8.", None),
 ("Stairs and ramps: sized from the pile heights in the floor level table (Tables 6 to 8). Confirm with the architect whether an accessible route is required to each unit.", None),
 ("Shelter in place: the raised floors give dry refuge, but the engineer states how long the access route could be cut off. Not known: needs the hydrograph.", ORG),
 ("Emergency plan: flood warning sign-up, evacuation route signage and a one-page plan in every tenancy pack. Template to be written once the model gives route depths.", None)])
# ---- Stormwater
d.add_heading("Stormwater, compensatory storage and no-worsening", 1)
para(d, "The report must prove the development does not raise flood levels on neighbouring land or upstream and downstream, which is what Council and Building Act s72 turn on.")
imp = E["impervious"]
bullets(d, [("Pre and post comparison: model flood levels and flow paths before and after the development, and show no increase at the boundaries. Not modelled: needs the engineer's hydraulic model.", ORG),
 ("Fill: none intended. Any pad, ramp or walkway volume in the floodplain needs compensatory storage cut from the same level band on site. Pile displacement is in Table 13; stairs, ramps and walkways are open structures and are not volumed.", None),
 ("Blockage: include a blockage allowance for piles, fences and debris in the post-development model.", None),
 ("Impervious area: check the Stormwater Management Area Flow controls and size attenuation (tanks or underfloor storage) for the new roofs and hardstand. [ENGINEER] SMAF overlay is not mapped at the lots (point test, S11). New impervious per four-unit group: roof 240 m² + driveway 140.8 m² + parking 100 m² = 480.8 m² (CALCULATED); each 10 mm of storage over that area is 4.8 m³. The Council attenuation requirement (Stormwater Code of Practice / GD01) was not read: UNVERIFIED.", ORG),
 ("Outlets: confirm the connection point and capacity for the site's stormwater with Healthy Waters. Nearest public stormwater pipe 157 to 173 m away; no catchpit or manhole within 250 m in the layer (DATA S10). PC120 Combined Wastewater Network Control applies (S9): UNVERIFIED.", ORG)])
d.add_heading("Table 13: displaced flood storage by piles (CALCULATED: 300 mm square piers, 25% allowance for bracing and lattice; m³)", 3)
table(d, ["Unit"] + [f"@ {x} m" for x in D], [(k,) + tuple(f2(v[x]) for x in D) for k, v in E["storage"].items()], widths=[2.4, 3.7, 3.7, 3.7, 3.7], rule=False)
# ---- Engineer deliverables
d.add_heading("Engineer deliverables", 1)
para(d, "Brief the engineer to produce these eight items, and ask for a fixed fee against this list.")
table(d, ["#", "Deliverable", "Content", "Status in this pack"], [
 (1, "Topographic survey", "Levels, boundaries, flow path features, existing services.", "Not done. LiDAR 1 m DEM used instead (S6); accuracy not stated here: UNVERIFIED."),
 (2, "Geotechnical report", "Soil profile, bearing capacity, scour depth, pile recommendations.", "Not done. Confirmed Input 2 is ASSUMED."),
 (3, "Flood model", "Council flood data as baseline, site refinement, climate change case, pre and post development.", "Not done. Confirmed Inputs 1 and 3 are ASSUMED. Council layers give extent only."),
 (4, "Flood hazard assessment", "Depth, velocity and hazard maps, FFL schedule, no-worsening statement.", "FFL schedule drafted (Table 6) from ASSUMED depths. No maps or statement."),
 (5, "Structural design", "Pile layout, chassis connections, flood and uplift loads, drawings.", "PRELIMINARY loads (Tables 9, 10); pile layout drawing 3."),
 (6, "Stormwater management plan", "Attenuation, impervious area controls, compensatory storage if any.", "Impervious areas and pile displacement only."),
 (7, "Access and egress assessment", "Route hazard rating, walkway and ramp design, emergency plan.", "Stair and ramp lengths only (Table 8)."),
 (8, "Producer statements", "PS1 design from the CPEng, PS4 construction review before code compliance.", "Not drafted. Left for the engineer.")], widths=[0.7, 3.6, 6.2, 6.7], size=8)
# ---- Design basis
d.add_heading("Design basis", 1)
para(d, "The engineer states the design basis once at the front of the report, so Council and the financier can see every assumption. Standards and versions below are the engineer's to confirm against the current Building Code citations. [ENGINEER]", fill=ORG)
table(d, ["Parameter", "Basis", "Used in this pack"], [
 ("Flood design event for floor levels", "1% AEP flood level, including the climate change allowance Council requires, plus 500mm freeboard.", "ASSUMED depth 0.3 to 1.2 m; climate change allowance not available (UNVERIFIED)."),
 ("Building Code E1.3.2 check", "Show the 2% AEP surface water level stays below every floor level.", "Not checkable: no 2% AEP level. FFL is above the 1% AEP level by 0.5 m."),
 ("Building Code E1.3.1 check", "Show surface water collected or concentrated by the buildings and sitework in a 10% AEP event causes no damage or nuisance to other property.", "Not checked: needs the model."),
 ("Design working life", "50 years for the foundations, chassis connections and other elements that give structural stability or are hard to replace (B2.3.1). Shorter lives for easily replaced elements, as B2 allows.", "Taken as written; B2.3.1 UNVERIFIED."),
 ("Gravity, wind and seismic actions", "AS/NZS 1170.0 and 1170.1, AS/NZS 1170.2 and NZS 1170.5, with the load combinations from AS/NZS 1170.0.", "Gravity only, ASSUMED loads (G 120 kg/m², Q 1.5 kPa). Wind and seismic not calculated. Standards not read: UNVERIFIED."),
 ("Flood actions", "Hydrostatic pressure, hydrodynamic drag, debris impact, scour and uplift. There is no prescriptive NZ standard for these, so the engineer names the method adopted (for example ASCE 7 Chapter 5 or FEMA P-259) and applies it consistently.", "Drag F = ½ρC_dAv² with ASSUMED C_d; hydrostatic ½ρgh²; uplift = buoyancy − dead load. Method not adopted from ASCE 7 or FEMA P-259 (neither read): UNVERIFIED. Debris impact and scour not calculated."),
 ("Foundation design", "Specific engineering design under Building Code B1 using the geotechnical report. NZS 3604 is not used for flood-loaded foundations.", "Taken as written."),
 ("Hydraulic model", "Council's flood hazard model as the baseline, refined on site, with pre and post development runs for the 1% AEP event and the climate change case.", "Not available. Council layers (S2, S3) give extent and a spill level only."),
 ("Datums", "Levels on the datum Council's flood model uses, confirmed with Healthy Waters and stated on every drawing.", "LiDAR NZVD2016 (ASSUMED); flood layers NZVD2016; flow path layer NZVD1946. UNVERIFIED offset."),
 ("Ground parameters", "Soil profile, bearing capacity, scour depth and groundwater from the geotechnical report.", "ASSUMED, Confirmed Input 2.")], widths=[3.4, 7.2, 6.6], size=8)
# ---- Calculation schedule
d.add_heading("Calculation schedule", 1)
para(d, "Each calculation below goes in the report as a numbered calculation sheet with inputs, method, result and a pass or fail against the criterion. [ENGINEER]", fill=ORG)
table(d, ["#", "Calculation", "Inputs", "Output the report must state", "Result in this pack"], [
 ("C1", "Flood level and floor level per unit", "Model levels, climate change allowance, freeboard", "FFL for each unit, with the 2% AEP margin.", "Table 6 (CALCULATED from ASSUMED depth). 2% AEP margin: not available. Criterion: FFL ≥ level + 0.5 m: met by construction; PENDING real level."),
 ("C2", "Pre and post development flood comparison", "Baseline and developed models", "Level, depth and velocity change at each boundary, shown as zero or below.", "PENDING: needs the hydraulic model."),
 ("C3", "Hazard rating", "Depth and velocity grid", "Hazard class at each unit, parking cell, walkway and the street access.", "D×V values only (Table 9). No hazard scale applied: PENDING."),
 ("C4", "Flood loads on piles and units", "Peak depth, velocity, debris assumption", "Hydrostatic, drag and debris forces per pile line.", "Hydrostatic and drag in Tables 9 and 10. Debris PENDING."),
 ("C5", "Pile design", "Loads, geotech parameters, scour depth", "Pile size, spacing, embedment and capacity check, vertical and lateral.", "PRELIMINARY only (Table 9). Embedment and capacity PENDING geotech."),
 ("C6", "Uplift and tie-downs", "Buoyancy case above design event, wind uplift", "Tie-down capacity at each pile.", "Buoyancy case Table 10: tie-down demand up to 46.6 kN per pile at 1.1 m above design level (CALCULATED). Wind uplift PENDING."),
 ("C7", "Chassis and floor frame check", "Manufacturer drawings, new support points", "Member capacity at the pile positions.", "PENDING: no manufacturer drawings."),
 ("C8", "Bracing and lateral stability", "Flood, wind and seismic loads", "Brace sizes and connection capacity.", "Flood axial force only (Table 9). Wind and seismic PENDING."),
 ("C9", "Compensatory storage", "Volume of any pad, ramp or walkway in the floodplain", "Storage cut on site, by level band, equal to or above the volume displaced.", "Pile displacement ≤ 1.2 m³ per unit at 1.2 m depth (Table 13). Stairs and ramps not volumed. Cut volume: none planned: PENDING."),
 ("C10", "Stormwater attenuation", "New roof and hardstand area, Stormwater Management Area Flow controls", "Tank or storage volume and outlet size.", "Areas only (480.8 m² per four-unit group). Requirement UNVERIFIED: PENDING."),
 ("C11", "Access and egress", "C3 hazard grid, walkway levels", "Route rating and walkway levels from each unit to the street.", "Stair and ramp lengths (Table 8). Route rating PENDING.")], widths=[0.9, 3, 3.4, 4.2, 5.7], size=7.5)
# ---- E36.9(2) outline
d.add_heading("Flood hazard assessment: report outline", 1)
para(d, "The engineer's flood hazard assessment follows E36.9(2)(a)–(l), so one document answers every item Council must see with the resource consent. Section headings below are the report's headings. [ENGINEER]", fill=ORG)
table(d, ["E36.9(2) item", "Report section", "What to include", "Content available from this pack"], [
 ("(a) Type, frequency and scale of the hazard", "1. Hazard characterisation", "1% AEP floodplain and overland flow paths, depths, velocities, duration, climate change case. Use the next 100 years as the E36.9(2) timeframe.", "DATA: 100% flood plain cover and FPA 30836607 on all lots (S2, S3); flow path 852976 across lot 2 (S5). Depth and velocity: ASSUMED ranges only."),
 ("(b) Activity and its vulnerability", "2. Activity", "Residential dwellings, a more vulnerable activity. State the number of units and occupants.", "8 units indicative (operative zoning, amalgamated); 6 units on four titles (current legal position). Occupants: to complete."),
 ("(c) Consequences of an event", "3. Consequence assessment", "What a design event and an event above design does to people and units.", "Uplift case Table 10. Rest PENDING."),
 ("(d) Effects on public safety and other property", "4. Off-site effects", "C2 results at each boundary.", "PENDING"),
 ("(e) Exacerbation or new hazard", "5. No-worsening statement", "C2 and C9, with a signed conclusion that the hazard is not increased.", "Table 13 only. Signed conclusion: engineer."),
 ("(g) Non-structural solutions", "6. Options considered", "Why open piled units and a clear flow path were chosen over fill or walls.", "Concept: piled, no fill (owner)."),
 ("(h) Design and construction of buildings", "7. Building design", "Floor levels, piles, connections, materials, services. Cross-refer to the calculation sheets.", "Tables 6 to 10."),
 ("(i) Effects on landscape and public access", "8. Landscape and access", "Effect of walkways and open fencing on the street frontage.", "Drawing 1."),
 ("(j) Site layout, access and exit", "9. Layout and egress", "C3 and C11, the egress route and refuge.", "Drawings 1 to 3; Table 8, 11, 12."),
 ("(k) Consent duration and climate change", "10. Long-term exposure", "Resilience over the building's life and how the climate change case was used.", "PENDING: climate change level unavailable."),
 ("(l) Measures and plans proposed", "11. Mitigation and management plan", "The measures in this document, the maintenance schedule and the tenant flood plan.", "Sections 'Owner's maintenance and flood plan' and 'Access, egress and emergency plan'."),
 ("Conclusion", "12. Statement and sign-off", "A plain statement that the design meets the matrices in this document, with the CPEng signature and number.", "")], widths=[3.6, 3, 5.2, 5.4], size=7.5)
para(d, "Item (f) in E36.9(2) concerns coastal relocation and does not apply to this inland site, so the report states that in one line. (VERIFIED: item (f) is the coastal item in the operative text, S7.)")
# ---- Drawings
d.add_heading("Drawings and building consent pack", 1)
para(d, "The resource consent comes first, then each unit needs a building consent. The engineer prepares the drawings and statements below so the building consent application can be lodged without rework. Confirm the lodgement requirements with Auckland Council's building consent team, including what they need for relocated buildings. [ENGINEER]", fill=ORG)
table(d, ["Item", "Content", "Status"], [
 ("Site plan", "Boundaries, unit positions, flood extents, overland flow paths, FFL for each unit, parking and access, datum stated.", "Generated: Drawing 1 (below), DRAFT. FFLs in Table 6. No modelled flood extent."),
 ("Flood plan and sections", "1% AEP level drawn on site sections through each unit, showing the freeboard and the clear under-croft.", "Generated: Drawing 4, one indicative long section (L2-U1 at 0.9 m ASSUMED depth). Other sections by the engineer."),
 ("Pile layout plan", "Pile positions, sizes, embedment depths and setout dimensions.", "Generated: Drawing 3, positions only. Sizes and embedment PENDING."),
 ("Foundation details", "Pile-to-chassis connection, tie-downs, bracing, underfloor lattice or breakaway panels.", ""),
 ("Elevations", "FFL, flood level and stair or ramp levels on each unit type.", "Levels in Tables 6 to 8. Drawings: manufacturer / architect."),
 ("Services drawings", "Raised electrical and plant, non-return valves, drainage connections and levels.", ""),
 ("Access plan", "Raised walkways, stairs and ramps, with levels and the egress route.", "Lengths only (Table 8)."),
 ("Stormwater and flood storage plan", "Attenuation, outlets and any compensatory storage.", ""),
 ("Relocated unit report", "Condition and compliance of each unit before the move, with the manufacturer's structural drawings.", ""),
 ("Producer statements", "PS1 design from the CPEng. Council may also ask for PS2 design review.", ""),
 ("Natural hazard information", "The flood hazard assessment, answering Building Act ss71–73.", ""),
 ("Resource consent", "The decision and conditions, attached once issued.", "")], widths=[3.6, 8, 5.6], size=8)
for f, cap in (("01_site_plan.png", "Drawing 1: site plan (indicative)"), ("02_flow_path_plan.png", "Drawing 2: flood and overland flow path plan"), ("03_pile_layout.png", "Drawing 3: indicative pile layout"), ("04_section.png", "Drawing 4: indicative section")):
    para(d, cap, bold=True); img(d, OUT / "drawings" / f, 17.4)
# ---- hold points
d.add_heading("Construction hold points and completion", 1)
para(d, "The engineer's construction review is what lets the code compliance certificate issue. Each hold point below is signed off before the next stage starts. [ENGINEER]", fill=ORG)
table(d, ["#", "Hold point", "Evidence", "Draft acceptance reference (engineer sets limits)"], [
 ("H1", "Pile setout", "Surveyor's setout check against the pile layout plan.", "Drawing 3 positions; tolerance ASSUMED ± 25 mm, engineer sets."),
 ("H2", "Pile installation", "Driving, torque or pour records and embedment depths against design.", "Embedment per geotech: PENDING."),
 ("H3", "Pile top levels", "Surveyed levels confirming FFL is achievable at every unit, before the units are placed.", "Chassis underside RL per unit and depth: Table 6 minus 0.30 m (ASSUMED); tolerance ASSUMED ± 10 mm."),
 ("H4", "Unit placement and connections", "Inspection of chassis-to-pile connections, tie-downs and bracing.", "Per-pile demand Tables 9, 10."),
 ("H5", "Services above FFL", "Inspection of electrical, plant and non-return valves at their levels.", "Level ≥ FFL."),
 ("H6", "Underfloor and access", "Lattice or breakaway panels, walkways, stairs and ramps as drawn.", "≥ 90% void; Table 8."),
 ("H7", "Flow path and landscaping", "Flow path clear, no fill placed, any compensatory storage cut to level.", "Flow path 852976 corridor clear on lot 2."),
 ("H8", "As-built survey", "Final FFL for each unit and flood storage, compared with the design.", "FFL Table 6."),
 ("H9", "Completion statements", "PS4 construction review from the CPEng, plus PS3 from the builder or installer.", "Not drafted. Left for the engineer and builder.")], widths=[0.9, 3.4, 6.4, 6.5], size=8)
# ---- maintenance
d.add_heading("Owner's maintenance and flood plan", 1)
bullets(d, [("Inspect the underfloor space and clear debris every year and after any flood.", None), ("Test non-return valves and check tie-downs and bracing every year.", None), ("Keep the flow path, fences and gaps between units clear of stored items.", None), ("Give every tenant a one-page flood plan with the warning sign-up, the egress route and the refuge.", None), ("Keep the engineer's report, as-built survey and producer statements with the title records for the next owner and the financier.", None)])
table(d, ["Task", "Frequency", "Responsible", "Record"], [("Underfloor inspection and debris clearance", "Yearly and after any flood", "", ""), ("Non-return valve test", "Yearly", "", ""), ("Tie-down and bracing check", "Yearly", "", ""), ("Flow path and fence clearance", "Quarterly (ASSUMED)", "", ""), ("Tenant flood plan issue", "At each tenancy", "", ""), ("Records filed with title papers", "On completion", "", "")], widths=[6, 4, 3.6, 3.6], size=8, rule=True)
# ---- consent path
d.add_heading("Consent path and hold points", 1)
para(d, "Expect a resource consent under E36 for the dwellings in the floodplain, plus the density consent for the zoning, then a building consent for each relocated unit. Work through these in order, because each one gates the next.")
numbered(d, ["Get the LIMs and Council property files for 2, 4, 6 and 8 from the Bayleys data room before committing. Not obtained; capital values not in the app.", "Appoint one CPEng, who commissions the survey and geotech. Not appointed.", "Engineer runs the flood model and locks the FFL schedule and unit count. Not run.", "Engineer issues the flood hazard assessment, structural design and PS1. Not issued.", "Lodge the resource consent with the report attached, then building consents per unit. Not lodged. Confirm the PC120 version in force at lodgement (PC120 decisions are due by June 2027)."])
# ---- Sources
d.add_heading("Sources", 1)
bullets(d, [("2-8 Parrish Road listing, realestate.co.nz (owner's list; not re-fetched here)", None), ("Council flood assessment citing the 500mm freeboard (owner's list; not read: UNVERIFIED)", ORG), ("E36 restricted discretionary status for dwellings in the floodplain (read in S7: A37, A38)", None), ("Plan Change 120 and flood resilience, NZIA (owner's list; not read)", None), ("Auckland Unitary Plan chapter E36, operative (read, July 2026 text)", None), ("MBIE natural hazard decision guide, Building Act ss71–74 (not read officially: UNVERIFIED)", ORG), ("MBIE determination 2024/053, s72 grant on flood land (not read: UNVERIFIED)", ORG), ("Building Code clause E1 Surface water, compliance document (not read officially: UNVERIFIED)", ORG)])
para(d, "Data sources used in this pack", bold=True)
table(d, ["ID", "Source", "Where / URL", "Retrieved"], [(k, v[0], v[1], v[2]) for k, v in SOURCES.items()], widths=[1, 6.4, 6.4, 3.4], size=7, rule=False)
# ---- Appendix A
d.add_heading("Appendix A: pile ground levels (LiDAR, DATA S6; m RL)", 1)
rows = [(u["id"],) + tuple(f2(p["ground"]) for p in u["piles"]) for u in U]
table(d, ["Unit"] + [f"{'P' + str(k) + s}" for k in range(1, 6) for s in "ab"], rows, widths=[1.6] + [1.56] * 10, size=7, rule=False)
para(d, "Pile rows at 0.5, 4.0, 7.5, 11.0 and 14.5 m from the street end of each unit, a and b at ±1.5 m from the centreline (ASSUMED). Easting and northing for each pile are in data/hazard/parrish/eng_results.json.")
d.save(OUT / "Engineering_Flood_Report.docx"); print("saved")
