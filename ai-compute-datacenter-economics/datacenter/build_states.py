#!/usr/bin/env python3
"""
Build the Data Center map's cartography from the us-atlas boundary file.

Outputs
    data/us_states.geojson  contiguous state outlines, each carrying its
                            two-letter code and a label anchor inside the state
    data/us_mask.geojson    the world with the United States punched out, so
                            the page can darken everything outside the country

The CARTO dark-matter basemap does carry a `boundary_state` layer, but its
filter only draws US state lines from zoom 6, and the map opens on the whole
contiguous US at about zoom 4. Rather than depend on what the vector tiles
happen to contain at low zoom, the outlines ship as a local file.

Source
    us-atlas (TopoJSON, public domain, derived from US Census Bureau
    cartographic boundary files). https://github.com/topojson/us-atlas

Run from anywhere; paths resolve from this file:

    python3 ai-compute-datacenter-economics/datacenter/build_states.py

The download is cached next to the output, so a rerun needs no network.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# us-atlas 3.0.1 ships only the 10m resolution for states.
SOURCE_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json"
CACHE = DATA / "us_states_topo.json"
OUT = DATA / "us_states.geojson"
OUT_MASK = DATA / "us_mask.geojson"

USER_AGENT = "fin-telligent-datacenter-map/1.0 (+https://github.com/yixuan116/fin-telligent)"

# Coordinates are rounded to 4 decimals, about 11 m. Far finer than a state
# outline drawn at national zoom needs, and it keeps the file small.
PRECISION = 4

# The 50 states plus DC. us-atlas also carries Puerto Rico and the other
# territories, which have no sites in this dataset.
TERRITORY_FIPS = {"60", "66", "69", "72", "78"}

# The map frames the contiguous US and nothing else: every tracked site is in
# it, and leaving Alaska and Hawaii in the file only invites the camera to
# reveal them at the edges. They are dropped from the outlines, from the label
# set and from the mask, so the Pacific stays as dark as Canada does.
NON_CONTIGUOUS_FIPS = {"02", "15"}

STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT",
    "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL",
    "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY",
    "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

# The crowded northeast. These labels cannot sit inside their own state at a
# national zoom without colliding, so each is parked just off its own coast
# with a short leader line back to the state. Earlier these sat in one column
# far out in the Atlantic, which made New Jersey's leader cross three states;
# each now sits a short hop from the shoreline it belongs to. The page hides
# any whose state has no live site at the selected time, which is most of
# them: only New Jersey holds a tracked site.
OFFSHORE_LABELS = {
    "VT": (-71.4, 45.1),
    "NH": (-70.5, 44.2),
    "MA": (-69.7, 42.3),
    "RI": (-70.6, 40.9),
    "CT": (-71.8, 40.3),
    "NJ": (-73.3, 39.2),
    "DE": (-74.4, 38.3),
    "MD": (-74.9, 37.5),
    "DC": (-75.4, 36.8),
}

# A handful of states whose computed anchor is technically inside the state but
# reads badly: too close to a border, or on the wrong lobe. Nudged by hand.
ANCHOR_OVERRIDES = {
    "MI": (-84.7, 43.6),    # lower peninsula, not the strait
    "LA": (-92.3, 31.2),    # above the delta
    "FL": (-81.7, 28.3),    # peninsula, not the panhandle
    "VA": (-78.6, 37.7),    # off the Delmarva tail
    "ID": (-114.6, 44.2),
    "CA": (-119.8, 37.0),
    "AK": (-152.0, 63.5),
    "HI": (-155.5, 19.6),   # Hawaii island, not the channel between islands
}

# Anything whose centre falls outside this box is not part of the contiguous
# US and is left under the mask.
CONTIGUOUS_BBOX = (-128.0, 23.0, -64.0, 51.0)

# The ring the mask is cut out of. Longitudes stay inside the projection's
# valid range so the fill does not wrap around the globe.
WORLD_RING = [
    [-179.99, -85.0], [179.99, -85.0], [179.99, 85.0], [-179.99, 85.0],
    [-179.99, -85.0],
]


def fetch_topology() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    CACHE.write_bytes(raw)
    return json.loads(raw)


def decode_arc(topology: dict, index: int) -> list[list[float]]:
    """One TopoJSON arc as absolute lon/lat, honouring the reversal convention.

    Arcs are delta-encoded against the topology's quantization grid, and a
    negative index means "that arc, backwards" with ~i giving its position.
    """
    reverse = index < 0
    arc = topology["arcs"][~index if reverse else index]
    scale = topology["transform"]["scale"]
    translate = topology["transform"]["translate"]

    points: list[list[float]] = []
    x = y = 0
    for dx, dy in arc:
        x += dx
        y += dy
        points.append(
            [
                round(x * scale[0] + translate[0], PRECISION),
                round(y * scale[1] + translate[1], PRECISION),
            ]
        )
    return points[::-1] if reverse else points


def stitch(topology: dict, arc_indexes: list[int]) -> list[list[float]]:
    """Join a ring's arcs, dropping the point each shares with the previous."""
    ring: list[list[float]] = []
    for position, index in enumerate(arc_indexes):
        points = decode_arc(topology, index)
        ring.extend(points if position == 0 else points[1:])
    return ring


def unwrap_antimeridian(ring: list[list[float]]) -> list[list[float]]:
    """Keep a ring on one side of the dateline.

    Alaska's Aleutian islands run past 180 degrees east, so the raw ring mixes
    longitudes near -179 with longitudes near +179. Drawn as is, each such
    polygon is stretched right across the map as a horizontal streak. Shifting
    the positive longitudes 360 degrees west makes the ring contiguous.
    """
    if not any(lon > 0 for lon, _ in ring) or not any(lon < -100 for lon, _ in ring):
        return ring
    return [[lon - 360 if lon > 0 else lon, lat] for lon, lat in ring]


def to_feature(topology: dict, geometry: dict) -> dict:
    kind = geometry["type"]
    if kind == "Polygon":
        coordinates = [unwrap_antimeridian(stitch(topology, ring))
                       for ring in geometry["arcs"]]
    elif kind == "MultiPolygon":
        coordinates = [
            [unwrap_antimeridian(stitch(topology, ring)) for ring in polygon]
            for polygon in geometry["arcs"]
        ]
    else:
        raise ValueError(f"unexpected geometry type {kind!r}")

    name = geometry.get("properties", {}).get("name")
    code = STATE_CODES.get(name)
    rings = coordinates if kind == "Polygon" else [p[0] for p in coordinates]
    anchor = ANCHOR_OVERRIDES.get(code) or label_anchor(rings)
    offshore = OFFSHORE_LABELS.get(code)

    # `label` is where the two-letter code is drawn; `anchor` is the point a
    # leader line starts from, which is always inside the state itself.
    return {
        "type": "Feature",
        "id": geometry.get("id"),
        "properties": {
            "name": name,
            "code": code,
            "anchor": [round(anchor[0], 4), round(anchor[1], 4)],
            "label": [round(offshore[0], 4), round(offshore[1], 4)] if offshore else
                     [round(anchor[0], 4), round(anchor[1], 4)],
            "offshore": bool(offshore),
        },
        "geometry": {"type": kind, "coordinates": coordinates},
    }


def ring_area(ring: list[list[float]]) -> float:
    total = 0.0
    for i in range(len(ring) - 1):
        total += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(total) / 2


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        if (y1 > y) != (y2 > y):
            t = (y - y1) / (y2 - y1)
            if x < x1 + t * (x2 - x1):
                inside = not inside
    return inside


def distance_to_ring(x: float, y: float, ring: list[list[float]]) -> float:
    best = float("inf")
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        dx, dy = x2 - x1, y2 - y1
        span = dx * dx + dy * dy
        t = 0.0 if span == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / span))
        px, py = x1 + t * dx, y1 + t * dy
        best = min(best, ((x - px) ** 2 + (y - py) ** 2) ** 0.5)
    return best


def label_anchor(rings: list[list[list[float]]]) -> tuple[float, float]:
    """A point well inside the state's largest lobe.

    A plain centroid lands in Lake Michigan for Michigan and in the Gulf for
    Louisiana, so this takes the biggest ring and searches a grid for the
    interior point furthest from any edge: a coarse pole of inaccessibility.
    """
    ring = max(rings, key=ring_area)
    xs = [c[0] for c in ring]
    ys = [c[1] for c in ring]
    best = None
    steps = 48
    for i in range(1, steps):
        x = min(xs) + (max(xs) - min(xs)) * i / steps
        for j in range(1, steps):
            y = min(ys) + (max(ys) - min(ys)) * j / steps
            if not point_in_ring(x, y, ring):
                continue
            d = distance_to_ring(x, y, ring)
            if best is None or d > best[0]:
                best = (d, x, y)
    if best is None:
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    return (best[1], best[2])


def build_mask(topology: dict) -> dict:
    """The world with the country punched out.

    The holes come from us-atlas's `nation` object, not from the 51 state
    polygons. Adjacent states share their borders, so using them would hand
    the renderer 285 holes that touch along every edge, and the tessellator
    turns that into black wedges across the middle of the country. The nation
    outline is the same arcs already merged, so the mask is a world ring with
    a few dozen clean, non-touching holes.
    """
    geometry = topology["objects"]["nation"]["geometries"][0]
    if geometry["type"] == "Polygon":
        polygons = [geometry["arcs"]]
    else:
        polygons = geometry["arcs"]

    holes = []
    for polygon in polygons:
        # Only the outer ring of each landmass; an inner ring would be a lake,
        # and re-darkening lakes is not worth the geometry at this zoom.
        ring = unwrap_antimeridian(stitch(topology, polygon[0]))
        if len(ring) < 4:
            continue
        # Alaska and Hawaii stay covered by the mask, so if the camera ever
        # drifts far enough to include them they read as dark as Canada.
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        centre = (sum(lons) / len(lons), sum(lats) / len(lats))
        if not (CONTIGUOUS_BBOX[0] <= centre[0] <= CONTIGUOUS_BBOX[2]
                and CONTIGUOUS_BBOX[1] <= centre[1] <= CONTIGUOUS_BBOX[3]):
            continue
        holes.append(ring)

    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"holes": len(holes)},
            "geometry": {"type": "Polygon", "coordinates": [WORLD_RING] + holes},
        }],
    }


def main() -> int:
    topology = fetch_topology()
    geometries = topology["objects"]["states"]["geometries"]

    features = [
        to_feature(topology, geometry)
        for geometry in geometries
        if geometry.get("id") not in TERRITORY_FIPS
        and geometry.get("id") not in NON_CONTIGUOUS_FIPS
    ]
    features.sort(key=lambda f: f["properties"]["name"] or "")

    OUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": features},
                   separators=(",", ":")) + "\n"
    )
    OUT_MASK.write_text(
        json.dumps(build_mask(topology), separators=(",", ":")) + "\n"
    )

    lons = []
    lats = []
    for feature in features:
        stack = [feature["geometry"]["coordinates"]]
        while stack:
            item = stack.pop()
            if item and isinstance(item[0], (int, float)):
                lons.append(item[0])
                lats.append(item[1])
            else:
                stack.extend(item)

    # Every label anchor must land inside its own state, or the two-letter
    # code floats in the sea next to the state it names.
    stray = []
    for feature in features:
        ax, ay = feature["properties"]["anchor"]
        geometry = feature["geometry"]
        rings = (geometry["coordinates"] if geometry["type"] == "Polygon"
                 else [p[0] for p in geometry["coordinates"]])
        if not any(point_in_ring(ax, ay, ring) for ring in rings):
            stray.append(feature["properties"]["code"])

    missing_code = [f["properties"]["name"] for f in features
                    if not f["properties"]["code"]]

    print(f"states written : {len(features)}  (expected 49: the 48 contiguous states + DC)")
    print(f"anchors outside their state : {stray or 'none'}")
    print(f"states with no two-letter code : {missing_code or 'none'}")
    print(f"offshore labels : "
          f"{sorted(f['properties']['code'] for f in features if f['properties']['offshore'])}")
    print(f"lon range      : {min(lons):.3f} .. {max(lons):.3f}")
    print(f"lat range      : {min(lats):.3f} .. {max(lats):.3f}")
    print(f"output         : {OUT.relative_to(HERE.parent.parent)} "
          f"({OUT.stat().st_size / 1024:.0f} KB)")

    ok = len(features) == 49 and not stray and not missing_code
    print("\nALL CHECKS PASSED" if ok else "\nCHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
