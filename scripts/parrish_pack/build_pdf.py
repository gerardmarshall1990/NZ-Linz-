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
DS = jload(DATA / "design.json"); em = DS["embedment"]; pt = DS["piling_total"]
S += [P_("Flood hazard and mitigation", h2), P_("The houses are designed to be lifted on piles above the 1% AEP flood level so floodwater passes beneath them and the site loses no flood storage. Nothing below is certified; it states what the design is designed to meet.", sty), Spacer(1, 1.5)]
bul = [
 "<b>Floor level:</b> 1% AEP flood level plus 500 mm freeboard (owner's specification), intended to sit above the Building Code 2% AEP level (E1.3.2, UNVERIFIED: not read officially). At ASSUMED depths of 0.3 to 1.2 m the floor sits 0.8 to 1.7 m above the lowest lot ground; stairs need up to 10 risers and ramps up to 19.7 m at 1.2 m depth (CALCULATED).",
 "<b>Depth is the open question:</b> if the lot hollows fill to the published 37.03 m RL spill level, depth would be 2.9 to 4.8 m (CALCULATED from LiDAR), far above the 0.3 to 1.2 m planning range used here (ORANGE until the flood model confirms).",
 f"<b>Structure (designed in the report, Part B):</b> {pt['piles']} bored 300 mm piers ({em['L_adopted_m']} m each, {pt['pier_m']:,.0f} m in total) with galvanised steel posts: 12 piles per Dulwich, 10 per Williams. The 52.5 kN event-above-design uplift sets the depth; a design-event-only option cuts it to about {DS['piling_alt']['pier_m']:,.0f} m. Adopted conservative basis: 1.2 m depth, 2.0 m/s, soft clay, 150 kg/m² houses (all ASSUMED).",
 "<b>Flow paths:</b> the Council flow path crosses lot 2 only; a 2 m clearance (ASSUMED) takes 73 m² of that lot and houses H1 and H2 sit clear of it.",
 "<b>Neighbours:</b> pre and post development modelling is to show no worse flooding on other land. Not yet run; a momentum estimate is in Part B5.",
 "<b>Safety:</b> raised walkways, an assessed egress route and a flood plan for every tenancy (Part B8).",
 "<b>Sign-off:</b> the engineering design and specification are complete in the report; the CPEng checks the adopted values and signs the report and PS1 (checklist in Part B9). None is appointed.",
 "<b>Compliance:</b> each measure is mapped to AUP chapter E36 (rows checked against the operative July 2026 text), the Building Act ss71–73 and the Building Code (those two UNVERIFIED)."]
for b in bul: S.append(P_("• " + b, sty))
S += [Spacer(1, 4), P_("Site plan: 10 houses with footprints, yards, gaps, flow path and coverage per lot", h2), Image(str(OUT / "drawings" / "01_site_plan.png"), width=13.6 * cm, height=13.6 * 1250 / 1800 * cm),
      P_("Teal = Dulwich 25 type (7 x 12 m, ASSUMED, x9); orange = Williams 1 type minor dwelling (5 x 13 m, ASSUMED); pale blue = Council overland flow path plus 2 m clearance (ASSUMED); navy = title boundaries (LINZ). Red numbers: 1.5 m front yard and 0.8 m end-to-end gaps. Coverage: lot 2 31.9%, lot 4 47.0%, lot 6 36.2%, lot 8 46.7%. Indicative, not surveyed.", sm)]
S.append(PageBreak())
S += [P_("Proposed development", h2), P_("Place ten Forde Brothers relocatable houses on piles, as one coordinated scheme across all four properties, two on lot 2, three on lot 4, two on lot 6 and three on lot 8.", sty), Spacer(1, 1.5)]
dev = [["Item", "Detail"],
 ["Concept", "Relocatable houses on engineered piles, one column per lot along the lot axis, 0.8 m between houses end to end (ASSUMED), flow path kept clear."],
 ["Unit count", "<b>10 dwellings</b> (2 / 3 / 2 / 3). Not delivered under any single zoning regime: operative zoning 9, current legal position (PC120 immediate-effect rezoning of lots 2 and 4) 8, PC120 as notified 9, PC120 as amended (Single House) 5 (CALCULATED, Zoning_Feasibility.xlsx). The brief lists 8 Dulwich; 2 / 3 / 2 / 3 needs 9, used here."],
 ["Unit type and size", "9 x Dulwich 25 type: 85 m² listed, 3 bed, 1 bath, modelled 7 x 12 m (84 m², ASSUMED). 1 x Williams 1 type minor dwelling: 65 m², 2 bed, modelled 5 x 13 m (ASSUMED), lot 2 only. Dulwich listed at $100,000 + GST including delivery within 200 km and placement on foundations (owner's brief; listing UNVERIFIED: fordebrothers.co.nz not reachable). House dimensions and weights: supplier data to obtain."],
 ["Density basis", "Yards, coverage and dwelling caps per zone. Lots 4 and 8 take 3 houses only with a 1.5 m front yard (0.12 m slack); Mixed Housing Urban needs 2.5 m and 45% coverage (3 houses = 47.0% / 46.7%), so 2. Lot 2: one house plus one minor dwelling (65 m²) is within Single House (35% coverage: 31.9%). Parking: AUP E27.6.2(1) has no minimum; 0 per house assumed (1 per house does not fit on lots 4 and 8)."],
 ["Consents", "Restricted discretionary resource consent for buildings in the 1% AEP floodplain (E36 A37, A38; A42 on lot 2's flow path), dwellings under the zone rules (Mixed Housing Urban up to 3 per site permitted, 4+ restricted discretionary; Terrace Housing restricted discretionary; Single House one dwelling plus one 65 m² minor dwelling), then a building consent per house."],
 ["Exit", "[sell or hold and rent, to complete]"]]
S += [tbl(dev, [3.2, W - 3.2], fills=auto(dev)), Spacer(1, 3)]
fe = [["Regime (all lots, 2 / 3 / 2 / 3 target)", "Separate titles", "One site", "Limit"],
 ["A. Operative AUP (2, 4 THAB; 6, 8 MHU)", "9 (2/3/2/2)", "9", "Lot 8 is MHU: 2.5 m front yard, 45% coverage"],
 ["B. Current legal position (lot 2 Single House, lot 4 MHU)", "8 (2/2/2/2)", "2", "Lots 4 and 8 MHU: 2 houses each; Single House part caps a one-site scheme at 2"],
 ["C. PC120 as notified (2 SHZ, 4 MHU, 6 and 8 THAB)", "9 (2/2/2/3)", "2", "Lot 4 MHU: 2 houses"],
 ["D. PC120 as amended Aug 2026 (all Single House)", "5 (2/1/1/1)", "2", "1 dwelling + minor dwelling (65 m² max) per site; Dulwich cannot be a minor dwelling; 8 only if three more 65 m² minors are sourced (ASSUMED)"]]
note = P_("What would deliver 10: three houses on lot 8 need a 1.5 m front yard (THAB) or Dulwich houses of about 11.5 m (80 m²) or less, which the listed 85 m² does not allow; three on lot 4 need THAB standards (regime A). Slack with 3 houses at 1.5 m front yard: 0.12 m (the 85 m² listing implies about 12.14 m, which does not fit: longest 12.04 m). Zoning_Feasibility.xlsx holds the formulas, the length sensitivity and the parking test.", sm)
S += [P_("Feasibility summary (Zoning_Feasibility.xlsx: houses delivered)", sb), Spacer(1, 1.5), tbl(fe, [6.4, 2.5, 1.7, 7.8], fills={}), Spacer(1, 2), note, Spacer(1, 3)]
S += [P_("Approvals, sign-off and key risks", h2), P_("The technical risk rests on one CPEng's flood hazard assessment and producer statement, and the remaining approvals are Council consents. The first risk below decides whether 10 is possible at all.", sty), Spacer(1, 1.5)]
rk = [["Risk", "Position"],
 ["1. Zoning: 10 is not delivered, and PC120 cuts it further", "No regime gives 10 on separate titles: 9 operative, 8 under the current legal position (lot 2 already Single House and lot 4 Mixed Housing Urban by immediate legal effect from 3 Nov 2025), 9 as notified, and 5 if Council's Aug 2026 amendments (Single House on all four lots, decisions due June 2027) are adopted. UNVERIFIED which standards Council applies to each lot and how an amalgamated site spanning two zones is treated; PC120 hazard-category statuses (non-complying possible) and a Combined Wastewater Network Control standard also apply."],
 ["2. Flood design", "CPEng-signed flood hazard assessment, structural design and PS1 before lodgement. Published spill level implies up to 2.9 to 4.8 m if the hollow fills: depth, velocity, climate-change level, scour and soil all unconfirmed. Piling is about 1,000 m of bored pier unless uplift is designed to the design event only."],
 ["3. Stormwater and wastewater", "Nearest public stormwater pipe 157 to 173 m away; PC120 Combined Wastewater Network Control on all four lots. Connection and capacity UNVERIFIED (Watercare data not loaded)."],
 ["4. Resource consent", "Restricted discretionary under E36 for the floodplain (verified in AUP July 2026). Council's discretion is limited to the flood matters in the report. PC120 proposes different statuses; the version in force at lodgement governs."],
 ["5. Building consent", "Per house, after resource consent. Council may grant under s72 with a s73 notice on the titles (Building Act text UNVERIFIED). Relocated-house condition reports and Building Code fire separation at 0.8 m gaps are UNVERIFIED."],
 ["6. House data", "House sizes (7 x 12, 5 x 13 m), weights (150 kg/m²) and the Williams price are not supplied. Existing buildings on lots 2 and 6 assumed removed."]]
S += [tbl(rk, [3.2, W - 3.2], fills=auto(rk)), Spacer(1, 3)]
S += [P_("Financing request", h2), P_("Terms to complete once the purchase price and feasibility are locked.", sty), Spacer(1, 1.5)]
fin = [["Item", "Entry", "Item", "Entry"],
 ["Borrower", "", "Loan to value", ""],
 ["Facility sought", "", "Term and exit", ""],
 ["Purpose", "Land acquisition, flood mitigation works, relocation and piling, consents", "Sponsor equity", ""],
 ["Security", "First mortgage over 2, 4, 6 and 8 Parrish Road", "Total project cost", "Houses: 9 x $100,000 = $900,000 + GST (CALCULATED from the listing; UNVERIFIED). Williams, land, piling, consents: not supplied"],
 ["Purchase price", "[to complete]", "GDV or rental income", "Not computed: no sale or rent data supplied"]]
fills = {(1, 1): YEL, (2, 1): YEL, (1, 3): YEL, (2, 3): YEL, (3, 3): YEL, (4, 3): ORG, (5, 1): YEL, (5, 3): YEL}
S += [tbl(fin, [2.6, 6.0, 3.0, W - 11.6], fills=fills)]
doc.build(S); print("built")
