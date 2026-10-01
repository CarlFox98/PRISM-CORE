/* ============================================================
   PRISM 2.0 — chat preview feed (preview scenes only)

   Draws synthetic messages into #pc-feed using the SAME DOM the real
   renderer builds (core/prism-chat.js: .pc-item > .pc-inner > .pc-meta /
   .pc-reply / .pc-body), so a set's chat-theme.css can be judged in a
   browser without Stream Manager running.

   It used to emit the retired third-party widget's markup instead, so the
   preview showed something the overlay has not used since 2.1.0 — and
   chat-theme.css, the sheet that actually ships, was previewed by nothing.
   See docs/CHANGELOG.md 2.2.2. (The old class names are deliberately not
   written out here: scripts/test-socials.mjs greps this file for them, and
   a guard that matches its own explanation catches nothing.)

   Mirrors prism-chat.js's CFG where it is visible: max 6 on screen, the
   [0.72, 0.50, 0.30] fade ramp, newest last and never dimmed, and
   .pc-newest on the newest item. It deliberately cycles through the variant
   classes (first-chatter, mod, vip, broadcaster, cheer, mention, reply,
   /me) because seeing those styled is the point of a preview.

   Tunables: window.PRISM_CHATDEMO = { colors:['#..'], max:6, every:2600 }

   Builds nodes rather than markup strings, same rule as the real renderer,
   so the repo-wide guard in scripts/test-socials.mjs stays true.
   ============================================================ */
(function () {
  "use strict";

  var O = window.PRISM_CHATDEMO || {};
  var C = O.colors || ['#57F2E4', '#6C8BFF', '#B983FF', '#FF7ACB', '#FFD86B'];
  var MAX = O.max || 6;
  var EVERY = O.every || 2600;
  var FADE = [0.72, 0.50, 0.30];

  function c(i) { return C[((i % C.length) + C.length) % C.length]; }

  function badge(col) {
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' width='18' height='18'>" +
      "<rect width='18' height='18' rx='4' fill='" + col + "'/>" +
      "<circle cx='9' cy='9' r='3.4' fill='rgba(255,255,255,.85)'/></svg>");
  }

  // One entry per thing a theme has to style. flags map to the pc- classes
  // prism-chat.js sets from the chat contract's flags/bits/action fields.
  var MSGS = [
    { u: 'Nova_Rider',  b: 1, m: 'the new overlay goes so hard' },
    { u: 'pixel_witch', b: 2, m: 'okay that countdown font is perfect', flags: ['pc-mod'] },
    { u: 'grumbot',     b: 0, m: 'chat is readable on my phone now' },
    { u: 'lumen',       b: 0, m: 'hi hi, just got here — what did I miss?', flags: ['pc-first'] },
    { u: 'Aria.exe',    b: 1, m: 'gg on that last run!!', mention: '@NeoTheFox98' },
    { u: 'deltaWolf',   b: 1, m: 'x100 for the fox', flags: ['pc-cheer'] },
    { u: 'K3RN3L',      b: 2, m: 'the shoutout card slaps', flags: ['pc-vip'] },
    { u: 'NeoTheFox98', b: 2, m: 'thank you!! 💜', flags: ['pc-broadcaster'] },
    { u: 'soft_static', b: 1, m: 'followed! love the vibes in here',
      reply: { name: 'lumen', text: 'what did I miss?' } },
    { u: 'pixel_witch', b: 2, m: 'waves at the fox', flags: ['pc-action'] }
  ];

  var feed = document.getElementById('pc-feed');
  if (!feed) return;

  var n = 0;

  function el(tag, cls) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    return e;
  }

  function build(d) {
    var item = el('div', 'pc-item');
    (d.flags || []).forEach(function (f) { item.classList.add(f); });
    if (d.mention) item.classList.add('pc-mention');
    item.style.setProperty('--user-color', c(n + 1));

    var inner = el('div', 'pc-inner');

    var meta = el('div', 'pc-meta');
    for (var i = 0; i < (d.b || 0); i++) {
      var img = el('img', 'pc-badge');
      img.src = badge(c(n + i));
      img.alt = '';
      meta.appendChild(img);
    }
    var name = el('span', 'pc-name');
    name.textContent = d.u;
    meta.appendChild(name);
    inner.appendChild(meta);

    if (d.reply) {
      var rp = el('div', 'pc-reply');
      rp.textContent = '↳ ' + d.reply.name + ': ' + d.reply.text;
      inner.appendChild(rp);
    }

    var body = el('div', 'pc-body');
    if (d.mention) {
      var at = el('span', 'pc-at pc-at-self');
      at.textContent = d.mention;
      body.appendChild(at);
      body.appendChild(document.createTextNode(' ' + d.m));
    } else {
      body.appendChild(document.createTextNode(d.m));
    }
    inner.appendChild(body);

    item.appendChild(inner);
    n++;
    return item;
  }

  // Same ramp as prism-chat.js: newest last, never dimmed, and only fade
  // once the feed is full so a half-empty preview isn't grey for no reason.
  function reflow() {
    var kids = [].slice.call(feed.children);
    var full = kids.length >= MAX;
    var dim = Math.min(FADE.length, kids.length - 1);
    kids.forEach(function (k, i) {
      k.classList.toggle('pc-newest', i === kids.length - 1);
      var f = (full && i < dim) ? FADE[dim - 1 - i] : null;
      k.style.opacity = (f != null) ? String(f) : '';
    });
  }

  function line(d) {
    feed.appendChild(build(d));
    while (feed.children.length > MAX) feed.removeChild(feed.firstChild);
    reflow();
  }

  MSGS.slice(0, 4).forEach(line);
  var i = 4;
  setInterval(function () { line(MSGS[i % MSGS.length]); i++; }, EVERY);
})();
