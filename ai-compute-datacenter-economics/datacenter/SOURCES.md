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

## Orange County's land area

Orange County, California, 792.84 sq mi of land, US Census Bureau QuickFacts,
<https://www.census.gov/quickfacts>, retrieved 2026-10-27. The 2025 county
Gazetteer file gives 793.249 sq mi, a 0.05% difference.

This was the land behind a "same land, about 180x the power" comparison with
the AWS Cumulus campus. That line is no longer on the page, and neither is the
footer clause that carried its arithmetic, so the Cumulus entry has been
removed from `data/sources.json` with it. The land area is kept here, and in
that file, as the counterpart to the Orange County load figure above, which is
still what "1 GW is about half of Orange County" rests on.

## Two lines the Where view ends on

Step 5 names one site: "Amazon New Carlisle: 16 months from start to first
building live, vs about 4 years average grid wait". The 16 months is Epoch's
own dates for that site, 2024-02-09 to 2025-06-23, which is 500 days; the four
years is the JLL figure above. The same caveat applies: one is a build, the
other is a national average queue, so the line compares orders of magnitude
rather than two measurements of one thing.

A 2025-and-later site's card adds: "This group splits in two: seven sites
within 53 mi, seven beyond 161 mi." Computed from `data/metros.json`: of the 14
sites in that group, 7 sit 12.2 to 52.5 mi from their nearest metro of a
million or more and 7 sit 161.0 to 288.7 mi, with nothing in between, so the
group's 107 mi median falls in an empty gap. That is why a site in that group
carries the line and the others do not.

## Time to power

JLL, "2026 Global Data Center Outlook". The US national average wait for a grid
connection is about four years, and building the data center itself takes 18 to
24 months in most US markets. <https://www.jll.com> Retrieved 2026-10-27.

Both figures are quoted from Electrical Contractor Magazine, "How Long Does It
Take to Power a Data Center?",
<https://www.ecmag.com/magazine/articles/article-detail/how-long-does-it-take-to-power-a-data-center>,
which states the first as "the national average wait time is four years,
according to the 2026 JLL Global Data Center Outlook". The same article is the
source for large power transformers taking two to four years from most
manufacturers.

They were asked for as cited by EC&M. The article carrying them is in
Electrical Contractor Magazine (ecmag.com), a different title from EC&M /
Electrical Construction & Maintenance (ecmweb.com); no ecmweb.com page stating
them was found, so the magazine that does state them is the one cited here.
There is no verified deep link to the JLL report itself.

On the page they are the two numbers on the Why there headline view, rounded to
whole years: "2 yrs" captioned "Build the data center" and "4 yrs" captioned
"Wait for grid power (US average)". The transformer figure is the second line of
the card behind the second number.

Two notes on reading them. The two clocks overlap rather than running end to
end: one is construction, the other is measured from the developer's
interconnection request to the day the utility can deliver the contracted
megawatts. And other outlets put large transformers higher, commonly three to
five years, with Wood Mackenzie's survey averaging 128 weeks for power
transformers and 143 for generator step-up units; the page quotes the lower,
more widely reported range.

`data/sources.json` carries the same entries, with the arithmetic and these
caveats beside the figures.

## Make your own power, and the last step of Connect to the Grid

Step 6, the last of Connect to the Grid, compares two sites on Epoch's own clock, first
dated observation to first operational: Amazon New Carlisle, 2024-02-09 to
2025-06-23, 500 days, shown as 16 months; Google Council Bluffs East,
2022-09-06 to 2024-11-19, 805 days, shown as 26 months. Unlike the earlier
steps this one compares like with like. What the dates cannot carry is why.

The Make Your Own Power view rests on the same Epoch dates for its two
finished examples, and on four outside sources for what is behind them. Each
card carries its own numbered citations; the full entries, with the caveats
below, are in `data/sources.json`.

- **Colossus 1, temporary turbines.** Action News 5, "xAI begins removal of
  temporary gas turbines", 2025-05-06,
  <https://www.actionnews5.com/2025/05/06/xai-begins-removal-temporary-gas-turbines>,
  with Cleanview's Colossus report,
  <https://cleanview.co/reports/behind-the-meter-data-centers/full-report/colossus>.
  Simplified on the card: the site also ran on Tesla Megapacks and some MLGW
  supply, and the first substation came online in spring 2025, after the four
  months Epoch's dates cover.
- **Stargate Abilene, substation and gas.** Epoch AI's directory page,
  <https://epoch.ai/data/ai-data-centers/directory/openai-stargate-abilene>,
  for the 200 MW substation built in 2022 and expanded in 2024; Cleanview's
  Stargate Abilene report,
  <https://cleanview.co/reports/behind-the-meter-data-centers/full-report/stargate-abilene>,
  for the on-site gas and the December 2024 turbine order. Turbine counts
  differ by source (5 installed, 10 permitted, 29 reported ordered) and Crusoe
  has said they are for backup; the card claims the order date and the
  existence of on-site gas, not a count or a duty cycle.
- **Haskell County, Google and Intersect.** Cleary Gottlieb, "Alphabet
  Completes $4.75 Billion Acquisition of Intersect Power", 2026-03-12,
  <https://www.clearygottlieb.com/news-and-insights/news-listing/alphabet-completes-4-75-billion-acquisition-of-intersect-power>.
  The marker sits at the county's own internal point from the 2025 county
  Gazetteer file (GEOID 48207, 33.175964, -99.730774), not at the site, which
  is why the card says the location is shown at county level.
- **A turbine ordered today.** GE Vernova's Q2 2026 earnings call transcript,
  2026-07-22,
  <https://www.gevernova.com/sites/default/files/gev_webcast_transcript_07222026.pdf>.
  The company gave slot availability, not a delivery date: mostly sold out
  through 2030, with more than half of 2031's 30 GW expected under contract by
  the end of 2026. "Arrives around 2031" follows from that rather than being
  quoted, and the page says "around" for that reason.

The three examples are not the same kind of thing: two are finished builds
with their own power on site, the third is a company purchase whose site is
still under construction. The view says so by giving the third no bar.
