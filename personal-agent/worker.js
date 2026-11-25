/**
 * Personal Agent, server side.
 *
 * Three things only: it hands out a session when someone opens a private
 * link, it reads and writes one JSON state per user, and it leaves
 * everything else to the static assets.
 *
 * There are no passwords. A link carries a token; D1 holds only that
 * token's SHA-256, so the table is useless to anyone who reads it, and a
 * link is revoked by deleting its row.
 */

const YEAR_SECONDS = 31536000;
const MAX_STATE_BYTES = 1024 * 1024;
const SESSION_COOKIE = "pa_session";

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }
  });

const text = (body, status = 200) =>
  new Response(body, {
    status,
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" }
  });

async function sha256Hex(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function readCookie(request, name) {
  const header = request.headers.get("cookie") || "";
  for (const part of header.split(";")) {
    const at = part.indexOf("=");
    if (at > 0 && part.slice(0, at).trim() === name) return part.slice(at + 1).trim();
  }
  return null;
}

function newToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** The user this request belongs to, or null. Expired rows never match. */
async function userFor(request, env) {
  const raw = readCookie(request, SESSION_COOKIE);
  if (!raw) return null;
  const row = await env.DB
    .prepare("SELECT user_id FROM sessions WHERE token_hash = ?1 AND expires_at > ?2")
    .bind(await sha256Hex(raw), Date.now())
    .first();
  return row ? row.user_id : null;
}

/** /join?t=... : trade a private link for a session cookie. */
async function join(request, env, url) {
  const token = url.searchParams.get("t") || "";
  if (!token) return text("This link is missing its token.", 400);

  const invite = await env.DB
    .prepare("SELECT user_id FROM invites WHERE token_hash = ?1")
    .bind(await sha256Hex(token))
    .first();
  if (!invite) return text("This link is not valid. Ask for a new one.", 403);

  const session = newToken();
  await env.DB
    .prepare("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?1, ?2, ?3)")
    .bind(await sha256Hex(session), invite.user_id, Date.now() + YEAR_SECONDS * 1000)
    .run();

  /* Old sessions for this user are left alone on purpose: the same person
     signs in from a phone and a laptop on the same link. */
  return new Response(null, {
    status: 302,
    headers: {
      location: "/",
      "cache-control": "no-store",
      "set-cookie":
        `${SESSION_COOKIE}=${session}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${YEAR_SECONDS}`
    }
  });
}

async function getState(userId, env) {
  const row = await env.DB
    .prepare("SELECT state, updated_at FROM states WHERE user_id = ?1")
    .bind(userId)
    .first();
  return json({
    state: row ? JSON.parse(row.state) : null,
    updatedAt: row ? row.updated_at : 0
  });
}

async function putState(request, userId, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "body must be JSON" }, 400);
  }
  const state = body && body.state;
  if (!state || typeof state !== "object" || Array.isArray(state)) {
    return json({ error: "state must be an object" }, 400);
  }

  const blob = JSON.stringify(state);
  if (blob.length > MAX_STATE_BYTES) return json({ error: "state too large" }, 413);

  const now = Date.now();
  await env.DB
    .prepare(
      `INSERT INTO states (user_id, state, updated_at) VALUES (?1, ?2, ?3)
       ON CONFLICT(user_id) DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at`
    )
    .bind(userId, blob, now)
    .run();
  return json({ ok: true, updatedAt: now });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/join") return join(request, env, url);

    if (url.pathname.startsWith("/api/")) {
      const userId = await userFor(request, env);
      if (!userId) return json({ error: "no session" }, 401);

      if (url.pathname === "/api/state") {
        if (request.method === "GET") return getState(userId, env);
        if (request.method === "PUT") return putState(request, userId, env);
        return json({ error: "method not allowed" }, 405);
      }
      return json({ error: "not found" }, 404);
    }

    /* Anything else is a file. Assets that exist are served before this
       Worker runs at all; this catches the rest. */
    return env.ASSETS.fetch(request);
  }
};
