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
    item.style.setProperty("--user-color", (m.user && m.user.color) || "");

    var f = m.flags || {};
    if (f.first) item.classList.add("pc-first");
    if (f.mod) item.classList.add("pc-mod");
    if (f.vip) item.classList.add("pc-vip");
    if (f.broadcaster) item.classList.add("pc-broadcaster");
    if (m.bits > 0) item.classList.add("pc-cheer");

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
    kids.forEach(function (k, i) {
      k.classList.toggle("pc-newest", i === n - 1);
      // Indexed from the OLDEST end so the ramp still lands on the messages
      // nearest the chop at any CFG.max, not just the default 6.
      var f = full ? CFG.fade[CFG.fade.length - 1 - i] : null;
      k.style.opacity = (i < CFG.fade.length && f != null) ? String(f) : "";
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
    if (m.v !== CONTRACT) return warnOnce("contract v" + m.v + " (this overlay renders v" + CONTRACT + ")");
    if (m.kind !== "msg") return;                 // clearmsg/clearchat/event: later phases
    // Dedupe the backfill/poll overlap — but only on a real id. An empty id
    // would match every id-less message and silently swallow the lot.
    if (m.id && feed.querySelector('[data-id="' + cssEscape(m.id) + '"]')) return;
    var node = build(m);
    feed.appendChild(node);
    if (CFG.ageOut > 0) setTimeout(function () { drop(node); }, CFG.ageOut * 1000);
    trim();
    restyle();
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

  function get(path) {
    return fetch(API + path, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function start() {
    get("/api/chat/backfill?n=" + CFG.backfill).then(function (d) {
      (d.messages || []).forEach(add);           // already oldest-first
      lastId = d.last_id || 0;
    }).catch(function () {
      // Stream Manager down or still starting: show nothing, never an error
      // on stream, and let the poll loop's backoff handle the retry.
    }).then(poll);
  }

  function poll() {
    var idle = 0;
    get("/api/effects/chat?since=" + lastId).then(function (d) {
      errDelay = 0;
      var evs = d.events || [];
      if (evs.length) {
        evs.forEach(function (e) { if (e && e.data) add(e.data); });
        lastId = d.last_id || lastId;
      } else if (lastId === 0) {
        // The shared endpoint answers a since=0 poll IMMEDIATELY instead of
        // long-polling, so re-polling on response would spin at full speed
        // until the first event ever fires. Pace it until we have a real id.
        lastId = d.last_id || 0;
        idle = 2000;
      }
      // A genuine long-poll timeout returns no events with lastId > 0:
      // re-poll at once, which is the whole point of the long poll.
    }).catch(function () {
      errDelay = Math.min(errDelay ? errDelay * 2 : 1000, 15000);
    }).then(function () {
      setTimeout(poll, errDelay || idle);
    });
  }

  start();
})();
