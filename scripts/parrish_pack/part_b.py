"""Part B: complete engineering design and specification on the adopted basis."""
from docx_lib import *
from common import *
def build(d, E, DS):
    B = DS["basis"]; u = {x["id"]: x for x in E["units"]}
    d.add_heading("Part B: Complete engineering design and specification (adopted basis)", 1)
    para(d, "Part B completes the design so the engineer's role is to check the adopted values, check the calculations and sign. It is complete to the extent the inputs allow: every input that the flood model, geotechnical report or survey would normally supply is replaced by a stated ADOPTED value chosen on the conservative side. If the engineer's confirmed values are less onerous than these, the design stays safe; if they are more onerous, the affected line below is re-run (scripts/parrish_pack/design.py). Nothing here is certified and no clause of a standard is quoted: methods are named, values are stated, and the standard references are UNVERIFIED.", fill=ORG)
    d.add_heading("B1 Adopted design basis (all ASSUMED unless stated)", 2)
    rows = [("Design flood depth on lowest lot ground", f"{B['depth']} m (top of the 0.3 to 1.2 m planning range)", "ASSUMED: replaces Confirmed Input 1. Above this the piled concept is not viable (stair and ramp lengths, Table 8)."),
     ("Design flow velocity", f"{B['v']} m/s", "ASSUMED upper bound: replaces Confirmed Input 3."),
     ("Soil model", f"Cohesive, undrained shear strength su = {B['su']} kPa (soft to firm), adhesion factor {B['alpha']}, geotechnical reduction {B['phi_geo']}, groundwater at ground surface", "ASSUMED: replaces Confirmed Input 2."),
     ("Scour allowance", f"{B['scour']} m below ground ignored for resistance", "ASSUMED upper end of 0.3 to 1.0 m."),
     ("Pile system", f"Bored concrete pier {int(B['pier_D']*1000)} mm diameter with galvanised steel post CHS {B['post_OD']} x {B['post_t']} mm cast in; steel grade fy {B['fy']} MPa", "ADOPTED. Section availability UNVERIFIED."),
     ("Pile grid", "10 piles per unit: 5 rows at 0.5, 4.0, 7.5, 11.0, 14.5 m from the street end, 2 per row at 3.0 m centres", "ADOPTED (Drawing 3)."),
     ("Floor frame depth", "0.30 m below top of floor; FFL = design flood level + 0.5 m", "ASSUMED; manufacturer drawings to confirm."),
     ("Loads", "Dead 120 kg/m2; live 1.5 kPa; 1.2G + 1.5Q for gravity; strength reduction 0.9 steel", "ASSUMED; combinations from AS/NZS 1170.0 UNVERIFIED."),
     ("Flood actions", "Hydrostatic 0.5 rho g h2; drag 0.5 rho Cd A v2 (Cd 2.0 square, 1.2 round, blockage 1.5); uplift = buoyancy less 0.9 x dead load; debris by impulse-momentum", "Methods named; coefficients ASSUMED; ASCE 7 Ch.5 and FEMA P-259 not read: UNVERIFIED."),
     ("Debris", f"{B['debris_kg']:.0f} kg object at {B['v']} m/s stopping in {B['debris_dt']} s on one pile", "ASSUMED."),
     ("Uplift case", "Water 1.1 m above the design level (event above design)", "ASSUMED; governs embedment and tie-downs."),
     ("Working life", "50 years foundations and structure; B2.3.1", "UNVERIFIED (snippet only).")]
    table(d, ["Parameter", "Adopted value", "Basis"], rows, widths=[4.2, 7.4, 5.6], size=8)
    d.add_heading("B2 Adopted floor level schedule (design depth 1.2 m on the lowest ground of each lot)", 2)
    rows = []
    for k, x in u.items():
        l = x["levels"]["1.2"]; rows.append((k, f"{l['flood_level_RL']:.2f}", f"{l['ffl_RL']:.2f}", f"{l['chassis_underside_RL']:.2f}", f"{l['pile_exposed_min_m']:.2f} to {l['pile_exposed_max_m']:.2f}", f"{l['stair_risers']} risers, run {l['stair_run_m']} m; ramp {max(l['ramp_length_m'], 0):.1f} m"))
    table(d, ["Unit", "Design flood level (m RL)", "FFL (m RL)", "Chassis underside (m RL)", "Exposed pile height (m)", "Stairs / ramp at door end"], rows, widths=[1.8, 3, 2.4, 3, 3.2, 3.8], rule=False)
    para(d, "Where the exposed pile height is negative the ground is above the chassis underside at that pile: the pad is cut to the underside less 0.15 m clearance (cut volume to be balanced on site, C9). Confirmed lower levels reduce these FFLs; Table 6 gives FFL for 0.3, 0.6 and 0.9 m.")
    d.add_heading("B3 Foundation design checks (worst case, unit " + DS["worst_pile_unit"] + ")", 2)
    s = DS["section"]; db = DS["debris"]; bk = DS["buckling"]; em = DS["embedment"]; cn = DS["connection"]
    rows = [("Steel post section", f"CHS {B['post_OD']} x {B['post_t']}: A = {s['A_mm2']:.0f} mm2, I = {s['I_mm4']:.0f} mm4, Z = {s['Z_mm3']:.0f} mm3", "CALCULATED", "-"),
     ("Bending: debris + drag at fixity", f"M = {db['M_debris_kNm']} (debris {db['F_kN']} kN x {db['lever_m']} m) + {db['M_drag_kNm']} (drag) = {db['M_total_kNm']} kNm vs capacity {db['M_cap_kNm']} kNm (0.9 fy Z)", "CALCULATED", f"{db['util']:.2f}"),
     ("Axial buckling (Euler, K = 2.0)", f"Le = {bk['Le_m']} m; Pcr = {bk['Pcr_kN']} kN; yield capacity {bk['Pyield_kN']} kN; demand {bk['demand_kN']} kN", "CALCULATED", f"{bk['util_Pcr']:.2f}"),
     ("Embedment for uplift (event above design)", f"Demand {em['uplift_demand_kN']} kN per pile; skin friction + submerged weight reaches {em['uplift_cap_at_adopted_kN']} kN at {em['L_adopted_m']} m embedment of the 300 mm pier", "CALCULATED", "1.00 at adopted length"),
     ("Embedment for lateral load (Broms short pile, factor 2)", f"Demand {em['lateral_demand_kN']} kN (unit drag per pile + debris); needs {em['L_lateral_m']} m minimum", "CALCULATED", "OK"),
     ("Bearing (compression)", f"Capacity {em['down_capacity_kN']} kN (9 su end bearing + shaft, reduced) vs demand {em['down_demand_kN']} kN at adopted length", "CALCULATED", f"{em['down_demand_kN']/em['down_capacity_kN']:.2f}"),
     ("Adopted embedment", f"{em['L_adopted_m']} m bored pier length (uplift governs)", "ADOPTED", "-")]
    table(d, ["Check", "Result", "Basis", "Utilisation"], rows, widths=[4, 8.4, 2.2, 2.6], size=8, rule=False)
    para(d, "Finding the engineer should read first: the event-above-design uplift case, not flood drag, sets the foundation. At su = 25 kPa a 300 mm pier needs about 7.75 m embedment to hold 46.6 kN. Options for the engineer: (a) accept bored piers of that depth (adopted here); (b) helical screw piles; (c) design uplift only to the design event (no exceedance tie-down; zero uplift at design because the chassis underside is 0.2 m above the design level). A real geotechnical report may change this either way.", fill=ORG)
    d.add_heading("B4 Connections and bracing", 2)
    rows = [("Chassis to post", f"Steel cap plate welded to post, {B['nbolts']} x M16 grade 8.8 (As = {B['bolt_As']:.0f} mm2) through the chassis rail; tie capacity {cn['tie_cap_kN']} kN (phi 0.8 x fu x As x 2)", f"demand {cn['tie_demand_kN']} kN", "CALCULATED; bolt standard UNVERIFIED"),
     ("Post to pier", "Post cast 600 mm into the pier with a welded stud ring; galvanised", "to carry the 46.6 kN uplift into the pier", "ADOPTED detail, not calculated: engineer"),
     ("Bracing", f"Tension-only 50 x 50 x 5 EA diagonals (A = {B['brace_A']:.0f} mm2) between post lines, bolted M12; capacity {cn['brace_cap_kN']} kN", f"flood demand {cn['brace_demand_kN']} kN", "CALCULATED; minimum practical section governs; wind/seismic not calculated"),
     ("Underfloor", "Open timber or galvanised lattice at least 90% void or breakaway panels; no solid skirts", "-", "ADOPTED"),
     ("Fixings in the wetting zone", "Hot-dip galvanised or stainless steel; no untreated steel below the design level plus 0.5 m", "-", "ADOPTED; coating standard UNVERIFIED")]
    table(d, ["Item", "Adopted detail", "Demand", "Status"], rows, widths=[3, 7.6, 3, 3.6], size=8)
    d.add_heading("B5 Hazard rating, no-worsening and flood storage", 2)
    af = DS["afflux_mm_per_unit"]
    para(d, "Hazard rating: depth x velocity is tabulated in Table 9 (0.15 to 2.4 m2/s). No hazard scale is applied because the official scale could not be retrieved (the AIDR guideline host is outside this session's network allow-list: knowledge.aidr.org.au). Allow it and the classes can be added: UNVERIFIED.", fill=ORG)
    para(d, "No-worsening, simple momentum estimate (CALCULATED; not a substitute for the hydraulic model): afflux per unit = unit drag / (rho g W d) with a 10 m flow width.", bold=False)
    rows = [(f"{dd} m", ) + tuple(f"{af[f'{dd}|{vv}']} mm" for vv in ("0.5", "1.0", "2.0")) for dd in D_]
    table(d, ["Depth", "0.5 m/s", "1.0 m/s", "2.0 m/s"], rows, widths=[3, 4, 4, 4], rule=False)
    para(d, "At 2.0 m/s the estimate is 14 to 34 mm per unit row and would stack across several rows: no-worsening cannot be assumed at that velocity, and the engineer's model must show it. At 1.0 m/s or less it is under 9 mm per unit. Pile displacement of flood storage is in Table 13.", fill=ORG)
    d.add_heading("B6 Stormwater (indicative storage volumes)", 2)
    rr = DS["runoff_m3"]
    table(d, ["Runoff depth stored", "Four-unit group (480.8 m2 impervious), m3", "Whole eight-unit scheme (961.6 m2), m3"], [(k, str(v[0]), str(v[1])) for k, v in rr.items()], widths=[4, 6.6, 6.6], rule=False)
    para(d, "The Council's required attenuation depth (Stormwater Code of Practice / GD01) was not retrievable: UNVERIFIED. Read the required depth from this table. Storage can be an underfloor tank per unit.", fill=ORG)
    d.add_heading("B7 Construction specification", 2)
    cl = [("1 General", "Work to the drawings in this report and the engineer's issued-for-construction set. Setout by a registered surveyor on the datum stated on every drawing. Hold points H1 to H9 are binding: no stage starts before the previous hold point is signed."),
     ("2 Bored piers", f"{int(B['pier_D']*1000)} mm diameter, {DS['embedment']['L_adopted_m']} m minimum embedment below pile top or to the geotechnical depth, whichever is greater. Concrete strength and cover as the engineer specifies (standard UNVERIFIED). Pour records kept for H2."),
     ("3 Steel posts", f"CHS {B['post_OD']} x {B['post_t']}, grade {B['fy']:.0f}; hot-dip galvanised after fabrication. Cast 600 mm into the pier. Top level set to the chassis underside less cap plate; tolerance +/- 10 mm."),
     ("4 Chassis connection", "Cap plate and 2 x M16 bolts per post; torque recorded; tie-down check at H4."),
     ("5 Bracing", "Diagonals fixed before the unit is placed; checked at H4."),
     ("6 Underfloor", "At least 90% void lattice or breakaway panels; no solid skirts; inspected at H6."),
     ("7 Services", "All electrical, hot water, heat pump and gas above FFL; non-return valves on wastewater and stormwater; flexible connections at the ground; routed on a raised spine outside the flow path."),
     ("8 Earthworks", "No fill. Cut only to clear pile pads, balanced on site; no spoil in the floodplain."),
     ("9 Fencing", "At least 70% non-solid inside the floodplain."),
     ("10 Records", "As-built survey of pile tops and FFL (H8); engineer's PS4 and builder's PS3 on completion (H9).")]
    table(d, ["Clause", "Requirement"], cl, widths=[3.4, 13.8], size=8, rule=False)
    d.add_heading("B8 Egress route and tenant flood plan (draft text)", 2)
    para(d, "Egress route (from the site plan): from each unit door by raised walkway to the shared driveway, then along the driveway to Parrish Road. Route depth along the driveway equals the lot design depth (Table 12): it is the weak link and is not shown to be safe. [ENGINEER to rate once depths are known.]", fill=ORG)
    bullets(d, [("Before a flood: sign up to Auckland Council / Emergency Management warnings (owner to supply the link); keep a go-bag and torch above floor level.", None), ("When warned: move cars out of the underfloor and parking area; secure bins and loose items; know the route to Parrish Road.", None), ("During a flood: the floor is designed to stay dry above the design level; stay inside, do not walk or drive through moving water; call 111 if in danger.", None), ("After: do not use electrics that were wetted; owner inspects the underfloor, valves and tie-downs before re-occupation.", None), ("Contacts: owner [to complete]; Auckland Council flood hotline [to confirm]; emergency 111.", ORG)])
    d.add_heading("B9 Engineer's checking list (what remains for sign-off)", 2)
    table(d, ["#", "Engineer checks", "Where"], [(1, "Replace or accept the adopted flood depth, velocity, soil and scour values (B1).", "Confirmed Inputs"), (2, "Accept the 1.2 m FFL envelope or lower it per lot (B2, Table 6).", "B2"), (3, "Check the pile, uplift, bearing and lateral calculations and choose pier or screw pile (B3).", "B3"), (4, "Check connections, bracing and lattice detail; wind and seismic (B4).", "B4"), (5, "Run or accept the no-worsening assessment; the 2.0 m/s case needs the model (B5).", "B5"), (6, "Confirm attenuation depth and compensatory storage (B6, Table 13).", "B6"), (7, "Confirm the compliance matrix rows marked UNVERIFIED against the official texts.", "Compliance matrix"), (8, "Rate the egress route and accept the tenant flood plan (B8).", "B8"), (9, "Sign: name, CPEng number, report reference, date, signature; issue PS1; later PS4.", "Engineer sign-off")], widths=[0.8, 12.6, 3.8], size=8, rule=False)
    para(d, "Not achievable without data this pack does not have: the hydraulic model (depth, velocity, 2% and 10% AEP levels, climate change level), a geotechnical report, a topographic survey and manufacturer chassis drawings. The adopted values stand in for them; the engineer's sign-off is what turns them into confirmed values.", fill=ORG)
D_ = [0.3, 0.6, 0.9, 1.2]
