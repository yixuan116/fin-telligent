/**
 * embed-latest — fold the newest Nimble pull into the page.
 *
 *   npx tsx scripts/embed-latest.ts
 *
 * Reads the most recent data/nimble_latest_*.csv and rewrites two things in
 * ai-compute-datacenter-economics/index.html: the NEWCART_RAW table the New
 * Shopping Cart shops from, and NEWCART_AS_OF, which every date on the block
 * is rendered from. Nothing else in the file is touched.
 *
 * Only priced rows are embedded -- a row without both prices, or with an
 * intelligence index missing, can never be a candidate, so carrying it would
 * only inflate the page.
 */
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

const DATA_DIR = resolve(process.cwd(), 'data');
const PAGE = resolve(process.cwd(), 'ai-compute-datacenter-economics/index.html');

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

  const asOf = prettyDate(usable[0]?.as_of ?? rows[0]?.as_of ?? '');
  let page = readFileSync(PAGE, 'utf8');

  const rawBlock = `  var NEWCART_RAW = [\n${table.map((t) => `    ${JSON.stringify(t)}`).join(',\n')}\n  ];`;
  const rawRe = /  var NEWCART_RAW = \[[\s\S]*?\n  \];/;
  if (!rawRe.test(page)) throw new Error('NEWCART_RAW block not found in the page');
  page = page.replace(rawRe, rawBlock);

  const asOfRe = /  var NEWCART_AS_OF = "[^"]*";/;
  if (!asOfRe.test(page)) throw new Error('NEWCART_AS_OF not found in the page');
  page = page.replace(asOfRe, `  var NEWCART_AS_OF = "${asOf}";`);

  writeFileSync(PAGE, page);
  console.log(`Embedded ${table.length} priced models, as of ${asOf}`);
}

main();
