# Architecture

PRISM Shoutout is a small asyncio application split into single-responsibility
modules. Everything funnels through one action — `service.do_shoutout(login)` —
which is invoked either by a chat command/raid or (if you embed the package)
directly from your own code.

## Runtime flow

```
                         ┌───────────────────────────────┐
   Twitch IRC  ─────────▶│ chat.chat_reader(handler)      │
   (!so / raid)          │  parse tags, check privilege   │
                         └───────────────┬───────────────┘
                                         │ handler(login)
                                         ▼
                         ┌───────────────────────────────┐
                         │ service.do_shoutout(login)     │
                         │  cooldown, orchestration       │
                         └───┬───────────────┬───────────┘
                             │               │
             clips.lookup    │               │  chat.post_chat (optional)
        (Helix + GQL clip)   ▼               ▼
                  ┌────────────────┐   Twitch chat line
                  │ overlay.broadcast │
                  └────────┬───────┘
                           │ JSON over ws://127.0.0.1:8777
                           ▼
                  prism-shoutout.html  (OBS Browser Source)
                           │ emits clipstart / clipend
                           ▼
                  obs_duck.clip_playing_changed(±1)
                     lowers / restores OBS audio
```

## Modules

| Module | Responsibility | Depends on |
|--------|----------------|------------|
| `config` | All settings; loads secrets from env → `prism-secrets.json`. | — |
| `twitch_api` | Helix app-token auth, `helix_get()`, and GQL `clip_mp4()` (slug → signed MP4). | `config` |
| `clips` | Two-tier selection (`pick_recent` / `pick_popular_random`, with dedupe) and `lookup()` which builds the overlay payload. | `config`, `twitch_api` |
| `obs_duck` | obs-websocket v5 client; fades other audio down while a clip plays and back up after. | `config` |
| `overlay` | Local WebSocket server the overlay connects to; `broadcast()` and clip event handling. | `obs_duck` |
| `chat` | Twitch IRC reader (commands + raids), privilege checks, optional chat posting. | `config` |
| `service` | `do_shoutout()` orchestration + `run()` entry point wiring the server and reader together. | all of the above |

The dependency graph is acyclic. `chat.chat_reader` receives the shoutout
handler as an argument (rather than importing `service`), which keeps `chat`
independent and avoids a circular import.

## State

State is intentionally small and in-memory:

- `twitch_api._token` — cached Helix app token (auto-refreshes).
- `clips._last_clips` — per-login `deque` of recently shown clip IDs.
- `overlay.clients` — set of connected overlay WebSockets.
- `obs_duck._duck` — saved original volumes + count of clips currently playing.
- `service._until` — per-login timestamp before which a repeat is refused.
- `service._screen_free_at` — when the overlay is expected to finish everything
  it has been sent, so the repeat guard can outlive a queued card.
- `service._enabled` / `service._pending_raid` — flipped by the mod controls.
- `obs_duck._conn` — the single held obs-websocket connection.
- `obs_duck._targets` — the cached list of sources to lower (`DUCK_TARGET_TTL`).

The one thing that *is* persisted is the shoutout log (`SHOUTOUT_LOG`). It is
read once at startup to prime `clips._last_clips`, so clip rotation survives a
restart; everything else is still rebuilt from scratch each run, so restarting
the service is always safe.

The service also tracks two derived things worth naming: `_reserved` (the
logins whose guard came from a booked card, so `!so clear` releases exactly
those) and `_MAX_GUARDS` (a hard ceiling on `_until`, since expiry alone is not
a bound during a raid train).

## Concurrency notes

- The whole app runs on one asyncio event loop.
- `clips.lookup()` does blocking `requests` calls, so `do_shoutout` runs it in a
  thread via `asyncio.to_thread` to avoid stalling the loop.
- **Every user of the OBS socket must hold `_duck_lock`.** One connection is
  held open and `_obs_req` reads until it sees its own reply, so two concurrent
  callers would steal each other's responses — or, on newer `websockets`,
  raise `ConcurrencyError` and tear the socket down mid-fade. `emergency_restore`
  takes the lock for exactly this reason: at shutdown an overlay handler can
  still be releasing its duck.
- `_req` has a hard `OBS_REQ_TIMEOUT`. Because the connection is long-lived, a
  half-open socket is a realistic steady state, and a bare `recv` would hang
  forever *while holding the lock* — stranding the watchdog that exists to
  restore your audio. A hang is not an exception, so it is made into one.
- The watchdog (`MAX_DUCK_SEC`) is the only retry for a failed restore, so it is
  cancelled only once `_duck["saved"]` is actually empty, and it retries a few
  times before giving up. `_duck_up` clears `saved` on success only — clearing
  it in a `finally` would erase the levels the recovery needs.
- `service._main` awaits `server.wait_closed()` before the exit restore:
  `close()` only schedules the shutdown, and a handler still in its `finally` is
  releasing the duck on the same socket.

## Extending it

To trigger shoutouts from your own bot instead of the built-in chat reader,
import the package and call the handler directly:

```python
import asyncio
from prism_shoutout import service, overlay
from prism_shoutout.config import WS_HOST, WS_PORT
import websockets

async def main():
    await websockets.serve(overlay.overlay_server, WS_HOST, WS_PORT)
    await service.do_shoutout("somestreamer")
    await asyncio.Future()  # keep the overlay server alive

asyncio.run(main())
```
