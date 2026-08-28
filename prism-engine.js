/* ============================================================
   PRISM — shared engine
   Particle motes + live Twitch data (via DecAPI, no secrets).

   Per-scene config, set on <body>:
     data-channel="NeoTheFox98"   (Twitch login name)
     data-goal="100"              (follower goal, optional)
     data-motes="72"              (particle count, optional)

   Live-data hooks (add these classes to elements in a scene):
     img.js-avatar        -> src set to current Twitch avatar
     .js-followcount      -> textContent set to follower total
     .js-goal-fill        -> width set to count/goal %
     .js-goal-now         -> textContent set to current count
     .js-goal-target      -> textContent set to goal
     .js-latest           -> textContent set to newest follower name
     .js-latest-wrap[hidden] -> unhidden when a latest follower loads
   Everything degrades gracefully if the network/endpoint fails.
   ============================================================ */
(function(){
  "use strict";
  var body = document.body;
  var CFG   = window.PRISM_CONFIG || {};
  /* Identity comes from prism-config.js first; data-* on <body> is a
     per-scene fallback/override so nothing breaks if config is absent. */
  var CH    = (CFG.channel || body.dataset.channel || '').trim();
  var GOAL  = parseInt(body.dataset.goal || CFG.goal || '0', 10) || 0;
  var MOTES = parseInt(body.dataset.motes || '72', 10);
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- brand icons (inline SVG, no network) ----------
     Keyed by the `icon` value in prism-config.js. Drawn in currentColor so
     they inherit the PRISM ink colour. Set PRISM_CONFIG.iconStyle = 'favicon'
     to fall back to the old Google favicon images, or give a social its own
     `svg` path string in the config to add a brand that isn't listed here. */
  var ICONS = {
    'x.com': 'M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z',
    'youtube.com': 'M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z',
    'telegram.org': 'M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z',
    'steamcommunity.com': 'M11.979 0C5.678 0 .511 4.86.022 11.037l6.432 2.658c.545-.371 1.203-.59 1.912-.59.063 0 .125.004.188.006l2.861-4.142V8.91c0-2.495 2.028-4.524 4.524-4.524 2.494 0 4.524 2.031 4.524 4.527s-2.03 4.525-4.524 4.525h-.105l-4.076 2.911c0 .052.004.105.004.159 0 1.875-1.515 3.396-3.39 3.396-1.635 0-3.016-1.173-3.331-2.727L.436 15.27C1.862 20.307 6.486 24 11.979 24c6.627 0 11.999-5.373 11.999-12S18.605 0 11.979 0zM7.54 18.21l-1.473-.61c.262.543.714.999 1.314 1.25 1.297.539 2.793-.076 3.332-1.375.263-.63.264-1.319.005-1.949s-.75-1.121-1.377-1.383c-.624-.26-1.29-.249-1.878-.03l1.523.63c.956.4 1.409 1.5 1.009 2.455-.397.957-1.497 1.41-2.454 1.012H7.54zm11.415-9.303c0-1.662-1.353-3.015-3.015-3.015-1.665 0-3.015 1.353-3.015 3.015 0 1.665 1.35 3.015 3.015 3.015 1.663 0 3.015-1.35 3.015-3.015zm-5.273-.005c0-1.252 1.013-2.266 2.265-2.266 1.249 0 2.266 1.014 2.266 2.266 0 1.251-1.017 2.265-2.266 2.265-1.253 0-2.265-1.014-2.265-2.265z'
  };
  var SVGNS = 'http://www.w3.org/2000/svg';

  function makeIcon(s){
    var path = s.svg || ICONS[s.icon];
    if(path && (CFG.iconStyle || 'svg') !== 'favicon'){
      var svg = document.createElementNS(SVGNS, 'svg');
      svg.setAttribute('class', 'ico');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('aria-hidden', 'true');
      svg.setAttribute('fill', 'currentColor');
      var p = document.createElementNS(SVGNS, 'path');
      p.setAttribute('d', path);
      svg.appendChild(p);
      return svg;
    }
    var img = document.createElement('img');           /* fallback: favicon service */
    img.className = 'ico';
    img.src = 'https://www.google.com/s2/favicons?domain=' + encodeURIComponent(s.icon || '') + '&sz=32';
    img.alt = s.alt || '';
    return img;
  }

  /* ---------- socials (rendered from config) ----------
     Any <div class="socials" data-prism-socials></div> is filled from
     CFG.socials, so handles live in one place instead of every scene. */
  (function(){
    var list = CFG.socials;
    if(!list || !list.length) return;
    Array.prototype.forEach.call(document.querySelectorAll('.socials[data-prism-socials]'), function(wrap){
      wrap.innerHTML = '';
      list.forEach(function(s){
        var item = document.createElement('div');
        item.className = 'social-item';
        var lab = document.createElement('span');
        lab.className = 'label';
        lab.textContent = s.label || '';
        item.appendChild(makeIcon(s)); item.appendChild(lab);
        if(s.url){ item.setAttribute('data-url', s.url); }
        wrap.appendChild(item);
      });
    });
  })();

  /* avatar fallback from config (live data overwrites it moments later) */
  if(CFG.avatarFallback){
    Array.prototype.forEach.call(document.querySelectorAll('img.js-avatar'), function(img){
      if(!img.getAttribute('src')) img.src = CFG.avatarFallback;
    });
  }

  /* ---------- prismatic light motes ---------- */
  (function(){
    var p = document.getElementById('particles'); if(!p) return;
    var COLORS = ['#57F2E4','#6C8BFF','#B983FF','#FF7ACb','#FFD86B','#EAF0FF'];
    var n = reduce ? Math.min(MOTES, 24) : MOTES;
    for(var i=0;i<n;i++){
      var m=document.createElement('div'); m.className='mote';
      var s=(1+Math.random()*3.4).toFixed(1);
      var c=COLORS[Math.floor(Math.random()*COLORS.length)];
      var dur=(9+Math.random()*15).toFixed(1);
      var anim = reduce ? '' : 'animation:mote-drift '+dur+'s linear '+(-Math.random()*dur).toFixed(1)+'s infinite;';
      m.style.cssText='left:'+(Math.random()*100)+'%;top:'+(Math.random()*100)+'%;width:'+s+'px;height:'+s+'px;'+
        'background:radial-gradient(circle,'+c+' 0%,transparent 70%);box-shadow:0 0 '+(6+Math.random()*10).toFixed(0)+'px '+c+';'+
        '--dx:'+(Math.random()*140-70).toFixed(0)+'px;'+(reduce?'opacity:0.5;':'')+anim;
      p.appendChild(m);
    }
  })();

  /* ---------- live Twitch data (DecAPI) ---------- */
  if(!CH) return;
  var API = 'https://decapi.me/twitch/';

  function get(path){
    var ctrl = new AbortController();
    var to = setTimeout(function(){ ctrl.abort(); }, 6000);
    return fetch(API+path+'/'+encodeURIComponent(CH), {signal:ctrl.signal})
      .then(function(r){ clearTimeout(to); if(!r.ok) throw 0; return r.text(); })
      .then(function(t){ t=(t||'').trim(); if(!t || /error|unable|not found|must be/i.test(t)) throw 0; return t; });
  }
  function each(sel, fn){ Array.prototype.forEach.call(document.querySelectorAll(sel), fn); }
  function fmt(n){ return (''+n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  /* last-good cache — keeps the overlay populated across brief DecAPI outages
     and OBS restarts. Keyed per channel; degrades silently if storage is off. */
  var LS = 'prism_' + CH + '_';
  function cacheGet(k){ try{ return localStorage.getItem(LS + k); }catch(e){ return null; } }
  function cacheSet(k, v){ try{ localStorage.setItem(LS + k, v); }catch(e){} }

  function applyAvatar(url){
    if(!/^https?:\/\//.test(url)) return;
    each('img.js-avatar', function(img){ img.src = url; });
  }
  function applyFollows(n){
    if(isNaN(n)) return;
    each('.js-followcount', function(el){ el.textContent = fmt(n); });
    each('.js-goal-now', function(el){ el.textContent = fmt(n); });
    if(GOAL > 0){
      each('.js-goal-target', function(el){ el.textContent = fmt(GOAL); });
      var pct = Math.max(0, Math.min(100, (n / GOAL) * 100));
      each('.js-goal-fill', function(el){ el.style.width = pct.toFixed(1) + '%'; });
    }
  }
  function applyLatest(name){
    if(!name) return;
    each('.js-latest', function(el){ el.textContent = name; });
    each('.js-latest-wrap', function(el){ el.hidden = false; });
  }

  function loadAvatar(){
    get('avatar').then(function(url){
      applyAvatar(url); cacheSet('avatar', url);
    }).catch(function(){ applyAvatar(cacheGet('avatar')); });
  }
  function loadFollows(){
    get('followcount').then(function(txt){
      var n = parseInt(txt.replace(/[^0-9]/g,''), 10);
      if(isNaN(n)) return;
      applyFollows(n); cacheSet('follows', String(n));
    }).catch(function(){ applyFollows(parseInt(cacheGet('follows'), 10)); });
  }
  function loadLatest(){
    get('followers').then(function(name){
      if(!name) return;
      applyLatest(name); cacheSet('latest', name);
    }).catch(function(){ applyLatest(cacheGet('latest')); /* endpoint may need broadcaster auth */ });
  }

  /* paint last-good values immediately, before the first network round-trip */
  (function primeFromCache(){
    applyAvatar(cacheGet('avatar'));
    applyFollows(parseInt(cacheGet('follows'), 10));
    applyLatest(cacheGet('latest'));
  })();

  function refresh(){ loadAvatar(); loadFollows(); loadLatest(); }
  refresh();
  setInterval(refresh, 60000);
})();
