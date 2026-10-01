// PRISM chat overlay behaviour test.
//
// test-socials.mjs greps the sources for the guards below; this drives the REAL
// prism-chat.js in a real browser against a scriptable fake Stream Manager, so
// the behaviour is covered and not just the spelling. Every case here is a
// defect that actually shipped.
//
//   npm i -D playwright && npx playwright install chromium
//   node scripts/test-chat-overlay.mjs
//
// Skips cleanly (exit 0) when playwright is not installed, so it can sit in a
// test script without becoming a hard dependency.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

let chromium;
try { ({ chromium } = await import('playwright')); }
catch { console.log('· chat overlay behaviour test skipped (playwright not installed)'); process.exit(0); }

const REPO = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const FILES = {
  '/chat.html': 'chat/prism-chat.html',
  '/prism-chat.js': 'core/prism-chat.js',
  '/prism-chat-base.css': 'core/prism-chat-base.css',
};
const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript' };

let pass = 0, fail = 0;
const ok = (c, why) => { if (c) { pass++; console.log('  ok   ' + why); }
                         else { fail++; console.log('  FAIL ' + why); } };

// ── fake Stream Manager ───────────────────────────────────────────────────
// Mirrors stream_manager/effects.py: ONE globally monotonic id across all
// channels, and last_id falls back to that global id when the chat channel has
// no ring buffer yet. That fallback is what caused the 400-req/s spin, so the
// fake has to reproduce it or the regression test proves nothing.
const S = { seq: 0, buf: [], polls: 0, stallMs: 0 };
const emit = (data) => { S.seq += 1; S.buf.push({ id: S.seq, channel: 'chat', data }); };
const bump = (n = 1) => { S.seq += n; };            // another overlay's effect
const restart = () => { S.seq = 0; S.buf = []; };
const lastId = () => (S.buf.length ? S.buf[S.buf.length - 1].id : S.seq);

const srv = http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://x');
  const json = (o) => { const b = JSON.stringify(o);
    res.writeHead(200, { 'Content-Type': 'application/json', 'Content-Length': b.length }); res.end(b); };
  if (u.pathname === '/api/chat/backfill') {
    const n = Math.max(0, Math.min(100, parseInt(u.searchParams.get('n') || '25', 10) || 0));
    let evs = [], seen = 0;
    if (n) { for (let i = S.buf.length - 1; i >= 0; i--) { evs.push(S.buf[i]);
              if (S.buf[i].data.kind === 'msg' && ++seen >= n) break; } evs.reverse(); }
    return json({ messages: evs.map(e => e.data), last_id: lastId() });
  }
  if (u.pathname === '/api/effects/chat') {
    S.polls++;
    if (S.stallMs) await new Promise(r => setTimeout(r, S.stallMs));
    const since = parseInt(u.searchParams.get('since') || '0', 10) || 0;
    return json({ events: S.buf.filter(e => e.id > since), last_id: lastId() });
  }
  const rel = FILES[u.pathname];
  if (!rel) { res.writeHead(404); return res.end('nf'); }   // themes/fonts 404 on purpose
  const p = path.join(REPO, rel);
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'text/plain' });
  res.end(fs.readFileSync(p));
});
await new Promise(r => srv.listen(0, '127.0.0.1', r));
const BASE = 'http://127.0.0.1:' + srv.address().port;

const msg = (id, text, extra = {}) => ({
  v: 1, kind: 'msg', id, ts: Date.now(),
  user: { login: 'chatter' + id, name: 'Chatter' + id, id: 'u' + id, color: '#5CF2E3' },
  badges: [], flags: {}, bits: 0, action: false, reply_to: null,
  text, fragments: [{ type: 'text', text }], mentions: [], ...extra,
});

// CI images sometimes ship a chromium that doesn't match the pinned
// playwright. PW_CHROMIUM points at one that does; unset, playwright finds its
// own. Same escape hatch as stream-manager's tests/dashboard_layout.mjs.
const LAUNCH = { args: ['--no-sandbox'] };
if (process.env.PW_CHROMIUM) LAUNCH.executablePath = process.env.PW_CHROMIUM;
const browser = await chromium.launch(LAUNCH);
async function open(qs = '') {
  const page = await browser.newPage({ viewport: { width: 700, height: 800 } });
  const warns = [];
  page.on('console', m => { if (m.type() === 'warning') warns.push(m.text()); });
  await page.goto(BASE + '/chat.html' + qs, { waitUntil: 'domcontentloaded' });
  return { page, warns };
}
const items = (page) => page.$$eval('.pc-item:not(.pc-leaving)', ns => ns.map(n => ({
  id: n.getAttribute('data-id'), user: n.getAttribute('data-user'),
  login: n.getAttribute('data-login'), opacity: n.style.opacity,
  text: n.querySelector('.pc-body').textContent,
})));
async function waitFor(page, fn, ms = 6000) {
  const t0 = Date.now();
  for (;;) { if (await fn()) return true; if (Date.now() - t0 > ms) return false;
             await page.waitForTimeout(60); }
}
const count = (page, n) => waitFor(page, async () => (await items(page)).length === n);

// ── 1. the fade ramp must never dim the newest message ────────────────────
console.log('\n1. fade ramp (?max=1 rendered the only message at 30% opacity)');
for (const max of [1, 2, 3, 6]) {
  restart();
  for (let i = 1; i <= max; i++) emit(msg('m' + i, 'line ' + i));
  const { page } = await open('?max=' + max);
  await count(page, max);
  const got = await items(page);
  const newest = got[got.length - 1];
  ok(got.length === max, `max=${max}: ${max} on screen`);
  ok(newest.opacity === '' || Number(newest.opacity) === 1,
     `max=${max}: newest fully opaque (was "${newest.opacity}")`);
  if (max > 1) ok(Number(got[0].opacity) < 1, `max=${max}: oldest dimmed (${got[0].opacity})`);
  await page.close();
}

// ── 2. trim drops the oldest, keeps the newest ────────────────────────────
console.log('\n2. trim direction');
restart();
for (let i = 1; i <= 10; i++) emit(msg('t' + i, 'line ' + i));
{
  const { page } = await open('?max=4');
  await count(page, 4);
  ok((await items(page)).map(x => x.id).join(',') === 't7,t8,t9,t10', 'kept the last four');
  await page.close();
}

// ── 3. the poll must never spin ───────────────────────────────────────────
console.log('\n3. poll pacing (measured at 400 req/s before the lastId advance)');
restart();
bump(5);                                    // a shoutout fired; nobody has chatted
{
  const { page } = await open('?max=5');
  await page.waitForTimeout(600);
  S.polls = 0;
  bump(4);                                  // another effect: global id passes ours
  await page.waitForTimeout(3000);
  ok(S.polls <= 8, `${S.polls} polls in 3s with no chat events (must stay low)`);
  await page.close();
}

// ── 4. moderation ─────────────────────────────────────────────────────────
console.log('\n4. moderation');
restart();
emit(msg('a1', 'hello', { user: { login: 'nice', name: 'Nice', id: 'u1', color: '#fff' } }));
emit(msg('a2', 'a slur', { user: { login: 'baddie', name: 'Baddie', id: 'u2', color: '#fff' } }));
emit(msg('a3', 'more', { user: { login: 'baddie', name: 'Baddie', id: 'u2', color: '#fff' } }));
{
  const { page } = await open('?max=10');
  await count(page, 3);
  emit({ v: 1, kind: 'clearmsg', ts: Date.now(), target_id: 'a2', login: 'baddie', text: 'a slur' });
  ok(await waitFor(page, async () => !(await items(page)).some(x => x.id === 'a2')),
     'CLEARMSG removes its target');
  ok((await items(page)).length === 2, 'and only its target');

  emit({ v: 1, kind: 'clearchat', ts: Date.now(), user_id: 'u2', login: 'baddie', seconds: 600 });
  ok(await count(page, 1), 'CLEARCHAT with a user removes that user');
  ok((await items(page))[0].id === 'a1', 'and leaves everyone else');

  emit({ v: 1, kind: 'clearchat', ts: Date.now(), user_id: '', login: '', seconds: 0 });
  ok(await count(page, 0), 'CLEARCHAT with no target clears the room');
  await page.close();
}
console.log('\n5. a CLEARMSG with no target must not wipe the chatter');
restart();
emit(msg('c1', 'one', { user: { login: 'baddie', name: 'B', id: 'u9', color: '#fff' } }));
emit(msg('c2', 'two', { user: { login: 'baddie', name: 'B', id: 'u9', color: '#fff' } }));
{
  const { page } = await open('?max=10');
  await count(page, 2);
  emit({ v: 1, kind: 'clearmsg', ts: Date.now(), target_id: '', login: 'baddie', text: '' });
  await page.waitForTimeout(700);
  ok((await items(page)).length === 2, 'both messages stay (CLEARMSG deletes one message, not a history)');
  await page.close();
}

// ── 6. a deleted message must not come back on an OBS source refresh ──────
console.log('\n6. backfill replays moderation');
restart();
emit(msg('b1', 'keep me'));
emit(msg('b2', 'delete me'));
emit({ v: 1, kind: 'clearmsg', ts: Date.now(), target_id: 'b2', login: 'x', text: 'delete me' });
{
  const { page } = await open('?max=10');
  await waitFor(page, async () => (await items(page)).length >= 1);
  await page.waitForTimeout(500);
  const got = await items(page);
  ok(got.length === 1 && got[0].id === 'b1',
     'a deleted message does not return after a refresh (got ' + got.map(x => x.id) + ')');
  await page.close();
}
console.log('\n7. backfill counts messages, not events');
restart();
for (let i = 1; i <= 12; i++) {
  emit(msg('k' + i, 'line ' + i));
  if (i % 2 === 0) emit({ v: 1, kind: 'clearmsg', ts: Date.now(), target_id: 'gone' + i, login: 'x', text: '' });
}
{
  const { page } = await open('?max=20&backfill=8');
  await page.waitForTimeout(700);
  ok((await items(page)).length === 8, 'backfill=8 restored 8 messages despite interleaved mod events');
  await page.close();
}

// ── 8. Stream Manager restart ─────────────────────────────────────────────
console.log('\n8. restart resync');
restart();
for (let i = 1; i <= 40; i++) emit(msg('r' + i, 'pre-restart ' + i));
{
  const { page, warns } = await open('?max=5');
  await count(page, 5);
  ok((await items(page)).map(x => x.id).join(',') === 'r36,r37,r38,r39,r40', 'primed from the backfill');
  restart();                                 // ids start over at 1
  emit(msg('n1', 'post-restart 1'));
  ok(await waitFor(page, async () => (await items(page)).some(x => x.id === 'n1'), 40000),
     'post-restart messages arrive with no OBS refresh');
  ok(warns.some(w => /restarted/i.test(w)), 'and it says so in the console');
  ok(!(await items(page)).some(x => x.id.startsWith('r')), 'stale pre-restart messages cleared');
  await page.close();
}

// ── 9. a request that never answers ──────────────────────────────────────
console.log('\n9. stall watchdog');
restart();
emit(msg('s1', 'before the stall'));
{
  const { page } = await open('?max=5');
  await count(page, 1);
  S.stallMs = 120000;                        // never answers in time
  await page.waitForTimeout(1500);
  S.stallMs = 0;
  emit(msg('s2', 'after the stall'));
  ok(await waitFor(page, async () => (await items(page)).some(x => x.id === 's2'), 70000),
     'recovers from a hung request (aborts and re-polls)');
  await page.close();
}

// ── 10. untrusted input, /me, and no theme at all ────────────────────────
console.log('\n10. rendering');
restart();
const nasty = '<img src=x onerror="window.__pwned=1">';
emit(msg('x1', nasty, { fragments: [{ type: 'text', text: nasty }] }));
emit(msg('x2', 'waves', { action: true, fragments: [{ type: 'text', text: 'waves' }] }));
{
  const { page } = await open('?max=5');
  await count(page, 2);
  ok(await page.evaluate(() => window.__pwned === undefined), 'no script execution from message text');
  ok(await page.$eval('[data-id="x1"] .pc-body', n => n.textContent === '<img src=x onerror="window.__pwned=1">'),
     'markup renders as literal text');
  ok(await page.$eval('[data-id="x1"] .pc-body', n => n.querySelector('img') === null), 'no element injected');
  ok(await page.$eval('[data-id="x2"]', n => n.classList.contains('pc-action')), '/me gets .pc-action');
  ok(await page.$eval('[data-id="x2"] .pc-body', n => getComputedStyle(n).fontStyle === 'italic'),
     '/me italic with no theme loaded');
  const px = await page.$eval('[data-id="x1"] .pc-body', n => parseFloat(getComputedStyle(n).fontSize));
  ok(px === 30, 'body still 30px with the theme 404ing (got ' + px + ')');
  const w = await page.$eval('[data-id="x1"] .pc-name', n => n.getBoundingClientRect().width);
  ok(w > 60, 'short usernames not ellipsised (' + Math.round(w) + 'px)');
  await page.close();
}

await browser.close(); srv.close();
console.log(`\n${fail ? '✗' : '✓'} chat overlay: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
