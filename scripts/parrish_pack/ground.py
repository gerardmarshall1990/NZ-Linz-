"""LiDAR ground sampling from the saved 1 m DEM window (data/hazard/parrish/dem.asc, EPSG:2193)."""
import numpy as np
from shapely import contains_xy
from common import DATA
_h = _Z = None
def load():
    global _h, _Z
    if _Z is None:
        with open(DATA / "dem.asc") as f:
            _h = {}
            for _ in range(6): k, v = f.readline().split(); _h[k.lower()] = float(v)
            _Z = np.loadtxt(f)
        _Z = np.where(_Z == _h.get("nodata_value", -9999), np.nan, _Z)
    return _h, _Z
def sample(x, y):
    """Bilinear ground level (m) at an EPSG:2193 point."""
    h, Z = load(); cs = h["cellsize"]; n = int(h["nrows"])
    fx = (x - h["xllcorner"]) / cs - 0.5; fy = (h["yllcorner"] + n * cs - y) / cs - 0.5
    x0, y0 = int(np.floor(fx)), int(np.floor(fy)); tx, ty = fx - x0, fy - y0; v = 0.0; w = 0.0
    for dx, dy, wt in ((0, 0, (1 - tx) * (1 - ty)), (1, 0, tx * (1 - ty)), (0, 1, (1 - tx) * ty), (1, 1, tx * ty)):
        xx, yy = x0 + dx, y0 + dy
        if 0 <= yy < Z.shape[0] and 0 <= xx < Z.shape[1] and not np.isnan(Z[yy, xx]): v += Z[yy, xx] * wt; w += wt
    return v / w if w else float("nan")
def grid():
    h, Z = load(); n, m = Z.shape; cs = h["cellsize"]
    xs = h["xllcorner"] + (np.arange(m) + .5) * cs; ys = h["yllcorner"] + (n - np.arange(n) - .5) * cs
    X, Y = np.meshgrid(xs, ys); return X, Y, Z
def inside(poly):
    X, Y, Z = grid(); m = contains_xy(poly, X, Y) & ~np.isnan(Z); return X[m], Y[m], Z[m]
