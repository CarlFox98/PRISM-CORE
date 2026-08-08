# Configuration reference

All settings live in [`prism_shoutout/config.py`](../prism_shoutout/config.py).
Edit that file for behavior, and keep **secrets** out of it — those come from
environment variables or `prism-secrets.json`.

## Secrets and how they're resolved

For each secret, the value is taken from the **first** source that has it:

1. an environment variable of the same name
2. `prism-secrets.json`
3. a built-in default (usually empty)

`prism-secrets.json` is searched for in this order (first match wins):

1. the path in the `PRISM_SECRETS` environment variable, if set
2. the current working directory
3. the repo root (next to the `prism_shoutout` package)
4. the parent of the repo root (e.g. the `prismenv` folder)

This is why the service finds your secrets whether it's started with
`python -m prism_shoutout` from the repo, or via the `Start-PRISM-Shoutout.bat`
launcher from the parent folder. On startup it prints which file it loaded.

| Key | Meaning |
|-----|---------|
| `CHANNEL` | Your Twitch login (the channel whose chat is watched). |
| `CLIENT_ID` | Twitch application Client ID. |
| `CLIENT_SECRET` | Twitch application Client Secret. |
| `OBS_WS_PASSWORD` | Password from OBS → Tools → WebSocket Server Settings (only needed for ducking). |
| `BOT_USERNAME` | Account used to post the shoutout line in chat (optional). |
| `BOT_OAUTH` | OAuth token for that account, format `oauth:xxxx` (optional). |

## Overlay server

| Setting | Default | Notes |
|---------|---------|-------|
| `WS_HOST` | `127.0.0.1` | Bind address of the overlay WebSocket server. |
| `WS_PORT` | `8777` | Port the overlay connects to. Change here **and** in the overlay if needed. |

## Trigger behavior

| Setting | Default | Notes |
|---------|---------|-------|
| `COMMAND` | `!so` | The chat command that fires a shoutout. |
| `MODS_ONLY` | `True` | If true, only mods/broadcaster can trigger. |
| `RAID_SHOUTOUT` | `True` | Auto-shout whoever raids the channel. |
| `COOLDOWN_SEC` | `3` | Ignore repeat `!so` for the same user within N seconds. |

## Card timing

| Setting | Default | Notes |
|---------|---------|-------|
| `HOLD_MS` | `18000` | Fallback on-screen time for a card with a clip, if the clip length is unknown. |
| `NOCLIP_HOLD_MS` | `8000` | On-screen time when the user has no clip. |

When a clip's real duration is known, the card holds for the clip length
(clamped 6–40s, plus ~1.4s) instead of `HOLD_MS`.

## Clip selection

Two tiers, in order:

1. **Primary** — **randomly among the newest `CLIP_RECENT_POOL`** clips (by date)
   created within `CLIP_RECENT_DAYS`. Recent, but it rotates rather than looping
   just the single newest.
2. **Fallback** — if there are none that recent, **randomly pick among the most
   popular** clips (by views) created within `CLIP_POPULAR_DAYS`.

Both tiers skip the last `CLIP_HISTORY` clips already shown for that streamer, so
repeated shoutouts rotate instead of replaying one clip. If the streamer has no
clips within the fallback window either, the overlay shows a "no clip" card.

| Setting | Default | Notes |
|---------|---------|-------|
| `CLIP_RECENT_DAYS` | `7` | Primary window — consider clips created within this many days. |
| `CLIP_RECENT_POOL` | `8` | Primary — randomize among the newest N clips (by date) in that window. |
| `CLIP_POPULAR_DAYS` | `30` | Fallback window — random among most-viewed clips within this many days. |
| `CLIP_TOP_N` | `5` | Fallback only: pick randomly among the strongest N clips by view count. |
| `CLIP_HISTORY` | `3` | Remember this many recent clips per streamer to avoid repeats. |

> The clip query passes **both** `started_at` and `ended_at`. Passing only
> `started_at` makes Twitch use a 1-week window from that date — which used to
> collapse the pool to a single old clip and caused the same clip to replay.

## Chat posting

| Setting | Default | Notes |
|---------|---------|-------|
| `CHAT_SEND` | `True` | Master switch; posting still only happens if bot creds are set. |
| `CHAT_TEMPLATE` | … | Line posted for an offline user. Placeholders: `{name}`, `{login}`, `{game}`. |
| `CHAT_TEMPLATE_LIVE` | … | Line posted when the user is live now. |
| `NOTFOUND_TEMPLATE` | … | Line posted when the login can't be found. Placeholder: `{login}`. |

## OBS audio ducking

| Setting | Default | Notes |
|---------|---------|-------|
| `DUCK_ENABLED` | `True` | Master switch for ducking. |
| `OBS_WS_URL` | `ws://127.0.0.1:4455` | obs-websocket address (also reads env `OBS_WS_URL`). |
| `OBS_WS_PASSWORD` | *(secret)* | obs-websocket password. |
| `DUCK_KEEP` | `0.30` | Fraction of volume kept while a clip plays (0.30 ≈ −70%). |
| `DUCK_SOURCES` | `[]` | Explicit source names to lower; empty = auto (all audio sources). |
| `DUCK_EXCLUDE` | `["PRISM Shoutout"]` | Never lower these — put your shoutout Browser Source name here. |
| `DUCK_FADE_MS` | `320` | Fade duration down/up in milliseconds. |
| `MAX_DUCK_SEC` | `65` | Safety cap; audio is force-restored after this even if a `clipend` is lost. |
