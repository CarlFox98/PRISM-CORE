# PRISM Shoutout — setup

A mod types **`!so @username`** in your Twitch chat →  a PRISM card slides
in with that streamer's hex avatar, their last category, and an
**autoplaying recent clip**, then gracefully fades out.

Two pieces:

| File | What it is | Where it runs |
|------|------------|---------------|
| `prism-shoutout.html` | the on-screen overlay | **hosted** (GitHub Pages) → OBS Browser Source |
| `prism_shoutout_service.py` | watches chat, does Twitch lookups, drives the overlay | on your PC (Python) |

The overlay must be **hosted** (not a local file) so the Twitch clip can
autoplay — the clip embed requires a real domain as its "parent", and your
`carlfox98.github.io` gives us that.

--------------------------------------------------------------------
## 1. Host the overlay
--------------------------------------------------------------------
Add `prism-shoutout.html` to your existing Pages repo (the `streaming`
one). From that repo folder:

```
copy "C:\Users\NeoTheFox98\Pictures\OBS Assets\overlays\PRISM\prism-shoutout.html" .
git add prism-shoutout.html
git commit -m "PRISM shoutout overlay"
git push
```

Live URL:  **`https://carlfox98.github.io/streaming/prism-shoutout.html`**

--------------------------------------------------------------------
## 2. Add it to OBS
--------------------------------------------------------------------
Add a **Browser Source** → URL = the link above, **1920×1080**, and place
it above your scene(s) where you want the card to appear. It's transparent
and idle until a shout fires. It auto-connects to the service on
`ws://127.0.0.1:8777`.

--------------------------------------------------------------------
## 3. Run the service
--------------------------------------------------------------------
```
pip install websockets requests
```

Open `prism_shoutout_service.py` and set (top of file, or as env vars):

- `CHANNEL` → `NeoTheFox98`  (already set)
- `CLIENT_ID` → your SYSFOX app Client ID  (already filled in)
- `CLIENT_SECRET` → your SYSFOX app **Client Secret**  ← the only thing you must add

Then run it (keep it running while you stream):

```
python prism_shoutout_service.py
```

You'll see `[chat] listening…` and `[overlay] connected` once OBS loads the
source. Have a mod (or you) type `!so @someone` — the card appears.

--------------------------------------------------------------------
## Options / notes
--------------------------------------------------------------------
- **Mods only** by default (`MODS_ONLY = True`). Broadcaster always allowed.
- **Chat message:** off by default. Either let SYSFOX post the `!so` line,
  or set `CHAT_SEND = True` + `BOT_USERNAME` + `BOT_OAUTH` (an `oauth:...`
  token for the sending account) to have this service post it too.
- **On-screen time:** `HOLD_MS` (default 18s). Clips can be up to 60s.
- **Clip choice:** newest clip within `CLIP_LOOKBACK_DAYS` (90); falls back
  to the channel's top clip if none recent. Shows a tasteful "No recent
  clip" panel if the user has none.
- **No secret is ever exposed** — the secret lives only in this local
  service; the hosted overlay just receives display data over local WS.
- **Prefer to fold it into SYSFOX?** Import the logic and call
  `await do_shoutout("username")` from your own command handler instead of
  using the built-in chat reader — the WebSocket overlay push is the same.
- The service must be running for shouts to show. If the overlay ever fails
  to connect (rare CEF quirk with loopback WebSockets), tell me and I'll add
  a secure-tunnel fallback.

Tip: open `…/prism-shoutout.html?demo` in a normal browser to preview the
card design any time.
