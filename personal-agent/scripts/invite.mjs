#!/usr/bin/env node
/**
 * Make a private link.
 *
 *   npm run invite -- <name>
 *
 * The token is generated here, printed here, and never stored anywhere but
 * your terminal: D1 gets its SHA-256 only. Nothing this writes belongs in
 * the repository.
 *
 * The name decides which state the link opens, so running it twice with the
 * same name gives that person a second device on the same calendar.
 *
 * Revoking a link stops it being used to sign in again:
 *
 *   npx wrangler d1 execute personal-agent-db --remote \
 *     --command "DELETE FROM invites WHERE label = '<name>'"
 *
 * Devices already signed in keep their year-long cookie, so to lock those
 * out as well, drop their sessions too:
 *
 *   npx wrangler d1 execute personal-agent-db --remote \
 *     --command "DELETE FROM sessions WHERE user_id = '<the user_id>'"
 */

import { execFileSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";

const DB = "personal-agent-db";
const DEFAULT_ORIGIN = "https://agent.fin-telligent.com";

const name = process.argv.slice(2).join(" ").trim();
if (!name) {
  console.error("Usage: npm run invite -- <name>");
  process.exit(1);
}
if (!/^[\w .'-]{1,40}$/u.test(name)) {
  console.error("Use letters, numbers, spaces, dots, apostrophes or hyphens, up to 40.");
  process.exit(1);
}

const origin = (process.env.PA_ORIGIN || DEFAULT_ORIGIN).replace(/\/+$/, "");
const sha = (value) => createHash("sha256").update(value).digest("hex");

const token = randomBytes(32).toString("base64url");
/* Derived rather than random, so the same person asking twice lands on the
   same state instead of an empty one. */
const userId = sha("personal-agent:" + name.toLowerCase()).slice(0, 24);
const label = name.replace(/'/g, "''");

execFileSync(
  "npx",
  [
    "wrangler", "d1", "execute", DB, "--remote", "--command",
    `INSERT INTO invites (token_hash, user_id, label, created_at)
     VALUES ('${sha(token)}', '${userId}', '${label}', ${Date.now()})`
  ],
  { stdio: ["ignore", "ignore", "inherit"] }
);

console.log("");
console.log(`Invite for ${name}`);
console.log(`${origin}/join?t=${token}`);
console.log("");
console.log("Open it once on each device. The cookie lasts a year.");
console.log("This link is not stored anywhere else. Copy it now.");
