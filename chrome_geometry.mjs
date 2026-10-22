// chrome_geometry.mjs — where is the main content of a page, really?
//
// Part of Echo's mouse (Jakob's order, 2026-10-19: people watching
// Echo's screen must be able to tell what he's clicking on). This
// script renders a page in a throwaway headless Chrome at a given
// viewport size and reports the center of the page's main heading —
// or, failing a heading, its main text block or a main link — as
// {found, kind, tag, text, cx, cy}. chrome_screen.py moves Echo's
// real X pointer to exactly that spot on his display before taking
// the screenshot people see. Nothing is estimated or invented: the
// coordinates come from Chrome's own layout of the real page.
//
// Usage: node chrome_geometry.mjs <url> <viewport_width> <viewport_height>
// Prints one JSON line on stdout.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const url = process.argv[2];
const W = parseInt(process.argv[3] || '1280', 10);
const H = parseInt(process.argv[4] || '711', 10);
const RELAY = 'http://127.0.0.1:18081'; // chrome_relay.py, as elsewhere

const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'echo-geom-'));
const chrome = spawn('/usr/bin/google-chrome', [
  '--headless=new', '--no-sandbox', '--disable-gpu',
  '--disable-dev-shm-usage', '--disable-component-update',
  '--disable-background-networking', '--disable-sync',
  '--no-first-run', '--no-default-browser-check',
  `--user-data-dir=${prof}`, `--proxy-server=${RELAY}`,
  '--remote-debugging-port=0', `--window-size=${W},${H}`, 'about:blank',
], { stdio: 'ignore' });

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
try {
  let port = null;
  for (let i = 0; i < 50 && !port; i++) {
    await sleep(200);
    try {
      const [p] = fs.readFileSync(path.join(prof, 'DevToolsActivePort'), 'utf8').split('\n');
      if (p) port = parseInt(p, 10);
    } catch {}
  }
  if (!port) throw new Error('no devtools port');
  let target = null;
  for (let i = 0; i < 25 && !target; i++) {
    const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    target = list.find(t => t.type === 'page');
    if (!target) await sleep(200);
  }
  if (!target) throw new Error('no page target');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0; const pending = new Map(); const events = [];
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
    else if (d.method) events.push(d.method);
  };
  const send = (method, params = {}) => new Promise(res => {
    const id = ++seq; pending.set(id, res);
    ws.send(JSON.stringify({ id, method, params }));
  });
  await send('Page.enable');
  await send('Page.navigate', { url });
  for (let i = 0; i < 80 && !events.includes('Page.loadEventFired'); i++) await sleep(500);
  // Wait until the document itself reports complete (the load event
  // above can belong to the initial about:blank).
  for (let i = 0; i < 40; i++) {
    const chk = await send('Runtime.evaluate', {
      expression: 'document.readyState + "|" + location.href',
      returnByValue: true,
    });
    const v = chk.result?.result?.value || '';
    if (v.startsWith('complete|') && !v.endsWith('about:blank')) break;
    await sleep(500);
  }
  // Let late content settle (pages that expand after load, e.g.
  // script-injected sections): wait until the visible text length
  // stops changing so the measured box is the finished layout —
  // the same layout Echo's display window ends up showing.
  let lastLen = -1;
  for (let i = 0; i < 8; i++) {
    const chk = await send('Runtime.evaluate', {
      expression: '(document.body && document.body.innerText || "").length',
      returnByValue: true,
    });
    const len = chk.result?.result?.value || 0;
    if (len > 0 && len === lastLen) break;
    lastLen = len;
    await sleep(700);
  }
  await sleep(300);
  const expr = `(() => {
    const pick = (sel) => { for (const el of document.querySelectorAll(sel)) { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); if (r.width > 4 && r.height > 4 && s.visibility !== 'hidden' && s.display !== 'none' && r.bottom > 0 && r.top < innerHeight) return { el, r }; } return null; };
    const tries = [
      ['heading', 'h1'], ['heading', 'h2'], ['heading', '[role="heading"]'],
      ['heading', 'h3'],
      ['text', 'main p, article p, body > div p, body p'],
      ['link', 'main a, article a, body a'],
    ];
    for (const [kind, sel] of tries) {
      const hit = pick(sel);
      if (hit) {
        const { el, r } = hit;
        return { found: true, kind, tag: el.tagName,
          text: (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
          cx: Math.round(r.left + r.width / 2), cy: Math.round(r.top + r.height / 2),
          w: Math.round(r.width), h: Math.round(r.height) };
      }
    }
    return { found: false };
  })()`;
  const out = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  console.log(JSON.stringify(out.result?.result?.value ?? { found: false }));
  ws.close();
} catch (e) {
  console.log(JSON.stringify({ found: false, error: String(e).slice(0, 200) }));
} finally {
  chrome.kill('SIGKILL');
  fs.rmSync(prof, { recursive: true, force: true });
}
