"""Zoning_Feasibility.xlsx: every scenario with live formulas. Values tagged DATA / CALCULATED / ASSUMED / UNVERIFIED."""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
P = jload(DATA / "pack_data.json"); RUNS = jload(DATA / "scenario_runs.json"); E = jload(DATA / "eng_results.json")
LOTS = {NUM[i]: P["lots"][str(i)] for i in IDS}
YEL = PatternFill("solid", fgColor="FFF2CC"); ORG = PatternFill("solid", fgColor="F8CBAD"); HDR = PatternFill("solid", fgColor="1F3864"); GRY = PatternFill("solid", fgColor="EDEDED")
B = Font(bold=True); WH = Font(bold=True, color="FFFFFF")
thin = Side(style="thin", color="BBBBBB"); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
wb = Workbook()
def head(ws, row, cols, widths=None):
    for j, c in enumerate(cols, 1):
        x = ws.cell(row, j, c); x.font = WH; x.fill = HDR; x.alignment = Alignment(wrap_text=True, vertical="center"); x.border = BOX
    if widths:
        for j, w in enumerate(widths, 1): ws.column_dimensions[CL(j)].width = w
    ws.freeze_panes = f"A{row + 1}"
# ---------------- README
ws = wb.active; ws.title = "README"
rd = [("2-8 Parrish Road, Sandringham: zoning and feasibility workbook", B), (f"Built {TODAY} from this project's app. Screening only, not advice, not a design, not certified.", None), ("", None),
 ("How to read it", B), ("Rules: zone standards with AUP clause references (AUP operative July 2026 text, S7) and PC120 legal-effect notes (S8, S9).", None),
 ("Lots: per-lot DATA (LINZ area, zone, LiDAR ground, slope, flow path length and usable area).", None),
 ("Groups: one row per scenario x site x physical-zone group. Coverage cap and delivered units are live formulas; layout fit comes from the app's layout engine (S14), cached in scenario_runs.json.", None),
 ("Sites: caps for dwellings enabled (formulas) and delivered units per site. Scenarios: totals per regime and combination. Ranking: by units delivered, then risk. Reconciliation: why counts differ.", None), ("", None),
 ("Regimes (what zoning is applied)", B),
 ("A. Operative AUP only: 2 and 4 THAB; 6 and 8 MHU. Ignores PC120. Shown for reference; NOT the current legal position.", None),
 ("B. Current legal position (ASSUMED reading): operative standards PLUS PC120 rezoning with immediate legal effect on lots 2 (to Single House) and 4 (to Mixed Housing Urban). Most restrictive dwelling rule applies. UNVERIFIED legal interpretation: planner/lawyer to confirm.", None),
 ("C. PC120 as notified 3 Nov 2025: 2 SHZ, 4 MHU, 6 THAB, 8 THAB. Not operative except where immediate legal effect.", None),
 ("D. PC120 as amended 27 Aug 2026 (proposed): all four Single House Zone. Not operative. Decisions expected mid-2027.", None), ("", None),
 ("Assumptions that change the numbers (edit the yellow cells to rerun the formulas)", B),
 ("TARGET SCHEME (see sheet Target_Scheme): all four lots amalgamated as one site assessed to Mixed Housing Urban standards (stricter than THAB): 9 dwellings with 1 parking space per unit, 10 with no on-site parking and outdoor living met by 16 m2 ground + 5 m2 raised deck. The other sheets are the regime-by-regime comparison with 2 spaces per unit.", None), ("Unit = 60 m2 relocatable, 4 m x 15 m, height 3.8 m (ASSUMED). 2 car spaces per unit in the comparison sheets (ASSUMED default; the plan sets no minimum, E27 Table T17). 3.5 m shared driveway (ASSUMED; E27 width test). Existing buildings on lots 2 and 6 assumed removed (ASSUMED).", None),
 ("Flow path clearance: 2 m each side of the Council centreline (ASSUMED planning offset, not a Council rule). Flood-affected land is NOT excluded from building: units are piled over the floodplain (the owner's concept).", None),
 ("Layout fit is a packing result in the app, not an architect's design. Dwelling counts must be confirmed by a planner.", None), ("", None),
 ("Where one title spans lots whose zones differ (regimes B, C), the most restrictive zone sets the dwelling cap for that whole site: conservative, UNVERIFIED.", None), ("Colour key: yellow = user input / supply, orange = confirm or UNVERIFIED, grey = DATA from sources, white = CALCULATED.", None)]
for i, (t, f) in enumerate(rd, 1):
    c = ws.cell(i, 1, t); c.alignment = Alignment(wrap_text=True)
    if f: c.font = f
ws.column_dimensions["A"].width = 150
# ---------------- Rules
ws = wb.create_sheet("Rules")
cols = ["Zone code", "Zone name", "Building coverage max %", "Impervious max %", "Landscaped min %", "Height max (m)", "HIRB", "Yards front / side / rear (m)", "Dwellings: activity status", "Dwelling cap per site (formula input)", "AUP clauses", "Legal-effect note", "Basis"]
head(ws, 1, cols, [10, 38, 12, 12, 12, 10, 18, 18, 52, 14, 60, 58, 14])
R = [("THAB", "Residential - Terrace Housing and Apartment Building Zone", 50, 70, 30, 16, "45 deg from 3 m", "1.5 / 1 / 1", "Dwellings: restricted discretionary (H6.4.1 A3)", 999, "H6.4.1 A3; H6.6.5 height; H6.6.6 HIRB; H6.6.9 yards; H6.6.10 impervious; H6.6.11 coverage; H6.6.12 landscaped; H6.6.15 outdoor living (20 m2, 4 m)", "Operative on lots 2 and 4. PC120 notified rezones 6 and 8 to THAB (proposed, not operative).", "DATA (S7)"),
     ("MHU", "Residential - Mixed Housing Urban Zone", 45, 60, 35, 11, "45 deg from 3 m", "2.5 / 1 / 1", "Up to 3 dwellings per site permitted (H5.4.1 A3); 4 or more restricted discretionary (A4)", 999, "H5.4.1 A3, A4; H5.6.4 height; H5.6.5 HIRB; H5.6.8 yards; H5.6.9 impervious; H5.6.10 coverage; H5.6.11 landscaped; H5.6.14 outdoor living (20 m2, 4 m)", "Operative on lots 6 and 8. PC120 notified rezones lot 4 to MHU (immediate legal effect).", "DATA (S7)"),
     ("SHZ", "Residential - Single House Zone", 35, 60, 40, 8, "45 deg from 2.5 m", "3 / 1 / 1", "One dwelling per site permitted (H3.4.1 A3 [row not re-read]); one minor dwelling (<=65 m2 excluding decks and garaging) permitted (A5, H3.6.4); more than one dwelling non-complying (A6)", 2, "H3.4.1 A5, A6; H3.6.4 minor dwellings; H3.6.6 height; H3.6.7 HIRB; H3.6.8 yards; H3.6.9 impervious (60%); H3.6.10 coverage (35%); H3.6.11 landscaped (40%)", "PC120 rezoning to SHZ had immediate legal effect from 3 Nov 2025 (s86B(3)(f) RMA) on lots 2 (and lot 4 only as MHU). Aug 2026 amendments propose SHZ for all four (not operative).", "DATA (S7, S8); yards/HIRB UNVERIFIED vs table")]
for i, r in enumerate(R, 2):
    for j, v in enumerate(r, 1):
        c = ws.cell(i, j, v); c.alignment = Alignment(wrap_text=True, vertical="top"); c.border = BOX
        if j == 10: c.fill = YEL
        if j in (7, 8) and r[0] == "SHZ": c.fill = ORG
ws.cell(6, 1, "Dwelling cap per site: 999 = no numeric cap (consent pathway differs). SHZ = 1 dwelling + 1 minor dwelling per site; a third is non-complying and is not counted as deliverable here. Yellow cells are editable.").alignment = Alignment(wrap_text=True)
ws.cell(7, 1, "Other AUP/PC120 items NOT modelled: PC120 deep-soil (10%), street-glazing (20%), 1 m buffer, THAB height/HIRB changes; PC120 Combined Wastewater Network Control standard (H3.6.3A etc.): all UNVERIFIED for these lots.").alignment = Alignment(wrap_text=True)
ws.cell(8, 1, "Unit size and parking inputs:"); ws.cell(9, 1, "Unit area (m2)"); ws.cell(9, 2, 60).fill = YEL; ws.cell(10, 1, "Parking spaces per unit"); ws.cell(10, 2, 2).fill = YEL; ws.cell(11, 1, "Space area (m2, 2.5 x 5.0)"); ws.cell(11, 2, 12.5).fill = YEL
# ---------------- Lots
ws = wb.create_sheet("Lots")
cols = ["Lot", "Address", "Title ref", "Legal description", "Land area m2 (LINZ)", "Tenure", "AUP zone (operative)", "PC120 notified zone", "PC120 amended zone", "Flood plain cover %", "Overland flow path inside lot (m)", "Usable m2 after 2 m flow-path clearance", "LiDAR ground min (m RL)", "LiDAR ground max", "Ground mean", "Slope mean %", "Slope p95 %", "Existing building footprint m2", "Capital value", "Basis"]
head(ws, 1, cols, [6, 36, 14, 18, 12, 10, 40, 36, 36, 10, 12, 14, 10, 10, 10, 9, 9, 12, 38, 40])
for i, n in enumerate(("2", "4", "6", "8"), 2):
    l = LOTS[n]; fl = l["flow_path_location_in_lot"]
    row = [int(n), l["address"], l["title_no"], l["appellation"], l["area_m2"], l["tenure"], l["zone_operative"], l["pc120"]["notified_nov2025"]["zone"], l["pc120"]["amended_aug2026"]["zone"], l["flood_layers"]["ac_hz_flood_plains"][0]["covers_pct"], sum(x["length_m"] for x in fl),
           l["usable_after_clearance"]["2m_each_side"]["usable_m2"], l["ground"]["elevation_min_m"], l["ground"]["elevation_max_m"], l["ground"]["elevation_mean_m"], l["ground"]["slope_mean_pct"], l["ground"]["slope_p95_pct"], sum(l["buildings"]["footprint_m2"]), "UNVERIFIED: Council rating value not in the app", "DATA S1, S2, S5, S6, S9"]
    for j, v in enumerate(row, 1):
        c = ws.cell(i, j, v); c.fill = ORG if j == 19 else GRY; c.border = BOX; c.alignment = Alignment(wrap_text=True, vertical="top")
ws.cell(7, 1, "Total"); ws.cell(7, 5, "=SUM(E2:E5)"); ws.cell(7, 12, "=SUM(L2:L5)"); ws.cell(7, 11, "=SUM(K2:K5)")
ws.cell(8, 1, "Listed total area (owner's term sheet / listing, UNVERIFIED)"); ws.cell(8, 5, 2006).fill = ORG; ws.cell(9, 1, "Difference LINZ minus listed (m2)"); ws.cell(9, 5, "=E7-E8")
# ---------------- scenario build
ZN = {"THAB": "Residential - Terrace Housing and Apartment Building Zone", "MHU": "Residential - Mixed Housing Urban Zone", "SHZ": "Residential - Single House Zone"}
REG = {"A": ({"2": "THAB", "4": "THAB", "6": "MHU", "8": "MHU"}, {"2": "THAB", "4": "THAB", "6": "MHU", "8": "MHU"}, "Operative AUP only"),
       "B": ({"2": "THAB", "4": "THAB", "6": "MHU", "8": "MHU"}, {"2": "SHZ", "4": "MHU", "6": "MHU", "8": "MHU"}, "Current legal position (operative + PC120 immediate effect)"),
       "C": ({"2": "SHZ", "4": "MHU", "6": "THAB", "8": "THAB"}, {"2": "SHZ", "4": "MHU", "6": "THAB", "8": "THAB"}, "PC120 as notified"),
       "D": ({"2": "SHZ", "4": "SHZ", "6": "SHZ", "8": "SHZ"}, {"2": "SHZ", "4": "SHZ", "6": "SHZ", "8": "SHZ"}, "PC120 as amended Aug 2026")}
COMBOS = [("2", [["2"]]), ("4", [["4"]]), ("6", [["6"]]), ("8", [["8"]]), ("2+4", [["2", "4"]]), ("6+8", [["6", "8"]]), ("2+4+6+8", [["2", "4", "6", "8"]]), ("(2+4)|(6+8)", [["2", "4"], ["6", "8"]]), ("2|4|6|8 (four titles)", [["2"], ["4"], ["6"], ["8"]])]
RANK = {"SHZ": 3, "MHU": 2, "THAB": 1}; ORDER = ["2", "4", "6", "8"]
def groups(site, phys):
    out = []; cur = []
    for n in site:
        if cur and phys[n] == phys[cur[-1]]: cur.append(n)
        else:
            if cur: out.append(cur)
            cur = [n]
    out.append(cur); return out
def key(g, z): return f"{'+'.join(g)}|{z}|flood", f"{'+'.join(g)}|{z}|noflood"
ws = wb.create_sheet("Groups")
gcols = ["Scenario ID", "Regime", "Combination", "Site (titles amalgamated)", "Group lots", "Physical zone (standards used)", "Land area m2", "Usable m2 after flow-path clearance", "Max building coverage %", "Max coverage m2", "Coverage cap (units of 60 m2)", "Layout fit, flood-clear (units)", "Layout fit, ignoring flood (units)", "Units lost to flood clearance", "Fit x coverage = MIN", "Binding constraint in engine", "Driveway m2 (CALCULATED)", "Parking m2 (spaces x area)", "Roof m2", "Impervious m2 (roof + drive + parking)", "Impervious % of site", "Impervious limit %", "Impervious test", "Landscaped (approx 1 - impervious) %", "Landscaped min %", "Landscaped test", "Basis"]
head(ws, 1, gcols, [26, 7, 22, 24, 12, 10, 11, 13, 10, 11, 11, 11, 11, 11, 11, 26, 11, 11, 10, 13, 11, 10, 10, 13, 10, 10, 40])
srows = []; r = 2; sidx = {}
for reg, (phys, rule, rname) in REG.items():
    for cname, sites in COMBOS:
        for si, site in enumerate(sites, 1):
            for g in groups(site, phys):
                z = phys[g[0]]; kf, kn = key(g, z)
                if kf not in RUNS: raise SystemExit("missing run " + kf)
                rf, rn = RUNS[kf], RUNS[kn]; sid = f"{reg}|{cname}"
                lotrefs = "+".join(f"Lots!$E${2+ORDER.index(n)}" for n in g); usable = "+".join(f"Lots!$L${2+ORDER.index(n)}" for n in g)
                ws.append([sid, reg, cname, f"S{si}: " + "+".join(site), "+".join(g), z])
                ws.cell(r, 7, "=" + lotrefs); ws.cell(r, 8, "=" + usable)
                ws.cell(r, 9, f"=INDEX(Rules!$C$2:$C$4,MATCH(F{r},Rules!$A$2:$A$4,0))"); ws.cell(r, 10, f"=I{r}/100*G{r}"); ws.cell(r, 11, f"=ROUNDDOWN(J{r}/Rules!$B$9,0)")
                ws.cell(r, 12, rf["units"]).fill = GRY; ws.cell(r, 13, rn["units"]).fill = GRY; ws.cell(r, 14, f"=M{r}-L{r}"); ws.cell(r, 15, f"=MIN(K{r},L{r})")
                ws.cell(r, 16, ", ".join(rf["binding"])).fill = GRY; ws.cell(r, 17, round(rf.get("access_m2", 0) or 0, 1)).fill = GRY
                ws.cell(r, 18, f"=O{r}*Rules!$B$10*Rules!$B$11"); ws.cell(r, 19, f"=O{r}*Rules!$B$9"); ws.cell(r, 20, f"=Q{r}+R{r}+S{r}"); ws.cell(r, 21, f"=T{r}/G{r}*100")
                ws.cell(r, 22, f"=INDEX(Rules!$D$2:$D$4,MATCH(F{r},Rules!$A$2:$A$4,0))"); ws.cell(r, 23, f'=IF(U{r}<=V{r},"PASS","CHECK")'); ws.cell(r, 24, f"=100-U{r}")
                ws.cell(r, 25, f"=INDEX(Rules!$E$2:$E$4,MATCH(F{r},Rules!$A$2:$A$4,0))"); ws.cell(r, 26, f'=IF(X{r}>=Y{r},"PASS","CHECK")'); ws.cell(r, 27, "Fit: S14 layout engine (4x15 m, 2 spaces/unit, 3.5 m drive, 2 m flow-path offset). Caps: S7 formulas.")
                sidx.setdefault((sid, si, "+".join(site)), []).append(r); r += 1
G_END = r - 1
# ---------------- Sites
ws2 = wb.create_sheet("Sites")
scols = ["Scenario ID", "Regime", "Combination", "Site", "Lots on one title", "Zone whose dwelling rules apply (most restrictive)", "Sum of group fit x coverage", "Dwelling cap (formula)", "Delivered units (MIN)", "Built floor area m2 (units x 60)", "Governing constraint", "Consent pathway for dwellings", "Flood consent", "Dwellings enabled by zone", "Site area m2", "Max coverage m2 (site)", "Risk score (1 low - 6 high)", "Basis"]
head(ws2, 1, scols, [26, 7, 22, 8, 14, 14, 11, 11, 11, 12, 40, 52, 36, 50, 11, 11, 10, 40])
sr = 2; srow_of = {}
for (sid, si, lots), grs in sidx.items():
    reg, cname = sid.split("|", 1); site = lots.split("+"); rule = REG[reg][1]
    zr = max((rule[n] for n in site), key=lambda x: RANK[x]); a, b = grs[0], grs[-1]
    ws2.append([sid, reg, cname, f"S{si}", lots, zr])
    ws2.cell(sr, 7, f"=SUMIFS(Groups!$O$2:$O${G_END},Groups!$A$2:$A${G_END},A{sr},Groups!$D$2:$D${G_END},\"S{si}: \"&E{sr})")
    ws2.cell(sr, 8, f"=INDEX(Rules!$J$2:$J$4,MATCH(F{sr},Rules!$A$2:$A$4,0))"); ws2.cell(sr, 9, f"=MIN(G{sr},H{sr})"); ws2.cell(sr, 10, f"=I{sr}*Rules!$B$9")
    ws2.cell(sr, 11, f'=IF(I{sr}=0,"None fit",IF(H{sr}<G{sr},"Zoning: dwelling cap ("&F{sr}&")",IF(SUMIFS(Groups!$N$2:$N${G_END},Groups!$A$2:$A${G_END},A{sr},Groups!$D$2:$D${G_END},"S{si}: "&E{sr})>0,"Flood clearance",IF(SUMIFS(Groups!$K$2:$K${G_END},Groups!$A$2:$A${G_END},A{sr},Groups!$D$2:$D${G_END},"S{si}: "&E{sr})<SUMIFS(Groups!$L$2:$L${G_END},Groups!$A$2:$A${G_END},A{sr},Groups!$D$2:$D${G_END},"S{si}: "&E{sr}),"Zoning: building coverage","Physical fit (envelope / access / parking)"))))')
    ws2.cell(sr, 12, f'=IF(F{sr}="THAB","Restricted discretionary (H6.4.1 A3)",IF(F{sr}="MHU",IF(I{sr}<=3,"Permitted up to 3 (H5.4.1 A3)","Restricted discretionary, 4+ (H5.4.1 A4)"),IF(I{sr}<=1,"Permitted 1 dwelling (H3.4.1 A3)",IF(I{sr}=2,"Permitted 1 + minor dwelling (A3 + A5, unit <=65 m2: a 60 m2 unit qualifies)","Non-complying (H3.4.1 A6)"))))')
    ws2.cell(sr, 13, "E36 restricted discretionary: A37/A38 (buildings in 1% AEP floodplain); A42 where in overland flow path; E36.9 report"); ws2.cell(sr, 14, f"=INDEX(Rules!$I$2:$I$4,MATCH(F{sr},Rules!$A$2:$A$4,0))")
    ws2.cell(sr, 15, "=" + "+".join(f"Groups!$G${x}" for x in grs)); ws2.cell(sr, 16, "=" + "+".join(f"Groups!$J${x}" for x in grs))
    base_r = {"A": 4, "B": 3, "C": 3, "D": 1}[reg]; ws2.cell(sr, 17, f"={base_r}+IF(LEN(E{sr})>1,1,0)").fill = ORG
    ws2.cell(sr, 18, "Caps: S7. Risk score is ASSUMED judgement: regime base (A=4 relies on zoning PC120 removes, B/C=3, D=1) +1 if titles are amalgamated.")
    srow_of[(sid, si)] = sr; sr += 1
S_END = sr - 1
# ---------------- Scenarios
ws3 = wb.create_sheet("Scenarios")
head(ws3, 1, ["Scenario ID", "Regime", "Regime name", "Combination", "Units delivered", "Built area m2 (60 m2 each)", "Total land area m2", "Risk (max site score)", "Governing text (first site)", "Rank within regime (units desc, risk asc)", "Rank overall (units desc, risk asc)", "Zones applied", "PC120 status note"], [26, 7, 44, 24, 11, 13, 12, 10, 40, 12, 12, 40, 60])
rr = 2; notes = {"A": "Operative zoning only. Does not reflect PC120 immediate-effect rezoning of lots 2 and 4. Treat as upside case.", "B": "Lot 2 SHZ and lot 4 MHU dwelling rules have legal effect now (s86B(3)(f)); remainder operative. Interpretation UNVERIFIED.", "C": "Notified Nov 2025; not operative except immediate-effect rezoning. Superseded in part by Aug 2026 amendments.", "D": "Proposed Aug 2026; decisions expected June 2027; not operative. Downside case if adopted."}
for reg, (phys, rule, rname) in REG.items():
    for cname, sites in COMBOS:
        sid = f"{reg}|{cname}"
        ws3.append([sid, reg, rname, cname]); rr_ = ws3.max_row
        ws3.cell(rr_, 5, f"=SUMIFS(Sites!$I$2:$I${S_END},Sites!$A$2:$A${S_END},A{rr_})"); ws3.cell(rr_, 6, f"=E{rr_}*Rules!$B$9")
        ws3.cell(rr_, 7, "=" + "+".join(f"Lots!$E${2+ORDER.index(n)}" for s in sites for n in s)); ws3.cell(rr_, 8, f"=SUMPRODUCT(MAX((Sites!$A$2:$A${S_END}=A{rr_})*Sites!$Q$2:$Q${S_END}))")
        ws3.cell(rr_, 9, f"=INDEX(Sites!$K$2:$K${S_END},MATCH(A{rr_},Sites!$A$2:$A${S_END},0))")
        ws3.cell(rr_, 12, ", ".join(f"{n}={phys[n]}/{rule[n]}" for n in ORDER) + " (physical/dwelling rules)"); ws3.cell(rr_, 13, notes[reg])
last = ws3.max_row
for i in range(2, last + 1):
    ws3.cell(i, 10, f"=COUNTIFS($B$2:$B${last},B{i},$E$2:$E${last},\">\"&E{i})+COUNTIFS($B$2:$B${last},B{i},$E$2:$E${last},E{i},$H$2:$H${last},\"<\"&H{i})+1")
    ws3.cell(i, 11, f"=COUNTIFS($E$2:$E${last},\">\"&E{i})+COUNTIFS($E$2:$E${last},E{i},$H$2:$H${last},\"<\"&H{i})+1")
    ws3.cell(i, 14, f"=K{i}+COUNTIF($K$2:K{i},K{i})-1")
ws3.cell(1, 14, "Unique rank (tie-break by order)").font = WH; ws3.cell(1, 14).fill = HDR; ws3.column_dimensions["N"].width = 12
wr = wb.create_sheet("Ranking")
head(wr, 1, ["Rank", "Scenario ID", "Regime", "Combination", "Units delivered", "Risk (1 low - 6 high)", "Governing constraint", "Status of the zoning it relies on"], [7, 26, 44, 24, 12, 12, 42, 70])
for n in range(1, last):
    rw = n + 1; m = f"MATCH($A{rw},Scenarios!$N$2:$N${last},0)"
    wr.cell(rw, 1, n); wr.cell(rw, 2, f"=INDEX(Scenarios!$A$2:$A${last},{m})"); wr.cell(rw, 3, f"=INDEX(Scenarios!$C$2:$C${last},{m})"); wr.cell(rw, 4, f"=INDEX(Scenarios!$D$2:$D${last},{m})")
    wr.cell(rw, 5, f"=INDEX(Scenarios!$E$2:$E${last},{m})"); wr.cell(rw, 6, f"=INDEX(Scenarios!$H$2:$H${last},{m})"); wr.cell(rw, 7, f"=INDEX(Scenarios!$I$2:$I${last},{m})"); wr.cell(rw, 8, f"=INDEX(Scenarios!$M$2:$M${last},{m})")
wr["J1"] = "Target schemes T10 (10 dwellings) and T9 (9) on sheet Target_Scheme outrank every row here. This ranking compares the title-by-title and zoning-regime cases (2 parking spaces per unit)."
wr.column_dimensions["J"].width = 70
wr.cell(last + 2, 1, "Ranking is by units delivered (high first) then risk (low first). Risk is an ASSUMED 1-6 judgement (Sites sheet). Regime A is the operative-only upside case and is NOT the current legal position; regime B is the working legal position; D is the downside if PC120 amendments are adopted.").alignment = Alignment(wrap_text=True)
# ---------------- Reconciliation
ws4 = wb.create_sheet("Reconciliation")
head(ws4, 1, ["Item", "Result", "Explanation", "Basis"], [58, 16, 110, 30])
def fit(k): return RUNS[k]["units"]
rec = [("Per-lot fit, 4x15 m (lots 2 / 4 / 6 / 8)", f"{fit('2|THAB|flood')} / {fit('4|THAB|flood')} / {fit('6|MHU|flood')} / {fit('8|MHU|flood')}", "Lot widths (about 9-11 m) allow one or two 4 m wide units side by side after 1-3 m side yards, 1.5-3 m front yard and parking; lots 4 and 8 are deeper/wider than 2 and 6.", "CALCULATED S14"),
       ("Per-lot fit, other shapes (5x12 / 6x10), best of three", "1 / 2 / 2 / 2", "Shape matters only on lot 6: 5x12 m fits two, 4x15 m and 6x10 m fit one. The user's working unit is 4 x 15 m, so lot 6 counts one. A 5 x 12 unit would add one unit to lot 6 and therefore to totals.", "CALCULATED S14 (hazard_report.json)"),
       ("Sum of four lots on separate titles (regime A)", f"=SUM(E6:E9)".replace("E6:E9", "B7:B7") if False else "6", "1 + 2 + 1 + 2.", "CALCULATED"),
       ("2+4 amalgamated vs 2 and 4 separate", f"{fit('2+4|THAB|flood')} vs {fit('2|THAB|flood')+fit('4|THAB|flood')}", "Sharing one 3.5 m driveway and one yard set removes boundary yards between lots, so the pooled site fits one more unit. Needs boundary change or easements (UNVERIFIED consent route).", "CALCULATED S14"),
       ("6+8 amalgamated vs 6 and 8 separate", f"{fit('6+8|MHU|flood')} vs {fit('6|MHU|flood')+fit('8|MHU|flood')}", "Same effect as above.", "CALCULATED S14"),
       ("All four, operative zones (2+4 THAB, 6+8 MHU), 2 spaces per unit", f"{fit('2+4|THAB|flood')+fit('6+8|MHU|flood')}", "This is the earlier 8-unit comparison case (superseded as the headline by sheet Target_Scheme: 9 with 1 space per unit, 10 with none). The difference is the parking assumption (2 per unit) and treating lots as separate groups. Coverage caps (50% / 45%) are not binding: 8 x 60 = 480 m2 is 24% of 2,007 m2.", "CALCULATED"),
       ("All four amalgamated, Single House Zone (regime D)", f"{fit('2+4+6+8|SHZ|flood')} physical, 2 enabled", "The layout fits 4 but SHZ enables 1 dwelling + 1 minor dwelling per site. One amalgamated site therefore delivers 2 under restricted discretionary; four separate titles deliver up to 1+1+1+1 = 4 only if each lot fits a unit (it does, 1 each). A fifth unit on the 2,007 m2 site is blocked by vehicle access: 5 units need more than 9 car spaces so the driveway becomes a 5.5 m corridor against a 3.5 m input.", "CALCULATED S14, S7"),
       ("Does flow-path clearance change any count?", "No", "With a 2 m offset each side of the Council centreline (lot 2 only: 73 m2 corridor), flood-clear fit equals the fit ignoring flood on all 34 runs. Flood limits the project by pile height, access and consent, not by lost floor space.", "CALCULATED S14"),
       ("Coverage cap vs fit", "Coverage never binds", "Smallest coverage cap is SHZ lot 2: 35% x 467 m2 / 60 = 2.7, rounds to 2, vs fit 1. Fit binds first everywhere.", "CALCULATED"),
       ("Term sheet area vs LINZ", "=Lots!E9", "Owner document: 2,006 m2. LINZ titles total 2,006.9 m2 (467.4 + 536.0 + 463.6 + 539.9). The owner's note of 467 m2 for lot 2 matches; the 4/6/8 total of 1,539 m2 is 1,539.5 m2. Differences are rounding.", "DATA S1, S12"),
       ("Spec says zoning THAB on 2 and 4, MHU on 6 and 8", "Matches operative only", "That is the operative AUP zoning (S1/S9). PC120 notified (Nov 2025) rezones 2 to SHZ and 4 to MHU with immediate legal effect, 6 and 8 to THAB; the Aug 2026 amendments rezone all four to SHZ.", "DATA S9")]
for r_ in rec: ws4.append(list(r_))
ws4["B4"] = "=Scenarios!E2+Scenarios!E3+Scenarios!E4+Scenarios!E5"
for row in ws4.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")

# ---------------- Target scheme
RT = RUNS
wt = wb.create_sheet("Target_Scheme", 1)
head(wt, 1, ["Item", "T9: 9 dwellings", "T10: 10 dwellings", "Basis"], [58, 22, 22, 90])
rows = [
 ("Site: lots 2+4+6+8 amalgamated, one site, MHU standards applied", "one site", "one site", "ASSUMED. MHU standards (45% coverage, 2.5 m front yard, 20 m2 outdoor living) are stricter than THAB, so they are the safe physical test for lots 2 and 4. Units straddle the old title lines, so amalgamation (or cross-lease/unit title) is needed: UNVERIFIED route."),
 ("Dwellings fitted by the app's layout engine (flood-clear, 2 m flow-path offset)", RT["T9"]["units"], RT["T10"]["units"], "CALCULATED S14 (scenarios in scenario_runs.json: T9, T10)"),
 ("Parking spaces per unit (on site)", 1, 0, "ASSUMED. AUP E27 sets no minimum parking for residential (Table T17 'no minimum or maximum', read in S7). T10 has none: tenants rely on street parking."),
 ("Outdoor living: ground m2 + raised deck m2 per unit", "20 + 0", "16 + 5", "H5.6.14(1): 20 m2 may be ground (min 4 m dimension) and/or balcony/patio/terrace (min 5 m2, 1.8 m). T10 uses a 4 x 4 m ground space plus a 5 m2 deck on the piled floor level. UNVERIFIED whether Council accepts a deck at piled floor level as 'patio/balcony'."),
 ("Site area m2", "=Lots!E7", "=Lots!E7", "DATA S1"),
 ("Built floor area m2 (units x 60)", "=B3*Rules!$B$9", "=C3*Rules!$B$9", "CALCULATED"),
 ("Building coverage % (decks add up to 5 m2 each in T10)", "=B7/B6*100/1", "=(C7+5*C3)/C6*100", "CALCULATED"),
 ("MHU building coverage limit %", "=Rules!C3", "=Rules!C3", "H5.6.10 (S7)"),
 ("Coverage test", '=IF(B8<=B9,"PASS","FAIL")', '=IF(C8<=C9,"PASS","FAIL")', "CALCULATED"),
 ("Driveway / access m2", RT["T9"]["access_m2"], RT["T10"]["access_m2"], "CALCULATED S14 (3.5 m strip along the east boundary; walkways to each unit not drawn)"),
 ("Parking m2 (spaces x 12.5)", "=B3*B4*Rules!$B$11", "=C3*C4*Rules!$B$11", "CALCULATED"),
 ("Impervious m2 (roof + access + parking + deck 0 (open))", "=B7+B11+B12", "=C7+C11+C12", "CALCULATED; paths and paving not drawn: add"),
 ("Impervious % of site", "=B13/B6*100", "=C13/C6*100", "CALCULATED"),
 ("MHU impervious limit %", "=Rules!D3", "=Rules!D3", "H5.6.9 (S7)"),
 ("Impervious test", '=IF(B14<=B15,"PASS","FAIL")', '=IF(C14<=C15,"PASS","FAIL")', "CALCULATED"),
 ("Landscaped % (approx 100 - impervious)", "=100-B14", "=100-C14", "CALCULATED approximation; the AUP measures landscaped area directly"),
 ("MHU landscaped minimum %", "=Rules!E3", "=Rules!E3", "H5.6.11 (S7)"),
 ("Landscaped test", '=IF(B17>=B18,"PASS","FAIL")', '=IF(C17>=C18,"PASS","FAIL")', "CALCULATED"),
 ("Dwellings enabled in MHU", "Up to 3 per site permitted (H5.4.1 A3); 4 or more restricted discretionary (A4)", "same", "DATA S7. Because the units straddle title lines the whole site is one site: 4 or more dwellings = restricted discretionary."),
 ("Consent pathway for dwellings", '=IF(B3<=3,"Permitted (H5.4.1 A3)","Restricted discretionary, 4+ dwellings (H5.4.1 A4)")', '=IF(C3<=3,"Permitted (H5.4.1 A3)","Restricted discretionary, 4+ dwellings (H5.4.1 A4)")', "CALCULATED from the rule text"),
 ("Flood consent", "E36 restricted discretionary (A37/A38; A42 on lot 2 flow path)", "same", "DATA S7"),
 ("Dwellings by old title (centroid)", "2: %s, 4: %s, 6: %s, 8: %s" % tuple(RT["T9"]["alloc_by_lot"].get(k, 0) for k in "2468"), "2: %s, 4: %s, 6: %s, 8: %s" % tuple(RT["T10"]["alloc_by_lot"].get(k, 0) for k in "2468"), "CALCULATED. Not 3/3/3/1: the lots are 13-14.5 m wide and 40 m deep, so no lot holds three 4 x 15 m units on its own (best per lot 1/2/1/2, sheet Groups)."),
 ("Engine standards that PASS", "yards, coverage, height, HIRB, outdoor living, dwelling size", "yards, coverage, height, HIRB, outdoor living (16 + deck), dwelling size", "S14"),
 ("Standards the engine cannot test (need design)", "impervious/landscaped detail, outlook (H5.6.13), daylight (H5.6.14 per rule list), vehicle crossing", "same, no on-site parking", "UNVERIFIED: outlook and daylight standards are untested and are the likely limit at this density. A dwelling failing them needs consent under the RD rule's matters of discretion."),
 ("PC120 effect on this scheme", "Lot 2 is rezoned Single House (immediate legal effect): one dwelling permitted there, more is non-complying. Aug 2026 amendments propose Single House on all four lots: 2 dwellings per site.", "same", "DATA S8, S9. This is the main risk to 9 and 10 dwellings. UNVERIFIED how Council treats an amalgamated site spanning two zones."),
]
for r in rows: wt.append(list(r))
for row in wt.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical="top"); c.border = BOX
for rr_ in (4, 5): 
    for cc in (2, 3): wt.cell(rr_, cc).fill = YEL
wt.cell(len(rows) + 3, 1, "Sensitivity (units that fit AND pass the engine's tested standards, flood-clear). Engine runs 10 Nov 2026 (S14).").font = B
sens_hdr = ["Parking spaces per unit", "All four lots, standard outdoor living 20 m2", "All four, ground 16 m2 + 5 m2 deck", "Lots 4+6+8 only, standard", "Note"]
r0 = len(rows) + 4
for j, h in enumerate(sens_hdr, 1):
    c = wt.cell(r0, j, h); c.font = WH; c.fill = HDR; c.alignment = Alignment(wrap_text=True)
for i, v in enumerate([(2, 4, 4, 4, "Vehicle access (5.5 m corridor for many spaces) binds"), (1, 9, 9, 7, "Outdoor living / access bind"), (0, 9, 10, 7, "No on-site parking; 10 needs the deck")]): 
    for j, x in enumerate(v, 1): wt.cell(r0 + 1 + i, j, x).fill = GRY
wt.cell(r0 + 5, 1, "Lots 4+6+8 alone never reach 9 compliant (7); lot 2 contributes 1 to 2. Separate titles with 4 x 15 m units: 1 / 2 / 1 / 2 = 6 (sheet Groups). The owner's 3 + 3 + 3 + 1 split is not physically achievable with 4 x 15 m units on the existing lot shapes.").alignment = Alignment(wrap_text=True)
for w in wb: 
    if w.title not in ("README",): w.sheet_view.zoomScale = 90
wb.save(OUT / "Zoning_Feasibility.xlsx"); print("saved", G_END, S_END)
