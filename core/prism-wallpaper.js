/* ============================================================
   PRISM — living wallpaper behaviour
   Shared by the 2.0 sets. Everything is optional; each part runs only
   when its element exists.

     body[data-tod]   set to night|dawn|day|dusk|evening (theme CSS tints)
     body[data-season] set to winter|spring|summer|autumn
     #season          filled with .p particles (class = season) to animate
     #wp-wins         recent wins from Stream Manager (/api/interactive + SSE)
     #wp-quote        a community quote every 25s (/api/quotes)
     #fx              a ripple + sparks on each Stream Manager event
     .js-surge        gets class "surge" for 1.4s on each event

   Colours per event channel: window.PRISM_WALLPAPER = { tint:{wheel:'#..'} }
   ============================================================ */
(function(){
  "use strict";
  var O = window.PRISM_WALLPAPER || {};
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var TINT = Object.assign({ wheel:'#B983FF', coinflip:'#57F2E4', slots:'#FFD86B', hype:'#FF7ACB' }, O.tint || {});
  var FALLBACK_TINT = O.fallbackTint || '#8CA6FF';
  var body = document.body;
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>]/g, function(c){ return { '&':'&amp;', '<':'&lt;', '>':'&gt;' }[c]; }); }
  function $(id){ return document.getElementById(id); }

  /* time of day */
  function tod(){
    var h = new Date().getHours();
    body.setAttribute('data-tod', h < 6 ? 'night' : h < 9 ? 'dawn' : h < 17 ? 'day' : h < 20 ? 'dusk' : 'evening');
  }
  tod(); setInterval(tod, 300000);

  /* season */
  var mo = new Date().getMonth();
  var season = (mo === 11 || mo < 2) ? 'winter' : mo < 5 ? 'spring' : mo < 8 ? 'summer' : 'autumn';
  body.setAttribute('data-season', season);
  var box = $('season');
  if(box && !reduce){
    for(var i = 0; i < (O.seasonCount || 22); i++){
      var p = document.createElement('div');
      p.className = 'p ' + season;
      var sz = 4 + Math.random() * 10;
      p.style.cssText = 'left:' + (Math.random() * 100) + '%;width:' + sz.toFixed(1) + 'px;height:' + sz.toFixed(1) + 'px;' +
        '--drift:' + ((Math.random() * 80 - 40) | 0) + 'px;--o:' + (0.35 + Math.random() * 0.5).toFixed(2) + ';' +
        'animation-duration:' + (9 + Math.random() * 10).toFixed(1) + 's;animation-delay:' + (-Math.random() * 18).toFixed(1) + 's;';
      box.appendChild(p);
    }
  }

  /* recent wins + event reactions */
  var winsBox = $('wp-wins'), fx = $('fx'), wins = [];
  function pushWin(text){
    if(!winsBox || !text) return;
    var w = document.createElement('div'); w.className = 'w'; w.innerHTML = '<b>' + esc(text) + '</b>';
    winsBox.insertBefore(w, winsBox.firstChild); wins.unshift(w);
    requestAnimationFrame(function(){ w.classList.add('on'); });
    while(wins.length > 3){ var old = wins.pop(); old.classList.remove('on'); setTimeout(function(x){ return function(){ x.remove(); }; }(old), 600); }
    setTimeout(function(){
      w.classList.remove('on'); setTimeout(function(){ w.remove(); }, 600);
      var ix = wins.indexOf(w); if(ix >= 0) wins.splice(ix, 1);
    }, 14000);
  }
  function react(ev){
    var color = TINT[ev.channel] || FALLBACK_TINT;
    if(fx && !reduce){
      var r = document.createElement('div'); r.className = 'ripple'; r.style.borderColor = color; r.style.color = color;
      fx.appendChild(r); setTimeout(function(){ r.remove(); }, 1800);
      for(var i = 0; i < 14; i++){
        var sp = document.createElement('div'); sp.className = 'spark'; sp.style.color = color;
        var a = Math.random() * 6.283, d = 120 + Math.random() * 220;
        sp.style.setProperty('--dx', (Math.cos(a) * d).toFixed(0) + 'px');
        sp.style.setProperty('--dy', (Math.sin(a) * d).toFixed(0) + 'px');
        fx.appendChild(sp); setTimeout(function(x){ return function(){ x.remove(); }; }(sp), 1200);
      }
    }
    Array.prototype.forEach.call(document.querySelectorAll('.js-surge'), function(el){
      el.classList.add('surge'); setTimeout(function(){ el.classList.remove('surge'); }, 1400);
    });
    if(ev.summary) pushWin(ev.summary);
  }
  fetch('/api/interactive', { cache:'no-store' }).then(function(r){ return r.json(); }).then(function(d){
    (d.recent || []).slice(0, 2).reverse().forEach(function(it){ if(it.text) pushWin(it.text); });
  }).catch(function(){});
  if(window.EventSource){
    try{
      var es = new EventSource('/api/stream');
      es.onmessage = function(e){ var ev; try{ ev = JSON.parse(e.data); }catch(_){ return; } react(ev); };
      es.onerror = function(){};
    }catch(_){}
  }

  /* community quotes */
  var qEl = $('wp-quote'), quotes = [];
  function loadQuotes(){
    fetch('/api/quotes', { cache:'no-store' }).then(function(r){ return r.json(); })
      .then(function(d){ quotes = (d.quotes || []).filter(function(q){ return q.text; }); }).catch(function(){});
  }
  function showQuote(){
    if(!qEl || !quotes.length) return;
    var q = quotes[(Math.random() * quotes.length) | 0];
    qEl.innerHTML = '<span class="q">“' + esc(q.text) + '”</span>' + (q.added_by ? ' <span class="by">— ' + esc(q.added_by) + '</span>' : '');
    qEl.classList.add('on'); setTimeout(function(){ qEl.classList.remove('on'); }, 9000);
  }
  if(qEl){ loadQuotes(); setInterval(loadQuotes, 240000); setTimeout(function(){ showQuote(); setInterval(showQuote, 25000); }, 3000); }
})();
