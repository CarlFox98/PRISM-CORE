/* ============================================================
   PRISM — Technical Difficulties status checker
   Shared by the 2.0 sets (the 1.x holo scene keeps its inline copy).

   Watches whether the channel is live (DecAPI uptime — no token, no
   secret). OBS state comes from Stream Manager's /api/status when the
   scene is served by it (it already polls OBS with the password from
   its .env, so nothing secret lives in this page); OBS's own websocket
   is used on top of that for the desktop-audio tile and to switch OBS
   to sceneToSwitch once the stream is back. The websocket only works
   when OBS's WebSocket authentication is off, or a password is given
   below — prefer leaving it out and letting Stream Manager report.

   Markup hooks (all optional):
     #itemPc, #itemAudio        status tiles; get state-ok|warn|error,
                                their .icon-check gets a short label
     #statusDot / #statusText   stream status line
     #backAnnouncement          gets class "visible" when back

   Override defaults before this script loads:
     window.PRISM_TECHCHECK = { obs:{ port:4455, password:'' }, ... }
   Never put a Twitch client secret in a browser source.
   ============================================================ */
(function(){
  "use strict";
  var CFG = window.PRISM_CONFIG || {};
  var O = window.PRISM_TECHCHECK || {};
  var CONFIG = {
    channel: O.channel || CFG.channel || '',
    obs: Object.assign({ enabled:true, host:'localhost', port:4455, password:'', sceneToSwitch:'Starting Soon' }, O.obs || {}),
    pollInterval: O.pollInterval || 30000,
    minShowTime: O.minShowTime || 15000
  };
  var STATES = ['state-ok','state-warn','state-error'];
  var $ = function(id){ return document.getElementById(id); };
  var dot = $('statusDot'), statusText = $('statusText'), announcement = $('backAnnouncement');
  var isLive = false, shownAt = Date.now();
  var obsWs = null, obsReqId = 0, obsPending = {};

  function setItem(id, state, label){
    var el = $(id); if(!el) return;
    STATES.forEach(function(c){ el.classList.remove(c); });
    if(state) el.classList.add('state-' + state);
    var check = el.querySelector('.icon-check');
    if(check) check.textContent = label || '';
  }
  function setStatus(state, text){
    if(dot){ dot.classList.remove('live','offline','error'); if(state) dot.classList.add(state); }
    if(statusText) statusText.textContent = text;
    document.body.setAttribute('data-stream', state || '');
  }
  function showBack(){
    if(announcement) announcement.classList.add('visible');
    setTimeout(switchScene, 3000);
    setTimeout(function(){ if(announcement) announcement.classList.remove('visible'); }, 8000);
  }
  function req(type, data){
    return new Promise(function(resolve, reject){
      if(!obsWs || obsWs.readyState !== WebSocket.OPEN){ reject(new Error('OBS not connected')); return; }
      var rid = 'r' + (++obsReqId);
      obsPending[rid] = { resolve:resolve, reject:reject };
      obsWs.send(JSON.stringify({ op:6, d:{ requestType:type, requestId:rid, requestData:data || {} } }));
      setTimeout(function(){ if(obsPending[rid]){ obsPending[rid].reject(new Error('OBS timeout')); delete obsPending[rid]; } }, 5000);
    });
  }
  function b64(buf){ return btoa(String.fromCharCode.apply(null, new Uint8Array(buf))); }
  function connect(){
    if(!CONFIG.obs.enabled) return;
    try{
      obsWs = new WebSocket('ws://' + CONFIG.obs.host + ':' + CONFIG.obs.port);
      obsWs.onmessage = async function(ev){
        var msg = JSON.parse(ev.data);
        if(msg.op === 0){
          var id = { op:1, d:{ rpcVersion:1 } };
          if(CONFIG.obs.password && msg.d.authentication){
            /* OBS websocket v5: base64(sha256(base64(sha256(password + salt)) + challenge)) */
            var enc = new TextEncoder(), a = msg.d.authentication;
            var secret = b64(await crypto.subtle.digest('SHA-256', enc.encode(CONFIG.obs.password + a.salt)));
            id.d.authentication = b64(await crypto.subtle.digest('SHA-256', enc.encode(secret + a.challenge)));
          }
          obsWs.send(JSON.stringify(id));
        }
        if(msg.op === 2){ setItem('itemPc', 'ok', 'OK'); poll(); setInterval(poll, CONFIG.pollInterval); }
        if(msg.op === 7){ var p = obsPending[msg.d.requestId]; if(p){ delete obsPending[msg.d.requestId]; p.resolve(msg.d); } }
      };
      obsWs.onerror = function(){ if(!smSeen) setItem('itemPc', 'error', 'NO OBS'); };
      obsWs.onclose = function(){ obsWs = null; if(!smSeen) setItem('itemPc', 'error', 'DISCONNECTED'); setTimeout(connect, 10000); };
    }catch(e){ setItem('itemPc', 'error', 'NO OBS'); }
  }
  function switchScene(){
    if(!obsWs || obsWs.readyState !== WebSocket.OPEN) return;
    req('SetCurrentProgramScene', { sceneName: CONFIG.obs.sceneToSwitch }).catch(function(){});
  }
  async function poll(){
    if(!obsWs || obsWs.readyState !== WebSocket.OPEN) return;
    try{
      var r = await req('GetInputList', { inputKind:'wasapi_output_capture' });
      var desk = (r.inputs || []).find(function(i){ return i.inputName && i.inputName.indexOf('Desktop') !== -1; });
      if(desk){
        var m = await req('GetInputMute', { inputName: desk.inputName });
        setItem('itemAudio', m.inputMuted ? 'warn' : 'ok', m.inputMuted ? 'MUTED' : 'OK');
      } else setItem('itemAudio', 'warn', 'NO SRC');
    }catch(e){ setItem('itemAudio', 'warn', '--'); }
    try{
      var s = await req('GetStreamStatus');
      if(s.outputActive && !isLive) setStatus('live', 'OBS STREAMING');
    }catch(e){}
  }
  async function check(){
    try{
      var ctrl = new AbortController(), to = setTimeout(function(){ ctrl.abort(); }, 6000);
      var res = await fetch('https://decapi.me/twitch/uptime/' + encodeURIComponent(CONFIG.channel), { signal: ctrl.signal });
      clearTimeout(to);
      if(!res.ok) throw new Error('HTTP ' + res.status);
      var text = (await res.text()).trim();
      isLive = !!text && !/offline|error|unable|not found|must be/i.test(text);
      if(isLive){ setStatus('live', 'STREAM LIVE'); if(Date.now() - shownAt >= CONFIG.minShowTime) showBack(); }
      else setStatus('offline', 'STREAM OFFLINE');
    }catch(e){ setStatus('error', 'CHECK FAILED'); }
  }
  /* Stream Manager's view of OBS (same origin when served from :5000). */
  var smSeen = false;
  function pollManager(){
    fetch('/api/status', { cache:'no-store' }).then(function(r){ if(!r.ok) throw 0; return r.json(); })
      .then(function(st){
        var o = (st && st.obs) || {};
        smSeen = true;
        if(!obsWs || obsWs.readyState !== WebSocket.OPEN){
          setItem('itemPc', o.running ? 'ok' : 'error', o.running ? 'OK' : 'NO OBS');
        }
        setItem('itemOverlay', 'ok', 'OK');          /* this page loaded from Stream Manager */
        if(o.streaming && !isLive) setStatus('live', 'OBS STREAMING');
      })
      .catch(function(){ if(smSeen) setItem('itemOverlay', 'error', 'NO SERVER'); });
  }
  function boot(){
    shownAt = Date.now();
    if(!CONFIG.channel){ setStatus('error', 'SETUP REQUIRED'); return; }
    setStatus('', 'CHECKING…');
    setTimeout(function(){ check(); setInterval(check, CONFIG.pollInterval); }, 2000);
    pollManager(); setInterval(pollManager, 10000);
    connect();
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
