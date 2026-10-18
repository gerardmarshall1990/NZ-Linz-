"""Capture Guide (MASTER_SPEC Part 7, remote capture): plain-English instructions for the owner or agent to capture what plans cannot show, with a phone, remotely. It lists what is still unknown for THIS property
(from the Property Record and evidence gaps), so nothing is asked twice. Drafts instructions only: no measurement is invented and nothing is sent."""
from . import gaps
from .facts import get_property
from .pack_pdf import md_to_pdf
from .plan_request import SITE_VISIT

HOW = ["Get the owner's (or agent's) permission before entering any part of the building. Do not enter occupied rooms without the occupant's consent, and do not contact tenants about this.",
       "Photograph in landscape, with good light, from a corner so two walls and the floor show. Put a tape measure or an A4 sheet in frame for scale in each room.",
       "Name files `L<level>-<room>-<direction>.jpg`, for example `L1-Bedroom03-north.jpg`. Keep the order of rooms the same as the floor plan.",
       "Measure with a tape: narrowest corridor clear width and narrowest door clear width (between the door and the frame with the door open), in metres to two decimals. Write each number with where you measured it.",
       "If the phone has a LiDAR room-scan app that exports a PDF or DXF floor plan, run it in each room and upload the export as received; it is stored as a reference and a person confirms it before anything is measured from it.",
       "Upload everything to the property's Plans area in the app, or hand the files to the owner of the tool; photos taken by you are evidence, not confirmed facts, until reviewed."]
SHOTS = ["Each room: all four walls and the ceiling, with the room name on a sheet of paper in one frame",
         "Every exit door and the route to it (corridors, stairs, ramps, lift)",
         "Fire equipment: alarm panel, detectors, sprinkler heads, extinguishers, hose reels, exit signs, emergency lights",
         "Switchboard (open, labels readable), hot water cylinder or heat pump, boiler or HVAC plant",
         "Kitchen, laundry, and each bathroom or ensuite (fixtures visible)",
         "Roof from the ground and any visible damp, cracks or settlement",
         "Any compliance schedule, BWOF certificate or fire report on display or in the office (photograph the pages)"]

def build(parcel_id: int) -> dict:
    rec = get_property(parcel_id); s = rec["site"]; facts = rec["facts"]; gp = gaps.compute(parcel_id)
    unknown = [(f, l) for f, l in SITE_VISIT if facts.get(f, {}).get("value") is None]
    known = [(f, l, facts[f]["value"], facts[f]["confidence"]) for f, l in SITE_VISIT if facts.get(f, {}).get("value") is not None]
    L = [f"# Capture guide: {s['address']}, {s['suburb']}", "", "A short guide for capturing this building's details remotely with a phone. Draft prepared from the property record; it asks only for what is still unknown.", "", "## How to capture"] + [f"{i}. {t}" for i, t in enumerate(HOW, 1)]
    L += ["", "## Photos and videos to take"] + [f"- {t}" for t in SHOTS]
    L += ["", "## Measurements and counts still needed"] + ([f"- [ ] {l}  (now: unknown)" for _, l in unknown] or ["- Nothing: every item on the site visit form is already recorded."])
    if known: L += ["", "## Already recorded (confirm if you see it differs)"] + [f"- {l}: {v} ({c})" for _, l, v, c in known]
    L += ["", "## Questions only the owner or agent can answer"] + [f"- {g['title']}: {g['why']}" for g in gp["gaps"] if g["status"] in ("NEEDS_PROFESSIONAL", "REQUESTED")][:8]
    L += ["", "## What happens next", "A person reviews the uploaded plans and photos, confirms the readings, and only then are bed layouts, compliance checks and costs run. Nothing here is a statement that the building complies with anything."]
    return {"parcel_id": parcel_id, "markdown": "\n".join(L), "unknown_items": [f for f, _ in unknown]}

def pdf(parcel_id: int) -> bytes: return md_to_pdf(build(parcel_id)["markdown"], "", stamp="Capture guide: draft instructions")
