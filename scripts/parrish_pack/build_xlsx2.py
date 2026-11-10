"""Zoning_Feasibility.xlsx for the 10-house Forde Brothers scheme. Live formulas; values tagged DATA / CALCULATED / ASSUMED / UNVERIFIED."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
P = jload(DATA / "pack_data.json"); LAY = jload(DATA / "forde_layout.json"); E = jload(DATA / "eng_results.json")
LOTS = {NUM[i]: P["lots"][str(i)] for i in IDS}
YEL = PatternFill("solid", fgColor="FFF2CC"); ORG = PatternFill("solid", fgColor="F8CBAD"); HDR = PatternFill("solid", fgColor="1F3864"); GRY = PatternFill("solid", fgColor="EDEDED")
B = Font(bold=True); WH = Font(bold=True, color="FFFFFF"); thin = Side(style="thin", color="BBBBBB"); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
wb = Workbook()
def head(ws, row, cols, widths):
    for j, c in enumerate(cols, 1):
        x = ws.cell(row, j, c); x.font = WH; x.fill = HDR; x.alignment = Alignment(wrap_text=True, vertical="center"); x.border = BOX
    for j, w in enumerate(widths, 1): ws.column_dimensions[CL(j)].width = w
    ws.freeze_panes = f"A{row + 1}"
def wrap(ws):
    for row in ws.iter_rows():
        for c in row:
            if c.row > 1 or True: c.alignment = Alignment(wrap_text=True, vertical="top")
# README
ws = wb.active; ws.title = "README"
rd = [("2-8 Parrish Road, Sandringham: zoning and feasibility workbook, 10-dwelling scheme with Forde Brothers houses", B), (f"Built {TODAY} from the project app. Screening only: not advice, not a design, not certified.", None), ("", None),
 ("The scheme", B), ("10 dwellings: 9 x Dulwich 25 type (listed 85 m2, 3 bed, 1 bath, modelled 7 x 12 m = 84 m2) and 1 x Williams 1 type minor dwelling (65 m2, 2 bed, modelled 5 x 13 m) on lot 2. Target 2 / 3 / 2 / 3 houses on lots 2 / 4 / 6 / 8, one column per lot along the lot axis.", None),
 ("Discrepancy flagged: the brief says 8 Dulwich + 1 Williams, but 2/3/2/3 = 10 dwellings needs 9 Dulwich + 1 Williams (the brief's own figure shows 9 Dulwich + 1 Williams). This workbook uses 9 + 1.", ORG),
 ("House dimensions (7 x 12, 5 x 13) are ASSUMED: supplier data to obtain. Prices: Dulwich listed $100,000 + GST incl. delivery within 200 km and placement on foundations (from the owner's brief; listing not re-fetched: UNVERIFIED). fordebrothers.co.nz is not reachable from this session.", ORG), ("", None),
 ("Sheets", B), ("Houses: the house set. Rules: zone standards and dwelling caps with AUP clause references (S7). Lots: DATA per title. Fit: layout-engine results per lot and yard set (shapely solve on the real LINZ polygon, S14). Regimes: lot-by-lot delivered houses under four zoning regimes. Scenarios: totals, with separate titles and amalgamated. Sensitivity: house length 11.5 to 12.2 m. Parking. Reconciliation.", None), ("", None),
 ("Regimes", B), ("A. Operative AUP: 2 and 4 THAB; 6 and 8 MHU. B. Current legal position (ASSUMED reading): lot 2 Single House and lot 4 Mixed Housing Urban under PC120 rezoning with immediate legal effect (s86B(3)(f) RMA); 6 and 8 operative MHU. C. PC120 as notified 3 Nov 2025: 2 SHZ, 4 MHU, 6 THAB, 8 THAB. D. PC120 as amended 27 Aug 2026: Single House on all four (proposed, not operative; decisions due June 2027).", None),
 ("Constraints applied: yards per zone (front 1.5 THAB / 2.5 MHU / 3 SHZ; 1 m side and rear), 0.8 m between houses end to end (ASSUMED; Building Code fire separation UNVERIFIED), 2 m clear of Council flow paths (ASSUMED), building coverage per zone on net site area, dwelling cap per zone. The owner's brief yard set (1.5 front, 1 side and rear) is carried as 'USER'.", None), ("", None),
 ("Colour key: yellow = input to supply or edit, orange = confirm / ASSUMED / UNVERIFIED, grey = DATA, white = CALCULATED.", None)]
for i, (t, f) in enumerate(rd, 1):
    c = ws.cell(i, 1, t); c.alignment = Alignment(wrap_text=True)
    if f is B: c.font = B
    elif f is ORG: c.fill = ORG
ws.column_dimensions["A"].width = 160
# Houses
wh = wb.create_sheet("Houses"); head(wh, 1, ["Code", "House", "Listed floor area m2", "Modelled width m", "Modelled length m", "Footprint m2 (formula)", "Bedrooms", "Bathrooms", "Price (owner's brief)", "Basis"], [8, 22, 12, 12, 12, 14, 10, 10, 60, 70])
wh.append(["D", "Dulwich 25 type", 85, 7, 12, "=D2*E2", 3, 1, "$100,000 + GST incl. delivery within 200 km and placed on foundations; 9 houses = $900,000 + GST (CALCULATED)", "Listed data from the owner's brief (UNVERIFIED here). Dimensions ASSUMED: obtain from supplier. Dead load ASSUMED 150 kg/m2."])
wh.append(["W", "Williams 1 type (minor dwelling)", 65, 5, 13, "=D3*E3", 2, 1, "not supplied", "Listed area 65 m2 = the AUP minor dwelling limit (65 m2 excluding decks and garaging, H3.6.4(1)), so any deck or garage pushes it over: UNVERIFIED. Lot 2 only. Dimensions ASSUMED."])
for r in (2, 3):
    for c in (4, 5): wh.cell(r, c).fill = ORG
wh.cell(5, 1, "Counts"); wh.cell(6, 1, "Dulwich"); wh.cell(6, 2, 9).fill = YEL; wh.cell(7, 1, "Williams"); wh.cell(7, 2, 1).fill = YEL; wh.cell(8, 1, "Total dwellings"); wh.cell(8, 2, "=B6+B7"); wh.cell(9, 1, "Total footprint m2"); wh.cell(9, 2, "=B6*F2+B7*F3"); wh.cell(10, 1, "Total bedrooms"); wh.cell(10, 2, "=B6*G2+B7*G3"); wh.cell(11, 1, "Dulwich cost ex GST NZD"); wh.cell(11, 2, "=B6*100000")
wrap(wh)
# Rules
wr = wb.create_sheet("Rules")
head(wr, 1, ["Zone", "Name", "Building coverage max %", "Impervious max %", "Landscaped min %", "Front yard m", "Side yard m", "Rear yard m", "Dwelling cap, lot with house + minor dwelling (lot 2)", "Dwelling cap, other lots (Dulwich only)", "Clauses (AUP operative July 2026, S7)", "Notes"], [8, 36, 11, 11, 11, 9, 9, 9, 16, 16, 62, 70])
rules = [("THAB", "Residential - Terrace Housing and Apartment Building", 50, 70, 30, 1.5, 1, 1, 99, 99, "H6.4.1 A3 dwellings RD; H6.6.9 yards; H6.6.10 impervious; H6.6.11 coverage; H6.6.12 landscaped", "99 = no numeric cap; consent pathway restricted discretionary."),
         ("MHU", "Residential - Mixed Housing Urban", 45, 60, 35, 2.5, 1, 1, 99, 3, "H5.4.1 A3 up to 3 dwellings per site permitted, A4 four or more RD; H5.6.8 yards; H5.6.9 impervious; H5.6.10 coverage; H5.6.11 landscaped", "Cap column shows 3 permitted dwellings per site; more is restricted discretionary and not counted as permitted here. Lot 2 box: 99 (RD pathway) as a house + minor dwelling is two dwellings."),
         ("SHZ", "Residential - Single House", 35, 60, 40, 3, 1, 1, 2, 1, "H3.4.1 A3 one dwelling P [row not re-read]; A5 minor dwelling P (H3.6.4: 65 m2 max excluding decks and garaging, one per site); A6 more than one dwelling NC; H3.6.8 yards; H3.6.9 impervious 60%; H3.6.10 coverage 35%; H3.6.11 landscaped 40%", "A5 minor dwelling row carries 'PC 120 immediate legal effect under s86B(3)(f)' in the AUP text. Second dwelling on lots 4, 6 and 8 would be a Dulwich (84 m2), which exceeds 65 m2 and so is not a minor dwelling: cap 1. SHZ yard values UNVERIFIED against the table.")]
for r in rules: wr.append(list(r))
for r in range(2, 5):
    for c in (9, 10): wr.cell(r, c).fill = YEL
wr["A6"] = "THAB and MHU values: DATA, read in S7 (zone_rules_used in hazard_report.json). Yellow cells are editable caps."
wrap(wr)
# Lots
wl = wb.create_sheet("Lots")
head(wl, 1, ["Lot", "Address", "Title ref", "Land area m2 (LINZ)", "Operative zone", "PC120 notified zone", "PC120 amended zone", "Flood plain cover %", "Flow path inside lot m", "Usable m2 after 2 m clearance", "LiDAR ground min m RL", "Ground mean", "Slope mean %", "Frontage depth m (lot frame)", "Width m (lot frame)", "Existing building m2", "Basis"], [6, 34, 13, 11, 36, 34, 34, 9, 10, 12, 10, 9, 9, 11, 11, 11, 30])
for i, n in enumerate(("2", "4", "6", "8"), 2):
    l = LOTS[n]; fp = l.get("flow_path_location_in_lot") or []
    row = [int(n), l["address"], l["title_no"], l["area_m2"], l["zone_operative"], l["pc120"]["notified_nov2025"]["zone"], l["pc120"]["amended_aug2026"]["zone"], l["flood_layers"]["ac_hz_flood_plains"][0]["covers_pct"], sum(x["length_m"] for x in fp), l["usable_after_clearance"]["2m_each_side"]["usable_m2"], l["ground"]["elevation_min_m"], l["ground"]["elevation_mean_m"], l["ground"]["slope_mean_pct"], LAY["lots"][n]["depth_m"], LAY["lots"][n]["width_m"], sum(l["buildings"]["footprint_m2"]), "DATA S1, S2, S5, S6, S9; S14"]
    for j, v in enumerate(row, 1): c = wl.cell(i, j, v); c.fill = GRY
wl.cell(7, 1, "Total"); wl.cell(7, 4, "=SUM(D2:D5)"); wl.cell(7, 10, "=SUM(J2:J5)"); wrap(wl)
# Fit
wf = wb.create_sheet("Fit")
head(wf, 1, ["Key", "Lot", "Yard set", "Front yard m", "Fit 1 house", "Fit 2 houses", "Fit 3 houses", "Max houses that fit", "Max length of every house in the column (m)", "Basis"], [12, 6, 10, 10, 9, 9, 9, 11, 22, 80])
comp = {2: 2, 4: 3, 6: 2, 8: 3}; fr = 2
for n in (2, 4, 6, 8):
    for yk in ("THAB", "MHU", "SHZ", "USER"):
        ml = LAY["maxlen"].get(f"{n}|{yk}") or LAY.get("maxlen_short", {}).get(f"{n}|{yk}")
        row = [f"{n}|{yk}", n, yk, LAY["yards"][yk][0]] + [1 if LAY["fits"].get(f"{n}|{yk}|{k}") else (0 if k <= comp[n] else None) for k in (1, 2, 3)]
        wf.append(row); wf.cell(fr, 8, f"=SUM(E{fr}:G{fr})"); wf.cell(fr, 9, ml); wf.cell(fr, 10, "CALCULATED S14: house column(s) solved on the lot polygon in its frame; yards per set; 0.8 m end gaps; 2 m flow-path offset; 12.0 m houses (lot 2: 12 m + 13 m). Length for lots where 3 do not fit = longest equal length that does fit."); fr += 1
wrap(wf)
# Regimes
wg = wb.create_sheet("Regimes")
cols = ["Key", "Regime", "Lot", "Zone standards applied", "Target houses", "Max that fit (yards)", "Land area m2", "Coverage limit %", "Footprint of target m2", "Coverage of target %", "Coverage cap (houses)", "Dwelling cap", "Delivered (MIN)", "Fit-limited (for amalgamation)", "Footprint of fit-limited m2", "Governing", "Consent pathway", "Flood consent", "PC120 legal-effect note"]
head(wg, 1, cols, [8, 7, 6, 10, 9, 10, 10, 10, 11, 11, 11, 10, 10, 12, 12, 40, 44, 34, 60])
REG = {"A": {2: "THAB", 4: "THAB", 6: "MHU", 8: "MHU"}, "B": {2: "SHZ", 4: "MHU", 6: "MHU", 8: "MHU"}, "C": {2: "SHZ", 4: "MHU", 6: "THAB", 8: "THAB"}, "D": {2: "SHZ", 4: "SHZ", 6: "SHZ", 8: "SHZ"}}
NOTE = {("B", 2): "Rezoned to Single House with immediate legal effect (s86B(3)(f)); the Single House minor dwelling rule A5 also carries immediate effect.", ("B", 4): "Rezoned to Mixed Housing Urban with immediate legal effect.", ("A", 2): "Operative; PC120 immediate-effect rezoning is NOT applied in regime A.", ("A", 4): "Operative; PC120 immediate-effect rezoning is NOT applied in regime A."}
r = 2; rows_by = {}
for reg, zs in REG.items():
    for n in (2, 4, 6, 8):
        z = zs[n]; li = 2 + (n // 2 - 1); tg = comp[n]
        wg.append([f"{reg}|{n}", reg, n, z, tg])
        wg.cell(r, 6, f'=INDEX(Fit!$H$2:$H$17,MATCH(C{r}&"|"&D{r},Fit!$A$2:$A$17,0))')
        wg.cell(r, 7, f"=Lots!$D${li}"); wg.cell(r, 8, f"=INDEX(Rules!$C$2:$C$4,MATCH(D{r},Rules!$A$2:$A$4,0))")
        wg.cell(r, 9, "=Houses!$F$2+Houses!$F$3" if n == 2 else f"=E{r}*Houses!$F$2"); wg.cell(r, 10, f"=I{r}/G{r}*100")
        wg.cell(r, 11, f"=IF(C{r}=2,IF(H{r}/100*G{r}>=Houses!$F$2+Houses!$F$3,2,IF(H{r}/100*G{r}>=Houses!$F$2,1,0)),ROUNDDOWN(H{r}/100*G{r}/Houses!$F$2,0))")
        wg.cell(r, 12, f"=INDEX({'Rules!$I$2:$I$4' if n == 2 else 'Rules!$J$2:$J$4'},MATCH(D{r},Rules!$A$2:$A$4,0))")
        wg.cell(r, 13, f"=MIN(E{r},F{r},K{r},L{r})"); wg.cell(r, 14, f"=MIN(E{r},F{r})")
        wg.cell(r, 15, f"=IF(C{r}=2,IF(N{r}>=2,Houses!$F$2+Houses!$F$3,IF(N{r}=1,Houses!$F$2,0)),N{r}*Houses!$F$2)")
        wg.cell(r, 16, f'=IF(M{r}=E{r},"Target met",IF(M{r}=F{r},"Yards / lot depth (front yard "&INDEX(Rules!$F$2:$F$4,MATCH(D{r},Rules!$A$2:$A$4,0))&" m)",IF(M{r}=K{r},"Building coverage ("&H{r}&"% limit)","Dwelling cap ("&D{r}&")")))')
        wg.cell(r, 17, f'=IF(D{r}="THAB","Restricted discretionary (H6.4.1 A3)",IF(D{r}="MHU",IF(M{r}<=3,"Permitted up to 3 (H5.4.1 A3)","Restricted discretionary, 4+ (H5.4.1 A4)"),IF(C{r}=2,"Permitted: 1 dwelling (A3) + minor dwelling (A5)","Permitted: 1 dwelling (A3); a second needs a minor dwelling of 65 m2 or less, else non-complying (A6)")))')
        wg.cell(r, 18, "E36 restricted discretionary (A37, A38; A42 on lot 2 flow path)"); wg.cell(r, 19, NOTE.get((reg, n), "PC120 proposed (not operative) except where marked immediate legal effect in the AUP text." if reg in "CD" else ""))
        rows_by.setdefault(reg, []).append(r); r += 1
G_END = r - 1
for rr in range(2, G_END + 1): wg.cell(rr, 5).fill = YEL
wrap(wg)
# Scenarios
wsn = wb.create_sheet("Scenarios", 1)
head(wsn, 1, ["Regime", "Description", "Target dwellings", "Delivered, separate titles", "Shortfall vs target", "Lots 2/4/6/8 delivered", "Delivers 10?", "Fit-limited total (amalgamated)", "Site coverage % (fit-limited)", "Site coverage limit % (most restrictive lot)", "Dwelling cap for one site", "Delivered, one amalgamated site", "Delivers 10 amalgamated?", "Consent pathway when amalgamated", "Main limit"], [8, 52, 10, 12, 11, 16, 10, 12, 12, 14, 12, 14, 12, 40, 70])
desc = {"A": "Operative AUP (2, 4 THAB; 6, 8 MHU)", "B": "Current legal position (lot 2 SHZ, lot 4 MHU by PC120 immediate effect)", "C": "PC120 as notified (2 SHZ, 4 MHU, 6 THAB, 8 THAB)", "D": "PC120 as amended Aug 2026 (all Single House)"}
limit = {"A": "Lot 8 (MHU) front yard 2.5 m and coverage 45%: only 2 houses; lot 4 (THAB) takes 3 only because THAB front yard is 1.5 m.", "B": "Lots 4 and 8 are MHU: front yard 2.5 m and coverage 45% allow 2 houses each, not 3.", "C": "Lot 4 MHU allows 2; lot 6 THAB is not the limit (target 2); lot 8 THAB takes 3.", "D": "Single House: one dwelling per site plus one minor dwelling of 65 m2 or less. Only the Williams on lot 2 qualifies; on lot 6 the 35% coverage also allows only 1 house."}
for k, (reg, rs) in enumerate(rows_by.items(), 2):
    a, b = rs[0], rs[-1]
    wsn.append([reg, desc[reg], f"=SUM(Regimes!E{a}:E{b})", f"=SUM(Regimes!M{a}:M{b})", f"=C{k}-D{k}", f'=Regimes!M{a}&" / "&Regimes!M{a+1}&" / "&Regimes!M{a+2}&" / "&Regimes!M{a+3}', f'=IF(D{k}>=10,"YES","no")', f"=SUM(Regimes!N{a}:N{b})", f"=SUM(Regimes!O{a}:O{b})/Lots!$D$7*100", f"=MIN(Regimes!H{a}:H{b})",
                f'=IF(COUNTIF(Regimes!D{a}:D{b},"SHZ")>0,2,99)', f"=MIN(H{k},K{k},ROUNDDOWN((J{k}/100*Lots!$D$7-Houses!$F$3)/Houses!$F$2,0)+1)", f'=IF(L{k}>=10,"YES","no")', f'=IF(COUNTIF(Regimes!D{a}:D{b},"SHZ")>0,"Single House part: 1 dwelling + minor dwelling per site; more is non-complying","Restricted discretionary, 4+ dwellings (MHU H5.4.1 A4 / THAB H6.4.1 A3)")', limit[reg]])
wsn.cell(8, 1, "Reading it").font = B
txt = ["No regime delivers 10 under separate titles with 7 x 12 m Dulwich houses: lots 4 and 8 can take 3 houses only with a 1.5 m front yard (THAB or the owner's set) and then only 0.12 m of slack in the 40.2 m lot depth, and 3 houses breach the Mixed Housing Urban coverage limit (47.0% and 46.7% against 45%).",
       "Amalgamating the lots does not relieve the front yard (the street boundary is the same) and the Single House part caps the whole site at 2 in regimes B to D. Regime A amalgamated reaches 9 because lot 8 is MHU.",
       "Which standards apply to each lot is the legal question: lot 2 and lot 4 are rezoned by PC120 with immediate legal effect (regime B); regime A ignores that and is shown for reference only. The 'amalgamated' columns assume the most restrictive lot's coverage limit and any Single House part caps the site: ASSUMED, UNVERIFIED reading."]
for i, t in enumerate(txt): c = wsn.cell(9 + i, 1, t); c.alignment = Alignment(wrap_text=True)
wsn.merge_cells("A9:O9"); wsn.merge_cells("A10:O10"); wsn.merge_cells("A11:O11")
for rr in (9, 10, 11): wsn.row_dimensions[rr].height = 48
for rr in range(2, 6):
    for cc in range(1, 16): wsn.cell(rr, cc).alignment = Alignment(wrap_text=True, vertical="top")
# Sensitivity
wsv = wb.create_sheet("Sensitivity")
head(wsv, 1, ["Lot", "House length m (all 3 houses)", "Footprint of 3 houses m2", "Coverage %", "MHU limit %", "THAB limit %", "Max length that fits, 1.5 m front yard (THAB / owner set)", "Fits at 1.5 m front yard?", "Slack along the lot, 3 houses (m)", "Max length that fits, MHU 2.5 m front yard", "Fits at MHU 2.5 m?", "Coverage OK under MHU?", "Coverage OK under THAB?"], [6, 12, 12, 10, 9, 9, 18, 12, 14, 18, 12, 12, 12])
r = 2
for n in (4, 8):
    li = 2 + n // 2 - 1
    for L in (11.5, 11.7, 12.0, 12.2):
        wsv.append([n, L, f"=3*7*B{r}", f"=C{r}/Lots!$D${li}*100", "=Rules!$C$3", "=Rules!$C$2", f'=INDEX(Fit!$I$2:$I$17,MATCH("{n}|USER",Fit!$A$2:$A$17,0))', f'=IF(B{r}<=G{r},"yes","NO")', f"=(G{r}-B{r})*3", f'=INDEX(Fit!$I$2:$I$17,MATCH("{n}|MHU",Fit!$A$2:$A$17,0))', f'=IF(B{r}<=J{r},"yes","NO")', f'=IF(D{r}<=E{r},"yes","NO")', f'=IF(D{r}<=F{r},"yes","NO")'])
        wsv.cell(r, 2).fill = YEL; r += 1
wsv.cell(r + 1, 1, "At 12.0 m the owner's set leaves about 0.12 m of slack on lots 4 and 8 (the brief estimated about 0.14 m: difference is the polygon's lot depth). At 12.2 m (the 85 m2 listing implies 7 x 12.14 m) three houses do NOT fit: 12.04 m is the longest. Under the Mixed Housing Urban standards three houses need houses of about 11.7 m or less for the front yard (2.5 m) and about 11.5 m or less for coverage (45%): at 11.5 m lot 8 would pass both (so regime A would reach 10), but lot 4 is marginally over (45.06%) and the listed 85 m2 floor area does not fit a 7 x 11.5 m house: supplier data needed.").alignment = Alignment(wrap_text=True)
wsv.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=13); wsv.row_dimensions[r + 1].height = 60
# Parking
wp = wb.create_sheet("Parking")
head(wp, 1, ["Item", "Result", "Basis"], [50, 40, 100])
wp.append(["Does the AUP require parking for dwellings in THAB, MHU or SHZ?", "No minimum. No maximum for residential.", "AUP E27.6.2(1): the number of parking spaces must not exceed the maximum rates specified (a); the minimum-rate limb (b) is [Deleted]. Residential rows in Tables E27.6.2.3 and E27.6.2.4 (T28 to T43) read 'Maximum rate: No maximum' with the minimum [Deleted] (DATA S7, read 10 Nov 2026). Correction: an earlier draft cited Table T17 'No minimum or maximum'; that row is for the Centre Fringe Office Control area, not dwellings."])
wp.append(["NPS-UD parking rule", "UNVERIFIED", "National Policy Statement on Urban Development (removal of minimum parking requirements) not read in official text. The AUP text above already has no minimum."])
wp.append(["Test 0 spaces per house", "Passes: nothing to place", "E27.6.2(1)(b) minimum deleted."])
wp.append(["Test 1 space per house (informational)", "see table below", "Spaces 2.5 x 5.0 m (ASSUMED) outside house footprints + 0.5 m and the flow-path corridor, inside a 1 m yard, on ground at or below 200 mm depth (E36.6.1.7) for the ASSUMED lot-minimum flood level + depth. Vehicle access and manoeuvring (E27.6.4) are not tested for this layout: there is no driveway in the 10-house layout. UNVERIFIED."])
wp.append([]); wp.append(["Lot / design depth", "Spaces at <=200 mm | at <=500 mm", "Required (1 per house on lot)"])
for n in ("2", "4", "6", "8"):
    for d in ("0.3", "0.6", "0.9", "1.2"):
        e = E["parking"][n][d]; wp.append([f"Lot {n} at {d} m", f"{e['le200mm']['spaces']} | {e['le500mm']['spaces']}", e["required_spaces"]])
wrap(wp)
# Reconciliation
wc = wb.create_sheet("Reconciliation")
head(wc, 1, ["Item", "Result", "Explanation"], [60, 28, 120])
wc.append(["Brief says 8 Dulwich + 1 Williams; 2/3/2/3 is 10 dwellings", "9 Dulwich + 1 Williams", "2 + 3 + 2 + 3 = 10 dwellings; with one Williams on lot 2 that is 9 Dulwich. The brief's figure also shows 9 teal houses and 1 orange. Workbook uses 9 + 1; cost 9 x $100,000 = $900,000 + GST."])
wc.append(["Term sheet 'PC120 amended: 4 units' vs one dwelling + one minor dwelling", "see Scenarios regime D", "The earlier 4 came from 60 m2 4 x 15 m units: one per lot (that unit shape fits one per lot) under a Single House cap of 2 per site. With these houses the Single House cap is 1 dwelling + 1 minor dwelling of 65 m2 or less per lot: Dulwich (84 m2) cannot be the minor dwelling, so lots 4, 6, 8 take 1 house each, and lot 2 takes 1 house + the Williams: 5 dwellings with the stock listed. 8 (2 per lot) only if three more minor dwellings of 65 m2 or less are sourced (ASSUMED, not listed)."])
wc.append(["Why 10 is not delivered under separate titles", "see Scenarios", "Lots 4 and 8: 3 houses need a 1.5 m front yard (only THAB or the owner's set). Under MHU (2.5 m) the maximum house length for 3 is 11.7 m, and coverage 45% needs 81 m2 footprints or less (84 m2 gives 47%)."])
wc.append(["Overland flow path", "Lot 2 only", "2 m clearance removes 73 m2 on lot 2; H1 and the Williams sit clear of it. No other house is affected (DATA S5, CALCULATED)."])
wc.append(["Land area", "=Lots!D7", "LINZ titles 2,006.9 m2 against 2,006 m2 in the owner's documents (rounding)."])
wrap(wc)
for w in wb:
    if w.title != "README": w.sheet_view.zoomScale = 90
wb.save(OUT / "Zoning_Feasibility.xlsx"); print("saved")
