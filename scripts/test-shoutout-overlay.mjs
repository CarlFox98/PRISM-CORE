/**
 * Headless test for the PRISM shoutout overlay.
 *
 * Runs widgets/prism-shoutout.html's script in a stubbed DOM with a CONTROLLED
 * clock, and drives it through window.PRISM_SHOUTOUT. Timers are the point:
 * cards are a state machine over setTimeout, and an earlier version could
 * orphan a hold timer into the following card.
 *
 *   node scripts/test-shoutout-overlay.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, '..', 'widgets', 'prism-shoutout.html'), 'utf8');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

/* ---------- a controllable clock ---------- */
let now = 0, nextId = 1;
const timers = new Map();
function setTimeoutStub(fn, ms) {
  const id = nextId++;
  timers.set(id, { fn, at: now + (Number(ms) || 0) });
  return id;
}
function clearTimeoutStub(id) { timers.delete(id); }
function advance(ms) {
  const target = now + ms;
  for (;;) {
    let due = null;
    for (const [id, t] of timers) {
      if (t.at <= target && (due === null || t.at < timers.get(due).at)) due = id;
    }
    if (due === null) break;
    const t = timers.get(due);
    timers.delete(due);
    now = t.at;
    t.fn();
  }
  now = target;
}

/* ---------- the smallest DOM the overlay needs ---------- */
function el() {
  const node = {
    style: {}, textContent: '', innerHTML: '', src: '', className: '',
    scrollWidth: 0, clientWidth: 1000, offsetWidth: 0, children: [],
    classList: {
      _s: new Set(),
      add(...c) { c.forEach(x => this._s.add(x)); },
      remove(...c) { c.forEach(x => this._s.delete(x)); },
      contains(c) { return this._s.has(c); },
    },
    appendChild(c) { node.children.push(c); return c; },
    removeAttribute() {}, setAttribute() {}, remove() {},
    addEventListener() {}, pause() {}, play() { return { catch() {} }; },
    querySelector() { return null; },
  };
  return node;
}
const sandbox = {
  console,
  document: { getElementById: el, createElement: el },
  requestAnimationFrame(fn) { fn(); },
  setTimeout: setTimeoutStub, clearTimeout: clearTimeoutStub,
  setInterval() { return 0; }, clearInterval() {},
  Date: { now: () => now },
  location: { hostname: 'test', search: '' },
  URLSearchParams, JSON, Math,
  WebSocket: class { constructor() { this.readyState = 0; } send() {} close() {} },
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

const api = sandbox.window.PRISM_SHOUTOUT;
if (!api) { console.error('FAIL: overlay exposed no test hook'); process.exit(1); }

let failed = 0;
const check = (label, cond) => {
  console.log((cond ? '  ok   ' : '  FAIL ') + label);
  if (!cond) failed++;
};
const card = (login, hold = 8000) => ({ login, name: login, hold, noclipHold: 3000 });
const reset = () => { api.control('clear'); advance(5000); };

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
console.log('\ndying clip');
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

/* ---------- a malformed card must not strand the overlay ---------- */
console.log('\nrobustness');
reset();
api.enqueue({ login: 'ok-before', name: 'ok-before', hold: 5000 });
advance(5000 + 700);
api.enqueue({ login: {}, name: {}, hold: 5000 });   // nonsense payload
advance(700);
api.enqueue(card('after', 5000));
check('a malformed card does not strand the overlay', api.state().busy === true);

console.log(failed ? `\nFAILURES: ${failed}` : '\noverlay: all checks passed');
process.exit(failed ? 1 : 0);
