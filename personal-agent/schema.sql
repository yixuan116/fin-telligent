-- Personal Agent, D1 schema. Three tables and nothing else.
--
-- Only hashes are stored: a leaked copy of this database cannot be used to
-- sign in anywhere. Revoking a link is a DELETE from invites.

CREATE TABLE IF NOT EXISTS invites (
  token_hash TEXT PRIMARY KEY,      -- SHA-256 of the token in the link
  user_id    TEXT NOT NULL,         -- whose state the link opens
  label      TEXT,                  -- a note to yourself, never shown in the app
  created_at INTEGER NOT NULL       -- epoch ms
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,      -- SHA-256 of the cookie value
  user_id    TEXT NOT NULL,
  expires_at INTEGER NOT NULL       -- epoch ms
);
CREATE INDEX IF NOT EXISTS sessions_expires_at ON sessions (expires_at);

-- One row per user: the whole app state as JSON, exactly the shape the page
-- keeps in memory (canvases, events, fields, vals, tasks, settings).
CREATE TABLE IF NOT EXISTS states (
  user_id    TEXT PRIMARY KEY,
  state      TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);
