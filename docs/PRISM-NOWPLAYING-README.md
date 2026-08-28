# PRISM — Spotify Now-Playing Widget (permanent setup)

A standalone Spotify "now playing" card you add as its **own OBS Browser Source**,
floating over any scene (local or hosted). Set it up once; every scene benefits,
forever. No per-scene Spotify code.

## Why hosting fixes the flakiness
Spotify (since April 2025) only accepts a redirect URI that is **HTTPS** or a
loopback IP. A `file://` overlay can never authenticate. Hosting this one widget
on GitHub Pages gives it a permanent HTTPS address, so auth is registered once
and never breaks.

## One-time setup

1. **Publish to GitHub Pages**
   - Create a public repo (e.g. `stream-overlays`).
   - Upload `widgets/prism-nowplaying.html` (uploading it as `index.html` gives the
     cleanest URL).
   - Settings → Pages → Deploy from branch → `main` / root → Save.
   - Your URL will be like: `https://<username>.github.io/stream-overlays/`

2. **Register the Redirect URI in Spotify**
   - developer.spotify.com/dashboard → your app → Settings → Redirect URIs.
   - Add the **exact** URL from step 1 (the widget also prints it on screen).
   - Save.

3. **Authorize once, inside OBS** (important)
   - Add a Browser Source pointing at your Pages URL. Size ~460×110.
   - Right-click the source → **Interact** → click **Connect** → log in to Spotify.
   - The token is stored *inside OBS* and survives restarts. Because Chrome and
     OBS use separate storage, you must connect from within OBS, not desktop Chrome.

That's it. The card shows your current track and auto-refreshes.

## Notes
- Client ID: defaults to your existing app. Override with `?cid=YOUR_ID` on the URL.
- Nothing playing → the card shows a paused state; it keeps the last art briefly.
- The widget self-computes its redirect URI from its own address, so it works at
  any repo/path — just register whatever URL it prints.
- To retheme, edit the `--c1`…`--c5` palette variables in `core/prism-theme.css` (same as the
  rest of the PRISM set).
