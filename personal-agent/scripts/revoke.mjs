#!/usr/bin/env node
/**
 * Take a private link back.
 *
 *   npm run revoke -- <label>            the link, and every device it opened
 *   npm run revoke -- <label> --link     the link only; devices stay signed in
 *
 * A session remembers which link opened it, so revoking one link leaves the
 * others alone: `npm run revoke -- alex-phone` signs out Alex's phone and
 * nothing else.
 *
 * Sessions created before links were labelled have no link recorded. They
 * cannot be revoked by label; `npm run revoke -- --list` shows them.
 */

import { execFileSync } from "node:child_process";

const DB = "personal-agent-db";
const args = process.argv.slice(2);
const linkOnly = args.includes("--link");
const list = args.includes("--list");
const label = args.filter((a) => !a.startsWith("--")).join(" ").trim();

const sql = (command) => {
  const out = execFileSync("npx",
    ["wrangler", "d1", "execute", DB, "--remote", "--json", "--command", command],
    { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] });
  return JSON.parse(out.slice(out.indexOf("[")))[0].results;
};

if (list || !label) {
  const rows = sql(`SELECT i.label, i.user_id,
      (SELECT count(*) FROM sessions s WHERE s.invite = i.label AND s.user_id = i.user_id) AS devices
    FROM invites i ORDER BY i.created_at`);
  const old = sql(`SELECT count(*) AS n FROM sessions WHERE invite IS NULL OR invite = ''`)[0].n;
  console.log("\nLinks");
  for (const r of rows) console.log(`  ${r.label.padEnd(20)} ${r.devices} device(s) signed in`);
  if (old) console.log(`\n  ${old} older session(s) predate link labels and cannot be revoked by label.`);
  console.log("\nUsage: npm run revoke -- <label> [--link]\n");
  process.exit(0);
}

const safe = label.replace(/'/g, "''");
const found = sql(`SELECT user_id FROM invites WHERE label = '${safe}'`);
if (!found.length) {
  console.error(`No link labelled "${label}". Run: npm run revoke -- --list`);
  process.exit(1);
}

const before = sql(`SELECT count(*) AS n FROM sessions WHERE invite = '${safe}'`)[0].n;
sql(`DELETE FROM invites WHERE label = '${safe}'`);
if (!linkOnly) sql(`DELETE FROM sessions WHERE invite = '${safe}'`);

console.log(`\nRevoked "${label}".`);
console.log(linkOnly
  ? `  The link no longer works. ${before} device(s) already signed in through it keep working.`
  : `  The link no longer works, and ${before} device(s) signed in through it were signed out.`);
console.log("  Every other link and device is untouched.\n");
