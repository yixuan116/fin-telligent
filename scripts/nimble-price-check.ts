/**
 * nimble-price-check — build-time scrape of Artificial Analysis via Nimble.
 *
 * Run once at build time, never from the page:
 *   NIMBLE_API_KEY=... npm run nimble:price-check
 *
 * Add --pricing-search to also hunt each unpriced model's provider for an
 * official pricing page. That is slow and has never recovered a price, so it
 * is off by default and the scheduled job never runs it.
 *
 * Writes data/nimble_latest_<as_of>.csv. Every row carries the source_url it
 * came from. A field the scrape could not establish is left empty and named in
 * the row's not_found column -- nothing here is inferred or filled in by hand.
 *
 * The column names and units follow llm_price_performance_tracker_2026-03-31.csv
 * so the two can be compared directly: prices are USD per 1M tokens, TTFT is
 * seconds, and blended cost weights 3 input tokens to 1 output token.
 */
import Nimble from '@nimble-way/nimble-js';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const AS_OF = process.env.NIMBLE_AS_OF ?? new Date().toISOString().slice(0, 10);
const OUT = resolve(process.cwd(), `data/nimble_latest_${AS_OF}.csv`);

const AA_LEADERBOARD = 'https://artificialanalysis.ai/leaderboards/models';

const PRICING_SEARCH = process.argv.includes('--pricing-search') || process.env.NIMBLE_PRICING_SEARCH === '1';

const apiKey = process.env.NIMBLE_API_KEY;
if (!apiKey) {
  console.error('NIMBLE_API_KEY is not set. Export it and re-run; it is never read from a file in this repo.');
  process.exit(1);
}
const nimble = new Nimble({ apiKey });

/** One row of the output CSV. */
interface Row {
  model_name: string;
  provider: string;
  aa_intelligence_index: number | null;
  aa_coding_index: number | null;
  aa_math_index: number | null;
  input_cost_usd_per_1m: number | null;
  output_cost_usd_per_1m: number | null;
  blended_cost_usd_per_1m: number | null;
  time_to_first_token_s: number | null;
  source_url: string;
  pricing_page_checked: string;
  as_of: string;
  not_found: string[];
}

/** Artificial Analysis ships its table as an RSC flight payload, not as HTML. */
function flightPayload(html: string): string {
  const pushes = [...html.matchAll(/self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)/g)];
  return pushes.map((m) => JSON.parse(`"${m[1]}"`) as string).join('');
}

/**
 * Pull the one `models` array that carries the metrics. The page holds a second,
 * slimmer array of the same name, so the array is chosen by its contents rather
 * than by position.
 */
function modelsArray(flight: string): any[] {
  for (const m of flight.matchAll(/"models":\[/g)) {
    const start = flight.indexOf('[', m.index!);
    let depth = 0;
    let end = start;
    for (; end < flight.length; end++) {
      const ch = flight[end];
      if (ch === '[') depth++;
      else if (ch === ']' && --depth === 0) { end++; break; }
    }
    const raw = flight.slice(start, end);
    if (!raw.includes('intelligenceIndex')) continue;
    try { return JSON.parse(raw); } catch { /* try the next candidate */ }
  }
  throw new Error('Artificial Analysis payload no longer contains a models array with intelligenceIndex');
}

/** The tracker's convention: 3 input tokens weighted against 1 output token. */
function blended(input: number | null, output: number | null): number | null {
  if (input == null || output == null) return null;
  return (3 * input + output) / 4;
}

/**
 * For a model Artificial Analysis lists without a price, ask Nimble's search
 * for that provider's own pricing page and read it. Providers publish one page
 * for a whole family, so this runs per provider rather than per model.
 *
 * A hit is only accepted when the page it returns actually talks about this
 * provider. Left unchecked the search happily answers "OpenBMB pricing" with
 * OpenAI's page, and a wrong link is worse than an admitted gap.
 */
async function providerPricingPage(provider: string): Promise<string | null> {
  const token = provider.toLowerCase().replace(/[^a-z0-9]+/g, '');
  try {
    const found = await nimble.search({
      query: `${provider} API pricing per 1M tokens official`,
      max_results: 5,
      search_depth: 'lite',
    } as any);
    for (const hit of found.results ?? []) {
      if (!/pricing|price/i.test(hit.url)) continue;
      const page = await nimble.extract.run({
        url: hit.url,
        formats: ['markdown'],
        render: true,
        markdown_backend: 'main_content',
        request_timeout: 60_000,
      });
      if (page.status !== 'success') continue;
      const host = new URL(hit.url).hostname.toLowerCase().replace(/[^a-z0-9]+/g, '');
      const text = String((page.data as any).markdown ?? '').toLowerCase();
      const belongs = host.includes(token) || text.includes(provider.toLowerCase());
      if (belongs) return hit.url;
      console.warn(`    ${provider}: ignoring ${hit.url} (does not mention ${provider})`);
    }
    return null;
  } catch (err) {
    console.warn(`  search/extract failed for ${provider}: ${(err as Error).message}`);
    return null;
  }
}

function csvCell(v: unknown): string {
  if (v == null) return '';
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

async function main(): Promise<void> {
  console.log(`Nimble extract: ${AA_LEADERBOARD}`);
  const res = await nimble.extract.run({
    url: AA_LEADERBOARD,
    formats: ['html'],
    render: true,
    request_timeout: 120_000,
  });
  if (res.status !== 'success') {
    throw new Error(`Nimble extract returned status="${res.status}" for ${AA_LEADERBOARD}`);
  }

  const models = modelsArray(flightPayload((res.data as any).html ?? ''));
  const live = models.filter((m) => !m.deprecated && m.intelligenceIndex != null);
  console.log(`  ${models.length} models listed, ${live.length} current with an intelligence index`);

  const rows: Row[] = live.map((m) => {
    const input = m.price1mInputTokens ?? null;
    const output = m.price1mOutputTokens ?? null;
    const ttft = typeof m.medianTimeToFirstTokenSeconds === 'number' ? m.medianTimeToFirstTokenSeconds : null;
    const notFound: string[] = [];
    // Artificial Analysis retired its per-lane coding and math indices from this
    // payload. They are reported missing rather than substituted with a proxy.
    if (m.codingIndex == null) notFound.push('aa_coding_index');
    if (m.mathIndex == null) notFound.push('aa_math_index');
    if (input == null) notFound.push('input_cost_usd_per_1m');
    if (output == null) notFound.push('output_cost_usd_per_1m');
    if (ttft == null) notFound.push('time_to_first_token_s');
    return {
      model_name: m.name,
      provider: m.modelCreatorName ?? '',
      aa_intelligence_index: m.intelligenceIndex,
      aa_coding_index: m.codingIndex ?? null,
      aa_math_index: m.mathIndex ?? null,
      input_cost_usd_per_1m: input,
      output_cost_usd_per_1m: output,
      blended_cost_usd_per_1m: blended(input, output),
      time_to_first_token_s: ttft,
      source_url: AA_LEADERBOARD,
      pricing_page_checked: '',
      as_of: AS_OF,
      not_found: notFound,
    };
  });

  // Unpriced models: record which provider page was checked for a price, in a
  // column of its own. source_url stays the leaderboard, because that is where
  // every value in the row actually came from -- no price was read off these
  // pages, and labelling one as the row's source would imply otherwise.
  //
  // Off by default. It is a search plus an extract for every provider with an
  // unpriced model, which runs for minutes and, on every run so far, has not
  // recovered a single price -- so the scheduled job skips it and those fields
  // stay marked not_found. Pass --pricing-search (or NIMBLE_PRICING_SEARCH=1)
  // to run it by hand.
  const pricingPage = new Map<string, string>();
  if (PRICING_SEARCH) {
    const unpricedProviders = [...new Set(rows.filter((r) => r.input_cost_usd_per_1m == null).map((r) => r.provider))];
    console.log(`  ${unpricedProviders.length} providers have unpriced models; searching for official pricing pages`);
    for (const provider of unpricedProviders) {
      const url = await providerPricingPage(provider);
      if (url) {
        pricingPage.set(provider, url);
        console.log(`    ${provider} -> ${url}`);
      }
    }
  } else {
    const unpriced = rows.filter((r) => r.input_cost_usd_per_1m == null).length;
    console.log(`  ${unpriced} models are unpriced; provider pricing search skipped (pass --pricing-search to run it)`);
  }
  for (const r of rows) {
    if (r.input_cost_usd_per_1m == null && pricingPage.has(r.provider)) {
      r.pricing_page_checked = pricingPage.get(r.provider)!;
    }
  }

  const header = [
    'model_name', 'provider', 'aa_intelligence_index', 'aa_coding_index', 'aa_math_index',
    'input_cost_usd_per_1m', 'output_cost_usd_per_1m', 'blended_cost_usd_per_1m',
    'time_to_first_token_s', 'source_url', 'pricing_page_checked', 'as_of', 'not_found',
  ];
  const body = rows.map((r) =>
    header.map((h) => csvCell(h === 'not_found' ? r.not_found.join(' ') : (r as any)[h])).join(','));

  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, [header.join(','), ...body].join('\n') + '\n');
  console.log(`\nWrote ${rows.length} rows to ${OUT}`);
  const priced = rows.filter((r) => r.blended_cost_usd_per_1m != null).length;
  console.log(`  priced: ${priced}   unpriced: ${rows.length - priced}`);
}

main().catch((err) => {
  console.error('\nNimble scrape failed, no CSV written:');
  console.error(err);
  process.exit(1);
});
