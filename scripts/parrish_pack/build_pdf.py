"""Term_Sheet.pdf: exactly two pages. Yellow = owner supplies, orange = confirm / ASSUMED / UNVERIFIED."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Table, TableStyle, Spacer, Image, PageBreak, KeepInFrame
from openpyxl import load_workbook
P = jload(DATA / "pack_data.json"); LOT = {NUM[i]: P["lots"][str(i)] for i in IDS}
wb = load_workbook(OUT / "Zoning_Feasibility.xlsx")   # formulas only: recompute counts from cached engine values below
RUNS = jload(DATA / "scenario_runs.json")
YEL = colors.HexColor("#FFF2CC"); ORG = colors.HexColor("#F8CBAD"); NAVY = colors.HexColor("#1F3864"); GRY = colors.HexColor("#EDEDED")
FS = 7.1
sty = ParagraphStyle("b", fontName="Helvetica", fontSize=FS, leading=FS + 1.6); sb = ParagraphStyle("bb", parent=sty, fontName="Helvetica-Bold")
h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY, leading=15, spaceAfter=1); h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=9.5, textColor=NAVY, leading=11, spaceBefore=3, spaceAfter=2)
sm = ParagraphStyle("sm", parent=sty, fontSize=6.3, leading=7.6)
def P_(t, s=sty): return Paragraph(t, s)
def tbl(rows, widths, header=True, fills=None, fs=None):
    data = [[P_(c, sb if (i == 0 and header) else sty) if isinstance(c, str) else c for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2.5), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5), ("TOPPADDING", (0, 0), (-1, -1), 1.3), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]
    if header: st += [("BACKGROUND", (0, 0), (-1, 0), GRY)]
    for (r, c), col in (fills or {}).items(): st.append(("BACKGROUND", (c, r), (c, r), col))
    t.setStyle(TableStyle(st)); return t
def auto(rows, col=1):
    f = {}
    for i, r in enumerate(rows):
        if i == 0: continue
        t = r[col]
        if t.strip() == "" or t.startswith("[to complete]") or t.startswith("[sell"): f[(i, col)] = YEL
        elif any(k in t for k in ("UNVERIFIED", "ASSUMED", "Confirm", "confirm")): f[(i, col)] = ORG
    return f
doc = BaseDocTemplate(str(OUT / "Term_Sheet.pdf"), pagesize=A4, leftMargin=1.3 * cm, rightMargin=1.3 * cm, topMargin=1.1 * cm, bottomMargin=1.2 * cm, title="2-8 Parrish Road, Sandringham – Development Term Sheet", author="")
W = 21 - 2.6
def foot(c, d):
    c.saveState(); c.setFont("Helvetica", 6.5); c.drawString(1.3 * cm, 0.6 * cm, "DRAFT, screening only, not certified. Yellow = owner supplies; orange = confirm / ASSUMED / UNVERIFIED. Sources S1-S15: data_sources.md."); c.drawRightString(21 * cm - 1.3 * cm, 0.6 * cm, f"Page {d.page} of 2"); c.restoreState()
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, W * cm, 29.7 * cm - doc.topMargin - doc.bottomMargin, 0, 0, 0, 0)], onPage=foot)])
S = []
S += [P_("2–8 Parrish Road, Sandringham – Development Term Sheet", h1), P_("Nov 10, 2026 · @GERARD · Completed from the project app 10 Nov 2026. Indicative, unsigned.", sm), Spacer(1, 3)]
S += [P_("Land specifications", h2), P_("Four adjoining freehold properties totalling 2,006.9 m² (LINZ titles) in Sandringham. Zoned for terrace housing and mixed housing under the operative plan, but Plan Change 120 is already rezoning them (see risks). All four lie in the Council flood plain, with an overland flow path across 2 Parrish Road.", sty), Spacer(1, 2)]
g = {n: LOT[n] for n in "2468"}
land = [["Item", "Detail"],
 ["Address", "2, 4, 6 and 8 Parrish Road, Sandringham, Auckland"],
 ["Total land area", "2,006.9 m² (LINZ titles, DATA S1). Owner's documents and listing: 2,006 m² (UNVERIFIED; rounding)."],
 ["Area by property", "2 Parrish Road 467.4 m² (NA126A/727, Lot 1 DP 198192). 4: 536.0 m² (NA126A/728, Lot 2 DP 198192). 6: 463.6 m² (NA126B/387, Lot 1 DP 199186). 8: 539.9 m² (NA126B/388, Lot 2 DP 199186). 4, 6 and 8 combined 1,539.5 m². Areas per LINZ titles."],
 ["Tenure", "Freehold, fee simple 1/1 on each title (DATA S1)."],
 ["Zoning", "Operative AUP: Terrace Housing & Apartment Building on 2 and 4; Mixed Housing Urban on 6 and 8 (DATA S1, S9). PC120: rezoning of lot 2 to Single House Zone and lot 4 to Mixed Housing Urban has had legal effect since 3 Nov 2025 (s86B(3)(f) RMA). Council's Aug 2026 amendments propose Single House Zone on all four (proposed, not operative; decisions due June 2027) (DATA S8, S9). Confirm with a planner."],
 ["Flood hazards", "All four lots 100% inside the Council 1% AEP flood plain (Meola model, 2017, climate-change adjusted) and Flood Prone Area 30836607, published spill level 37.03 m RL, 'specific calculation is required' (DATA S2, S3). Overland flow path 852976 runs 18.6 m inside lot 2; the nearest paths are 0.4 to 4.8 m from lots 4, 6 and 8 (DATA S5). No flood-sensitive area (S4). Flood depth and velocity are not published: engineer's model needed. UNVERIFIED."],
 ["Topography", "LiDAR 1 m (NZ Elevation 2024, DATA S6): ground 32.2 to 34.2 m RL, lowest on lots 2 and 4 (hollow on the west side), highest on 6 and 8. Mean slope 10.1% / 6.8% / 4.4% / 4.4% (lots 2/4/6/8); 95th percentile 19.6 / 16.4 / 12.3 / 12.2%. Usable after 2 m flow-path clearance (ASSUMED offset): 394 / 536 / 464 / 532 m² = 1,925.7 m². Surveyor's topo to confirm."],
 ["Existing buildings, services", "Buildings: lot 2 182 m², lot 6 184 m²; lots 4 and 8 vacant (Council footprints); assumed removed (ASSUMED). Nearest public stormwater pipe 157 to 173 m (DATA S10). Watercare connections UNVERIFIED. Capital values UNVERIFIED (not in the app)."],
 ["Sale status", "Listed by Bayleys Real Estate Ltd, listing #1657716, by negotiation. Price not disclosed."],
 ["Purchase price", "[to complete]"]]
S += [tbl(land, [3.2, W - 3.2], fills=auto(land)), Spacer(1, 3)]
S += [P_("Flood hazard and mitigation", h2), P_("The units are designed to be lifted on piles above the 1% AEP flood level so floodwater passes beneath them and the site loses no flood storage. Nothing below is certified; it states what the design is designed to meet.", sty), Spacer(1, 1.5)]
bul = [
 "<b>Floor level:</b> 1% AEP flood level plus 500 mm freeboard (owner's specification), intended to sit above the Building Code 2% AEP level (E1.3.2, UNVERIFIED: not read officially). At ASSUMED depths of 0.3 to 1.2 m the floor sits 0.8 to 1.7 m above ground; stairs need 0 to 9 risers and ramps up to 17 m at 1.2 m depth (CALCULATED).",
 "<b>Depth is the open question:</b> if the lot hollows fill to the published 37.03 m RL spill level, depth would be 2.9 to 4.8 m (CALCULATED from LiDAR), far above the 0.3 to 1.2 m planning range used here. The engineer's model decides whether piled units work (ORANGE until confirmed).",
 "<b>Structure (designed in the report, Part B):</b> bored 300 mm concrete piers about 7.75 m deep with galvanised steel posts, open lattice underfloor, bolted tie-downs (46.6 kN uplift case sets the depth) and diagonal bracing; debris, drag, buoyancy, buckling and bearing checked on an adopted conservative basis (design depth 1.2 m, 2.0 m/s, soft clay). Values are ASSUMED until the survey, geotech and flood model confirm them.",
 "<b>Flow paths:</b> designed to be kept clear and used as shared open space; units sit on the higher ground. A 2 m offset each side of the Council centreline removes only 73 m² on lot 2 and no unit.",
 "<b>Neighbours:</b> pre and post development modelling is to show no worse flooding on other land. Not yet run.",
 "<b>Safety:</b> raised walkways, an assessed egress route and a flood plan for every tenancy (to be prepared once route depths are known).",
 "<b>Sign-off:</b> the engineering design and specification are complete in the report; the CPEng checks the adopted values and calculations (checklist in Part B9) and signs the report and PS1. None is appointed.",
 "<b>Compliance:</b> each measure is mapped to AUP chapter E36 (rows checked against the operative July 2026 text), the Building Act ss71–73 and the Building Code (those two UNVERIFIED)."]
for b in bul: S.append(P_("• " + b, sty))
S += [Spacer(1, 4), P_("Site plan and legend (indicative 10-unit layout: one amalgamated site)", h2), Image(str(OUT / "drawings" / "01_site_plan.png"), width=12.6 * cm, height=12.6 * 1250 / 1800 * cm),
      P_("Orange boxes = relocatable 4 x 15 m (60 m²); grey = 3.5 m shared driveway along the east boundary (walkways to units not drawn); blue line = Council overland flow path (centreline); green outline = 20 m² outdoor living; black = title boundaries (LINZ); background = LiDAR ground 32.0 to 34.4 m RL. Indicative screening layout, not surveyed, not engineer-checked. North up.", sm)]
S.append(PageBreak())
# ---- page 2
S += [P_("Proposed development", h2), P_("Place the maximum number of relocatable dwellings the flood model and zoning allow, on piles, as one coordinated scheme across all four properties.", sty), Spacer(1, 1.5)]
dev = [["Item", "Detail"],
 ["Concept", "Relocatable dwellings on engineered piles, laid out as one scheme with a shared flow-path corridor and shared driveways (indicative layout, site plan below)."],
 ["Unit count", "<b>10 dwellings</b> (target): all four lots amalgamated as one site, assessed to Mixed Housing Urban standards (stricter than Terrace Housing), no on-site parking, outdoor living met by 16 m² ground + 5 m² deck. <b>9 dwellings</b> if one parking space per unit and standard 20 m² outdoor living are kept. Both fit the flood-clear layout and pass the yard, coverage (27 to 32% vs 45%), height, HIRB and outdoor-living tests in the app (CALCULATED). Outlook and daylight standards are untested. A 3 + 3 + 3 + 1 split by title does not physically fit: best per title is 1/2/1/2 (6)."],
 ["Unit type and size", "Relocatable 4 m × 15 m, 60 m² gross, 3.8 m high, 2 bedrooms (ASSUMED working unit). Supplier, condition and manufacturer drawings: [to complete]"],
 ["Density basis", "Mixed Housing Urban standards (H5, S7) applied across the whole site: coverage 45%, yards 2.5/1/1 m, 20 m² outdoor living, 3.5 m shared driveway; the AUP sets no minimum parking (E27 Table T17). Usable area after the 2 m flow-path offset is 1,925.7 m²."],
 ["Consents", "Restricted discretionary resource consent for four or more dwellings (MHU H5.4.1 A4; THAB dwellings H6.4.1 A3) and for buildings in the 1% AEP floodplain (E36 A37, A38; A42 on lot 2's flow path), then a building consent per unit. Amalgamation (or unit title) is needed because units cross the old title lines: UNVERIFIED route. Up to 3 dwellings per site is permitted in MHU only on separate sites."],
 ["Exit", "[sell or hold and rent, to complete]"]]
S += [tbl(dev, [3.2, W - 3.2], fills=auto(dev)), Spacer(1, 3)]
# feasibility + site plan side by side
fe = [["Scenario", "Dwellings", "Consent route", "Relies on"],
 ["T10 target: one site, MHU standards, no on-site parking, deck outdoor living", "10", "RD (H5.4.1 A4) + E36 RD", "No parking minimum; deck accepted as outdoor living; lot 2 SHZ rezoning not limiting"],
 ["T9 target: one site, MHU standards, 1 space per unit, standard outdoor living", "9", "RD (H5.4.1 A4) + E36 RD", "Lot 2 SHZ rezoning not limiting"],
 ["Current legal position, four separate titles (lot 2 Single House)", "6", "Permitted (3 per MHU site, 1 on lot 2) + E36 RD", "Immediate-effect PC120 rules"],
 ["PC120 as amended Aug 2026 (all Single House), four titles / amalgamated", "4 / 2", "1 + minor dwelling per site", "Council amendments adopted (decisions due June 2027)"]]
note = P_("Units shown are flood-clear (flood changes no count) and pass the tests the app can run; outlook and daylight standards are untested and are the likely limit at this density. T9 and T10 are not lot-by-lot: units straddle title lines, so the whole site is one site (4 or more dwellings = restricted discretionary). Sensitivity: with 2 parking spaces per unit the same site fits only 4; 1 space gives 9; none gives 9, or 10 with the deck. Zoning_Feasibility.xlsx (sheet Target_Scheme) holds the formulas.", sm)
S += [P_("Feasibility summary (Zoning_Feasibility.xlsx: Target_Scheme and 36 comparison scenarios, live formulas)", sb), Spacer(1, 1.5), tbl(fe, [7.0, 1.6, 4.6, 5.2], fills={(1, 1): YEL}), Spacer(1, 2), note, Spacer(1, 3)]
S += [P_("Approvals, sign-off and key risks", h2), P_("The technical risk rests on one CPEng's flood hazard assessment and producer statement, and the remaining approvals are Council consents. The first risk below can cut the unit count by half.", sty), Spacer(1, 1.5)]
rk = [["Risk", "Position"],
 ["1. Plan Change 120 down-zoning", "Lot 2 is already Single House (immediate legal effect from 3 Nov 2025) and lot 4 Mixed Housing Urban. Council's Aug 2026 amendments propose Single House on all four lots; decisions due June 2027. Single House allows one dwelling plus one minor dwelling (65 m² max) per site, so 9 to 10 dwellings becomes 4 on four titles or 2 amalgamated. How Council would treat one amalgamated site spanning two zones is UNVERIFIED. PC120 also adds hazard-category statuses (non-complying possible; category per lot UNVERIFIED) and a Combined Wastewater Network Control standard."],
 ["2. Flood design", "CPEng-signed flood hazard assessment, structural design and PS1 before lodgement. Published spill level implies up to 2.9 to 4.8 m if the hollow fills: depth, velocity, climate-change level, scour and soil all unconfirmed."],
 ["3. Stormwater and wastewater", "Nearest public stormwater pipe 157 to 173 m away; PC120 Combined Wastewater Network Control on all four lots. Connection and capacity UNVERIFIED (Watercare data not loaded)."],
 ["4. Resource consent", "Restricted discretionary under E36 for the floodplain (verified in AUP July 2026). Council's discretion is limited to the flood matters in the report. PC120 proposes different statuses; the version in force at lodgement governs."],
 ["5. Building consent", "Per unit, after resource consent. Council may grant under s72 with a s73 notice on the titles (Building Act text UNVERIFIED)."],
 ["6. Unit count", "10 is a screening result: layout is dense (units 0.1 to 1 m apart), no on-site parking, outlook and daylight untested, walkways and fire-fighting access to every unit not drawn, building-code fire separation between units not checked (UNVERIFIED). Existing buildings on lots 2 and 6 assumed removed."]]
S += [tbl(rk, [3.2, W - 3.2], fills=auto(rk)), Spacer(1, 3)]
S += [P_("Financing request", h2), P_("Terms to complete once the purchase price and feasibility are locked.", sty), Spacer(1, 1.5)]
fin = [["Item", "Entry", "Item", "Entry"],
 ["Borrower", "", "Loan to value", ""],
 ["Facility sought", "", "Term and exit", ""],
 ["Purpose", "Land acquisition, flood mitigation works, relocation and piling, consents", "Sponsor equity", ""],
 ["Security", "First mortgage over 2, 4, 6 and 8 Parrish Road", "Total project cost", "Not computed: no purchase price or unit costs supplied"],
 ["Purchase price", "[to complete]", "GDV or rental income", "Not computed: no sale or rent data supplied"]]
fills = {(1, 1): YEL, (2, 1): YEL, (1, 3): YEL, (2, 3): YEL, (3, 3): YEL, (4, 3): YEL, (5, 1): YEL, (5, 3): YEL}
S += [tbl(fin, [2.6, 6.4, 3.0, W - 12], fills=fills)]
doc.build(S); print("built")
