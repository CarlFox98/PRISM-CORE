/* ============================================================
   PRISM — countdown (Starting Soon)
   Shared by the 2.0 sets. Markup hooks:
     [data-prism-countdown]     container (gets class "done" at 00:00)
       .js-cd-min / .js-cd-sec  filled with zero-padded minutes / seconds
       .js-cd                   OR one element filled with "MM:SS"
     .js-cd-settings            click -> prompt for a new duration
   Duration: ?timer=N on the URL, else the last value set with the
   gear (localStorage "timer_minutes"), else 5 minutes. 1–120 allowed.
   ============================================================ */
(function(){
  "use strict";
  var KEY = 'timer_minutes';
  function valid(n){ return n > 0 && n <= 120; }
  function stored(){ try{ return parseInt(localStorage.getItem(KEY), 10); }catch(e){ return NaN; } }
  function initial(){
    var q = parseInt(new URLSearchParams(location.search).get('timer'), 10);
    if(valid(q)) return q;
    var s = stored();
    return valid(s) ? s : 5;
  }
  function pad(n){ return (n < 10 ? '0' : '') + n; }
  function each(sel, fn){ Array.prototype.forEach.call(document.querySelectorAll(sel), fn); }

  var endAt = 0, tick = null;
  function paint(){
    var left = Math.max(0, Math.round((endAt - Date.now()) / 1000));
    var m = Math.floor(left / 60), s = left % 60;
    each('[data-prism-countdown] .js-cd-min', function(el){ el.textContent = pad(m); });
    each('[data-prism-countdown] .js-cd-sec', function(el){ el.textContent = pad(s); });
    each('[data-prism-countdown] .js-cd', function(el){ el.textContent = pad(m) + ':' + pad(s); });
    each('[data-prism-countdown]', function(el){ el.classList.toggle('done', left === 0); });
    if(left === 0 && tick){ clearInterval(tick); tick = null; }
  }
  function start(mins){
    if(tick) clearInterval(tick);
    /* wall-clock based, so a throttled background tab can't drift */
    endAt = Date.now() + mins * 60000;
    paint(); tick = setInterval(paint, 250);
  }
  each('.js-cd-settings', function(el){
    el.addEventListener('click', function(){
      var cur = stored();
      var input = prompt('Countdown duration in minutes (1-120):', valid(cur) ? cur : 5);
      if(input === null) return;
      var n = parseInt(input, 10);
      if(!valid(n)) return;
      try{ localStorage.setItem(KEY, String(n)); }catch(e){}
      start(n);
    });
  });
  start(initial());
})();
