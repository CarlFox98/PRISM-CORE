// Chat-preview behaviour test.
//
// Builds all three sets the way a deploy does, then renders each set's
// chat-preview.html in a real browser and checks it is showing the REAL chat
// overlay: the .pc-* DOM core/prism-chat.js builds, under prism-chat-base.css
// plus that set's chat-theme.css.
//
// This exists because the source-level guards in test-socials.mjs check that
// the fixes are still *spelled* right, and for two releases every set shipped a
// chat-preview that linked a retired third-party stopgap and had no DOM in
// common with the overlay — while every file it referenced existed, so nothing
// noticed. Files existing is not the same as a page working.
//
//   npm i -D playwright && npx playwright install chromium
//   node scripts/test-chat-preview.mjs
//
// Skips cleanly (exit 0) when playwright is absent, so it never blocks anyone.
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

let chromium;
try { ({ chromium } = await import('playwright')); }
catch { console.log('· chat preview test skipped (playwright not installed)'); process.exit(0); }

const REPO = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
               '.json': 'application/json', '.woff2': 'font/woff2' };
const SETS = ['prism-holo', 'prism-signal', 'prism-soft'];

const LAUNCH = { args: ['--no-sandbox'] };
if (process.env.PW_CHROMIUM) LAUNCH.executablePath = process.env.PW_CHROMIUM;

let pass = 0, fail = 0;
const ok = (c, why) => { if (c) { pass++; console.log('  ok   ' + why); }
                         else { fail++; console.log('  FAIL ' + why); } };

const out = fs.mkdtempSync(path.join(os.tmpdir(), 'prism-sets-'));
for (const s of SETS) {
  execFileSync('python3', [path.join(REPO, 'scripts/build-obs-set.py'),
                           '--set', s, '--out', path.join(out, s)], { stdio: 'ignore' });
}

for (const set of SETS) {
  const ROOT = path.join(out, set);
  const srv = http.createServer((req, res) => {
    const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\//, '') || 'index.html';
    const f = path.join(ROOT, rel);
    if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) {
      res.writeHead(404); return res.end('nf');
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'text/plain' });
    res.end(fs.readFileSync(f));
  });
  await new Promise(r => srv.listen(0, '127.0.0.1', r));
  const base = 'http://127.0.0.1:' + srv.address().port;

  const browser = await chromium.launch(LAUNCH);
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errs = [], missed = [];
  page.on('pageerror', e => errs.push(e.message));
  page.on('response', r => { if (r.status() >= 400) missed.push(r.url().replace(base, '')); });
  await page.goto(base + '/chat-preview.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);

  console.log(`\n${set} / chat-preview.html`);

  // A 2.0 set copies its whole theme folder, which is how the retired sheets
  // kept reaching overlays/active/ on a live stream. THEME_SKIP is what stops
  // that, and this is the assertion that keeps THEME_SKIP honest.
  const shipped = fs.readdirSync(ROOT)
    .filter(f => /^prism-chat-(signal|soft|holo-iridescent)\.css$/.test(f));
  ok(shipped.length === 0,
     `ships no retired chat sheet${shipped.length ? ' (found ' + shipped.join(', ') + ')' : ''}`);
  ok(errs.length === 0, `no page errors${errs.length ? ': ' + errs[0] : ''}`);

  // A partial local checkout can be missing font subsets; that is not this
  // test's business. Anything else 404ing is.
  const fonts = missed.filter(u => u.startsWith('/fonts/'));
  const real = missed.filter(u => !u.startsWith('/fonts/'));
  if (fonts.length) console.log(`  ·    (${fonts.length} font file(s) absent in this checkout — ignored)`);
  ok(real.length === 0, `nothing 404s${real.length ? ': ' + real.slice(0, 3).join(', ') : ''}`);

  const items = await page.$$eval('.pc-item', ns => ns.length);
  ok(items >= 4, `renders the real .pc-item DOM (${items} messages)`);
  ok(await page.$$eval('[class*="chat__"]', ns => ns.length) === 0,
     'no third-party-era markup left in the preview');
  ok(await page.$$eval('.pc-newest', ns => ns.length) === 1,
     'exactly one .pc-newest, as the renderer guarantees');

  // The skin must actually be reaching the card. A theme may paint with a
  // background-color OR with gradients (holo does the latter, so
  // backgroundColor reads as transparent), and may shape with a radius OR a
  // clip-path (Signal's notched panel is its documented look, radius 0).
  const st = await page.$eval('.pc-inner', n => {
    const c = getComputedStyle(n);
    return { bg: c.backgroundColor, img: c.backgroundImage,
             radius: c.borderTopLeftRadius, clip: c.clipPath };
  });
  ok(st.bg !== 'rgba(0, 0, 0, 0)' || st.img !== 'none',
     `chat-theme.css paints the card (${st.bg !== 'rgba(0, 0, 0, 0)' ? st.bg : 'gradient'})`);
  ok(parseFloat(st.radius) > 0 || (st.clip && st.clip !== 'none'),
     `and shapes it (${parseFloat(st.radius) > 0 ? 'radius ' + st.radius : 'clip-path'})`);

  const nameFont = await page.$eval('.pc-name', n => getComputedStyle(n).fontFamily);
  ok(/Chakra|Sora|Grotesk|JetBrains|Nunito/i.test(nameFont),
     `a PRISM family is applied (${nameFont.split(',')[0]})`);

  // The base layer owns sizing so a skin cannot shrink chat by accident.
  const size = await page.$eval('.pc-body', n => getComputedStyle(n).fontSize);
  ok(parseFloat(size) >= 24, `message size comes from the base layer (${size})`);

  await browser.close();
  srv.close();
}

fs.rmSync(out, { recursive: true, force: true });
console.log(`\n${fail ? '✗' : '✓'} chat preview: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
