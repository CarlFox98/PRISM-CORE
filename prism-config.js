/* ============================================================
   PRISM — shared config  (single source of truth)
   Change your identity ONCE here and every scene follows.
   Load this BEFORE prism-engine.js in each scene:
       <script src="prism-config.js"></script>
       <script src="prism-engine.js"></script>

   What lives here:
     channel        — Twitch login name (drives all live data)
     displayName    — how your name is shown / avatar alt text
     goal           — default follower-goal target (a scene may
                      still override with data-goal on <body>)
     avatarFallback — avatar shown before live data loads
     spotifyClientId— reference for the now-playing widget
                      (must match the id inside prism-nowplaying.html)
     socials        — the pills rendered into any element marked
                      <div class="socials" data-prism-socials></div>
   ============================================================ */
window.PRISM_CONFIG = {
  channel: "NeoTheFox98",
  displayName: "NeoTheFox98",
  goal: 100,
  avatarFallback: "https://static-cdn.jtvnw.net/jtv_user_pictures/f8059656-f846-4bfa-9cd5-e70afba5692e-profile_image-300x300.png",
  spotifyClientId: "a8793e9128944860af2dbe769651d44c",
  socials: [
    { icon: "x.com",              alt: "X",     label: "@NeoTheFox98",  url: "https://x.com/NeoTheFox98" },
    { icon: "youtube.com",        alt: "YT",    label: "/NeoTheFox-98", url: "https://www.youtube.com/@NeoTheFox-98" },
    { icon: "telegram.org",       alt: "TG",    label: "@NeoTheFox98",  url: "https://t.me/NeoTheFox98" },
    { icon: "steamcommunity.com", alt: "Steam", label: "/NeoTheFox98",  url: "https://steamcommunity.com/id/NeoTheFox98" }
  ]
};
