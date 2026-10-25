# PRISM Shoutout: setup

A mod types **`!so @username`** in Twitch chat, and a PRISM card slides in
with that streamer's avatar, their last category and a recent clip, then fades
out. A raid gets the gold "Raid · N viewers" variant automatically.

**Shoutouts are run by [Stream Manager](https://github.com/CarlFox98/stream-manager)
now.** The Python service that used to live here (`prism_shoutout_service.py`,
the `prism-shoutout/` package and `tools\Start-PRISM-Shoutout.bat`) was merged
into Stream Manager in September 2026 as `stream_manager/shoutout.py`, and
removed from this repo.

## Setup

1. Run Stream Manager. It already has the Twitch login the shoutout needs.
2. In OBS, add a **Browser Source** at
   `http://localhost:5000/static/interactive/shoutout.html`, sized
   **1920×1080**, above your scenes. It's transparent and idle until a
   shoutout fires.
3. Have a mod (or you) type `!so @someone`.

Stream Manager serves its own copy of the card over HTTP and feeds it through
a long-poll on `/api/effects/shoutout`. It plays the clip's video file
directly, so the card doesn't need to be hosted on a real domain.

## Options

Settings live in Stream Manager's `config.json` under `shoutout` (see
`DEFAULTS` in `stream_manager/shoutout.py`). The main ones:

- **`mods_only`** (on): only mods and the broadcaster can use `!so`.
- **`chat_send`** (on): post the shoutout line in chat as well.
- **`raid_shoutout`** (on), **`raid_min_viewers`** (2) and
  **`raid_require_approval`** (off): automatic raid shoutouts, optionally
  waiting for a mod's `!so ok`.
- **`blocklist`**: channels that never get a card.
- **How long the card stays:** with a clip, the clip's length (clamped to
  6–40 s); with no clip, `noclip_hold_ms` (8 s). `hold_ms` (18 s) is the
  fallback when a clip's length is unknown.

Mod controls in chat: `!so skip`, `!so clear`, `!so off`, `!so on`,
`!so ok` (approve a waiting raid) and `!so status`.

## The card in this repo

`widgets/prism-shoutout.html` is the original WebSocket build
(`ws://127.0.0.1:8777`). Nothing serves that socket any more, so the card in
this repo is a reference implementation and the target of the headless test,
not what OBS loads. A change to the card's look or timing has to be made in
**both** copies. The test runs against either:

```bash
node scripts/test-shoutout-overlay.mjs
node scripts/test-shoutout-overlay.mjs "<stream-manager>/static/interactive/shoutout.html"
```

Open either copy with `?demo` in a normal browser to preview the design.
