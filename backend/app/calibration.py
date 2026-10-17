"""Scale calibration (Part 3 section 2.2). A raster/PDF plan cannot be measured without it; unscaled plans yield no measured dimensions."""
import math
from fastapi import HTTPException

PDF_PREVIEW_DPI = 100  # preview pixels = PDF points * 100/72

def two_point(measurements: list[dict]) -> dict:
    """measurements: [{a:[x,y], b:[x,y], metres: d}] in preview pixels. Returns metres_per_px and the worst residual (metres) across the measurements."""
    if not measurements: raise HTTPException(422, "at least one measured distance is required")
    scales = []
    for m in measurements:
        px = math.dist(m["a"], m["b"])
        if px < 5 or not (m["metres"] > 0): raise HTTPException(422, "each measurement needs two distinct points and a positive real-world distance")
        scales.append(m["metres"] / px)
    mean = sum(scales) / len(scales)
    resid = max(abs(math.dist(m["a"], m["b"]) * mean - m["metres"]) for m in measurements)
    return {"method": "two_point", "metres_per_unit": mean, "unit": "preview_px", "residual_m": resid, "detail": {"measurements": measurements, "n": len(measurements)}}

def stated_scale(denominator: float, page_is_pdf: bool) -> dict:
    """Drawing stated as 1:denominator on a PDF whose page is true to paper size (preview px at 100 dpi)."""
    if not page_is_pdf: raise HTTPException(422, "a stated scale needs a PDF at true paper size; use two-point calibration for images")
    if denominator <= 0: raise HTTPException(422, "scale denominator must be positive")
    mm_per_px = 25.4 / PDF_PREVIEW_DPI
    return {"method": "stated_scale", "metres_per_unit": mm_per_px * denominator / 1000.0, "unit": "preview_px", "residual_m": None,
            "detail": {"scale": f"1:{denominator:g}", "assumes": "PDF printed at 100% (true paper size); verify with a known dimension"}}
