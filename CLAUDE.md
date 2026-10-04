# fin-telligent

A series of self-contained finance-analytics demos published as static pages on
GitHub Pages (`https://yixuan116.github.io/fin-telligent/<demo>/`). Each demo is
one folder holding a single `index.html` with all its HTML, CSS and JS inline;
there is no bundler and no build step for the pages themselves.

## AI Model Shopping Cart

The flagship demo. It lives in `ai-compute-datacenter-economics/`, not at the
repo root, and it is part 1/3 of the AI / Compute / Data Center series.

It frames LLM API pricing as a grocery run: you fill a cart of models, the page
re-prices that same cart against current listings, and the difference is booked
through a P&L so the reader sees token-price deflation as a cost variance rather
than a chart.

Moving parts:

- `ai-compute-datacenter-economics/index.html` — the whole demo. It `fetch`es
  its CSVs by **bare relative name** (`models.csv`, `pricing_history.csv`,
  `performance_benchmarks.csv`, `cost_efficiency.csv`,
  `llm_price_performance_tracker_2026-03-31.csv`), all siblings in the same
  folder. The same names are reused as download `href`s in the raw-data cards,
  so a rename has to be made in both places.
- `scripts/nimble-price-check.ts` — scrapes current listings through Nimble and
  writes `data/nimble_latest_<as_of>.csv`.
- `scripts/embed-latest.ts` — reads the newest `data/nimble_latest_*.csv` and
  rewrites the `NEWCART_RAW` table and `NEWCART_AS_OF` date inside
  `ai-compute-datacenter-economics/index.html`.
- `.github/workflows/nimble-daily.yml` — runs both scripts daily at 06:20 UTC
  and commits only when prices actually moved. Needs the `NIMBLE_API_KEY`
  repository secret.

Both scripts resolve paths from `process.cwd()`, so npm scripts
(`npm run nimble:refresh`) must be run from the repo root.

`ai-compute-datacenter-economics/dashboard/` holds pre-computed JSON built by
the `data_prep*.py` scripts. Those scripts still carry **hardcoded absolute
paths** under `/Users/yixuan/fin-telligent/...` and read from the untracked
`LLM API Pricing & Performance Benchmark Tracker/` folder, so they only run on
the original machine.

## Other demos

Each is independent and owns its folder: `price-volume-mix-waterfall/`,
`consumer-hardware-finance/`, `hardware-build-to-sell/`,
`retail-expansion-analytics/`, `finance-business-partnering/`.

`finance-business-partnering/` is the one demo that loads external content:
`data/public.yaml` (tracked) plus an optional `data/private.yaml` overlay that
is gitignored. Because it uses `fetch`, it needs a local server rather than
`file://`.

## compute/ and datacenter/

`compute/` and `datacenter/` are **separate demos** — parts 2/3 and 3/3 of the
AI / Compute / Data Center series. They are not part of the AI Model Shopping
Cart and do not share its data files or scripts. Each has its own `CLAUDE.md`.
Work on one demo should not reach into another.

## Conventions

- The repo is English only, templates included.
- Cross-demo links are relative (`../<demo>/`); the shared LinkedIn QR image is
  referenced as `../price-volume-mix-waterfall/Pictures/Linkedin.JPG`.
- Third-party libraries (Chart.js, PapaParse, js-yaml, Plotly, qrcode-generator)
  load from cdnjs; fonts from Google Fonts. Nothing is vendored.
