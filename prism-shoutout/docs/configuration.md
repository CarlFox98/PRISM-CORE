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
| `COMMAND_ALIASES` | `["!shoutout"]` | Other spellings that mean the same thing. |
| `ALLOW_SELF_SHOUTOUT` | `False` | Let `!so` target your own channel. |
| `MODS_ONLY` | `True` | If true, only mods/broadcaster can trigger. |
| `RAID_SHOUTOUT` | `True` | Auto-shout whoever raids the channel. |
| `COOLDOWN_SEC` | `3` | Debounce — ignore a repeat `!so` within N seconds. |
| `REPEAT_GUARD_SEC` | `30` | Also refuse the same login while its card is queued or on screen, plus this many seconds after it leaves. |
| `MAX_QUEUE_SEC` | `120` | Refuse new shoutouts once the overlay is this far backed up. |

A card can hold the screen for up to ~41 seconds, so the 3-second debounce was
never enough on its own: a raid followed by a mod's reflex `!so @raider` used to
queue a second identical card. The service now tracks how much card time it has
handed the overlay and guards each login until well after its card is gone.

`!so clear` releases that reservation. `!so skip` deliberately does not — if you
skipped a card, you probably do not want it back three seconds later.

The overlay enforces its own limits as a backstop, since anything pointed at the
WebSocket can send it cards: it drops a login already on screen or already
waiting, and holds at most `CFG.maxQueue` (5) cards behind the current one.

## Who may be shouted out

These are the safety gates. A raid is **unattended** — nobody approves it before
it reaches the screen — so if you are being raid-bombed, `RAID_REQUIRE_APPROVAL`
is the switch that puts a human back in the loop.

| Setting | Default | Notes |
|---------|---------|-------|
| `BLOCKLIST` | `[]` | Logins that are **never** shouted out, by command or by raid. Lowercase. |
| `RAID_ALLOWLIST` | `[]` | If non-empty, only these logins get an automatic raid shoutout. A manual `!so` is unaffected. |
| `RAID_REQUIRE_APPROVAL` | `False` | Hold every raid shoutout until a mod types `!so ok`. Nothing reaches the screen on its own. |
| `RAID_APPROVAL_TTL` | `120` | Seconds a pending raid stays approvable before it lapses. |
| `RAID_MIN_VIEWERS` | `2` | Ignore raids smaller than this. Does not affect a manual `!so`. |

Only one raid can be pending at a time — a second raid replaces the first.

## Mod controls

Subcommands of `COMMAND`, restricted by the same privilege check as `!so` itself.

| Command | What it does |
|---------|--------------|
| `!so skip` | Retires the card on screen right now; the queue continues. |
| `!so clear` | Retires the on-screen card **and** drops everything queued behind it. |
| `!so off` | Stops firing shoutouts — commands and raids both — until `!so on`. |
| `!so on` | Resumes. |
| `!so ok` | Approves the pending raid (see `RAID_REQUIRE_APPROVAL`). |
| `!so status` | Prints the current state to the service console. |

| Setting | Default | Notes |
|---------|---------|-------|
| `CONTROLS_ENABLED` | `True` | Master switch for the subcommands above. |

The target can be typed however a mod has it to hand — `@name`, `name`, or a
pasted `twitch.tv/name` link (with or without `https://`, `www.` or tracking
query junk). All of them resolve to the same login.

> A **bare** word is read as a control. Prefix with `@` to shout out someone
> whose name collides with one — `!so @skip` still shouts out the streamer
> called *skip*.

`skip` and `clear` are pushed to the overlay over the same WebSocket as the
cards, so they take effect immediately even mid-clip. Stopping the service is
no longer the only way out of a bad card.

## Card timing

| Setting | Default | Notes |
|---------|---------|-------|
| `HOLD_MS` | `18000` | Fallback on-screen time for a card with a clip, if the clip length is unknown. |
| `NOCLIP_HOLD_MS` | `8000` | On-screen time when the user has no clip. |

When a clip's real duration is known, the card holds for the clip length
(clamped 6–40s, plus ~1.4s) instead of `HOLD_MS`.

## The card itself

Most of the card needs no configuration, but two behaviours are worth knowing:

- **If a clip dies mid-play**, the card no longer sits on a dead frame for the
  clip's full runtime. The overlay caps what is left at `NOCLIP_HOLD_MS` and
  restarts the progress rail to match.
- **The name is fitted to the column**, shrinking from 44px until it fits on one
  line (floor 22px, then it wraps). A fixed size meant a 13-character name
  wrapped mid-word and moved everything below it.

When a streamer has no clip in either window, the card uses their Twitch
**offline banner** as the backdrop with the label as a caption, instead of a
grey panel. It comes from `offline_image_url` in the same `/users` response the
avatar comes from.

## Clip volume

| Setting | Default | Notes |
|---------|---------|-------|
| `CLIP_VOLUME` | `0.85` | Ceiling the clip is played at (0.0–1.0). |
| `CLIP_FADE_IN_MS` | `320` | Ramp up to that ceiling over this long. |

Clips used to play at full scale, which either buried them or clipped the mix
depending on how hot the source was. Both values ride along in the card payload,
so the overlay needs no edit when you change them.

Keeping `CLIP_FADE_IN_MS` equal to `DUCK_FADE_MS` matters: the clip's audio and
the duck then move as one. When the clip snapped to full volume at a fixed
250ms while the duck was still ramping over 320ms, the loudest moment of the
whole card was that overlap.

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

## Shoutout log

| Setting | Default | Notes |
|---------|---------|-------|
| `SHOUTOUT_LOG` | `prism-shoutout/shoutout-log.jsonl` | Append-only JSONL record of every shoutout. `""` turns it off. |

One line per shoutout: timestamp, login, display name, source (`command` /
`raid` / `approved`), raider count, live flag, category, clip id and whether a
clip actually played. The file is git-ignored.

It is not just a record. On startup the service reads it back to restore clip
rotation, so a restart no longer forgets what it has shown and replay the same
clip. Writing is best-effort — a log that cannot be written never costs you a
shoutout.

## Chat posting

| Setting | Default | Notes |
|---------|---------|-------|
| `CHAT_SEND` | `True` | Master switch; posting still only happens if bot creds are set. |
| `CHAT_TEMPLATE` | … | Line posted for an offline user. Placeholders: `{name}`, `{login}`, `{game}`. |
| `CHAT_TEMPLATE_LIVE` | … | Line posted when the user is live now. |
| `CHAT_TEMPLATE_RAID` | … | Line posted for a raid. Extra placeholder: `{viewers}` ("42 viewers", "1 viewer", or empty). |
| `NOTFOUND_TEMPLATE` | … | Line posted when the login can't be found. Placeholder: `{login}`. |

## OBS audio ducking

| Setting | Default | Notes |
|---------|---------|-------|
| `DUCK_ENABLED` | `True` | Master switch for ducking. |
| `OBS_WS_URL` | `ws://127.0.0.1:4455` | obs-websocket address (also reads env `OBS_WS_URL`). |
| `OBS_WS_PASSWORD` | *(secret)* | obs-websocket password. |
| `DUCK_KEEP` | `0.30` | Default fraction of volume kept while a clip plays (0.30 ≈ −70%). |
| `DUCK_LEVELS` | `{}` | Per-source overrides by OBS input name (case-insensitive). `1.0` leaves a source alone. |
| `DUCK_SOURCES` | `[]` | Explicit source names to lower; empty = auto (all audio sources). |
| `DUCK_EXCLUDE` | `["PRISM Shoutout"]` | Never lower these — put your shoutout Browser Source name here. |
| `DUCK_FADE_MS` | `320` | Fade duration down/up in milliseconds. |
| `MAX_DUCK_SEC` | `65` | Safety cap; audio is force-restored after this even if a `clipend` is lost. |
| `DUCK_TARGET_TTL` | `60` | Seconds to reuse the discovered source list before re-probing OBS. |

You usually talk **over** a shoutout clip, so a single flat level for everything
is the wrong shape — it drops your mic along with the game. Give the mic a high
keep and the noisy sources a low one:

```python
DUCK_LEVELS = {"Mic/Aux": 0.90, "Desktop Audio": 0.15, "Spotify": 0.10}
```

Anything not listed uses `DUCK_KEEP`. The level used for each source is saved
alongside its original volume, so the fade back up starts exactly where the fade
down finished.
