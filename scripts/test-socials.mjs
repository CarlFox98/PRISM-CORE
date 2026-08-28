// PRISM config/scene integrity test (no dependencies).
// Verifies prism-config.js is well-formed and every engine scene loads the
// config before the engine — the invariant the socials refactor depends on.
import fs from 'node:fs';

const url = (p) => new URL(p, import.meta.url);
let ok = true;
const fail = (m) => { console.error('  ✗ ' + m); ok = false; };

// 1) Load config the way the browser would (config.js sets window.PRISM_CONFIG).
const g = {};
new Function('window', fs.readFileSync(url('../prism-config.js'), 'utf8'))(g);
const cfg = g.PRISM_CONFIG;

if (!cfg) fail('prism-config.js did not define window.PRISM_CONFIG');
if (!cfg || !cfg.channel) fail('config.channel is missing');
if (!cfg || !Array.isArray(cfg.socials) || cfg.socials.length === 0) fail('config.socials is empty');
(cfg?.socials || []).forEach((s, i) => {
  if (!s.label) fail(`socials[${i}] missing label`);
  if (!s.icon)  fail(`socials[${i}] missing icon`);
});

// 2) Every configured social must have an inline icon (or its own svg path),
//    so nothing silently falls back to the network favicon service.
const engineSrc = fs.readFileSync(url('../prism-engine.js'), 'utf8');
const iconKeys = [...engineSrc.matchAll(/^\s*'([a-z0-9.\-]+)':\s*'M/gim)].map(m => m[1]);
if (iconKeys.length === 0) fail('no inline brand icons found in prism-engine.js');
(cfg?.socials || []).forEach((s, i) => {
  if (!s.svg && !iconKeys.includes(s.icon)) {
    fail(`socials[${i}] ("${s.icon}") has no inline icon — add one to ICONS or give it an svg path`);
  }
});

// 3) Every engine scene must load prism-config.js BEFORE prism-engine.js.
const scenes = [
  'prism-be-right-back.html', 'prism-stream-ending.html', 'prism-starting-soon.html',
  'prism-tech-difficulties.html', 'prism-wallpaper.html',
];
for (const f of scenes) {
  const h = fs.readFileSync(url('../' + f), 'utf8');
  const c = h.indexOf('prism-config.js');
  const e = h.indexOf('prism-engine.js');
  if (c < 0) fail(`${f}: does not load prism-config.js`);
  else if (e < 0) fail(`${f}: does not load prism-engine.js`);
  else if (c > e) fail(`${f}: loads engine before config`);
}

console.log(ok
  ? `✓ config OK — ${cfg.socials.length} socials (all with inline icons), ${scenes.length} scenes verified (config→engine order)`
  : '✗ integrity checks failed');
process.exit(ok ? 0 : 1);
