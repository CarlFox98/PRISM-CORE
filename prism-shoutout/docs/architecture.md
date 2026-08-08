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
- `service._recent` — per-login cooldown timestamps.

Nothing is persisted to disk, so restarting the service is always safe.

## Concurrency notes

- The whole app runs on one asyncio event loop.
- `clips.lookup()` does blocking `requests` calls, so `do_shoutout` runs it in a
  thread via `asyncio.to_thread` to avoid stalling the loop.
- Ducking is guarded by an `asyncio.Lock` and a watchdog (`MAX_DUCK_SEC`) so a
  lost `clipend` can never leave your audio stuck low.

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
