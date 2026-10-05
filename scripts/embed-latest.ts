/**
 * embed-latest — fold the newest Nimble pull into the page.
 *
 *   npx tsx scripts/embed-latest.ts
 *
 * Reads the most recent data/nimble_latest_*.csv and rewrites four things in
 * ai-compute-datacenter-economics/index.html: the NEWCART_RAW table the New
 * Shopping Cart shops from, NEWCART_AS_OF, which every date on the block is
 * rendered from, NEWCART_AS_OF_ISO, which also names the pull the footer link
 * points at, and NEWCART_META, the per-model arrival line the cards print.
 * Nothing else in the file is touched.
 *
 * NEWCART_META comes from data/new_models_since_2026-03-31.csv, written by
 * scripts/new-models-table.ts. Run that first; without it the meta map is
 * emitted empty and the cards simply fall back to the provider alone.
 *
 * Only priced rows are embedded -- a row without both prices, or with an
 * intelligence index missing, can never be a candidate, so carrying it would
 * only inflate the page.
 */
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';

const DATA_DIR = resolve(process.cwd(), 'data');
const PAGE = resolve(process.cwd(), 'ai-compute-datacenter-economics/index.html');
const NEW_MODELS = resolve(DATA_DIR, 'new_models_since_2026-03-31.csv');
/** Models shelved as new arrivals: everything released on or after this date. */
const POOL_FROM = '2026-07-20';
/** Lane -> the verified Artificial Analysis fields behind it. */
const LANE_FIELDS: Record<string, string[]> = {
  Knowledge: ['gpqa'],
  Coding: ['livecodebench', 'scicode'],
  Math: ['aime25'],
  Reasoning: ['hle'],
};

function newestBenchmarkFile(): string | null {
  const files = readdirSync(DATA_DIR).filter((f) => /^aa_benchmarks_.*\.csv$/.test(f)).sort();
  return files.length ? join(DATA_DIR, files[files.length - 1]) : null;
}

/** Minimal RFC-4180 reader: the scrape quotes any cell holding a comma. */
function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') { cell += '"'; i++; } else quoted = false;
      } else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(cell); cell = ''; }
    else if (ch === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; }
    else if (ch !== '\r') cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const header = rows.shift() ?? [];
  return rows.filter((r) => r.length === header.length)
    .map((r) => Object.fromEntries(header.map((h, i) => [h, r[i]])));
}

function newestCsv(): string {
  const files = readdirSync(DATA_DIR).filter((f) => /^nimble_latest_.*\.csv$/.test(f)).sort();
  if (!files.length) throw new Error(`no nimble_latest_*.csv in ${DATA_DIR} -- run the scrape first`);
  return join(DATA_DIR, files[files.length - 1]);
}

function num(v: string): number | null {
  return v === '' || v == null ? null : Number(v);
}

/** "2026-09-25" -> "Sep 25, 2026", the form the block prints. */
function prettyDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}

function main(): void {
  const csvPath = newestCsv();
  const rows = parseCsv(readFileSync(csvPath, 'utf8'));
  console.log(`Reading ${csvPath} (${rows.length} rows)`);

  const round3 = (n: number | null) => (n == null ? null : Math.round(n * 1000) / 1000);
  const usable = rows.filter((r) =>
    num(r.input_cost_usd_per_1m) != null &&
    num(r.output_cost_usd_per_1m) != null &&
    num(r.aa_intelligence_index) != null);

  const table = usable.map((r) => [
    r.model_name, r.provider,
    round3(num(r.aa_intelligence_index)),
    round3(num(r.input_cost_usd_per_1m)),
    round3(num(r.output_cost_usd_per_1m)),
    round3(num(r.time_to_first_token_s)),
  ]);

  const asOfIso = usable[0]?.as_of ?? rows[0]?.as_of ?? '';
  const asOf = prettyDate(asOfIso);
  let page = readFileSync(PAGE, 'utf8');

  const rawBlock = `  var NEWCART_RAW = [\n${table.map((t) => `    ${JSON.stringify(t)}`).join(',\n')}\n  ];`;
  const rawRe = /  var NEWCART_RAW = \[[\s\S]*?\n  \];/;
  if (!rawRe.test(page)) throw new Error('NEWCART_RAW block not found in the page');
  page = page.replace(rawRe, rawBlock);

  const asOfRe = /  var NEWCART_AS_OF = "[^"]*";/;
  if (!asOfRe.test(page)) throw new Error('NEWCART_AS_OF not found in the page');
  page = page.replace(asOfRe, `  var NEWCART_AS_OF = "${asOf}";`);

  // The footer's pull link is built from this at render time, so the link can
  // never name a different pull than the table above it.
  const asOfIsoRe = /  var NEWCART_AS_OF_ISO = "[^"]*";/;
  if (!asOfIsoRe.test(page)) throw new Error('NEWCART_AS_OF_ISO not found in the page');
  page = page.replace(asOfIsoRe, `  var NEWCART_AS_OF_ISO = "${asOfIso}";`);

  // [launch_date, first_seen_in_pull, strong_in] per model. Every value is
  // carried across exactly as the table holds it -- empties stay empty.
  const meta: Record<string, [string, string, string]> = {};
  if (existsSync(NEW_MODELS)) {
    for (const r of parseCsv(readFileSync(NEW_MODELS, 'utf8'))) {
      if (!r.model_name) continue;
      if (!r.launch_date && !r.first_seen_in_pull && !r.strong_in) continue;
      meta[r.model_name] = [r.launch_date ?? '', r.first_seen_in_pull ?? '', r.strong_in ?? ''];
    }
  } else {
    console.warn(`  ${NEW_MODELS} not found -- NEWCART_META emitted empty`);
  }
  const metaBlock = `  var NEWCART_META = {\n${Object.keys(meta).sort()
    .map((k) => `    ${JSON.stringify(k)}: ${JSON.stringify(meta[k])}`).join(',\n')}\n  };`;
  const metaRe = /  var NEWCART_META = \{[\s\S]*?\n  \};/;
  if (!metaRe.test(page)) throw new Error('NEWCART_META block not found in the page');
  page = page.replace(metaRe, metaBlock);

  // The arrival pool: every priced model Artificial Analysis dates on or after
  // POOL_FROM that this pull also lists, carrying the raw benchmark scores the
  // swimlanes are read from. Scores are copied as AA states them; a model with
  // no score for a lane simply has none, and nothing is substituted.
  const benchFile = newestBenchmarkFile();
  let poolRows: any[][] = [];
  let fetchedOn = '';
  if (benchFile) {
    const bench = parseCsv(readFileSync(benchFile, 'utf8'));
    const priced = new Map(rows.map((r) => [r.model_name, r]));
    for (const b of bench) {
      if (!b.release_date || b.release_date < POOL_FROM) continue;
      const p = priced.get(b.model_name);
      if (!p) continue;
      // Priced modes only. A row with no input/output price, or one whose
      // blended cost works out to zero, has no published price at all -- the
      // Cart's own pool reads it the same way -- so it never reaches a card.
      const inUsd = num(p.input_cost_usd_per_1m);
      const outUsd = num(p.output_cost_usd_per_1m);
      if (inUsd == null || outUsd == null) continue;
      if ((3 * inUsd + outUsd) / 4 <= 0) continue;
      fetchedOn = fetchedOn || b.fetched_on || '';
      poolRows.push([
        b.model_name, p.provider, b.release_date,
        round3(num(b.gpqa)), round3(num(b.livecodebench)), round3(num(b.scicode)),
        round3(num(b.aime25)), round3(num(b.hle)),
        round3(num(p.input_cost_usd_per_1m)), round3(num(p.output_cost_usd_per_1m)),
      ]);
    }
    poolRows.sort((a, b) => String(b[2]).localeCompare(String(a[2])));
  } else {
    console.warn('  no aa_benchmarks_*.csv found -- NEWCART_POOL emitted empty');
  }
  const poolBlock = `  var NEWCART_POOL = [\n${poolRows.map((r) => `    ${JSON.stringify(r)}`).join(',\n')}\n  ];`;
  const poolRe = /  var NEWCART_POOL = \[[\s\S]*?\n  \];/;
  if (!poolRe.test(page)) throw new Error('NEWCART_POOL block not found in the page');
  page = page.replace(poolRe, poolBlock);

  const fetchedRe = /  var NEWCART_BENCH_FETCHED = "[^"]*";/;
  if (!fetchedRe.test(page)) throw new Error('NEWCART_BENCH_FETCHED not found in the page');
  page = page.replace(fetchedRe, `  var NEWCART_BENCH_FETCHED = "${fetchedOn}";`);

  writeFileSync(PAGE, page);
  console.log(`Embedded ${table.length} priced models, as of ${asOf} (${asOfIso})`);
  console.log(`Embedded an arrival pool of ${poolRows.length} models released since ${POOL_FROM}`);
  console.log(`Embedded arrival meta for ${Object.keys(meta).length} models`);
}

main();
