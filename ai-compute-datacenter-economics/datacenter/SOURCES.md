# Sources

Every number on the Data Center page comes from one of these. All but the last
are fetched by a script in this folder and cached under `data/`, so a rerun is
offline and deterministic.

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

## Orange County electricity consumption

California Energy Commission, Electricity Consumption Dashboards.
<https://www.energy.ca.gov> Public domain. Retrieved 2026-10-27.

Orange County consumed 19,225 GWh in a year. Over 8,760 hours that is a 2.2 GW
average load, so 1 GW is a little under half the county. The page states the
figure as "1 GW is about half of Orange County's electricity use"; the
arithmetic is on the page's own sources line. This is the only number on the
page that is not from Epoch AI or the EIA, and nothing is computed from it --
it is there to give a gigawatt a size a reader already holds.

## Metro areas, for the Where view

US Census Bureau, public domain. Retrieved 2026-10-27. Both files are also
recorded, with the columns used, in `data/sources.json`.

- Population Estimates Program, metropolitan and micropolitan statistical area
  totals, vintage 2025 —
  <https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/metro/totals/cbsa-est2025-alldata.csv>
  The `POPESTIMATE2025` column of the CBSA total rows decides which metros
  clear a million people: 387 metropolitan statistical areas, 56 of them at a
  million or more.
- 2025 Gazetteer, core based statistical areas —
  <https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_cbsa_national.zip>
  `INTPTLAT` and `INTPTLONG` give each metro's internal point, which is the
  location distances are measured to.

Built by `build_metros.py` into `data/metros.json`: the 56 metros, each site's
nearest one, the great-circle distance in miles, and the median per start-year
group. The distance is to the metro as a whole rather than to its downtown,
because an internal point sits inside the whole CBSA; a metro that spans six
counties is therefore "nearer" from the side it sprawls towards.

## The land comparison under the number

Not from a dataset, and recorded in full in `data/sources.json`:

- Orange County, California, 792.84 sq mi of land, US Census Bureau
  QuickFacts, <https://www.census.gov/quickfacts>, retrieved 2026-10-27. The
  2025 county Gazetteer file gives 793.249 sq mi, a 0.05% difference.
- About 2.2 GW of average load, from the California Energy Commission figure
  above.
- The Cumulus campus next to the Susquehanna plant in Luzerne County,
  Pennsylvania: about 1,200 acres, up to 960 MW planned. Power Engineering,
  "AWS acquires data center campus connected to Susquehanna nuclear station",
  2024-03-06,
  <https://www.power-eng.com/nuclear/aws-acquires-data-center-campus-connected-to-susquehanna-nuclear-station/>,
  also reported by the American Nuclear Society's Nuclear Newswire,
  2024-03-07.

1,200 acres is 1.875 sq mi, so 960 MW is about 512 MW per sq mi against Orange
County's 2.8, which is the "about 180x" on the page. It is a planned peak
against an average load, so the two are not like for like: the claim is about
what the land is being built to draw, not what it draws today.

## Time to power

JLL, "2026 Global Data Center Outlook". The US national average wait for a grid
connection is about four years. <https://www.jll.com> Retrieved 2026-10-27.

The figure is quoted from Electrical Contractor Magazine, "How Long Does It
Take to Power a Data Center?",
<https://www.ecmag.com/magazine/articles/article-detail/how-long-does-it-take-to-power-a-data-center>,
which states it as "the national average wait time is four years, according to
the 2026 JLL Global Data Center Outlook". It was asked for as cited by EC&M;
EC&M (Electrical Construction & Maintenance, ecmweb.com) is a different title,
and no page of theirs stating the figure was found, so the magazine that does
state it is the one cited here. There is no verified deep link to the JLL
report itself.

It is the third of the three bars under the Why there headline. The other two
are Epoch's own dates, from a site's first dated observation to its first
operational date: xAI Colossus 1 took 109 days, shown as 4 months, and
Anthropic-Amazon New Carlisle took 500 days, shown as 16 months.

The three are not one stopwatch. JLL measures from the interconnection request
to the day the utility can deliver the contracted megawatts; Epoch's dates
measure a build. What the bars share is the question, not the clock, and
`data/sources.json` says so beside the figures.
