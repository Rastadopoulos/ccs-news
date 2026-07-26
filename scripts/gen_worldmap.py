#!/usr/bin/env python3
"""Regenerate scripts/_worldmap.py — vendored, simplified country outlines.

One-off build tool, NOT part of the dashboard build. It turns the public-domain
Natural Earth 110m country dataset into compact SVG path data that gets checked
into the repo, so `build_dashboard.py` never needs a network call or a runtime
map library and the built HTML stays fully self-contained.

Source (public domain, no attribution required — credit given anyway in the
generated file's header):
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson

Usage:
  curl -o /tmp/ne_110m.geojson <url above>
  python3 scripts/gen_worldmap.py /tmp/ne_110m.geojson

Projection is Robinson — the standard compromise projection for world maps.
Equirectangular was rejected because it inflates high-latitude countries
(Norway, Canada, Russia) so badly that a CCS map reads as misleading: Norway
is a major CCS player and should not look like a continent.
"""

from __future__ import annotations

import json
import math
import os
import sys

# Robinson projection lookup table, 5-degree steps of latitude 0..90.
# X = relative length of the parallel, Y = relative distance from the equator.
_ROB_X = [1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600, 0.9427,
          0.9216, 0.8962, 0.8679, 0.8350, 0.7986, 0.7597, 0.7186, 0.6732,
          0.6213, 0.5722, 0.5322]
_ROB_Y = [0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720, 0.4340,
          0.4958, 0.5571, 0.6176, 0.6769, 0.7346, 0.7903, 0.8435, 0.8936,
          0.9394, 0.9761, 1.0000]

WIDTH = 1000.0          # target SVG width in user units
SIMPLIFY_TOL = 0.55     # Douglas-Peucker tolerance, in projected px
MIN_RING_AREA = 2.0     # drop islands smaller than this (px^2); largest ring always kept
DROP = {"AQ"}           # Antarctica — conventional omission, no CCS relevance

# City-states / microstates the 110m dataset omits or renders sub-pixel. They still
# need a LABEL_POINT so the dashboard can draw a visible marker dot for them — a CCS
# map that silently loses Singapore is wrong, however small the landmass.
EXTRA_POINTS = {
    "SG": (103.82, 1.35),    # Singapore
    "BH": (50.55, 26.07),    # Bahrain
}


def _rob_interp(table, lat_abs):
    i = min(int(lat_abs / 5.0), 17)
    frac = (lat_abs - i * 5.0) / 5.0
    return table[i] + (table[i + 1] - table[i]) * frac


def project(lon, lat):
    """lon/lat degrees -> Robinson x/y in an arbitrary unit sphere (R=1)."""
    lat = max(-90.0, min(90.0, lat))
    a = abs(lat)
    x = 0.8487 * _rob_interp(_ROB_X, a) * math.radians(lon)
    y = 1.3523 * _rob_interp(_ROB_Y, a)
    if lat < 0:
        y = -y
    return x, y


def _perp_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def simplify(points, tol):
    """Iterative Douglas-Peucker (explicit stack — some rings are deep enough
    to blow the recursion limit)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        worst_d, worst_i = -1.0, -1
        for i in range(lo + 1, hi):
            d = _perp_dist(points[i], points[lo], points[hi])
            if d > worst_d:
                worst_d, worst_i = d, i
        if worst_d > tol:
            keep[worst_i] = True
            stack.append((lo, worst_i))
            stack.append((worst_i, hi))
    return [p for p, k in zip(points, keep) if k]


def ring_area(points):
    """Absolute shoelace area."""
    s = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def ring_centroid(points):
    """Area-weighted polygon centroid (falls back to mean for degenerate rings)."""
    cx = cy = a = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(a) < 1e-9:
        n = len(points)
        return sum(p[0] for p in points) / n, sum(p[1] for p in points) / n
    a *= 0.5
    return cx / (6 * a), cy / (6 * a)


def iso_of(props):
    for key in ("ISO_A2_EH", "ISO_A2", "ADM0_A3"):
        v = props.get(key)
        if v and v not in ("-99", "-999"):
            return v[:2].upper() if key.startswith("ISO_A2") else None
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <ne_110m_admin_0_countries.geojson>")
    src = sys.argv[1]
    with open(src, encoding="utf-8") as f:
        gj = json.load(f)

    # Pass 1: project every ring, collect for global bbox.
    raw = {}   # iso2 -> {"name": str, "rings": [[(x,y)…]…]}
    for feat in gj["features"]:
        props = feat["properties"]
        iso = iso_of(props)
        if not iso or iso in DROP:
            continue
        geom = feat["geometry"]
        polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
                 else geom["coordinates"])
        rings = []
        for poly in polys:
            outer = poly[0]  # exterior ring only — holes are invisible at this scale
            pts = [project(lon, lat) for lon, lat in outer]
            if len(pts) >= 4:
                rings.append(pts)
        if rings:
            raw[iso] = {"name": props.get("NAME") or iso, "rings": rings}

    # Global bbox -> scale/translate so the map fills WIDTH.
    all_pts = [p for c in raw.values() for r in c["rings"] for p in r]
    min_x = min(p[0] for p in all_pts)
    max_x = max(p[0] for p in all_pts)
    min_y = min(p[1] for p in all_pts)
    max_y = max(p[1] for p in all_pts)
    scale = WIDTH / (max_x - min_x)
    height = (max_y - min_y) * scale

    def to_px(p):
        # SVG y grows downward, so flip.
        return ((p[0] - min_x) * scale, (max_y - p[1]) * scale)

    out = {}
    centroids = {}
    for iso, c in sorted(raw.items()):
        px_rings = [[to_px(p) for p in r] for r in c["rings"]]
        areas = [ring_area(r) for r in px_rings]
        biggest = max(range(len(px_rings)), key=lambda i: areas[i])
        kept = [(r, a) for i, (r, a) in enumerate(zip(px_rings, areas))
                if a >= MIN_RING_AREA or i == biggest]
        d_parts = []
        for r, _ in kept:
            s = simplify(r, SIMPLIFY_TOL)
            if len(s) < 3:
                continue
            d_parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in s) + "Z")
        if not d_parts:
            continue
        out[iso] = "".join(d_parts)
        cx, cy = ring_centroid(px_rings[biggest])
        centroids[iso] = (round(cx, 1), round(cy, 1))

    # Microstates the dataset drops entirely still get a label point (see EXTRA_POINTS).
    for iso, (lon, lat) in EXTRA_POINTS.items():
        if iso not in centroids:
            x, y = to_px(project(lon, lat))
            centroids[iso] = (round(x, 1), round(y, 1))

    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_worldmap.py")
    with open(dest, "w", encoding="utf-8") as f:
        f.write('"""Vendored simplified world-country outlines — GENERATED, do not hand-edit.\n\n'
                'Regenerate with scripts/gen_worldmap.py (see that file for the source URL\n'
                'and the reasoning behind the projection and simplification settings).\n\n'
                'Source data: Natural Earth 110m Admin 0 Countries (public domain).\n'
                'Projection: Robinson. Antarctica omitted.\n\n'
                'COUNTRY_PATH maps ISO 3166-1 alpha-2 -> an SVG path "d" string in a\n'
                f'{int(WIDTH)}x{int(round(height))} user-unit viewBox. LABEL_POINT gives each\n'
                'country\'s largest-landmass centroid, for placing markers and labels.\n'
                '"""\n\n')
        f.write("import math\n\n")
        f.write(f"VIEWBOX_W = {int(WIDTH)}\n")
        f.write(f"VIEWBOX_H = {int(round(height))}\n\n")
        f.write("# Robinson projection constants, fitted to the paths below. project_lonlat()\n"
                "# must stay in lockstep with them: it is what places project pins by real\n"
                "# coordinates, and any drift would float pins off their countries.\n")
        f.write(f"_ROB_X = {_ROB_X!r}\n")
        f.write(f"_ROB_Y = {_ROB_Y!r}\n")
        f.write(f"_MIN_X = {min_x!r}\n")
        f.write(f"_MAX_Y = {max_y!r}\n")
        f.write(f"_SCALE = {scale!r}\n\n\n")
        f.write('def project_lonlat(lon, lat):\n'
                '    """Longitude/latitude in degrees -> (x, y) in this module\'s viewBox."""\n'
                '    lat = max(-90.0, min(90.0, lat))\n'
                '    a = abs(lat)\n'
                '    i = min(int(a / 5.0), 17)\n'
                '    frac = (a - i * 5.0) / 5.0\n'
                '    rx = _ROB_X[i] + (_ROB_X[i + 1] - _ROB_X[i]) * frac\n'
                '    ry = _ROB_Y[i] + (_ROB_Y[i + 1] - _ROB_Y[i]) * frac\n'
                '    x = 0.8487 * rx * math.radians(lon)\n'
                '    y = 1.3523 * ry\n'
                '    if lat < 0:\n'
                '        y = -y\n'
                '    return ((x - _MIN_X) * _SCALE, (_MAX_Y - y) * _SCALE)\n\n\n')
        f.write("COUNTRY_PATH = {\n")
        for iso in sorted(out):
            f.write(f'    "{iso}": "{out[iso]}",\n')
        f.write("}\n\n")
        f.write("LABEL_POINT = {\n")
        for iso in sorted(centroids):
            x, y = centroids[iso]
            f.write(f'    "{iso}": ({x}, {y}),\n')
        f.write("}\n")

    total = sum(len(v) for v in out.values())
    print(f"wrote {dest}")
    print(f"  {len(out)} countries · {total/1024:.0f} KB of path data · "
          f"viewBox {int(WIDTH)}x{int(round(height))}")


if __name__ == "__main__":
    main()
