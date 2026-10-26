#!/usr/bin/env python3
"""
Build data/sites.json for the Data Center demo (part 3 of the AI / Compute /
Data Center series) from Epoch AI's "AI data centers" dataset.

Source
    Epoch AI, 'AI data centers'. https://epoch.ai/data/ai-data-centers
    Licensed CC-BY 4.0; see data/EPOCH_LICENSE.md for the citation.

Inputs  (siblings in data/, copied from the Epoch download)
    data/data_centers.csv           one row per site
    data/data_center_timelines.csv  dated observations per site

Outputs
    data/sites.json                 US sites only, ready for the map
    data/geocode_cache.json         Nominatim responses, committed so a rerun
                                    is deterministic and needs no network

Scope is United States only (Country == "United States"), currently 77 sites.

Paths resolve from this file, not from the shell's cwd, so the script can be
run from anywhere:

    python3 ai-compute-datacenter-economics/datacenter/build_sites.py

Pass --refresh-geocode to re-query Nominatim for addresses that are not yet in
the cache (the default also does this; the flag additionally discards cached
failures so they are retried).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

SITES_CSV = DATA / "data_centers.csv"
TIMELINES_CSV = DATA / "data_center_timelines.csv"
OUT_JSON = DATA / "sites.json"
GEOCODE_CACHE = DATA / "geocode_cache.json"

COUNTRY = "United States"

# Half-year grid. H1 is the state of the world on Jan 1, H2 on Jul 1.
PERIOD_START_YEAR = 2021
PERIOD_END_YEAR = 2030  # inclusive, H1 only in the final year

# "Today" for the headline figure. Fixed rather than datetime.today() so the
# published JSON and the QA table stay reproducible.
AS_OF = dt.date(2026, 10, 26)

# Epoch appends a confidence tag to several free-text fields.
CONFIDENCE_RE = re.compile(r"#(confident|likely|speculative)\b")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "fin-telligent-datacenter-map/1.0 (+https://github.com/yixuan116/fin-telligent)"
NOMINATIM_DELAY_S = 1.1  # Nominatim's usage policy allows 1 request per second

US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN",
    "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}
STATE_ABBRS = set(US_STATES.values())

# ---------------------------------------------------------------------------
# Sites Epoch ships without a usable address.
#
# Eight rows have a blank Address and one ("Stream Phoenix") has a street with
# no city or state, so none of them can be geocoded as written. Each is pinned
# to a city (or county) and state taken from that row's own "Selected Sources"
# column, and the coordinate is then produced by the same Nominatim lookup as
# every other site -- the manual part is the place, not the arithmetic.
#
# `source` records where the place came from. `precision` says how tight the
# resulting pin is: "city" and "county" pins land on a centroid, not on the
# building, so the map must not imply street-level accuracy for them.
# ---------------------------------------------------------------------------
MANUAL_LOCATIONS: dict[str, dict[str, str]] = {
    "Google Mesa": {
        "query": "Mesa, Arizona, USA",
        "city": "Mesa", "state": "AZ", "precision": "city",
        "source": "Epoch Selected Sources: DCD, 'Google breaks ground on Mesa "
                  "data center campus in Arizona'",
    },
    "Google Kansas City East": {
        "query": "Kansas City, Missouri, USA",
        "city": "Kansas City", "state": "MO", "precision": "city",
        "source": "Epoch Selected Sources: DCD, 'Google files project plan for "
                  "data center in Kansas City, Missouri'; Hunt Midwest "
                  "Business Center press release",
    },
    "Google Storey County": {
        "query": "Storey County, Nevada, USA",
        "city": "Storey County", "state": "NV", "precision": "county",
        "source": "Epoch Selected Sources: Google data center page "
                  "datacenters.google/locations/storey-county-nevada; Nevada "
                  "NDEP air quality permit",
    },
    "Anthropic Barber Lake": {
        "query": "Colorado City, Texas, USA",
        "city": "Colorado City", "state": "TX", "precision": "city",
        "source": "Epoch Selected Sources: Cipher Mining releases and SEC 8-K "
                  "for the Barber Lake site, Mitchell County, Texas",
    },
    "OpenAI Stargate Michigan": {
        "query": "Saline Township, Washtenaw County, Michigan, USA",
        "city": "Saline Township", "state": "MI", "precision": "city",
        "source": "Epoch Selected Sources: Related Digital Michigan site page, "
                  "'Project Mitten' air permit, thesalinebarn.com local "
                  "information site, and the DTE Electric contract approved by "
                  "the Michigan PSC",
    },
    "OpenAI Stargate Milam": {
        "query": "Milam County, Texas, USA",
        "city": "Milam County", "state": "TX", "precision": "county",
        "source": "Epoch Selected Sources: DCD, 'SoftBank's SB Energy to build "
                  "and operate OpenAI's 1.2GW Stargate data center in Milam "
                  "County, Texas'",
    },
    "OpenAI Stargate New Mexico": {
        "query": "Dona Ana County, New Mexico, USA",
        "city": "Dona Ana County", "state": "NM", "precision": "county",
        "source": "Epoch Selected Sources: Project Jupiter website and the "
                  "Oracle/BorderPlex/Bloom Energy announcement, which place "
                  "the site in the BorderPlex region of Dona Ana County",
    },
    "OpenAI Stargate Wisconsin": {
        "query": "Port Washington, Wisconsin, USA",
        "city": "Port Washington", "state": "WI", "precision": "city",
        "source": "Epoch Selected Sources: Vantage Data Centers page for "
                  "'port-washington-wisconsin'",
    },
}

# ---------------------------------------------------------------------------
# Rows whose Address names a street but no city or state, so the string cannot
# be geocoded and no state can be parsed out of it. The town comes from that
# row's own "Selected Sources"; the street is Epoch's. These still go through
# the normal fallback chain, so they resolve at street level where OSM knows
# the road and fall back to the town otherwise.
# ---------------------------------------------------------------------------
ADDRESS_FIXES: dict[str, dict[str, str]] = {
    "AWS New Albany": {
        "address": "13360 Miller Rd NW, New Albany, Ohio, USA",
        "source": "Epoch Selected Sources: City of New Albany (Ohio) project "
                  "updates and community development reports; Epoch's address "
                  "is '13360 Miller Rd NW' with no town",
    },
    "Stream Phoenix": {
        "address": "2950 S Litchfield Rd, Goodyear, Arizona, USA",
        "source": "Epoch Selected Sources: Stream Data Centers pre-construction "
                  "document 'SDC-Goodyear-CaseStudy'; Epoch's address is "
                  "'2950 S. Litchfield Road' with no town",
    },
}

# US IT power and live-site counts the build is checked against. "Live" means
# a site whose carried-forward IT power is above zero at that instant.
EXPECTED_QA = [
    ("2021H1", 48.0, 1),
    ("2024H1", 408.0, 6),
    ("2025H1", 1800.0, 19),
    ("2026H1", 5700.0, 36),
    ("as_of", 12000.0, 60),
    ("2030H1", 33100.0, 77),
]
# The expected figures are quoted to 2 significant figures in GW, so compare
# with a tolerance rather than for equality.
QA_TOLERANCE_MW = 60.0


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def strip_tag(value: str) -> tuple[str, str | None]:
    """Split "Amazon #confident" into ("Amazon", "confident")."""
    text = (value or "").replace("\xa0", " ")
    found = CONFIDENCE_RE.search(text)
    confidence = found.group(1) if found else None
    cleaned = CONFIDENCE_RE.sub("", text).strip(" ,;")
    return re.sub(r"\s+", " ", cleaned), confidence


def split_users(value: str) -> list[dict[str, str | None]]:
    """Users is a comma-separated list, each entry carrying its own tag."""
    out = []
    for chunk in (value or "").split(","):
        name, confidence = strip_tag(chunk)
        if name:
            out.append({"name": name, "confidence": confidence})
    return out


def to_float(value: str) -> float:
    value = (value or "").strip()
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_state(address: str) -> str | None:
    """Pull a two-letter state code out of a free-text US address."""
    text = (address or "").replace("\xa0", " ").strip()
    if not text:
        return None
    # "..., TN 38109" or "..., OR" at the end of a segment
    for match in re.finditer(r"\b([A-Z]{2})\b(?=[\s,]*(?:\d{5}(?:-\d{4})?)?\s*$)", text):
        if match.group(1) in STATE_ABBRS:
            return match.group(1)
    # Spelled out, e.g. "Ridgeland, Mississippi"
    for name, abbr in US_STATES.items():
        if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            return abbr
    # Any bare abbreviation as a last resort
    for match in re.finditer(r"\b([A-Z]{2})\b", text):
        if match.group(1) in STATE_ABBRS:
            return match.group(1)
    return None


def parse_zip(address: str) -> str | None:
    """The postal code, never the house number.

    A five-digit house number leads the address ("13001 Rollins Ford Road,
    Bristow, VA 20136"), so a naive first-match grabs 13001 and geocodes it as
    a ZIP in New York. Only a group that follows a state token, or that ends
    the string, is treated as the ZIP.
    """
    text = re.sub(r"\s+", " ", (address or "").replace("\xa0", " ")).strip()
    text = re.sub(r",?\s*USA\s*$", "", text, flags=re.IGNORECASE).strip(" ,")
    if not text:
        return None

    after_state = re.search(r"\b[A-Z]{2}\b[\s,]*(\d{5})(?:-\d{4})?\b", text)
    if after_state:
        return after_state.group(1)
    for name in US_STATES:
        match = re.search(rf"\b{re.escape(name)}\b[\s,]*(\d{{5}})(?:-\d{{4}})?\b",
                          text, re.IGNORECASE)
        if match:
            return match.group(1)
    at_end = re.search(r"\b(\d{5})(?:-\d{4})?\s*$", text)
    return at_end.group(1) if at_end else None


def parse_city(address: str) -> str | None:
    """Best guess at the town: the words immediately before the state token."""
    text = re.sub(r"\s+", " ", (address or "").replace("\xa0", " ")).strip()
    if not text:
        return None

    # "..., Canton, Mississippi ..." or "... Papillion Nebraska, USA"
    for name in US_STATES:
        match = re.search(rf"(.*?)[,\s]+{re.escape(name)}\b", text, re.IGNORECASE)
        if match:
            head = match.group(1)
            break
    else:
        # "..., Toney, AL 35773"
        match = re.search(r"(.*?),\s*([A-Z]{2})\b(?:\s*\d{5})?", text)
        if not match or match.group(2) not in STATE_ABBRS:
            return None
        head = match.group(1)

    # The town is the last comma-separated chunk before the state, with any
    # leading house number or number range dropped.
    chunk = head.split(",")[-1].strip()
    chunk = re.sub(r"^[\d–—-]+\s+", "", chunk).strip()
    # Reject a chunk that is still a street rather than a town.
    if not chunk or re.search(
        r"\b(rd|road|st|street|ave|avenue|blvd|boulevard|dr|drive|ln|lane|"
        r"pkwy|parkway|hwy|highway|cir|circle|ct|court|way|lp|loop|"
        r"cr|trail|route)\b\.?$",
        chunk, re.IGNORECASE,
    ):
        return None
    return chunk


def geocode_queries(address: str) -> list[tuple[str, str]]:
    """Progressively coarser lookups for one address, as (query, precision).

    OSM often has no node for a brand new industrial road, so a street-level
    miss falls back to the postcode and then to the town. The precision that
    actually resolved is recorded on the site, because a postcode or town
    centroid must not be drawn as if it were the building.
    """
    text = re.sub(r"\s+", " ", (address or "").replace("\xa0", " ")).strip()
    if not text:
        return []

    queries: list[tuple[str, str]] = [(text, "address")]

    # Same string with range prefixes, trailing country and county suffixes
    # removed: "6030-6070 Technology Blvd, Sandston, VA 23150, USA" loses the
    # range OSM cannot match.
    simplified = re.sub(r",?\s*USA\s*$", "", text, flags=re.IGNORECASE)
    simplified = re.sub(r",?\s*[A-Za-z .]+\bCounty\b\s*$", "", simplified)
    simplified = re.sub(r"\b(\d+)[–—-]\d+\b", r"\1", simplified)
    simplified = simplified.strip(" ,")
    if simplified and simplified != text:
        queries.append((simplified, "address"))

    zip_code = parse_zip(text)
    if zip_code:
        queries.append((f"{zip_code}, USA", "postcode"))

    city = parse_city(text)
    state = parse_state(text)
    if city and state:
        # A few rows run the site description into the town
        # ("... Nissan Parkway and Highway 22 Canton, Mississippi"), so the
        # trailing words are tried as the town name too.
        words = city.split()
        for candidate in (city, " ".join(words[-2:]), words[-1]):
            # A candidate starting with a number is a fragment of the street,
            # not a town: "Highway 22 Canton" trimmed to "22 Canton" matches a
            # house on a Canton Drive in the wrong county.
            if candidate and not candidate.split()[0].isdigit():
                queries.append((f"{candidate}, {state}, USA", "city"))

    seen = set()
    unique = []
    for query, precision in queries:
        if query.lower() not in seen:
            seen.add(query.lower())
            unique.append((query, precision))
    return unique


def period_labels() -> list[tuple[str, dt.date]]:
    """2021H1 .. 2030H1, each with the date its value is read at."""
    out = []
    for year in range(PERIOD_START_YEAR, PERIOD_END_YEAR + 1):
        out.append((f"{year}H1", dt.date(year, 1, 1)))
        if year < PERIOD_END_YEAR:
            out.append((f"{year}H2", dt.date(year, 7, 1)))
    return out


def fmt_mw(mw: float) -> str:
    return f"{mw / 1000:.1f} GW" if mw >= 1000 else f"{mw:.0f} MW"


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def in_state(hit: dict, state: str | None) -> bool:
    """Does a Nominatim hit sit in the state the address claims?"""
    if not state:
        return True
    name = next((n for n, abbr in US_STATES.items() if abbr == state), None)
    display = hit.get("display_name", "")
    if not name or not display:
        return True
    return bool(re.search(rf"\b{re.escape(name)}\b", display, re.IGNORECASE))


def load_cache() -> dict:
    if GEOCODE_CACHE.exists():
        return json.loads(GEOCODE_CACHE.read_text())
    return {}


def save_cache(cache: dict) -> None:
    GEOCODE_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")


def geocode(query: str, cache: dict, stats: dict) -> dict | None:
    """Look a query up in the cache, falling back to one Nominatim request."""
    if query in cache:
        stats["cached"] += 1
        return cache[query]

    params = urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"}
    )
    request = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            results = json.loads(response.read())
    except Exception as exc:  # noqa: BLE001 - network failure is reported, not raised
        print(f"  ! geocode failed for {query!r}: {exc}", file=sys.stderr)
        stats["failed"] += 1
        return None
    finally:
        time.sleep(NOMINATIM_DELAY_S)

    stats["fetched"] += 1
    if not results:
        print(f"  ! no match for {query!r}", file=sys.stderr)
        cache[query] = None
        return None

    hit = results[0]
    cache[query] = {
        "lat": round(float(hit["lat"]), 6),
        "lon": round(float(hit["lon"]), 6),
        "display_name": hit.get("display_name", ""),
        "osm_type": hit.get("osm_type", ""),
        "addresstype": hit.get("addresstype", ""),
    }
    return cache[query]


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def read_us_sites() -> list[dict]:
    with SITES_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [r for r in rows if r["Country"].strip() == COUNTRY]


def read_timelines(names: set[str]) -> dict[str, list[tuple[dt.date, float, float]]]:
    """(date, IT power MW, buildings operational) per site, oldest first."""
    series: dict[str, list] = defaultdict(list)
    with TIMELINES_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = row["Data center"].strip()
            if name not in names:
                continue
            try:
                date = dt.date.fromisoformat(row["Date"].strip())
            except ValueError:
                continue
            series[name].append(
                (
                    date,
                    to_float(row["IT power (MW)"]),
                    to_float(row["Buildings operational"]),
                )
            )
    for name in series:
        series[name].sort(key=lambda item: item[0])
    return series


def value_asof(rows: list[tuple[dt.date, float, float]], when: dt.date) -> float:
    """IT power carried forward from the most recent row at or before `when`."""
    current = 0.0
    for date, it_mw, _buildings in rows:
        if date > when:
            break
        current = it_mw
    return current


def first_operational(rows: list[tuple[dt.date, float, float]]) -> str | None:
    for date, _it_mw, buildings in rows:
        if buildings > 0:
            return date.isoformat()
    return None


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(refresh: bool) -> dict:
    rows = read_us_sites()
    names = {r["Name"].strip() for r in rows}
    timelines = read_timelines(names)
    periods = period_labels()

    cache = load_cache()
    if refresh:
        cache = {k: v for k, v in cache.items() if v is not None}
    stats = {"cached": 0, "fetched": 0, "failed": 0}

    sites = []
    manual_log = []
    rejected: list[tuple[str, str, str | None, str]] = []

    for row in rows:
        name = row["Name"].strip()
        owner, owner_conf = strip_tag(row["Owner"])
        users = split_users(row["Users"])
        address = (row["Address"] or "").replace("\xa0", " ").strip()

        manual = MANUAL_LOCATIONS.get(name)
        fix = ADDRESS_FIXES.get(name)
        located = None
        query = None
        precision = None

        if manual:
            query, precision = manual["query"], manual["precision"]
            located = geocode(query, cache, stats)
            state = manual["state"]
        else:
            lookup_address = fix["address"] if fix else address
            state = parse_state(lookup_address)
            for candidate, candidate_precision in geocode_queries(lookup_address):
                hit = geocode(candidate, cache, stats)
                # A hit in the wrong state means the query matched something
                # else entirely, so keep going down the chain rather than
                # publishing a pin a thousand miles from the site.
                if hit and not in_state(hit, state):
                    print(f"  ~ {name}: {candidate!r} resolved outside "
                          f"{state}, trying a coarser lookup", file=sys.stderr)
                    rejected.append((name, candidate, state,
                                     hit.get("display_name", "")))
                    continue
                if hit:
                    located = hit
                    query, precision = candidate, candidate_precision
                    break
            if not located:
                query, precision = lookup_address or None, None

        if manual or fix:
            manual_log.append(
                {
                    "name": name,
                    "city": manual["city"] if manual else parse_city(fix["address"]),
                    "state": state,
                    "query": query,
                    "lat": located["lat"] if located else None,
                    "lon": located["lon"] if located else None,
                    "precision": precision,
                    "source": (manual or fix)["source"],
                    "original_address": address or "(blank)",
                }
            )

        rows_for_site = timelines.get(name, [])
        it_by_period = {
            label: round(value_asof(rows_for_site, when), 1)
            for label, when in periods
        }

        sites.append(
            {
                "name": name,
                # Epoch leaves Owner blank where the operator is a colocation
                # provider rather than the compute's owner.
                "owner": owner or "Colocation",
                "owner_confidence": owner_conf,
                "owner_disclosed": bool(owner),
                "users": ", ".join(u["name"] for u in users) or "Undisclosed",
                "users_detail": users,
                "users_disclosed": bool(users),
                "state": state,
                "lat": located["lat"] if located else None,
                "lon": located["lon"] if located else None,
                "geocode_precision": precision if located else None,
                "geocode_query": query or None,
                "geocode_match": located["display_name"] if located else None,
                "address": address or None,
                "project": strip_tag(row["Project"])[0] or None,
                "project_confidence": strip_tag(row["Project"])[1],
                "first_operational": first_operational(rows_for_site),
                "it_mw_by_period": it_by_period,
                "it_mw_as_of": round(value_asof(rows_for_site, AS_OF), 1),
                "it_mw_2030h1": it_by_period["2030H1"],
            }
        )

    save_cache(cache)
    sites.sort(key=lambda s: (-s["it_mw_as_of"], s["name"]))

    payload = {
        "meta": {
            "generated_by": "ai-compute-datacenter-economics/datacenter/build_sites.py",
            "source": "Epoch AI, 'AI data centers', https://epoch.ai/data/ai-data-centers",
            "license": "CC-BY 4.0",
            "geocoder": "Nominatim / OpenStreetMap (ODbL)",
            "country": COUNTRY,
            "as_of": AS_OF.isoformat(),
            "periods": [label for label, _ in periods],
            "site_count": len(sites),
        },
        "sites": sites,
    }
    payload["_manual_log"] = manual_log
    payload["_rejected"] = rejected
    payload["_geocode_stats"] = stats
    return payload


# ---------------------------------------------------------------------------
# QA
# ---------------------------------------------------------------------------

def totals(sites: list[dict], key: str) -> tuple[float, int]:
    total = sum(s[key] for s in sites)
    live = sum(1 for s in sites if s[key] > 0)
    return total, live


def period_totals(sites: list[dict], label: str) -> tuple[float, int]:
    values = [s["it_mw_by_period"][label] for s in sites]
    return sum(values), sum(1 for v in values if v > 0)


def report(payload: dict) -> bool:
    sites = payload["sites"]
    manual_log = payload["_manual_log"]
    stats = payload["_geocode_stats"]
    rejected = payload["_rejected"]
    ok = True

    print(f"\nUS sites: {len(sites)}  (expected 77)")
    if len(sites) != 77:
        print("  FAIL: site count")
        ok = False
    print(f"Geocode: {stats['cached']} cached, {stats['fetched']} fetched, "
          f"{stats['failed']} failed")

    print("\n=== QA: US IT power and live sites ===")
    print(f"{'Period':<12}{'IT power':>12}{'Sites':>8}   {'Expected':>12}{'Sites':>8}  Check")
    for label, want_mw, want_sites in EXPECTED_QA:
        if label == "as_of":
            got_mw, got_sites = totals(sites, "it_mw_as_of")
            shown = AS_OF.isoformat()
        else:
            got_mw, got_sites = period_totals(sites, label)
            shown = label
        mw_ok = abs(got_mw - want_mw) <= QA_TOLERANCE_MW
        site_ok = got_sites == want_sites
        if not (mw_ok and site_ok):
            ok = False
        print(f"{shown:<12}{fmt_mw(got_mw):>12}{got_sites:>8}   "
              f"{fmt_mw(want_mw):>12}{want_sites:>8}  "
              f"{'PASS' if mw_ok and site_ok else 'FAIL'}")

    print("\n=== Full half-year series (US total) ===")
    for label in payload["meta"]["periods"]:
        total, live = period_totals(sites, label)
        print(f"  {label:<8}{fmt_mw(total):>10}{live:>6} sites")

    print(f"\n=== IT MW by owner: today ({AS_OF}) vs 2030H1 ===")
    by_owner: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0])
    for site in sites:
        entry = by_owner[site["owner"]]
        entry[0] += site["it_mw_as_of"]
        entry[1] += site["it_mw_2030h1"]
        entry[2] += 1
    print(f"{'Owner':<28}{'Today':>12}{'2030H1':>12}{'Sites':>7}")
    for owner, (today, future, count) in sorted(
        by_owner.items(), key=lambda kv: -kv[1][1]
    ):
        print(f"{owner:<28}{fmt_mw(today):>12}{fmt_mw(future):>12}{count:>7}")
    today_total, _ = totals(sites, "it_mw_as_of")
    future_total, _ = totals(sites, "it_mw_2030h1")
    print(f"{'TOTAL':<28}{fmt_mw(today_total):>12}{fmt_mw(future_total):>12}"
          f"{len(sites):>7}")

    print("\n=== Geocode precision ===")
    precisions: dict[str, int] = defaultdict(int)
    for site in sites:
        precisions[site["geocode_precision"] or "unresolved"] += 1
    for level in ("address", "postcode", "city", "county", "unresolved"):
        if precisions.get(level):
            print(f"  {level:<12}{precisions[level]:>4} sites")

    print(f"\n=== Manual coordinates ({len(manual_log)}) ===")
    for entry in sorted(manual_log, key=lambda e: e["name"]):
        coords = (f"{entry['lat']}, {entry['lon']}"
                  if entry["lat"] is not None else "UNRESOLVED")
        print(f"  {entry['name']}")
        print(f"    place     : {entry['city']}, {entry['state']} "
              f"({entry['precision']} level)")
        print(f"    coords    : {coords}")
        print(f"    epoch addr: {entry['original_address']}")
        print(f"    resolved  : {entry['query']}")
        print(f"    source    : {entry['source']}")

    print(f"\n=== Geocode hits rejected for landing in the wrong state "
          f"({len(rejected)}) ===")
    if not rejected:
        print("  none")
    for name, candidate, state, display in rejected:
        print(f"  {name}")
        print(f"    query  : {candidate}   (expected {state})")
        print(f"    got    : {display[:100]}")

    coarse = [s for s in sites
              if s["geocode_precision"] in ("postcode", "city", "county")
              and s["name"] not in MANUAL_LOCATIONS
              and s["name"] not in ADDRESS_FIXES]
    print(f"\n=== Addressed sites that fell back to a centroid ({len(coarse)}) ===")
    if not coarse:
        print("  none")
    for site in coarse:
        print(f"  {site['name']:<34}{site['geocode_precision']:<10}"
              f"{site['geocode_query']}")

    missing = [s["name"] for s in sites if s["lat"] is None or s["lon"] is None]
    print(f"\n=== Sites missing coordinates ({len(missing)}) ===")
    if missing:
        for name in missing:
            print(f"  {name}")
        ok = False
    else:
        print("  none")

    no_state = [s["name"] for s in sites if not s["state"]]
    print(f"\n=== Sites missing state ({len(no_state)}) ===")
    print("  none" if not no_state else "\n".join(f"  {n}" for n in no_state))
    if no_state:
        ok = False

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-geocode", action="store_true",
        help="retry addresses whose cached lookup previously found nothing",
    )
    args = parser.parse_args()

    payload = build(refresh=args.refresh_geocode)
    ok = report(payload)

    out = {"meta": payload["meta"], "sites": payload["sites"]}
    OUT_JSON.write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nWrote {OUT_JSON.relative_to(HERE.parent.parent)} "
          f"({OUT_JSON.stat().st_size / 1024:.0f} KB)")
    print(f"Wrote {GEOCODE_CACHE.relative_to(HERE.parent.parent)}")

    print("\nALL CHECKS PASSED" if ok else "\nCHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
