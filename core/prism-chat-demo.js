/* ============================================================
   PRISM — chat preview feed (preview scenes only)
   Builds SoundAlerts-style chat markup (.chat__item …) into #feed and
   drops a new line every few seconds, so a set's chat CSS can be judged
   in a browser. The real overlay is the set's prism-chat-*.css pasted
   into SoundAlerts / the OBS source's Custom CSS.
   Palette: window.PRISM_CHATDEMO = { colors:['#..','#..'] }
   ============================================================ */
(function(){
  "use strict";
  var O = window.PRISM_CHATDEMO || {};
  var C = O.colors || ['#57F2E4','#6C8BFF','#B983FF','#FF7ACB','#FFD86B'];
  function c(i){ return C[i % C.length]; }
  function av(a, b){
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>" +
      "<stop offset='0' stop-color='" + a + "'/><stop offset='1' stop-color='" + b + "'/></linearGradient></defs>" +
      "<rect width='32' height='32' rx='9' fill='url(#g)'/></svg>");
  }
  function badge(col){
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' width='18' height='18'><rect width='18' height='18' rx='4' fill='" + col + "'/>" +
      "<circle cx='9' cy='9' r='3.4' fill='rgba(255,255,255,.85)'/></svg>");
  }
  var MSGS = [
    { u:'Nova_Rider',  b:[2],    m:'the new overlay goes so hard' },
    { u:'pixel_witch', b:[0,4],  m:'okay that countdown font is perfect' },
    { u:'grumbot',     b:[],     m:'chat is officially readable on my phone now' },
    { u:'Aria.exe',    b:[1],    m:'gg on that last run!!' },
    { u:'deltaWolf',   b:[0],    m:'Cheer100 <span class="chat__cheermote"><span class="chat__cheermote--amount">x100</span></span> for the fox' },
    { u:'lumen',       b:[],     m:'hi hi, just got here — what did I miss?' },
    { u:'K3RN3L',      b:[3,0],  m:'the shoutout card slaps' },
    { u:'soft_static', b:[4],    m:'followed! love the vibes in here' }
  ];
  var feed = document.getElementById('feed'); if(!feed) return;
  var n = 0;
  function line(d){
    var item = document.createElement('div');
    item.className = 'chat__item';
    var badges = d.b.map(function(i){ return '<img class="chat__badge" alt="" src="' + badge(c(i)) + '">'; }).join('');
    item.innerHTML =
      '<div class="chat__item-transform-wrapper"><div class="chat__item-inner">' +
      '<span class="chat__metadata"><span class="chat__metadata-inner">' +
      '<img class="chat__avatar" alt="" src="' + av(c(n), c(n + 2)) + '">' +
      '<span class="chat__badges">' + badges + '</span></span></span>' +
      '<span class="chat__user" style="--user-color:' + c(n + 1) + '">' + d.u + '</span>' +
      '<span class="chat__message">' + d.m + '</span></div></div>';
    n++;
    feed.insertBefore(item, feed.firstChild);
    while(feed.children.length > 9) feed.removeChild(feed.lastChild);
  }
  MSGS.slice(0, 5).reverse().forEach(line);
  var i = 5;
  setInterval(function(){ line(MSGS[i % MSGS.length]); i++; }, 2600);
})();
