# fin-telligent

Self-contained finance-analytics demos published as static pages on GitHub Pages
(`https://yixuan116.github.io/fin-telligent/<demo>/`). Each demo owns its folder
and is a single `index.html` with its HTML, CSS and JS inline; no build step.

- `ai-compute-datacenter-economics/` — AI Model Shopping Cart, part 1 of the AI / Compute / Data Center series; see its own `CLAUDE.md`. Holds `compute/` (part 2) and `datacenter/` (part 3) as separate demos.
- `ai-compute-datacenter-economics/datacenter/data/` — the Data Center demo's own data: Epoch AI's CC-BY CSVs plus the `sites.json`, `state_prices.json` (EIA), `metros.json` (Census) and `us_states.geojson` its three `build_*.py` scripts generate, with every source listed in the demo's `SOURCES.md` and in `data/sources.json`. Those scripts resolve paths from their own file, so they run from anywhere; the raw Epoch download in `Data Center demo/` is gitignored and must not be published.
- `price-volume-mix-waterfall/` — price / volume / mix bridge.
- `consumer-hardware-finance/` — consumer hardware build- and sell-side indicators.
- `hardware-build-to-sell/` — hardware build-to-sell indicators.
- `retail-expansion-analytics/` — retail store expansion analysis.
- `finance-business-partnering/` — business partnering story bank; loads `data/public.yaml` plus an optional gitignored `data/private.yaml`, so it needs a local server rather than `file://`.
- `pii-redaction/` — PII redaction benchmark scatter, cost or speed against leak rate. Everything on screen comes from its own `data.json`, which it fetches, so it needs a local server rather than `file://`; the page edits that config and copies it back out, so a new run is a data change rather than a code change.
- `scripts/` + `data/` — the daily Nimble price refresh feeding the Shopping Cart; run from the repo root.

The repo is English only, templates included.

## Browser testing

Never drive the user's own Chrome profile, and never use the Claude in Chrome
extension against it. It carries their live sessions and site storage: opening a
test login there replaces the cookie for the real one and signs them out, and
the page's `localStorage` is shared with whatever account is signed in.

Test in an isolated profile instead: headless Chrome with its own
`--user-data-dir` under the session scratchpad, driven over the DevTools
protocol (`scripts/cdp.mjs` in `personal-agent/` does this for the agent app).
Delete the profile directory when the run is over.

## Data safety (personal-agent)

Never delete, overwrite or lose anything the user or Alex has entered: events,
daily values, check-ins, photos, canvas content, settings. Every schema or UI
change must:

1. back up all user rows before deploying;
2. migrate non-destructively, so data written by the old version still renders;
3. after deploying, verify the row counts against the backup and report them.

Delete user data only when the user explicitly asks for a specific item.
