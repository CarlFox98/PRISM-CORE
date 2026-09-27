// PRISM config/scene integrity test (no dependencies).
// Verifies prism-config.js is well-formed and every engine scene loads the
// config before the engine — the invariant the socials refactor depends on.
import fs from 'node:fs';

const url = (p) => new URL(p, import.meta.url);
let ok = true;
const fail = (m) => { console.error('  ✗ ' + m); ok = false; };

// 1) Load config the way the browser would (config.js sets window.PRISM_CONFIG).
const g = {};
new Function('window', fs.readFileSync(url('../core/prism-config.js'), 'utf8'))(g);
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
const engineSrc = fs.readFileSync(url('../core/prism-engine.js'), 'utf8');
const iconKeys = [...engineSrc.matchAll(/^\s*'([a-z0-9.\-]+)':\s*'M/gim)].map(m => m[1]);
if (iconKeys.length === 0) fail('no inline brand icons found in prism-engine.js');
(cfg?.socials || []).forEach((s, i) => {
  if (!s.svg && !iconKeys.includes(s.icon)) {
    fail(`socials[${i}] ("${s.icon}") has no inline icon — add one to ICONS or give it an svg path`);
  }
});

// 3) Every engine scene must load prism-config.js BEFORE prism-engine.js.
const scenes = [
  'scenes/prism-be-right-back.html', 'scenes/prism-stream-ending.html', 'scenes/prism-starting-soon.html',
  'scenes/prism-tech-difficulties.html', 'scenes/prism-wallpaper.html',
];
for (const f of scenes) {
  const h = fs.readFileSync(url('../' + f), 'utf8');
  const c = h.indexOf('prism-config.js');
  const e = h.indexOf('prism-engine.js');
  if (c < 0) fail(`${f}: does not load prism-config.js`);
  else if (e < 0) fail(`${f}: does not load prism-engine.js`);
  else if (c > e) fail(`${f}: loads engine before config`);
}

// 4) 2.0 sets (themes/<name>/): every canonical scene exists, anything that
//    uses a core module loads the config first, and every local file a scene
//    links to exists — a wrong ../../ path would 404 inside OBS silently.
const THEME_SCENES = ['starting-soon', 'be-right-back', 'stream-ending', 'tech-difficulties',
  'webcam-frame', 'wallpaper', 'chat-preview', 'thank-you', 'gameplay'];
const themesDir = url('../themes/');
const themes = fs.existsSync(themesDir)
  ? fs.readdirSync(themesDir, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name) : [];
let themeScenes = 0;
for (const t of themes) {
  for (const w of ['shoutout-theme.css', 'nowplaying-theme.css', 'chat-theme.css']) {
    if (!fs.existsSync(url(`../themes/${t}/${w}`))) fail(`themes/${t}/${w}: missing (a widget reads it from the active set, so the set must ship one)`);
  }
  for (const sc of THEME_SCENES) {
    const rel = `themes/${t}/${sc}.html`;
    if (!fs.existsSync(url('../' + rel))) { fail(`${rel}: missing (every set needs all ${THEME_SCENES.length} scenes)`); continue; }
    themeScenes++;
    const h = fs.readFileSync(url('../' + rel), 'utf8');
    const c = h.indexOf('prism-config.js');
    for (const mod of ['prism-engine.js', 'prism-countdown.js', 'prism-techcheck.js', 'prism-wallpaper.js', 'prism-thankyou.js']) {
      const m = h.indexOf(mod);
      if (m >= 0 && (c < 0 || c > m)) fail(`${rel}: loads ${mod} without prism-config.js before it`);
    }
    for (const [, ref] of h.matchAll(/(?:src|href)="([^"#?:]+\.(?:js|css|json))"/g)) {
      if (!fs.existsSync(new URL(ref, url('../' + rel)))) fail(`${rel}: links to missing file ${ref}`);
    }
  }
}

// 5) chat overlay: the three deploy sources exist, holo has a real skin, and
//    every relative reference in the page resolves once deploy-chat.py has
//    flattened chat/ and core/ into one folder.
const CHAT_SRC = {
  'chat/prism-chat.html': 'chat.html',
  'core/prism-chat.js': 'prism-chat.js',
  'core/prism-chat-base.css': 'prism-chat-base.css',
};
for (const src of Object.keys(CHAT_SRC)) {
  if (!fs.existsSync(url('../' + src))) fail(`${src}: missing (deploy-chat.py copies it into stream-manager's static/chat/)`);
}
if (!fs.existsSync(url('../widgets/theme-holo-chat.css'))) fail('widgets/theme-holo-chat.css: missing (holo\'s chat skin)');
const chatPage = url('../chat/prism-chat.html');
let chatRefs = 0;
if (fs.existsSync(chatPage)) {
  const h = fs.readFileSync(chatPage, 'utf8');
  for (const [, ref] of h.matchAll(/(?:src|href)="([^"#?:]+\.(?:js|css))"/g)) {
    if (ref.startsWith('/')) continue;           // served by stream-manager, not from the repo
    chatRefs++;
    // The page sits beside its assets only AFTER the deploy flattens them.
    const flat = ['chat/', 'core/'].some(d => fs.existsSync(url('../' + d + ref)));
    if (!flat) fail(`chat/prism-chat.html: links to ${ref}, which is in neither chat/ nor core/`);
  }
  if (!h.includes('/overlays/PRISM/fonts/prism-fonts.css')) fail('chat/prism-chat.html: does not load the vendored fonts');
}
// A theme re-read every 60s must never @import fonts (the 2.0.2 bug).
for (const f of [...themes.map(t => `themes/${t}/chat-theme.css`), 'widgets/theme-holo-chat.css']) {
  const p = url('../' + f);
  if (fs.existsSync(p) && /^\s*@import/m.test(fs.readFileSync(p, 'utf8'))) {
    fail(`${f}: @import in a theme re-read every 60s re-downloads on every poll`);
  }
}

// 6) Chat guards earned the hard way — each of these was a real defect.
{
  const js = fs.readFileSync(url('../core/prism-chat.js'), 'utf8');
  const base = fs.readFileSync(url('../core/prism-chat-base.css'), 'utf8');

  // The fade ramp must be capped below the newest message, or ?max=1 renders
  // the only message on screen at 30% opacity.
  if (!/Math\.min\(CFG\.fade\.length,\s*n\s*-\s*1\)/.test(js)) {
    fail('prism-chat.js: the fade ramp is not capped at n-1 — the newest message can be dimmed');
  }
  // A hung fetch has no timeout of its own: without the abort, one half-open
  // request freezes chat for the rest of the stream.
  if (!js.includes('AbortController')) {
    fail('prism-chat.js: no fetch watchdog — a hung poll would never recover');
  }
  // Effect ids restart at 1, so the overlay must notice last_id going backwards.
  if (!/function restarted\(/.test(js)) {
    fail('prism-chat.js: no restart detection — chat dies silently if Stream Manager restarts');
  }
  // The backfill must route through handle(), or a CLEARMSG still in the ring
  // buffer is ignored and a deleted message comes back on an OBS refresh.
  if (!/\(d\.messages \|\| \[\]\)\.forEach\(handle\)/.test(js)) {
    fail('prism-chat.js: backfill does not replay moderation events — deleted messages would return');
  }
  if (!/m\.kind === "clearmsg"/.test(js) || !/m\.kind === "clearchat"/.test(js)) {
    fail('prism-chat.js: no CLEARMSG/CLEARCHAT handling — deleted messages stay on stream');
  }
  // Nothing in the message path may touch innerHTML: chat is untrusted input
  // and this page shares an origin with the dashboard's control endpoints.
  // Comments are stripped first — the file explains this rule in prose, and
  // matching its own comment made the guard fire on correct code.
  const jsCode = js.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  if (/\binnerHTML\b|\bouterHTML\b|insertAdjacentHTML|document\.write/.test(jsCode)) {
    fail('prism-chat.js: uses innerHTML — chat text is untrusted and same-origin with the dashboard');
  }
  if (!/\.pc-action\b/.test(base)) fail('prism-chat-base.css: no .pc-action rule — /me would render upright');
  // The base layer has to stand alone: a theme failing to load has happened.
  for (const v of ['--pc-msg-size', '--pc-name-size', '--pc-ink', '--pc-panel', '--pc-accent']) {
    // The DECLARATION, not a var() reference: a plain includes() was satisfied
    // by the usages and passed a file whose :root no longer defined the token.
    if (!new RegExp(v + '\\s*:\\s*[^;)\\s]').test(base)) {
      fail(`prism-chat-base.css: ${v} is not declared in the fallback palette`);
    }
  }
  // Structure belongs to the base layer, not to a skin.
  for (const f of [...themes.map(t => `themes/${t}/chat-theme.css`), 'widgets/theme-holo-chat.css']) {
    const pth = url('../' + f);
    if (!fs.existsSync(pth)) continue;
    const css = fs.readFileSync(pth, 'utf8');
    if (/#pc-feed\s*\{[^}]*(justify-content|flex-direction)/.test(css)) {
      fail(`${f}: a skin must not set the column's structure — that is the base layer's job`);
    }
    if (/animation:[^;]*\bboth\b/.test(css)) {
      fail(`${f}: animation fill-mode 'both' pins opacity at 1 and kills the fade ramp — use 'backwards'`);
    }
  }
}

console.log(ok
  ? `✓ config OK — ${cfg.socials.length} socials (all with inline icons), ${scenes.length} scenes verified (config→engine order), ${themes.length} 2.0 sets / ${themeScenes} scenes verified, chat overlay + ${chatRefs} refs OK`
  : '✗ integrity checks failed');
process.exit(ok ? 0 : 1);
