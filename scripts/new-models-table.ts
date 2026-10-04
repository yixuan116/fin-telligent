/**
 * new-models-table — the models the current pull lists that the March tracker
 * never did.
 *
 *   npx tsx scripts/new-models-table.ts
 *
 * Writes data/new_models_since_2026-03-31.csv, newest first.
 *
 * launch_date is read from Artificial Analysis, which carries a releaseDate per
 * model in the payload behind any /models/<slug> page -- one fetch returns the
 * whole catalogue, so this makes a single request. It is the date AA states;
 * nothing is inferred from a version number, a file date or a first sighting,
 * and a model AA has no date for is written empty. launch_date_source records
 * the page the date was read from, so every filled cell is traceable.
 *
 * first_seen_in_pull is the first data/nimble_latest_*.csv a model appears in,
 * and is only written when that is LATER than the earliest pull on disk. A
 * model present in the earliest pull was already shipping before this repo
 * started looking, so its first sighting says nothing about when it arrived.
 * It is kept as provenance only -- the page never prints it and never treats
 * it as a launch date.
 *
 * Needs NIMBLE_API_KEY. Without it the dates are left empty and the run says so
 * rather than writing a table that looks complete.
 */
import Nimble from '@nimble-way/nimble-js';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

const DATA_DIR = resolve(process.cwd(), 'data');
const TRACKER = resolve(process.cwd(),
  'ai-compute-datacenter-economics/llm_price_performance_tracker_2026-03-31.csv');
const OUT = resolve(DATA_DIR, 'new_models_since_2026-03-31.csv');
/** Any model page works: each embeds the full catalogue with release dates. */
const AA_MODEL_PAGE = 'https://artificialanalysis.ai/models/claude-sonnet-5-5-medium';

/**
 * name -> releaseDate, harvested from the page payload. The pairs sit in a
 * Next.js flight payload, so they are matched in the raw HTML rather than
 * parsed as JSON -- the payload is escaped differently in different places.
 */
async function releaseDates(): Promise<Map<string, string>> {
  const out = new Map<string, string>();
  const apiKey = process.env.NIMBLE_API_KEY;
  if (!apiKey) {
    console.warn('NIMBLE_API_KEY is not set -- launch_date will be left empty for every row.');
    return out;
  }
  const nimble = new Nimble({ apiKey });
  const res = await nimble.extract.run({
    url: AA_MODEL_PAGE, formats: ['html'], render: true, request_timeout: 120_000,
  });
  if (res.status !== 'success') {
    console.warn(`Artificial Analysis returned status="${res.status}" -- launch_date left empty.`);
    return out;
  }
  const html = String((res.data as any).html ?? '');
  const re = /\\?"name\\?":\\?"((?:[^"\\]|\\.){1,160}?)\\?"[^{}]{0,400}?\\?"releaseDate\\?":\\?"(\d{4}-\d{2}-\d{2})\\?"/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html))) {
    const name = m[1].replace(/\\"/g, '"').replace(/\\\\/g, '\\');
    if (!out.has(name)) out.set(name, m[2]);
  }
  console.log(`Artificial Analysis: ${out.size} models carry a releaseDate`);
  return out;
}

/** Minimal RFC-4180 reader: the scrape quotes any cell holding a comma. */
function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [], cell = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else quoted = false; }
      else cell += ch;
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

/** Same key the page joins on: the name with every parenthetical stripped. */
function baseName(name: string): string {
  return name.replace(/\s*\([^)]*\)\s*/g, ' ').replace(/\s+/g, ' ').trim();
}

function csvCell(v: unknown): string {
  if (v == null) return '';
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function pullFiles(): string[] {
  return readdirSync(DATA_DIR).filter((f) => /^nimble_latest_.*\.csv$/.test(f)).sort();
}
const dateOf = (file: string) => file.replace(/^nimble_latest_/, '').replace(/\.csv$/, '');

async function main(): Promise<void> {
  const pulls = pullFiles();
  if (!pulls.length) throw new Error(`no nimble_latest_*.csv in ${DATA_DIR}`);
  const earliestPull = dateOf(pulls[0]);
  const latestFile = pulls[pulls.length - 1];

  // First sighting per model across every pull on disk.
  const firstSeen = new Map<string, string>();
  for (const f of pulls) {
    const d = dateOf(f);
    for (const r of parseCsv(readFileSync(join(DATA_DIR, f), 'utf8'))) {
      if (!firstSeen.has(r.model_name)) firstSeen.set(r.model_name, d);
    }
  }

  const trackerBases = new Set(
    parseCsv(readFileSync(TRACKER, 'utf8')).map((r) => baseName(r.model_name)));

  const launch = await releaseDates();
  // Artificial Analysis spells some variants differently from the pull
  // ("(Medium, Default Fallback)" vs "(Adaptive Reasoning, Medium Effort,
  // Default Fallback)"), so an exact-name miss falls back to the family -- but
  // only when every AA entry for that family states the SAME date. One family
  // with staggered variant dates is ambiguous, so it is left empty instead of
  // having a date picked for it.
  const byFamily = new Map<string, Set<string>>();
  for (const [name, date] of launch) {
    const f = baseName(name);
    if (!byFamily.has(f)) byFamily.set(f, new Set());
    byFamily.get(f)!.add(date);
  }
  const familyDate = (name: string): string => {
    const set = byFamily.get(baseName(name));
    return set && set.size === 1 ? [...set][0] : '';
  };
  const latest = parseCsv(readFileSync(join(DATA_DIR, latestFile), 'utf8'));
  const isNew = latest.filter((r) => !trackerBases.has(baseName(r.model_name)));

  // strong_in is read off the scores already in the pull, never asserted.
  const num = (v: string) => (v === '' || v == null ? null : Number(v));
  const intels = latest.map((r) => num(r.aa_intelligence_index))
    .filter((v): v is number => v != null).sort((a, b) => b - a);
  const ttfts = latest.map((r) => num(r.time_to_first_token_s))
    .filter((v): v is number => v != null).sort((a, b) => a - b);
  const intelCut = intels.length ? intels[Math.max(0, Math.ceil(intels.length * 0.1) - 1)] : null;
  const ttftCut = ttfts.length ? ttfts[Math.max(0, Math.ceil(ttfts.length * 0.1) - 1)] : null;

  function strongIn(r: Record<string, string>): string {
    const out: string[] = [];
    const intel = num(r.aa_intelligence_index);
    const ttft = num(r.time_to_first_token_s);
    if (intel != null && intelCut != null && intel >= intelCut) out.push('Top 10% intelligence');
    if (ttft != null && ttftCut != null && ttft <= ttftCut) out.push('Fast response');
    return out.join('; ');
  }

  const rows = isNew.map((r) => {
    const seen = firstSeen.get(r.model_name) ?? '';
    const exact = launch.get(r.model_name) ?? '';
    const date = exact || familyDate(r.model_name);
    return {
      model_name: r.model_name,
      provider: r.provider,
      launch_date: date,
      launch_date_source: date ? AA_MODEL_PAGE : '',
      first_seen_in_pull: seen && seen > earliestPull ? seen : '',
      aa_intelligence_index: r.aa_intelligence_index,
      strong_in: strongIn(r),
      input_price: r.input_cost_usd_per_1m,
      output_price: r.output_cost_usd_per_1m,
      blended_price: r.blended_cost_usd_per_1m,
      source_url: r.source_url,
    };
  });

  // Newest first on launch_date. With launch_date empty it decides nothing, so
  // first_seen_in_pull then intelligence keep the order meaningful instead of
  // arbitrary -- neither is a stand-in for a launch date.
  rows.sort((a, b) =>
    (b.launch_date || '').localeCompare(a.launch_date || '') ||
    (b.first_seen_in_pull || '').localeCompare(a.first_seen_in_pull || '') ||
    (Number(b.aa_intelligence_index) || 0) - (Number(a.aa_intelligence_index) || 0));

  const header = ['model_name', 'provider', 'launch_date', 'launch_date_source',
    'first_seen_in_pull', 'aa_intelligence_index', 'strong_in', 'input_price',
    'output_price', 'blended_price', 'source_url'];
  writeFileSync(OUT, [header.join(','),
    ...rows.map((r) => header.map((h) => csvCell((r as any)[h])).join(','))].join('\n') + '\n');

  const CUTOFF = '2026-03-31';
  const withLaunch = rows.filter((r) => r.launch_date).length;
  const trulyNew = rows.filter((r) => r.launch_date && r.launch_date > CUTOFF).length;
  const withSeen = rows.filter((r) => r.first_seen_in_pull).length;
  const withStrong = rows.filter((r) => r.strong_in).length;
  console.log(`Earliest pull on disk: ${earliestPull}  (first_seen only written when later)`);
  console.log(`Compared ${latestFile} against the March tracker`);
  console.log(`\nNew models: ${rows.length}`);
  console.log(`  launch_date filled       : ${withLaunch}/${rows.length} (${(100 * withLaunch / rows.length).toFixed(1)}%)`);
  console.log(`  first_seen_in_pull filled: ${withSeen}/${rows.length} (${(100 * withSeen / rows.length).toFixed(1)}%)`);
  console.log(`  strong_in filled         : ${withStrong}/${rows.length} (${(100 * withStrong / rows.length).toFixed(1)}%)`);
  console.log(`  confirmed launched after ${CUTOFF}: ${trulyNew}  <- the only ones the page may shelve`);
  console.log(`\nWrote ${OUT}`);
}

main();
