/* ============================================================
   PRISM HAUNT: the night scenery every Haunt scene shares.
   Builds the backdrop into .stage[data-haunt] so the scene files only
   carry their own content. Pick layers with space-separated words:

     moon | crescent | blood   the moon (full, thin, or blood-red)
     tree                      gnarled dead tree reaching over the moon
     fox                       fox silhouette howling on the ridge
     pines                     two layers of pine treeline + the ridge
     graves                    a few crooked headstones (--graves-x/-y)
     eyes                      eyes that open and blink in the woods
     wisps                     drifting foxfire (kitsune-bi)
     bats                      a bat crosses now and then
     lightning                 a soft, rare flash behind the trees
     web                       cobweb in the top-left corner

   Placement knobs (CSS custom properties on .stage):
     --moon-x --moon-y --moon-size   --fox-x --fox-y --fox-scale
     --tree-x   --graves-x --graves-y
   Silhouette colours (also on .stage, e.g. the blood-moon scene):
     --h-far  --h-mid  --h-near      (far pines, near pines, ridge/tree/fox)
   data-seed="n" changes the random treeline / star layout.

   Motion budget: slow ambient drift (wisps, fog, clouds) runs always;
   sudden things (eyes, bats, lightning) are rare and never strobe.
     ?still   freezes everything (so does Windows' "reduce motion")
     ?calm    keeps the drift, drops eyes, bats, lightning and shooting stars
   Also: the tree sways, the fox breathes, numbers roll when they change.
   ============================================================ */
(function(){
  "use strict";
  var stage = document.querySelector('.stage[data-haunt]');
  if(!stage) return;
  var want = (stage.getAttribute('data-haunt') || '').split(/\s+/);
  function has(k){ return want.indexOf(k) >= 0; }
  var still = new URLSearchParams(location.search).has('still') ||
              (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  if(still) document.documentElement.classList.add('h-still');
  if(new URLSearchParams(location.search).has('calm')) document.documentElement.classList.add('h-calm');

  var seed = parseInt(stage.getAttribute('data-seed') || '13', 10) || 13;
  function rnd(){ seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
  function r(a, b){ return a + rnd() * (b - a); }
  var W = 1920, H = 1080;
  var cs = getComputedStyle(stage);
  function knob(name, dflt){ var v = parseFloat(cs.getPropertyValue(name)); return isNaN(v) ? dflt : v; }
  function colour(name, dflt){ var v = cs.getPropertyValue(name).trim(); return /^#[0-9a-f]{3,8}$/i.test(v) ? v : dflt; }
  var FAR = colour('--h-far', '#1B1648'), MID = colour('--h-mid', '#110D31'), NEAR = colour('--h-near', '#06051A');

  var frag = document.createDocumentFragment();
  function div(cls, html){ var d = document.createElement('div'); d.className = cls; if(html) d.innerHTML = html; frag.appendChild(d); return d; }
  function svg(cls, inner, vb){
    return div(cls, '<svg viewBox="' + (vb || ('0 0 ' + W + ' ' + H)) + '" preserveAspectRatio="none" aria-hidden="true">' + inner + '</svg>');
  }

  /* ---- sky + stars ---- */
  div('h-sky');
  var stars = [], tw = '';
  for(var i = 0; i < 150; i++){
    var x = r(0, W) | 0, y = r(0, 760) | 0, a = r(0.25, 0.9).toFixed(2), s = rnd() < 0.12 ? 2 : 1;
    stars.push(x + 'px ' + y + 'px 0 ' + (s - 1) + 'px rgba(255,250,235,' + a + ')');
  }
  div('h-stars').style.boxShadow = stars.join(',');
  for(i = 0; i < 9; i++){
    tw += '<i style="left:' + (r(40, W - 40) | 0) + 'px;top:' + (r(30, 600) | 0) + 'px;animation-delay:' + r(-8, 0).toFixed(1) + 's;animation-duration:' + r(4, 9).toFixed(1) + 's"></i>';
  }
  div('h-twinkle', tw);

  /* ---- moon + passing clouds ---- */
  var mx = knob('--moon-x', 1590), my = knob('--moon-y', 640), ms = knob('--moon-size', 500);
  if(has('moon') || has('blood') || has('crescent')){
    var kind = has('blood') ? ' blood' : has('crescent') ? ' crescent' : '';
    var m = div('h-moon' + kind, '<b class="c1"></b><b class="c2"></b><b class="c3"></b><b class="c4"></b>');
    m.style.cssText = 'left:' + (mx - ms / 2) + 'px;top:' + (my - ms / 2) + 'px;width:' + ms + 'px;height:' + ms + 'px';
    var halo = div('h-halo' + kind);
    halo.style.cssText = 'left:' + (mx - ms * 1.6) + 'px;top:' + (my - ms * 1.6) + 'px;width:' + (ms * 3.2) + 'px;height:' + (ms * 3.2) + 'px';
    var c1 = div('h-cloud'); c1.style.cssText = 'top:' + (my - ms * 0.05) + 'px;--dur:140s;--delay:-40s';
    var c2 = div('h-cloud thin'); c2.style.cssText = 'top:' + (my + ms * 0.32) + 'px;--dur:190s;--delay:-120s';
  }

  /* ---- lightning sits BEHIND the trees, so the woods silhouette against it ---- */
  if(has('lightning')) div('h-flash');

  /* ---- pines ---- */
  function pines(color, base, hmin, hmax, step, x0){
    var out = '', x = x0 || -40;
    while(x < W + 40){
      var h = r(hmin, hmax), w = h * r(0.36, 0.46), tiers = 5;
      var d = 'M' + x.toFixed(0) + ' ' + (base - h).toFixed(0);
      // jagged right side going down, then back up the left: one shaggy pine
      for(var t = 1; t <= tiers; t++){
        var ty = base - h + h * t / tiers, hw = w / 2 * (0.25 + 0.75 * t / tiers);
        d += ' L' + (x + hw).toFixed(0) + ' ' + ty.toFixed(0) + ' L' + (x + hw * 0.45).toFixed(0) + ' ' + (ty - h / tiers * 0.18).toFixed(0);
      }
      d += ' L' + (x + 5) + ' ' + (base + 30) + ' L' + (x - 5) + ' ' + (base + 30);
      for(t = tiers; t >= 1; t--){
        ty = base - h + h * t / tiers; hw = w / 2 * (0.25 + 0.75 * t / tiers);
        d += ' L' + (x - hw * 0.45).toFixed(0) + ' ' + (ty - h / tiers * 0.18).toFixed(0) + ' L' + (x - hw).toFixed(0) + ' ' + ty.toFixed(0);
      }
      out += '<path d="' + d + 'Z"/>';
      x += step + r(-16, 16);
    }
    return '<g fill="' + color + '">' + out + '<rect x="0" y="' + base + '" width="' + W + '" height="' + (H - base) + '"/></g>';
  }
  if(has('pines')){
    svg('h-layer h-far', pines(FAR, 930, 150, 270, 64));
    svg('h-layer h-mid', pines(MID, 990, 110, 210, 52, -10));
  }

  /* ---- eyes in the woods ---- */
  if(has('eyes')){
    var spots = [[220, 905], [860, 948], [1080, 912], [1270, 958], [470, 952], [1760, 930]];
    spots.forEach(function(p, k){
      var e = div('h-eyes' + (k % 3 === 1 ? ' ember' : ''), '<i></i><i></i>');
      e.style.cssText = 'left:' + p[0] + 'px;top:' + p[1] + 'px;--dur:' + r(17, 29).toFixed(1) + 's;--delay:' + r(-25, 0).toFixed(1) + 's;--s:' + r(0.75, 1.1).toFixed(2);
    });
  }

  /* ---- the ridge, the dead tree, the fox ---- */
  var near = '', treeSvg = '', treeOrigin = '', treeBox = null, foxSvg = '', foxOrigin = '', foxBox = null;
  var fx = knob('--fox-x', 1560), fy = knob('--fox-y', 862);
  if(has('pines') || has('fox') || has('tree')){
    // the ridge peaks under the fox, so it always has somewhere to sit
    near += '<path fill="' + NEAR + '" d="M0 1080 L0 1032 C 420 1014 820 1040 ' + (fx - 430) + ' ' + (fy + 128) +
      ' C ' + (fx - 230) + ' ' + (fy + 70) + ' ' + (fx - 110) + ' ' + (fy + 4) + ' ' + fx + ' ' + fy +
      ' C ' + (fx + 150) + ' ' + (fy - 4) + ' ' + (fx + 270) + ' ' + (fy + 40) + ' 1920 ' + (fy + 66) + ' L1920 1080 Z"/>';
  }
  if(has('tree')){
    var tx = knob('--tree-x', 1905), segs = '', bx0 = 1e9, bx1 = -1e9, by0 = 1e9;
    var branch = function(x, y, ang, len, wdt, depth){
      if(depth === 0 || len < 8) return;
      var x2 = x + Math.cos(ang) * len, y2 = y + Math.sin(ang) * len;
      // keep the fox's silhouette clear: no branch ends inside its head-room
      if(has('fox') && x2 > fx - 200 && x2 < fx + 150 && y2 > fy - 340) return;
      // a slight kink mid-branch so nothing is ruler-straight
      var kx = (x + x2) / 2 + r(-len, len) * 0.12, ky = (y + y2) / 2 + r(-len, len) * 0.12;
      bx0 = Math.min(bx0, x, x2, kx); bx1 = Math.max(bx1, x, x2, kx); by0 = Math.min(by0, y, y2, ky);
      segs += '<path d="M' + x.toFixed(1) + ' ' + y.toFixed(1) + ' Q' + kx.toFixed(1) + ' ' + ky.toFixed(1) + ' ' + x2.toFixed(1) + ' ' + y2.toFixed(1) + '" stroke-width="' + wdt.toFixed(1) + '"/>';
      var n = depth > 4 ? 2 : (rnd() < 0.7 ? 2 : 3);
      for(var b = 0; b < n; b++){
        var spread = (b - (n - 1) / 2) * r(0.35, 0.7);
        // branches lean left, toward the moon
        branch(x2, y2, ang + spread - 0.14, len * r(0.6, 0.8), wdt * 0.64, depth - 1);
      }
    };
    branch(tx, 1010, -Math.PI / 2 - 0.16, 230, 46, 7);
    branch(tx - 30, 760, -Math.PI / 2 - 0.95, 130, 18, 5);
    // the whole tree sways a fraction of a degree from the base of its trunk
    treeSvg = '<g fill="none" stroke="' + NEAR + '" stroke-linecap="round">' + segs + '</g>';
    treeBox = [Math.floor(bx0 - 30), Math.floor(by0 - 30), Math.ceil(Math.min(W, bx1 + 30)), H];
    treeOrigin = (tx - treeBox[0]) + 'px ' + (1010 - treeBox[1]) + 'px';
  }
  if(has('fox')){
    var sc = knob("--fox-scale", 1.75);
    // sitting fox in profile, muzzle raised to the moon, brush curled at its paws
    foxBox = [Math.floor(fx + 8 - 105 * sc), Math.floor(fy + 3 - 170 * sc), Math.ceil(fx + 8 + 50 * sc), Math.ceil(fy + 3 + 6)];
    foxOrigin = (fx + 8 - foxBox[0]) + 'px ' + (fy + 3 - foxBox[1]) + 'px';   // the paws: it breathes from the ground up
    foxSvg = '<g transform="translate(' + (fx + 8) + ' ' + (fy + 3) + ') scale(' + sc + ')" fill="' + NEAR + '">' +
      '<path d="M-70 0 C-94 -2 -100 -24 -86 -36 C-74 -46 -54 -40 -42 -26 C-50 -50 -44 -74 -30 -88 C-22 -98 -16 -106 -14 -116 ' +
      'C-14 -122 -16 -128 -18 -134 L-17 -156 L-6 -140 L1 -161 L9 -140 C16 -141 24 -146 32 -151 L41 -155 C39 -149 35 -143 29 -139 ' +
      'C23 -135 17 -129 15 -121 C21 -113 23 -103 17 -94 C15 -84 17 -70 17 -56 C17 -36 15 -16 15 0 L6 0 C6 -10 4 -18 0 -24 C-4 -16 -6 -8 -6 0 Z"/></g>';
  }
  if(has('graves')){
    var g = function(x, y, w, h, rot, word){
      return '<g transform="translate(' + x + ' ' + y + ') rotate(' + rot + ')"><path fill="#0B0926" d="M0 0 L0 ' + (-h + w / 2) + ' A' + (w / 2) + ' ' + (w / 2) + ' 0 0 1 ' + w + ' ' + (-h + w / 2) + ' L' + w + ' 0 Z"/>' +
        (word ? '<text x="' + (w / 2) + '" y="' + (-h * 0.42) + '" text-anchor="middle" font-family="Cinzel,serif" font-weight="700" font-size="' + (w * 0.22).toFixed(0) + '" fill="#3A3470">' + word + '</text>' : '') + '</g>';
    };
    var gx = knob('--graves-x', 1640), gy = knob('--graves-y', fy + 34);
    near += g(gx, gy, 84, 122, -6, 'R.I.P.') + g(gx + 112, gy + 8, 58, 84, 6, '') + g(gx + 186, gy + 12, 70, 102, -3, 'LAG');
  }
  if(near) svg('h-layer h-near', near);
  /* The tree and the fox get layers of their own, moved with transform, so the
     GPU just shifts a texture. Animating shapes inside the shared SVG made the
     whole 1920x1080 layer re-rasterise every frame. */
  function boxed(cls, inner, b, origin){   // a layer only as big as what it holds
    var d = svg(cls, inner, b[0] + ' ' + b[1] + ' ' + (b[2] - b[0]) + ' ' + (b[3] - b[1]));
    d.style.cssText = 'left:' + b[0] + 'px;top:' + b[1] + 'px;width:' + (b[2] - b[0]) + 'px;height:' + (b[3] - b[1]) + 'px;transform-origin:' + origin;
    return d;
  }
  if(treeSvg) boxed('h-near h-tree', treeSvg, treeBox, treeOrigin);
  if(foxSvg) boxed('h-near h-foxbody', foxSvg, foxBox, foxOrigin);

  /* ---- fog, wisps ---- */
  div('h-fog f1'); div('h-fog f2');
  if(has('wisps')){
    var wp = [[300, 160], [980, 110], [1250, 470], [520, 700], [1700, 640], [760, 330], [140, 560]];
    wp.forEach(function(p, k){
      var w = div('h-wisp' + (k % 4 === 3 ? ' warm' : ''));
      w.style.cssText = 'left:' + p[0] + 'px;top:' + p[1] + 'px;--dur:' + r(7, 13).toFixed(1) + 's;--delay:' + r(-12, 0).toFixed(1) + 's;--dx:' + r(-40, 40).toFixed(0) + 'px;--dy:' + r(-60, -20).toFixed(0) + 'px;--s:' + r(0.7, 1.25).toFixed(2);
    });
  }
  if(has('web')){
    svg('h-web', '<g fill="none" stroke="rgba(239,231,210,.22)" stroke-width="1.6">' +
      '<path d="M0 0 L260 70 M0 0 L200 180 M0 0 L90 250 M0 0 L10 290"/>' +
      '<path d="M48 13 Q40 32 38 48 Q20 46 2 58"/><path d="M104 28 Q86 64 78 100 Q40 96 4 116"/>' +
      '<path d="M160 43 Q130 96 120 150 Q60 146 6 172"/><path d="M220 59 Q176 128 160 208 Q80 204 8 232"/></g>', '0 0 300 300');
  }

  /* ---- bats ---- */
  var batHost = has('bats') ? div('h-bats') : null;
  div('h-vignette'); div('h-grain');
  stage.insertBefore(frag, stage.firstChild);

  if(batHost && !still){
    var BAT = '<svg viewBox="0 0 100 44" aria-hidden="true"><path d="M50 20 C47 12 41 10 35 14 C31 6 20 2 4 6 C13 10 15 17 13 23 C20 19 26 21 30 27 C34 23 40 23 44 29 L50 25 L56 29 C60 23 66 23 70 27 C74 21 80 19 87 23 C85 17 87 10 96 6 C80 2 69 6 65 14 C59 10 53 12 50 20 Z M47 15 L46 9 L49 13 Z M53 15 L54 9 L51 13 Z"/></svg>';
    var flyBat = function(){
      setTimeout(flyBat, r(16000, 34000));
      if(document.hidden || batHost.childElementCount >= 4) return;
      var b = document.createElement('div');
      var ltr = rnd() < 0.5, y = r(90, 520) | 0, size = r(46, 86) | 0;
      b.className = 'h-bat'; b.innerHTML = BAT;
      b.style.cssText = 'top:' + y + 'px;width:' + size + 'px;--from:' + (ltr ? -120 : W + 120) + 'px;--to:' + (ltr ? W + 120 : -120) + 'px;--bob:' + r(-140, 60).toFixed(0) + 'px;--dur:' + r(6, 10).toFixed(1) + 's';
      batHost.appendChild(b);
      b.addEventListener('animationend', function(){ b.remove(); });
      if(rnd() < 0.45) setTimeout(function(){ // a second bat tags along
        var b2 = b.cloneNode(true); b2.style.top = (y + r(30, 70)) + 'px'; b2.style.width = (size * 0.7) + 'px';
        batHost.appendChild(b2); b2.addEventListener('animationend', function(){ b2.remove(); });
      }, r(250, 700));
    };
    setTimeout(flyBat, r(2500, 7000));
  }

  /* ---- a shooting star now and then (not in ?calm or ?still) ---- */
  var calm = document.documentElement.classList.contains('h-calm');
  if(!still && !calm){
    var shoot = function(){
      setTimeout(shoot, r(18000, 42000));
      if(document.hidden) return;
      var st = document.createElement('div');
      st.className = 'h-shoot';
      st.style.cssText = 'left:' + (r(500, 1800) | 0) + 'px;top:' + (r(40, 300) | 0) + 'px;--ang:' + r(-28, -12).toFixed(1) + 'deg;--len:' + (-r(380, 640) | 0) + 'px';
      stage.insertBefore(st, stage.querySelector('.h-flash, .h-layer') || null);
      st.addEventListener('animationend', function(){ st.remove(); });
    };
    setTimeout(shoot, r(6000, 14000));
  }

  /* ---- numbers that change roll up into place (countdown, counts) ----
     Only when the value really changes: the countdown rewrites the same
     text four times a second. Off when motion is frozen, because a frozen
     animation would hold the number at its invisible first frame. */
  if(!still && window.MutationObserver){
    Array.prototype.forEach.call(document.querySelectorAll('.js-cd-min, .js-cd-sec, .js-roll'), function(el){
      var last = el.textContent;
      new MutationObserver(function(){
        if(el.textContent === last) return;
        last = el.textContent;
        el.classList.remove('roll'); void el.offsetWidth; el.classList.add('roll');
      }).observe(el, { childList:true, characterData:true, subtree:true });
    });
  }
})();
