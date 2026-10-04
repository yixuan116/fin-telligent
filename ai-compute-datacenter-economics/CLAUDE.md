# AI / Compute / Data Center series

Three demos. Part 1, the AI Model Shopping Cart, is this folder itself. Parts 2
and 3 live in the `compute/` and `datacenter/` subfolders and are separate
demos — they do not share this demo's data files or scripts, and each has its
own `CLAUDE.md`.

## AI Model Shopping Cart (part 1)

It frames LLM API pricing as a grocery run: you fill a cart of models, the page
re-prices that same cart against current listings, and the difference is booked
through a P&L so the reader sees token-price deflation as a cost variance rather
than a chart.

Moving parts:

- `index.html` — the whole demo, one file, all HTML/CSS/JS inline. It `fetch`es
  its CSVs by **bare relative name** (`models.csv`, `pricing_history.csv`,
  `performance_benchmarks.csv`, `cost_efficiency.csv`,
  `llm_price_performance_tracker_2026-03-31.csv`), all siblings in this folder.
  The same names are reused as download `href`s in the raw-data cards, so a
  rename has to be made in both places.
- `../scripts/nimble-price-check.ts` — scrapes current listings through Nimble
  and writes `../data/nimble_latest_<as_of>.csv`.
- `../scripts/embed-latest.ts` — reads the newest `../data/nimble_latest_*.csv`
  and rewrites the `NEWCART_RAW` table and `NEWCART_AS_OF` date inside this
  folder's `index.html`.
- `../.github/workflows/nimble-daily.yml` — runs both scripts daily at 06:20 UTC
  and commits only when prices actually moved. Needs the `NIMBLE_API_KEY`
  repository secret.

Both scripts resolve paths from `process.cwd()`, so npm scripts
(`npm run nimble:refresh`) must be run from the **repo root**, not from here.

`dashboard/` holds pre-computed JSON built by the `data_prep*.py` scripts. Those
scripts still carry **hardcoded absolute paths** under
`/Users/yixuan/fin-telligent/...` and read from the untracked
`LLM API Pricing & Performance Benchmark Tracker/` folder, so they only run on
the original machine.

Published at https://yixuan116.github.io/fin-telligent/ai-compute-datacenter-economics/

## Conventions

- English only, templates included.
- The shared LinkedIn QR image is referenced as
  `../price-volume-mix-waterfall/Pictures/Linkedin.JPG`.
- Third-party libraries (Chart.js, PapaParse, Plotly, qrcode-generator) load
  from cdnjs. Nothing is vendored.
