/* ============================================================
   PRISM 2.0 — chat renderer
   Consumes Stream Manager's "chat" effects channel (contract v1,
   see stream_manager/chatfeed.py) and draws it.

   No framework, no build step, no dependency — same house style as
   prism-engine.js. Everything tunable lives in CFG at the top.

   Placement is NOT set here. The page fills whatever box OBS gives the
   browser source, so position and size are the OBS transform, per scene.
   Only orientation comes from the URL:
     ?anchor=bottom|top   which edge messages grow from (default bottom)
     ?align=left|right    which side avatars and text sit on (default left)
   ============================================================ */
(function () {
  "use strict";

  var CONTRACT = 1;                 // refuse payloads we don't understand
  var API = location.origin;        // served by Stream Manager: same origin
  var Q = new URLSearchParams(location.search);

  var CFG = {
    max:      int(Q.get("max"), 6, 1),        // messages on screen
    fade:     [0.72, 0.50, 0.30],          // 4th, 5th, 6th newest
    ageOut:   int(Q.get("ageout"), 0),     // seconds; 0 = never expire
    backfill: int(Q.get("backfill"), 25),  // messages to restore on load
    exitMs:   220,                         // fade-out before removal
    anchor:   Q.get("anchor") === "top" ? "top" : "bottom",
    align:    Q.get("align") === "right" ? "right" : "left",
    theme:    Q.get("theme") || "/overlays/active/chat-theme.css"
  };

  function int(v, dflt, min) {
    var n = parseInt(v, 10);
    if (isNaN(n) || n < 0) return dflt;
    return (min != null && n < min) ? min : n;
  }

  var root = document.documentElement;
  root.setAttribute("data-anchor", CFG.anchor);
  root.setAttribute("data-align", CFG.align);

  var feed = document.getElementById("pc-feed");
  if (!feed) return;

  // ---------------------------------------------------------- theme ----
  // The page is set-independent so switching to a non-PRISM set can't 404
  // it; only the skin follows the active set, re-read on a timer exactly
  // like the shoutout card and the now-playing widget.
  (function theme() {
    var cur = document.getElementById("pc-theme");
    if (!cur) return;
    function fresh() {
      return CFG.theme + (CFG.theme.indexOf("?") < 0 ? "?" : "&") + "t=" + Date.now();
    }
    cur.href = fresh();           // cache-bust the first load too
    setInterval(function () {
      var next = document.createElement("link");
      next.rel = "stylesheet";
      next.href = fresh();
      next.onload = function () { if (cur && cur.parentNode) cur.parentNode.removeChild(cur); cur = next; };
      next.onerror = function () { if (next.parentNode) next.parentNode.removeChild(next); };
      document.head.appendChild(next);
    }, 60000);
  })();

  // ---------------------------------------------------------- render ----
  function el(tag, cls) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    return n;
  }

  // Chat is untrusted input from strangers, and this page shares an origin
  // with the Stream Manager dashboard and its control endpoints. Nothing in
  // the message path touches innerHTML — text nodes and createElement only.
  function build(m) {
    var item = el("div", "pc-item");
    item.setAttribute("data-id", m.id || "");
    item.setAttribute("data-user", (m.user && m.user.id) || "");
    // CLEARCHAT identifies its target by id, but falls back to the trailing
    // login when Twitch omits target-user-id, so both are on the node.
    item.setAttribute("data-login", (m.user && m.user.login) || "");
    item.style.setProperty("--user-color", (m.user && m.user.color) || "");

    var f = m.flags || {};
    if (m.action) item.classList.add("pc-action");
    if (f.first) item.classList.add("pc-first");
    if (f.mod) item.classList.add("pc-mod");
    if (f.vip) item.classList.add("pc-vip");
    if (f.broadcaster) item.classList.add("pc-broadcaster");
    if (m.bits > 0) item.classList.add("pc-cheer");
    // Phase 5: subs, resubs, gifts, raids and cheers carry an `event` and get
    // a card line above the (optional) message. Type is whitelisted before it
    // becomes a class name — it's server-built, but the class list is ours.
    var ev = m.event;
    var EV_TYPES = { sub: 1, resub: 1, gift: 1, giftbomb: 1, raid: 1, cheer: 1, announcement: 1 };
    if (ev && EV_TYPES[ev.type]) item.classList.add("pc-event", "pc-ev-" + ev.type);

    var inner = el("div", "pc-inner");

    var meta = el("div", "pc-meta");
    (m.badges || []).forEach(function (b) {
      if (!b.url) return;                       // unresolved badge: skip it
      var img = el("img", "pc-badge");
      img.src = b.url;
      img.alt = b.title || b.set || "";
      img.onerror = function () { if (img.parentNode) img.parentNode.removeChild(img); };
      meta.appendChild(img);
    });
    var name = el("span", "pc-name");
    name.textContent = (m.user && m.user.name) || "";
    meta.appendChild(name);
    inner.appendChild(meta);

    if (m.reply_to) {
      var rp = el("div", "pc-reply");
      rp.textContent = "\u21B3 " + (m.reply_to.name || "") + ": " + (m.reply_to.text || "");
      inner.appendChild(rp);
    }

    if (ev && EV_TYPES[ev.type] && ev.type !== "announcement") {
      var line = el("div", "pc-event-line");
      var icon = el("span", "pc-event-icon");
      icon.textContent = { sub: "\u2605", resub: "\u2605", gift: "\u2766", giftbomb: "\u2766",
                           raid: "\u27A4", cheer: "\u25C6" }[ev.type] || "";
      line.appendChild(icon);
      line.appendChild(document.createTextNode(" " + (ev.label || "")));
      inner.appendChild(line);
    }

    var body = el("div", "pc-body");
    var mentionsMe = false;
    var frags = m.fragments;
    if (!frags || !frags.length) frags = m.text ? [{ type: "text", text: m.text }] : [];
    frags.forEach(function (fr) {
      if (fr.type === "emote") {
        var im = el("img", "pc-emote");
        im.src = fr.url;
        im.alt = fr.name || "";
        // A dead emote CDN falls back to the emote's name as text.
        im.onerror = function () {
          if (im.parentNode) im.parentNode.replaceChild(document.createTextNode(fr.name || ""), im);
        };
        body.appendChild(im);
      } else if (fr.type === "mention") {
        if (fr.self) mentionsMe = true;
        var sp = el("span", "pc-at" + (fr.self ? " pc-at-self" : ""));
        sp.textContent = fr.text || "";
        body.appendChild(sp);
      } else {
        body.appendChild(document.createTextNode(fr.text || ""));
      }
    });
    if (mentionsMe) item.classList.add("pc-mention");
    if (!body.childNodes.length) body.classList.add("pc-body-empty");   // a bare sub card
    inner.appendChild(body);

    item.appendChild(inner);
    return item;
  }

  // ------------------------------------------------------- lifecycle ----
  function live() {
    return [].slice.call(feed.querySelectorAll(".pc-item:not(.pc-leaving)"));
  }

  // Opacity is applied by distance from the NEWEST message, which is the
  // last child: the column is a flex column anchored to its end, so new
  // messages append at the bottom.
  function restyle() {
    var kids = live();
    var n = kids.length;
    var full = n >= CFG.max;                      // only fade what's about to go
    // How many of the OLDEST messages the ramp covers. Capped at n-1 so the
    // newest is always at full opacity: at ?max=1 the old code handed the only
    // message on screen the dimmest step and rendered chat at 30%.
    var dim = Math.min(CFG.fade.length, n - 1);
    kids.forEach(function (k, i) {
      k.classList.toggle("pc-newest", i === n - 1);
      // Indexed from the OLDEST end so the ramp lands on the messages nearest
      // the chop at any CFG.max, not just the default 6.
      var f = (full && i < dim) ? CFG.fade[dim - 1 - i] : null;
      k.style.opacity = (f != null) ? String(f) : "";
    });
  }

  function drop(node) {
    if (!node || !node.isConnected || node.classList.contains("pc-leaving")) return;
    node.classList.add("pc-leaving");
    // Messages leave, they don't vanish — a node disappearing between two
    // frames reads as a rendering glitch to viewers.
    setTimeout(function () {
      if (node.parentNode) node.parentNode.removeChild(node);
      restyle();
    }, CFG.exitMs);
  }

  function trim() {
    var kids = live();
    while (kids.length > CFG.max) drop(kids.shift());
  }

  function add(m) {
    // Dedupe the backfill/poll overlap — but only on a real id. An empty id
    // would match every id-less message and silently swallow the lot.
    if (m.id && feed.querySelector('[data-id="' + cssEscape(m.id) + '"]:not(.pc-leaving)')) return;
    var node = build(m);
    feed.appendChild(node);
    if (CFG.ageOut > 0) setTimeout(function () { drop(node); }, CFG.ageOut * 1000);
    trim();
    restyle();
  }

  // ------------------------------------------------------ moderation ----
  function clearAll() {
    live().forEach(function (k) { drop(k); });
  }

  function removeBy(userId, login) {
    live().forEach(function (k) {
      if (userId ? k.getAttribute("data-user") === userId
                 : (login && k.getAttribute("data-login") === login)) drop(k);
    });
  }

  // Every payload enters here. A message a mod deleted has to LEAVE the
  // screen: before this, it sat there until it scrolled off, and with the
  // default ?ageout=0 that could be the rest of the stream.
  function handle(m) {
    if (!m || m.v !== CONTRACT) {
      return warnOnce("contract v" + (m && m.v) + " (this overlay renders v" + CONTRACT + ")");
    }
    if (m.kind === "msg" || m.kind === "event") return add(m);
    if (m.kind === "clearmsg") {
      // Exactly one message. No login fallback: CLEARMSG without a target id
      // is not licence to wipe a chatter's whole visible history.
      var t = m.target_id && feed.querySelector('[data-id="' + cssEscape(m.target_id) + '"]');
      if (t) drop(t);
      return;
    }
    if (m.kind === "clearchat") {
      if (m.user_id || m.login) removeBy(m.user_id, m.login);
      else clearAll();                            // whole room cleared
      return;
    }
    // Unknown kind: a later phase's event reaching an older overlay. Ignore it
    // rather than warn — the version check above already gates real breakage.
  }

  function cssEscape(s) {
    return String(s == null ? "" : s).replace(/["\\]/g, "\\$&");
  }

  var warned = {};
  function warnOnce(msg) {
    if (warned[msg]) return;
    warned[msg] = true;
    console.warn("[prism-chat] " + msg);
  }

  // ------------------------------------------------------- transport ----
  var lastId = 0;
  var errDelay = 0;
  // The server's long poll returns within 25s. This is the watchdog for the
  // other case: a socket that went half-open (Stream Manager restarted, the
  // loopback stack dropped it) and will never answer and never error, which
  // would leave the overlay frozen with no console trace for the whole stream.
  var POLL_TIMEOUT = 40000;

  function get(path) {
    var ctl = ("AbortController" in window) ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, POLL_TIMEOUT) : 0;
    function done(v) { if (timer) clearTimeout(timer); return v; }
    return fetch(API + path, { cache: "no-store", signal: ctl ? ctl.signal : undefined })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(done, function (e) { done(); throw e; });
  }

  // Stream Manager numbers effects from 1 on every start, and within one run
  // the id it reports is monotonic — so a last_id BELOW our high-water mark
  // can only mean it restarted. Without this the overlay waits for an id the
  // new process will not reach for hours: chat goes silently dead for the rest
  // of the stream while the poll loop hammers a 25s long poll forever.
  // INVARIANT: if effects ids are ever made persistent across restarts, this
  // detection stops working and needs a per-run nonce instead.
  function restarted(srvLast) {
    return typeof srvLast === "number" && srvLast > 0 && srvLast < lastId;
  }

  function backfill() {
    return get("/api/chat/backfill?n=" + CFG.backfill).then(function (d) {
      // handle(), not add(): a CLEARMSG still in the ring buffer must delete
      // its target again after an OBS source refresh, or a deleted message
      // comes straight back onto the screen.
      (d.messages || []).forEach(handle);         // already oldest-first
      lastId = d.last_id || 0;
    });
  }

  function start() {
    backfill().catch(function () {
      // Stream Manager down or still starting: show nothing, never an error
      // on stream, and let the poll loop's backoff handle the retry.
    }).then(poll);
  }

  // Floor for a zero-event response that came back too fast to have been a
  // real long poll. Belt and braces behind the lastId advance below.
  var MIN_IDLE = 1000;

  function poll() {
    var idle = 0;
    var t0 = Date.now();
    get("/api/effects/chat?since=" + lastId).then(function (d) {
      errDelay = 0;
      if (restarted(d.last_id)) {
        warnOnce("Stream Manager restarted — resyncing the chat feed");
        lastId = 0;
        clearAll();
        return backfill().catch(function () { lastId = 0; });
      }
      var evs = d.events || [];
      if (evs.length) {
        evs.forEach(function (e) { if (e && e.data) handle(e.data); });
      }
      // ALWAYS take a higher last_id, events or not. Effect ids are global and
      // monotonic, so anything the chat channel emits later is numbered above
      // whatever the server reports now — advancing loses nothing.
      //
      // Not advancing is what made this loop spin. The endpoint reports the
      // GLOBAL id whenever the chat channel has no ring buffer yet, so once any
      // other overlay's effect pushed that id past ours, every poll returned
      // instantly with no events and was re-issued with zero delay: measured at
      // 400 requests/second on the streaming PC, from overlay load until the
      // first chat message of the run.
      if (typeof d.last_id === "number" && d.last_id > lastId) lastId = d.last_id;
      if (!evs.length && Date.now() - t0 < MIN_IDLE) idle = MIN_IDLE;
      // A genuine long-poll timeout takes ~25s and re-polls at once, which is
      // the whole point of the long poll.
    }).catch(function () {
      errDelay = Math.min(errDelay ? errDelay * 2 : 1000, 15000);
    }).then(function () {
      setTimeout(poll, errDelay || idle);
    });
  }

  start();
})();
