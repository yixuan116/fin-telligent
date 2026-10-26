This folder is for the Data Center demo, part 3/3 of the AI / Compute / Data Center series. The AI Model Shopping Cart (part 1) lives in the parent folder ai-compute-datacenter-economics/; do not modify it from here.

## Data (step 1, no page yet)

`build_sites.py` turns Epoch AI's "AI data centers" dataset into
`data/sites.json`, the US-only site list the map will read. Run it from
anywhere; paths resolve from the script file, not from `cwd`:

    python3 ai-compute-datacenter-economics/datacenter/build_sites.py

- `data/data_centers.csv`, `data/data_center_timelines.csv` — copied from the
  Epoch download. CC-BY 4.0, cited in `data/EPOCH_LICENSE.md`.
- `data/sites.json` — 77 US sites: name, owner, users, state, lat/lon, the
  half-year IT-power series 2021H1 to 2030H1, and first operational date.
- `data/geocode_cache.json` — Nominatim responses, committed so a rerun is
  deterministic and makes no network calls. Delete it to re-geocode.

Two things the script will not do silently: a geocode hit that lands outside
the address's own state is rejected and retried at a coarser level, and every
coordinate carries a `geocode_precision` of address, postcode, city or county
so a centroid is never drawn as if it were the building. The script prints a
QA table and exits non-zero if any US total, site count or coordinate is
missing.
