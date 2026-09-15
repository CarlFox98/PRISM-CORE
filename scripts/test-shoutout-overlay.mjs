/**
 * Headless conformance test for the shoutout overlay.
 *
 * Two implementations exist — this repo's hosted card and the copy Stream
 * Manager serves — and they must behave identically. Run the same spec against
 * both:
 *
 *   node scripts/test-shoutout-overlay.mjs
 *   node scripts/test-shoutout-overlay.mjs <path-to-other-overlay.html>
 *
 * Runs widgets/prism-shoutout.html's script in a stubbed DOM with a CONTROLLED
 * clock, and drives it through window.PRISM_SHOUTOUT.
 *
 * Timers and playback are the point. Cards are a state machine over setTimeout,
 * and the ways a clip can die are the ways the card gets stuck: an earlier
 * version could orphan a hold timer into the following card, and a starved
 * <video> (which fires no 'error' and no 'ended') used to freeze on screen with
 * the OBS duck still engaged.
 *
 *   node scripts/test-shoutout-overlay.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
// Default: this repo's overlay. Pass a path to run the same spec against another
// implementation — Stream Manager serves its own copy of this card, and the two
// have to behave identically or the split silently drifts.
const target = process.argv[2]
  ? resolve(process.argv[2])
  : join(here, '..', 'widgets', 'prism-shoutout.html');
const html = readFileSync(target, 'utf8');
console.log('target: ' + target + '\n');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

/* ---------- a controllable clock (timeouts AND intervals) ---------- */
let now = 0, nextId = 1;
const timers = new Map();
const setTimeoutStub = (fn, ms) => {
  const id = nextId++;
  timers.set(id, { fn, at: now + (Number(ms) || 0), every: null });
  return id;
};
const setIntervalStub = (fn, ms) => {
  const every = Math.max(1, Number(ms) || 1);
  const id = nextId++;
  timers.set(id, { fn, at: now + every, every });
  return id;
};
const clearTimer = (id) => { timers.delete(id); };
function advance(ms) {
  const target = now + ms;
  for (;;) {
    let due = null, dueAt = Infinity;
    for (const [id, t] of timers) if (t.at <= target && t.at < dueAt) { due = id; dueAt = t.at; }
    if (due === null) break;
    const t = timers.get(due);
    now = t.at;
    if (t.every) t.at = now + t.every; else timers.delete(due);
    t.fn();
  }
  now = target;
}

/* ---------- enough DOM to run a <video> through its states ---------- */
function makeEl(tag) {
  const node = {
    tagName: (tag || 'div').toUpperCase(),
    style: {}, textContent: '', innerHTML: '', src: '', className: '',
    scrollWidth: 0, clientWidth: 1000, offsetWidth: 0,
    currentTime: 0, ended: false, paused: false, volume: 1, muted: true,
    children: [], parentNode: null, _l: {},
    classList: {
      _s: new Set(),
      add(...c) { c.forEach(x => this._s.add(x)); },
      remove(...c) { c.forEach(x => this._s.delete(x)); },
      contains(c) { return this._s.has(c); },
    },
    appendChild(c) { node.children.push(c); c.parentNode = node; return c; },
    remove() {
      const p = node.parentNode;
      if (p) { const i = p.children.indexOf(node); if (i >= 0) p.children.splice(i, 1); }
      node.parentNode = null;
    },
    removeAttribute() {}, setAttribute() {},
    addEventListener(t, fn) { (node._l[t] = node._l[t] || []).push(fn); },
    dispatch(t) { (node._l[t] || []).slice().forEach(fn => fn()); },
    pause() { node.paused = true; },
    play() { return Promise.resolve(); },
    querySelector(sel) {
      for (const c of node.children) {
        if (sel === 'video' && c.tagName === 'VIDEO') return c;
        if (sel === 'iframe' && c.tagName === 'IFRAME') return c;
        if (sel === 'img.thumb' && c.tagName === 'IMG' && c.className === 'thumb') return c;
        if (sel === 'img.offline' && c.tagName === 'IMG' && c.className === 'offline') return c;
      }
      return null;
    },
  };
  return node;
}
const byId = new Map();
const getElementById = (id) => {
  if (!byId.has(id)) byId.set(id, makeEl('div'));
  return byId.get(id);
};

/* The service has to learn when a clip actually starts and stops. The two
   overlays report it differently — one over the WebSocket, one by POSTing to
   /api/shoutout/clip — so record either. The spec cares that the report
   happens, not how it travels. */
const sent = [];
const record = (raw) => { try { sent.push(JSON.parse(raw)); } catch { sent.push(raw); } };
class FakeSocket {
  constructor() { this.readyState = 1; }
  send(m) { record(m); }
  close() {}
}
const fakeFetch = (url, opts) => {
  if (String(url).includes('/api/shoutout/clip') && opts && opts.body) record(opts.body);
  return Promise.resolve({ json: () => ({ last_id: 0, events: [] }) });
};

const sandbox = {
  console,
  document: { getElementById, createElement: makeEl },
  requestAnimationFrame(fn) { fn(); },
  setTimeout: setTimeoutStub, clearTimeout: clearTimer,
  setInterval: setIntervalStub, clearInterval: clearTimer,
  Date: { now: () => now },
  location: { hostname: 'test', search: '' },
  URLSearchParams, JSON, Math,
  WebSocket: FakeSocket,
  fetch: fakeFetch,
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

const api = sandbox.window.PRISM_SHOUTOUT;
if (!api) { console.error('FAIL: overlay exposed no test hook'); process.exit(1); }

const clipEl = getElementById('clip');
const video = () => clipEl.querySelector('video');
// true while the overlay has told the service a clip is playing
const clipReportedPlaying = () => {
  let on = false;
  for (const m of sent) { if (m.type === 'clipstart') on = true; if (m.type === 'clipend') on = false; }
  return on;
};

let failed = 0;
const check = (label, cond) => {
  console.log((cond ? '  ok   ' : '  FAIL ') + label);
  if (!cond) failed++;
};
const card = (login, hold = 8000, extra = {}) =>
  ({ login, name: login, hold, noclipHold: 3000, ...extra });
const withClip = (login, hold = 30000) =>
  card(login, hold, { clip: 'https://cdn.example/clip.mp4', thumb: '' });
const reset = () => { api.control('clear'); advance(5000); sent.length = 0; };

/* ---------- queue rules ---------- */
console.log('queue');
api.enqueue(card('alpha'));
check('the first card goes straight on screen', api.state().busy === true);
check('nothing is left waiting', api.state().queued === 0);
check('the on-screen login is tracked', api.state().onScreen === 'alpha');

api.enqueue(card('alpha'));
check('the login already on screen is not re-queued', api.state().queued === 0);

api.enqueue(card('bravo'));
check('a different login queues behind it', api.state().queued === 1);
api.enqueue(card('BRAVO'));
check('a queued login is not duplicated (case-insensitive)', api.state().queued === 1);

['c', 'd', 'e', 'f', 'g'].forEach(n => api.enqueue(card(n)));
check('the queue is capped at CFG.maxQueue', api.state().queued === 5);

api.control('clear');
check('clear empties the queue', api.state().queued === 0);
advance(5000);
check('clear also retires the card and frees the overlay', api.state().busy === false);

/* ---------- the card actually ends ---------- */
console.log('\ntiming');
reset();
api.enqueue(card('solo', 8000));
advance(7000);
check('the card is still up before its hold elapses', api.state().busy === true);
advance(1000 + 700);
check('the card retires after hold + the exit fade', api.state().busy === false);
check('onScreen is cleared on exit', api.state().onScreen === '');

reset();
api.enqueue(card('one', 20000));
api.enqueue(card('two', 20000));
advance(20000 + 700);
check('the queued card takes over', api.state().onScreen === 'two');
check('the queue is drained', api.state().queued === 0);

reset();
api.enqueue(card('long', 30000));
advance(2000);
api.control('skip');
advance(700);
check('skip retires the card early', api.state().busy === false);

/* ---------- the regression: a dying clip during the exit window ---------- */
console.log('\ndying clip during the exit window');
reset();
api.enqueue(card('first', 30000));
advance(2000);
api.control('skip');          // exit window opens, busy is still true
api.shortenHold();            // the <video> errors mid-fade
advance(700);                 // the exit completes
api.enqueue(card('second', 30000));
check('the next card starts', api.state().onScreen === 'second');
advance(4000);                // past where the orphaned timer would have fired
check('the next card is NOT cut short by the previous card timer',
      api.state().busy === true && api.state().onScreen === 'second');

reset();
api.enqueue(card('dying', 30000));
advance(1000);
api.shortenHold();            // clip dies normally, mid-card
advance(3000 + 700);
check('a dying clip shortens its own card to noclipHold', api.state().busy === false);

/* ---------- freezes: a starved <video> fires no 'error' and no 'ended' ---------- */
console.log('\nfrozen clip');
reset();
api.enqueue(withClip('frozen', 30000));
const v1 = video();
check('a card with a clip creates a video element', !!v1);
v1.dispatch('playing');
check('playback start is reported to the service', clipReportedPlaying() === true);

// play normally for a few seconds, then stop advancing currentTime
for (let i = 1; i <= 4; i++) { v1.currentTime = i; advance(1000); }
check('healthy playback is not mistaken for a stall',
      api.state().busy === true && !!video());

// stallMs is 3000 and the watchdog ticks every 500ms, so detection lands
// within ~3.5s of the freeze
advance(4500);                // currentTime frozen past CFG.stallMs
check('a stalled clip is detected', !video());
check('a stall is reported as clip-end', clipReportedPlaying() === false);
advance(3000 + 700);
check('the card ends early instead of holding the frozen frame',
      api.state().busy === false);

reset();
api.enqueue(withClip('neverstarts', 30000));
const v2 = video();
advance(8500);                // 'playing' never fires, past CFG.startMs
check('a clip that never starts is given up on', !video());
advance(3000 + 700);
check('and its card does not sit for the full runtime', api.state().busy === false);

reset();
api.enqueue(withClip('healthy', 12000));
const v3 = video();
v3.dispatch('playing');
for (let i = 1; i <= 10; i++) { advance(1000); v3.currentTime = i; }
check('a clip that plays through is left alone', !!video() && clipReportedPlaying() === true);
v3.ended = true;
v3.dispatch('ended');
check('ending normally is reported as clip-end', clipReportedPlaying() === false);
advance(2000 + 700);
check('the card then retires on its own schedule', api.state().busy === false);

reset();
api.enqueue(withClip('errored', 30000));
const v4 = video();
v4.dispatch('playing');
advance(1000);
v4.onerror();                 // the path that already worked, still works
check('an outright error still recovers', !video() && clipReportedPlaying() === false);
advance(3000 + 700);
check('and shortens the card', api.state().busy === false);

/* ---------- a malformed card must not strand the overlay ---------- */
console.log('\nrobustness');
reset();
api.enqueue(card('ok-before', 5000));
advance(5000 + 700);
api.enqueue({ login: {}, name: {}, hold: 5000 });   // nonsense payload
advance(700);
api.enqueue(card('after', 5000));
check('a malformed card does not strand the overlay', api.state().busy === true);

console.log(failed ? `\nFAILURES: ${failed}` : '\noverlay: all checks passed');
process.exit(failed ? 1 : 0);
