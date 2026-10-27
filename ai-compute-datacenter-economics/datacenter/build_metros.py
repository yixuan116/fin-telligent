#!/usr/bin/env python3
"""
Build data/metros.json for the Data Center demo: how far each tracked site is
from the nearest big US metro area, and the median distance per start-year
group, which is what the "Where" view of the Why there scene draws.

Sources
    US Census Bureau, Population Estimates Program, metropolitan statistical
    area totals (vintage 2025) -- which metros clear a million people.
    US Census Bureau, 2025 Gazetteer, core based statistical areas -- each
    metro's internal point, used as its location.
    Both are public domain; the URLs and retrieval dates are in
    data/sources.json and in SOURCES.md.

Inputs
    data/sites.json     built by build_sites.py; lat, lon and start year
                        per site

Output
    data/metros.json    the metro list, each site's nearest metro and
                        straight-line distance in miles, and the three
                        groups with their medians

The metro list is cached in the output and reused, so a rerun makes no
network calls; --refresh re-downloads it. Distances are always recomputed
from sites.json, so a change there lands without a download.

Paths resolve from this file, not from the shell's cwd:

    python3 ai-compute-datacenter-economics/datacenter/build_metros.py
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
import statistics
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

SITES_JSON = DATA / "sites.json"
OUT_JSON = DATA / "metros.json"

USER_AGENT = "fin-telligent-datacenter-demo/1.0 (+https://github.com/yixuan116/fin-telligent)"

POP_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/metro/"
    "totals/cbsa-est2025-alldata.csv"
)
GAZ_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/"
    "2025_Gaz_cbsa_national.zip"
)

POP_COLUMN = "POPESTIMATE2025"
POP_VINTAGE = "2025"
GAZ_VINTAGE = "2025"
POP_THRESHOLD = 1_000_000

# What a metro row is in the estimates file: the CBSA total line, not one of
# its metropolitan divisions (MDIV) or its county components (STCOU).
MSA_LSAD = "Metropolitan Statistical Area"

# Mean Earth radius in miles. Great-circle distance, which is what
# "straight-line" means on a globe.
EARTH_MILES = 3958.7613

# Sites are grouped by the year they broke ground. The boundaries are the
# story: a site started in 2023 or earlier, in 2024, or in 2025 or later.
GROUPS = [
    {"id": "early", "label": "2023 and earlier", "max_year": 2023},
    {"id": "y2024", "label": "2024", "max_year": 2024},
    {"id": "late", "label": "2025 and later", "max_year": None},
]

# What a good download looks like. A wrong file or a truncated one fails here
# rather than being written out as data.
EXPECT_MSA_COUNT = 387          # metropolitan statistical areas in the file
EXPECT_BIG_COUNT = 56           # of those, a million people or more
SPOT_CHECKS = [
    # code, name starts with, population at least, lat/lon box
    ("35620", "New York", 19_000_000, (40.0, 41.5), (-75.0, -72.5)),
    ("31080", "Los Angeles", 12_000_000, (33.0, 35.0), (-119.0, -117.0)),
    ("16980", "Chicago", 9_000_000, (41.0, 42.5), (-89.0, -87.0)),
]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    print(f"  fetching {url.rsplit('/', 1)[-1]} ...", file=sys.stderr)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def download_metros() -> list[dict]:
    """The metro areas of a million people or more, with their locations."""
    raw = fetch(POP_URL).decode("latin-1")
    metros: dict[str, dict] = {}
    msa_count = 0
    for row in csv.DictReader(io.StringIO(raw)):
        if row["LSAD"] != MSA_LSAD or row["MDIV"] or row["STCOU"]:
            continue
        msa_count += 1
        pop = int(row[POP_COLUMN])
        if pop >= POP_THRESHOLD:
            metros[row["CBSA"]] = {
                "code": row["CBSA"], "name": row["NAME"], "pop": pop,
            }

    if msa_count != EXPECT_MSA_COUNT:
        raise SystemExit(
            f"Expected {EXPECT_MSA_COUNT} metropolitan statistical areas in the "
            f"estimates file, found {msa_count}. Nothing was written."
        )

    # The Gazetteer ships as a zip of one pipe-delimited table.
    with zipfile.ZipFile(io.BytesIO(fetch(GAZ_URL))) as archive:
        name = archive.namelist()[0]
        text = archive.read(name).decode("latin-1")
    for row in csv.DictReader(io.StringIO(text), delimiter="|"):
        code = row["GEOID"].strip()
        if code in metros:
            metros[code]["lat"] = round(float(row["INTPTLAT"]), 6)
            metros[code]["lon"] = round(float(row["INTPTLONG"]), 6)

    missing = [m["name"] for m in metros.values() if "lat" not in m]
    if missing:
        raise SystemExit(
            "No Gazetteer internal point for: " + ", ".join(missing) +
            ". Nothing was written."
        )
    if len(metros) != EXPECT_BIG_COUNT:
        raise SystemExit(
            f"Expected {EXPECT_BIG_COUNT} metros of {POP_THRESHOLD:,} or more, "
            f"found {len(metros)}. Nothing was written."
        )

    for code, prefix, floor, lat_box, lon_box in SPOT_CHECKS:
        metro = metros.get(code)
        if metro is None or not metro["name"].startswith(prefix):
            raise SystemExit(f"Spot check failed: {code} is not {prefix}.")
        if metro["pop"] < floor:
            raise SystemExit(
                f"Spot check failed: {metro['name']} at {metro['pop']:,}."
            )
        if not (lat_box[0] <= metro["lat"] <= lat_box[1]
                and lon_box[0] <= metro["lon"] <= lon_box[1]):
            raise SystemExit(
                f"Spot check failed: {metro['name']} internal point at "
                f"{metro['lat']}, {metro['lon']}."
            )

    return sorted(metros.values(), key=lambda m: -m["pop"])


def load_metros(refresh: bool) -> list[dict]:
    """The cached metro list, or a fresh download if there is none."""
    if not refresh and OUT_JSON.exists():
        cached = json.loads(OUT_JSON.read_text()).get("metros") or []
        if len(cached) == EXPECT_BIG_COUNT and all(
            "lat" in m and "lon" in m and "pop" in m for m in cached
        ):
            return cached
        print("  cached metro list is incomplete; re-downloading",
              file=sys.stderr)
    return download_metros()


def miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = p2 - p1
    d_lambda = math.radians(lon2 - lon1)
    h = (math.sin(d_phi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2)
    return 2 * EARTH_MILES * math.asin(math.sqrt(h))


def group_of(year: int | None) -> str:
    for group in GROUPS:
        if group["max_year"] is None or (year is not None and year <= group["max_year"]):
            return group["id"]
    return GROUPS[-1]["id"]


def build(metros: list[dict]) -> dict:
    payload = json.loads(SITES_JSON.read_text())
    sites = [s for s in payload["sites"]
             if isinstance(s.get("lat"), (int, float))
             and isinstance(s.get("lon"), (int, float))]

    names = [s["name"] for s in sites]
    if len(set(names)) != len(names):
        raise SystemExit("Site names are not unique; they are the key here.")

    nearest: dict[str, dict] = {}
    for site in sites:
        best = min(
            metros,
            key=lambda m: miles(site["lat"], site["lon"], m["lat"], m["lon"]),
        )
        nearest[site["name"]] = {
            "metro": best["code"],
            "mi": round(miles(site["lat"], site["lon"], best["lat"], best["lon"]), 1),
            "group": group_of(site.get("start_year")),
            # Carried so the QA table reads without joining back to sites.json.
            "state": site.get("state"),
            "start_year": site.get("start_year"),
        }

    groups = []
    for spec in GROUPS:
        rows = [v["mi"] for v in nearest.values() if v["group"] == spec["id"]]
        if not rows:
            raise SystemExit(f"No sites in group {spec['id']}.")
        groups.append({
            "id": spec["id"],
            "label": spec["label"],
            "count": len(rows),
            "median_mi": round(statistics.median(rows), 1),
        })

    return {
        "meta": {
            "generated_by": "ai-compute-datacenter-economics/datacenter/build_metros.py",
            "retrieved": dt.date.today().isoformat(),
            "population_vintage": POP_VINTAGE,
            "gazetteer_vintage": GAZ_VINTAGE,
            "population_column": POP_COLUMN,
            "threshold": POP_THRESHOLD,
            "metro_count": len(metros),
            "site_count": len(nearest),
            "distance": "great-circle miles from the site to the metro's "
                        "Gazetteer internal point",
            "urls": {"population": POP_URL, "gazetteer": GAZ_URL},
            "license": "public domain (US Census Bureau)",
        },
        "metros": metros,
        "groups": groups,
        "sites": nearest,
    }


def report(out: dict) -> bool:
    metros = out["metros"]
    nearest = out["sites"]
    print(f"\nMetros of {POP_THRESHOLD:,} or more (vintage {POP_VINTAGE}): "
          f"{len(metros)}")
    print(f"  largest  {metros[0]['name']} {metros[0]['pop']:,}")
    print(f"  smallest {metros[-1]['name']} {metros[-1]['pop']:,}")

    print("\nDistance to the nearest metro of a million or more, by start year")
    for group in out["groups"]:
        rows = sorted(v["mi"] for v in nearest.values()
                      if v["group"] == group["id"])
        print(f"  {group['label']:18s} n={group['count']:2d}  "
              f"median {group['median_mi']:6.1f} mi   "
              f"range {rows[0]:.1f} to {rows[-1]:.1f}")

    by_name = {m["code"]: m["name"] for m in metros}
    ranked = sorted(nearest.items(), key=lambda kv: -kv[1]["mi"])
    print("\nFarthest five")
    for name, row in ranked[:5]:
        print(f"  {row['mi']:6.1f} mi  {name} ({row['state']}, "
              f"started {row['start_year']}) -> {by_name[row['metro']]}")
    print("\nNearest five")
    for name, row in ranked[-5:][::-1]:
        print(f"  {row['mi']:6.1f} mi  {name} ({row['state']}) -> "
              f"{by_name[row['metro']]}")

    ok = True
    if len(nearest) != out["meta"]["site_count"]:
        print("\nSite count does not match the metadata.", file=sys.stderr)
        ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true",
        help="re-download the Census estimates and Gazetteer tables",
    )
    args = parser.parse_args()

    metros = load_metros(refresh=args.refresh)
    out = build(metros)
    ok = report(out)

    OUT_JSON.write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nWrote {OUT_JSON.relative_to(HERE.parent.parent)} "
          f"({OUT_JSON.stat().st_size / 1024:.0f} KB)")
    print("\nALL CHECKS PASSED" if ok else "\nCHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
