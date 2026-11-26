/**
 * A browser for tests, and nobody's browser but this one.
 *
 * Headless Chrome with a profile of its own under a directory you pass in,
 * driven over the DevTools protocol with no dependencies. Nothing here
 * touches the profile a person is signed in to: the cookies, storage and
 * sessions a test creates live and die with that directory.
 *
 *   const b = await launch(dir);
 *   const p = await b.page("https://example.com");
 *   await p.eval(`document.title`);
 *   await b.close();
 *
 * `eval` runs the expression in the page and returns its value, waiting on
 * a promise if it gets one, so `await fetch(...)` works as written.
 */

import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, existsSync, rmSync } from "node:fs";

const CHROME = process.env.CHROME_BIN ||
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function devtoolsPort(dir, proc) {
  const file = dir + "/DevToolsActivePort";
  for (let i = 0; i < 100; i++) {
    if (proc.exitCode !== null) throw new Error("Chrome exited: " + proc.exitCode);
    if (existsSync(file)) {
      const port = readFileSync(file, "utf8").split("\n")[0].trim();
      if (port) return port;
    }
    await wait(100);
  }
  throw new Error("Chrome never opened a debugging port");
}

/** One websocket, many commands, replies matched by id. */
function connect(url) {
  const ws = new WebSocket(url);
  const waiting = new Map();
  let n = 0;
  const open = new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    const w = msg.id && waiting.get(msg.id);
    if (!w) return;
    waiting.delete(msg.id);
    msg.error ? w.rej(new Error(msg.error.message)) : w.res(msg.result);
  };
  return {
    async send(method, params = {}, sessionId) {
      await open;
      const id = ++n;
      return new Promise((res, rej) => {
        waiting.set(id, { res, rej });
        ws.send(JSON.stringify({ id, method, params, sessionId }));
      });
    },
    close() { try { ws.close(); } catch {} }
  };
}

export async function launch(dir, { headless = true } = {}) {
  mkdirSync(dir, { recursive: true });
  const args = [
    "--user-data-dir=" + dir,
    "--remote-debugging-port=0",
    "--no-first-run", "--no-default-browser-check",
    "--disable-background-networking", "--disable-sync",
    "--password-store=basic", "--use-mock-keychain",
    "about:blank"
  ];
  if (headless) args.unshift("--headless=new");
  /* Chrome is talkative on stderr; an unread pipe fills and stops it
     before it ever writes the port, so the noise is drained and kept in
     case a failure needs explaining. */
  const proc = spawn(CHROME, args, { stdio: ["ignore", "ignore", "pipe"] });
  const noise = [];
  proc.stderr.on("data", (d) => { noise.push(String(d)); if (noise.length > 200) noise.shift(); });
  proc.stderr.resume();
  let port;
  try { port = await devtoolsPort(dir, proc); }
  catch (e) { proc.kill("SIGKILL"); throw new Error(e.message + "\n" + noise.join("").slice(-800)); }
  const info = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
  const conn = connect(info.webSocketDebuggerUrl);

  return {
    /** A tab on `url`, loaded. */
    async page(url) {
      const { targetId } = await conn.send("Target.createTarget", { url: "about:blank" });
      const { sessionId } = await conn.send("Target.attachToTarget", { targetId, flatten: true });
      const page = {
        targetId,
        async eval(expression) {
          const r = await conn.send("Runtime.evaluate",
            /* replMode is what lets `await` appear at the top of the
               expression, the way it does in the console. */
            { expression, awaitPromise: true, returnByValue: true, userGesture: true, replMode: true }, sessionId);
          if (r.exceptionDetails) {
            throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
          }
          return r.result.value;
        },
        async goto(to) {
          await conn.send("Page.navigate", { url: to }, sessionId);
          await page.ready();
        },
        async ready(ms = 15000) {
          const until = Date.now() + ms;
          for (;;) {
            try {
              if (await page.eval(`document.readyState==='complete'`)) return;
            } catch {}
            if (Date.now() > until) throw new Error("page never finished loading");
            await wait(100);
          }
        },
        close() { return conn.send("Target.closeTarget", { targetId }); }
      };
      /* Navigating after the attach, rather than creating the target on
         the address, so the load is one this session can wait for. */
      if (url) await page.goto(url); else await page.ready();
      return page;
    },
    async close() {
      try { await conn.send("Browser.close"); } catch {}
      conn.close();
      proc.kill("SIGKILL");
      await wait(200);
    },
    /** The profile and everything in it. */
    wipe() { rmSync(dir, { recursive: true, force: true }); }
  };
}
