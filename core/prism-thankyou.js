/* ============================================================
   PRISM — Thank-a-follower card
   Shared by the 2.0 sets. Picks a random follower (no repeats until
   everyone has been thanked) and shows the card.

   Trigger: the on-screen button (OBS: Interact), Space/Enter, or ?auto
   on the URL. ?hidebar hides the button bar, ?demo shows a sample card.

   Markup hooks: #card (gets class "show"), #name, #msg, #bar, #pick, #note.
   Override defaults before this script loads:
     window.PRISM_THANKYOU = { messages:[...], autoHideSeconds:8 }
   ============================================================ */
(function(){
  "use strict";
  var CFG = window.PRISM_CONFIG || {};
  var O = window.PRISM_THANKYOU || {};
  var CONFIG = {
    channel: O.channel || CFG.channel || '',
    /* resolved against the PAGE: themes/<set>/ in the repo, flat in a built set */
    listUrl: O.listUrl || '../../data/prism-followers.json',
    autoHideSeconds: O.autoHideSeconds != null ? O.autoHideSeconds : 8,
    noRepeatUntilExhausted: O.noRepeatUntilExhausted !== false,
    messages: O.messages || [
      "Welcome to the pack — glad you're here!",
      "Thanks for the follow. Enjoy the stream!",
      "You just made the stream a little brighter.",
      "Big thanks for following — see you in chat!"
    ]
  };
  /* used only if prism-followers.json can't be read */
  var FALLBACK = ["SampleFox_01","NightOwlGamer","PixelPanda","QuietStorm88","RetroRacer",
                  "LunaByte","CaffeineKat","TheReal_Vex","MapleSyrupGG","Zephyr_Plays"];

  var $ = function(id){ return document.getElementById(id); };
  var card = $('card'), nameEl = $('name'), msgEl = $('msg'), bar = $('bar'), note = $('note');
  var params = new URLSearchParams(location.search);
  var names = [], pool = [], hideTimer = null, source = '';

  function showNote(t){ if(!note) return; note.textContent = t || ''; note.classList.toggle('hidden', !t); }
  function normalize(data){
    var arr = Array.isArray(data) ? data : (data && Array.isArray(data.followers) ? data.followers : null);
    if(!arr) return null;
    return arr.map(function(x){ return typeof x === 'string' ? x : (x && (x.name || x.user_name || x.login)); })
              .map(function(s){ return (s || '').trim(); }).filter(Boolean);
  }
  function loadList(){
    return fetch(CONFIG.listUrl, { cache:'no-store' })
      .then(function(r){ if(!r.ok) throw 0; return r.json(); })
      .then(function(j){ var n = normalize(j); if(n && n.length){ names = n; source = 'file'; return; } throw 0; })
      .catch(function(){
        names = FALLBACK.slice(); source = 'fallback';
        if(!CONFIG.channel) return;
        return fetch('https://decapi.me/twitch/followers/' + encodeURIComponent(CONFIG.channel))
          .then(function(r){ return r.ok ? r.text() : ''; })
          .then(function(t){ t = (t || '').trim();
            if(t && !/error|unable|not found|must be/i.test(t) && names.indexOf(t) === -1) names.unshift(t); })
          .catch(function(){});
      });
  }
  function refill(){
    pool = names.slice();
    for(var i = pool.length - 1; i > 0; i--){ var j = Math.floor(Math.random() * (i + 1)); var t = pool[i]; pool[i] = pool[j]; pool[j] = t; }
  }
  function next(){
    if(!names.length) return null;
    if(CONFIG.noRepeatUntilExhausted){ if(!pool.length) refill(); return pool.pop(); }
    return names[Math.floor(Math.random() * names.length)];
  }
  function show(who){
    nameEl.textContent = who;
    msgEl.textContent = CONFIG.messages[Math.floor(Math.random() * CONFIG.messages.length)];
    card.classList.remove('show'); void card.offsetWidth; card.classList.add('show');
    clearTimeout(hideTimer);
    if(CONFIG.autoHideSeconds > 0) hideTimer = setTimeout(function(){ card.classList.remove('show'); }, CONFIG.autoHideSeconds * 1000);
  }
  function pick(){ var who = next(); if(who) show(who); }

  if(bar && !params.has('hidebar')) bar.classList.remove('hidden');
  if($('pick')) $('pick').addEventListener('click', pick);
  document.addEventListener('keydown', function(e){ if(e.code === 'Space' || e.code === 'Enter'){ e.preventDefault(); pick(); } });

  if(params.has('demo')){
    names = ['PixelWitch']; CONFIG.autoHideSeconds = 0; show('PixelWitch');
    return;
  }
  loadList().then(function(){
    showNote(source === 'fallback' ? 'Using placeholder names — run tools\\refresh-followers.bat to load your real followers' : '');
    if(params.has('auto')) setTimeout(pick, 900);
  });
})();
