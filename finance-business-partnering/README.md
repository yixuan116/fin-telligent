# Finance Business Partnering

A story bank that maps career stories to the business finance needs they solve.

Live: https://yixuan116.github.io/fin-telligent/finance-business-partnering/

Selecting a story lights up the needs it covers. Selecting a need lights up the
stories that cover it. Primary coverage is solid, secondary coverage is outlined,
and everything else fades back.

## Running locally

The page reads its content with `fetch`, which browsers block on `file://`, so
opening `index.html` by double clicking it shows a load notice instead of the
story wall. Serve the repo over HTTP:

```bash
cd /path/to/fin-telligent
python3 -m http.server 8000
```

Then open http://localhost:8000/finance-business-partnering/

## Content

No build step. Plain HTML, CSS and JS in `index.html`, with all content in YAML
parsed in the browser by [js-yaml](https://github.com/nodeca/js-yaml) from a CDN.

| File | In git | Role |
| --- | --- | --- |
| `data/public.yaml` | yes | Needs taxonomy, counterparty enum, company order, and the public fields of every story. This is what the published page shows. |
| `data/private.yaml` | no, gitignored | Local only overlay. Adds the private fields and can also fill public fields left as `TODO`. |
| `data/private.example.yaml` | yes | Template for the above, with one story filled in. |

To start a private overlay:

```bash
cp data/private.example.yaml data/private.yaml
```

The overlay matches on story `id` and merges field by field, so an entry only
needs the `id` plus whatever it wants to override. When `private.yaml` is absent
or fails to parse, which is every visit to the published site, the page runs on
public data alone and says nothing about it.

### Needs taxonomy

Two tracks. Spend is grouped by lifecycle stage, Earn is flat. Render order is
the order written in `public.yaml`.

- **Spend / Plan**: Budget Setting, Incremental Ask
- **Spend / Execute**: Contract Structuring, Annual Cost-Down, Peak Ad Hoc Approval
- **Spend / Control**: Overrun Control
- **Spend / Impact**: Spend Impact Visibility, ROI
- **Earn**: Dynamic Pricing, Revenue Sharing

### Story fields

Public, in `public.yaml`: `id`, `company`, `title_en`, `hook`,
`goal_and_need`, `model_and_analysis`, `result`, `needs_primary[]`,
`needs_secondary[]`, `counterparty`.

Private, in `private.yaml`: `chat_url`, `interviewer_slot`, `notes`,
`absolute_figures`, and the optional `title_zh`.

`private.yaml` can also carry a top level `labels:` map, alternative wording
for the fixed taxonomy keyed by need id and counterparty id.

Two notes on what reaches the screen:

- The page is English, and so is everything committed here. `title_zh` and the
  `labels:` map are read onto the data but never rendered; they are reference
  fields for your local file, which is why the template leaves them commented
  out.
- With the overlay loaded the drawer runs Goal and Need, Model and Analysis,
  Result, then Figures (`absolute_figures`), Chat (`chat_url`), Interviewer
  Slot and Notes. Figures onward sits under a Private overlay marker, so
  nothing private reads as part of the public write up.

Adding a story means appending an entry to `stories:` in `public.yaml`. Adding a
company means adding it to `companies:`, which is also the wall order; a story
naming a company that is not in that list still gets a group, appended last.
