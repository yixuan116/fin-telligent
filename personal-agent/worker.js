/**
 * Personal Agent, server side.
 *
 * It hands out a session when someone opens a private link, reads and
 * writes one JSON state per user without ever overwriting a newer write,
 * backs every state up to R2 once a day, and leaves everything else to
 * the static assets.
 *
 * There are no passwords. A link carries a token; D1 holds only that
 * token's SHA-256, so the table is useless to anyone who reads it, and a
 * link is revoked by deleting its row.
 */

const YEAR_SECONDS = 31536000;
const MAX_STATE_BYTES = 1024 * 1024;
const MAX_PHOTO_BYTES = 2 * 1024 * 1024;
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

/* A write names the version it was built on. If someone else wrote in the
   meantime, nothing is overwritten: the caller gets the current state back
   (409), merges item by item, and tries again. */
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
  const base = body.baseUpdatedAt;
  if (typeof base !== "number") return json({ error: "baseUpdatedAt required, reload the page" }, 409);

  const blob = JSON.stringify(state);
  if (blob.length > MAX_STATE_BYTES) return json({ error: "state too large" }, 413);

  const now = Date.now();
  const res = base === 0
    ? await env.DB
        .prepare("INSERT INTO states (user_id, state, updated_at) VALUES (?1, ?2, ?3) ON CONFLICT(user_id) DO NOTHING")
        .bind(userId, blob, now).run()
    : await env.DB
        .prepare("UPDATE states SET state = ?2, updated_at = ?3 WHERE user_id = ?1 AND updated_at = ?4")
        .bind(userId, blob, now, base).run();

  if (!res.meta || res.meta.changes !== 1) {
    const cur = await getState(userId, env);
    return new Response(cur.body, { status: 409, headers: cur.headers });
  }
  return json({ ok: true, updatedAt: now });
}

/* ---- day photos ----
   One object per photo under the owner's own prefix, which is also how a
   read is authorised: a key that does not start with your id is not yours
   to fetch. The page sends an already compressed JPEG. */
function photoKey(userId, name) {
  return `${userId}/${name}`;
}

async function putPhoto(request, userId, env) {
  const body = await request.arrayBuffer();
  if (!body.byteLength) return json({ error: "empty" }, 400);
  if (body.byteLength > MAX_PHOTO_BYTES) return json({ error: "photo too large" }, 413);

  const key = photoKey(userId, crypto.randomUUID() + ".jpg");
  await env.PHOTOS.put(key, body, { httpMetadata: { contentType: "image/jpeg" } });
  return json({ key });
}

async function getPhoto(key, userId, env) {
  if (!key.startsWith(userId + "/")) return json({ error: "not found" }, 404);
  const obj = await env.PHOTOS.get(key);
  if (!obj) return json({ error: "not found" }, 404);
  return new Response(obj.body, {
    headers: {
      "content-type": obj.httpMetadata?.contentType || "image/jpeg",
      /* Private to one person and immutable once written. */
      "cache-control": "private, max-age=31536000, immutable"
    }
  });
}

async function deletePhoto(key, userId, env) {
  if (!key.startsWith(userId + "/")) return json({ error: "not found" }, 404);
  await env.PHOTOS.delete(key);
  return json({ ok: true });
}

/* ---- daily backup ----
   Every user's full state goes to R2 as daily/YYYY-MM-DD.json. Anything
   older than 365 days is removed in the same run. */
const KEEP_DAYS = 365;

async function backup(env) {
  const { results } = await env.DB.prepare("SELECT user_id, state, updated_at FROM states").all();
  const day = new Date().toISOString().slice(0, 10);
  const doc = {
    takenAt: new Date().toISOString(),
    users: results.map((r) => ({ user_id: r.user_id, updated_at: r.updated_at, state: JSON.parse(r.state) }))
  };
  await env.BACKUPS.put(`daily/${day}.json`, JSON.stringify(doc), {
    httpMetadata: { contentType: "application/json" }
  });

  const cutoff = new Date(Date.now() - KEEP_DAYS * 86400000).toISOString().slice(0, 10);
  let cursor;
  do {
    const list = await env.BACKUPS.list({ prefix: "daily/", cursor });
    const old = list.objects.map((o) => o.key).filter((k) => k.slice(6, 16) < cutoff);
    if (old.length) await env.BACKUPS.delete(old);
    cursor = list.truncated ? list.cursor : undefined;
  } while (cursor);

  return { key: `daily/${day}.json`, users: results.length };
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
      /* Run today's backup now, e.g. before a risky change. */
      if (url.pathname === "/api/backup" && request.method === "POST") return json(await backup(env));

      if (url.pathname === "/api/photo" && request.method === "POST") {
        return putPhoto(request, userId, env);
      }
      if (url.pathname.startsWith("/api/photo/")) {
        const key = decodeURIComponent(url.pathname.slice("/api/photo/".length));
        if (request.method === "GET") return getPhoto(key, userId, env);
        if (request.method === "DELETE") return deletePhoto(key, userId, env);
        return json({ error: "method not allowed" }, 405);
      }
      return json({ error: "not found" }, 404);
    }

    /* Anything else is a file. Assets that exist are served before this
       Worker runs at all; this catches the rest. */
    return env.ASSETS.fetch(request);
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(backup(env));
  }
};
