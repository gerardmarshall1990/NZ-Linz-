"""Shared constants and helpers for the 2-8 Parrish Road pack (screening documents built from the app's data). Nothing here is a design: every figure is tagged DATA, CALCULATED, ASSUMED or UNVERIFIED."""
import json, math, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
for l in (ROOT / ".env").read_text().splitlines():
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); os.environ.setdefault(k, v)
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data/hazard/parrish"
OUT = Path("/out"); OUT.mkdir(exist_ok=True)
TODAY = "2026-11-10"
IDS = [5098060, 5007030, 4775751, 4905036]          # 2, 4, 6, 8 Parrish Road
NUM = {5098060: "2", 5007030: "4", 4775751: "6", 4905036: "8"}
AUP_DATE = "AUP operative text dated July 2026 (index 16 Oct 2026)"
# source register: id -> (name, url or location, retrieved)
SOURCES = {
 "S1": ("LINZ NZ Property Parcels and Addresses, via this app (core.sites, raw.linz_addresses)", "data.linz.govt.nz (CC BY 4.0), loaded in the app database", "app load Oct 2026, read 2026-11-10"),
 "S2": ("Auckland Council Flood Plains layer (Meola model, URS 2017, 1D/2D coupled, 100-year ARI, climate-change adjusted, MPD)", "Auckland Council open data ArcGIS Flood_Plains (raw.ac_hz_flood_plains)", "app load Oct 2026, read 2026-11-10"),
 "S3": ("Auckland Council Flood Prone Areas layer (FPA 30836607)", "Auckland Council open data ArcGIS Flood_Prone_Areas (raw.ac_hz_flood_prone)", "app load Oct 2026, read 2026-11-10"),
 "S4": ("Auckland Council Flood Sensitive Areas layer", "Auckland Council open data ArcGIS Flood_Sensitive_Areas (raw.ac_hz_flood_sensitive)", "app load Oct 2026, read 2026-11-10"),
 "S5": ("Auckland Council Healthy Waters Overland Flow Paths (centrelines; WSP 2019 from 2016-17 LiDAR; NZVD1946)", "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Overland_Flow_Paths/FeatureServer/0", "live query 2026-11-10"),
 "S6": ("LINZ NZ Elevation, Auckland part 1 2024, 1 m DEM (LiDAR, bare earth), tile BA31_10000_0505, flown 2024-04-29 to 2024-06-26", "https://nz-elevation.s3.ap-southeast-2.amazonaws.com/auckland/auckland-part-1_2024/dem_1m/2193/BA31_10000_0505.tiff", "read 2026-11-10"),
 "S7": ("Auckland Unitary Plan operative text, Chapters E27, E36, H3, H5, H6 (official PDFs) and the rules table built from them in the app", "https://unitaryplan.aucklandcouncil.govt.nz/ (index data.xml dated 16 Oct 2026)", "downloaded Oct 2026, read 2026-11-10"),
 "S8": ("Auckland Council Plan Change 120 (Housing Intensification and Resilience): proposed text, information sheets and August 2026 explanatory note", "https://www.aucklandcouncil.govt.nz (PDFs saved in the app: data/pc120)", "downloaded Oct 2026, read 2026-11-10"),
 "S9": ("Auckland Council PC120 property summary layers (notified Nov 2025; proposed amendments Aug 2026)", "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/ PC120NotifiedForRevised_PROD_PropertySummary, PC120Revised_PROD_PropertySummary", "live query 2026-11-10"),
 "S10": ("Auckland Council stormwater network layers (Stormwater_Pipe, _Catchpit, _Connection)", "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/", "live query 2026-11-10"),
 "S11": ("Auckland Council Stormwater Management Area Control layer (SMAF)", "https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Stormwater_Management_Area_Control", "live query 2026-11-10"),
 "S12": ("Owner's draft documents: Flood Mitigation & Relocatable Foundation Specification (Draft for CPEng) and Development Term Sheet, both dated 10 Nov 2026", "supplied by the owner in this session", "2026-11-10"),
 "S13": ("Web search snippets of MBIE determinations and council guidance on Building Act ss71-74, Building Code E1 and B2 (full official text not read)", "building.govt.nz and council sites via web search", "2026-11-07 to 2026-11-10"),
 "S14": ("This app's layout engine (devlayout/devrules) run with the zone standards in S7", "scripts/hazard_report.py and scripts/parrish_pack", "run 2026-11-10"),
 "S15": ("AUP Chapter E27 Transport, vehicle access widths (config/transport_rules.yaml, quotes tested)", "data/aup E27 Transport.pdf (S7)", "2026-10-20"),
}
RHO = 1000.0; G = 9.81
DEPTHS = [0.3, 0.6, 0.9, 1.2]; VELS = [0.5, 1.0, 2.0]
FREEBOARD = 0.5            # spec: 1% AEP level + 500 mm (owner's spec; Council wording UNVERIFIED)
FLOOR_DEPTH = 0.30         # ASSUMED depth of floor frame/chassis below top of floor (manufacturer drawings needed)
UNIT_W, UNIT_L, UNIT_A = 4.0, 15.0, 60.0
def jload(p): return json.load(open(p))
def jdump(o, p): Path(p).write_text(json.dumps(o, indent=1, default=str))
