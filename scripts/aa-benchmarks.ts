/**
 * aa-benchmarks — the per-model benchmark scores behind the "Strong in" line.
 *
 *   NIMBLE_API_KEY=... npx tsx scripts/aa-benchmarks.ts
 *
 * Writes data/aa_benchmarks_<fetched>.csv: one row per model Artificial
 * Analysis lists, carrying its release date and the raw score for each
 * benchmark the page's swimlanes are built from. Values are copied exactly as
 * AA states them; nothing is scaled, filled or inferred here.
 *
 * Only benchmarks whose AA field was checked against the matching column of
 * llm_price_performance_tracker_2026-03-31.csv are collected, so a lane can
 * never be built on a field that merely looks right:
 *
 *   gpqa          == gpqa_diamond         (368 overlapping models, same scale)
 *   livecodebench == livecodebench        (306 overlapping models, same scale)
 *   scicode       == scicode              (37 overlapping models, same scale)
 *   hle           == humanitys_last_exam  (363 overlapping models, same scale)
 *   aime25        == aa_math_index / 100  (235 of 235 overlapping models)
 *
 * Chatbot Arena is deliberately absent: the payload's `elo` numbers are not
 * attached to model records and could belong to the image, music or video
 * arenas, so the Dialogue lane has no verified source and is not built.
 *
 * One page carries the whole catalogue, so this makes a single request.
 */
import Nimble from '@nimble-way/nimble-js';
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const DATA_DIR = resolve(process.cwd(), 'data');
/** Any model page works: each embeds the full catalogue. */
const AA_MODEL_PAGE = 'https://artificialanalysis.ai/models/claude-sonnet-5-5-medium';
const FETCHED = process.env.AA_FETCHED_ON ?? new Date().toISOString().slice(0, 10);

/** Verified AA field -> column name in the output. */
const FIELDS = ['gpqa', 'livecodebench', 'scicode', 'aime25', 'hle'] as const;

function csvCell(v: unknown): string {
  if (v == null) return '';
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

async function main(): Promise<void> {
  const apiKey = process.env.NIMBLE_API_KEY;
  if (!apiKey) {
    console.error('NIMBLE_API_KEY is not set. Export it and re-run.');
    process.exit(1);
  }
  const nimble = new Nimble({ apiKey });
  console.log(`Nimble extract: ${AA_MODEL_PAGE}`);
  const res = await nimble.extract.run({
    url: AA_MODEL_PAGE, formats: ['html'], render: true, request_timeout: 120_000,
  });
  if (res.status !== 'success') throw new Error(`Artificial Analysis returned status="${res.status}"`);
  const html = String((res.data as any).html ?? '');

  // The payload is a Next.js flight blob, escaped differently in different
  // places, so each model's fields are read out of a window after its name
  // rather than by parsing the whole thing as JSON.
  const rows = new Map<string, Record<string, string | number>>();
  const nameRe = /\\?"name\\?":\\?"((?:[^"\\]|\\.){1,160}?)\\?"/g;
  let m: RegExpExecArray | null;
  while ((m = nameRe.exec(html))) {
    const name = m[1].replace(/\\"/g, '"').replace(/\\\\/g, '\\');
    const win = html.slice(m.index, m.index + 3000);
    const row = rows.get(name) ?? { model_name: name };
    if (row.release_date == null) {
      const d = win.match(/\\?"releaseDate\\?":\\?"(\d{4}-\d{2}-\d{2})\\?"/);
      if (d) row.release_date = d[1];
    }
    for (const f of FIELDS) {
      if (row[f] == null) {
        const v = win.match(new RegExp('\\\\?"' + f + '\\\\?":\\s*(-?\\d+(?:\\.\\d+)?)'));
        if (v) row[f] = Number(v[1]);
      }
    }
    rows.set(name, row);
  }

  const header = ['model_name', 'release_date', ...FIELDS, 'fetched_on'];
  const body = [...rows.values()].map((r) =>
    header.map((h) => csvCell(h === 'fetched_on' ? FETCHED : r[h])).join(','));
  mkdirSync(DATA_DIR, { recursive: true });
  const out = resolve(DATA_DIR, `aa_benchmarks_${FETCHED}.csv`);
  writeFileSync(out, [header.join(','), ...body].join('\n') + '\n');

  const withDate = [...rows.values()].filter((r) => r.release_date).length;
  console.log(`Wrote ${rows.size} models to ${out}`);
  console.log(`  with a release date: ${withDate}`);
  for (const f of FIELDS) {
    const n = [...rows.values()].filter((r) => r[f] != null).length;
    console.log(`  ${f.padEnd(14)} ${n}`);
  }
}

main().catch((err) => { console.error('\nScrape failed, no CSV written:'); console.error(err); process.exit(1); });
