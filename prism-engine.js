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
        var ico = document.createElement('img');
        ico.className = 'ico';
        ico.src = 'https://www.google.com/s2/favicons?domain=' + encodeURIComponent(s.icon || '') + '&sz=32';
        ico.alt = s.alt || '';
        var lab = document.createElement('span');
        lab.className = 'label';
        lab.textContent = s.label || '';
        item.appendChild(ico); item.appendChild(lab);
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
