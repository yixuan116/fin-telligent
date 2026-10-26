#!/usr/bin/env python3
"""
Build data/us_states.geojson: state outlines for the Data Center map.

The CARTO dark-matter basemap does carry a `boundary_state` layer, but its
filter only draws US state lines from zoom 6, and the map opens on the whole
continental US at about zoom 3.6. Rather than depend on what the vector tiles
happen to contain at low zoom, the outlines ship as a small local file.

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

USER_AGENT = "fin-telligent-datacenter-map/1.0 (+https://github.com/yixuan116/fin-telligent)"

# Coordinates are rounded to 4 decimals, about 11 m. Far finer than a state
# outline drawn at national zoom needs, and it keeps the file small.
PRECISION = 4

# The 50 states plus DC. us-atlas also carries Puerto Rico and the other
# territories, which have no sites in this dataset.
TERRITORY_FIPS = {"60", "66", "69", "72", "78"}


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

    return {
        "type": "Feature",
        "id": geometry.get("id"),
        "properties": {"name": geometry.get("properties", {}).get("name")},
        "geometry": {"type": kind, "coordinates": coordinates},
    }


def main() -> int:
    topology = fetch_topology()
    geometries = topology["objects"]["states"]["geometries"]

    features = [
        to_feature(topology, geometry)
        for geometry in geometries
        if geometry.get("id") not in TERRITORY_FIPS
    ]
    features.sort(key=lambda f: f["properties"]["name"] or "")

    OUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": features},
                   separators=(",", ":")) + "\n"
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

    print(f"states written : {len(features)}  (expected 51: 50 states + DC)")
    print(f"lon range      : {min(lons):.3f} .. {max(lons):.3f}")
    print(f"lat range      : {min(lats):.3f} .. {max(lats):.3f}")
    print(f"output         : {OUT.relative_to(HERE.parent.parent)} "
          f"({OUT.stat().st_size / 1024:.0f} KB)")

    ok = len(features) == 51
    print("\nALL CHECKS PASSED" if ok else "\nCHECKS FAILED: state count")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
