# Sources

Every number on the Data Center page comes from one of these. Each is fetched
by a script in this folder and cached under `data/`, so a rerun is offline and
deterministic.

## Data center sites, power and timelines

Epoch AI, "AI data centers". <https://epoch.ai/data/ai-data-centers>
Licensed CC-BY 4.0; the citation is in `data/EPOCH_LICENSE.md`.
Retrieved 2026-10-26.

- `data/data_centers.csv` — one row per site: owner, users, address, project.
- `data/data_center_timelines.csv` — dated observations per site. The first
  dated row is the site's start date (usually land clearing); IT power is
  carried forward from the most recent row at or before each half-year.
- `data/data_center_chillers.csv` — chiller models, behind the rule of thumb in
  the "How we know" panel.

Built by `build_sites.py` into `data/sites.json` and `data/chiller_rule.json`.

## Electricity prices and sales by state

US Energy Information Administration, Electricity Data Browser.
Annual, by state, retrieved 2026-10-26. Public domain.

The browser's own JSON endpoint is used, with `topic` selecting the measure
and `endsec` the sector (`2` industrial, `4` commercial):

- Average retail price of electricity, industrial, cents per kWh —
  <https://www.eia.gov/electricity/data/browser/data/index.php?method=getAggregateData&topic=7&agg=1,0&geo=vvvvvvvvvvvvo&endsec=2&ids=&freq=A&rtype=s>
- Average retail price of electricity, commercial, cents per kWh —
  <https://www.eia.gov/electricity/data/browser/data/index.php?method=getAggregateData&topic=7&agg=1,0&geo=vvvvvvvvvvvvo&endsec=4&ids=&freq=A&rtype=s>
- Retail sales of electricity, industrial, million kWh —
  <https://www.eia.gov/electricity/data/browser/data/index.php?method=getAggregateData&topic=5&agg=1,0&geo=vvvvvvvvvvvvo&endsec=2&ids=&freq=A&rtype=s>

Built by `build_sites.py` into `data/state_prices.json`, years 2018 to 2025.
Seven values are spot-checked against the browser on every run and the build
stops rather than publish numbers nobody checked. The sales table is never
shown on the page; it is the denominator of the baseline the QA output prints.

## Geocoding

Nominatim / OpenStreetMap, ODbL. <https://nominatim.openstreetmap.org/>
Responses are committed in `data/geocode_cache.json` so a rerun makes no
network calls. Coordinates carry a `geocode_precision` of address, postcode,
city or county, and the page says so on the card when a pin is a centroid.

## State outlines

us-atlas 3.0.1, `states-10m.json`, public domain, derived from US Census
Bureau cartographic boundary files. <https://github.com/topojson/us-atlas>
Built by `build_states.py` into `data/us_states.geojson` (the 48 contiguous
states plus DC) and `data/us_mask.geojson`.

## Basemap

CARTO `dark-matter-nolabels`, token-free, over OpenStreetMap data.
<https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json>
