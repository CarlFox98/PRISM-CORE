"""
Overlay WebSocket server.

The hosted overlay (prism-shoutout.html, loaded in OBS as a Browser Source)
connects here. We push shoutout payloads to it with ``broadcast`` and listen
for the ``clipstart`` / ``clipend`` events it emits so OBS audio ducking can
follow the real playback state.
"""

import json

from . import obs_duck
from . import console

# connected overlay websockets
clients = set()


async def broadcast(payload):
    """Send a shoutout payload to every connected overlay."""
    if not clients:
        console.log("overlay", console.paint("(no overlay connected yet)", console.DIM))
    msg = json.dumps(payload)
    dead = []
    for ws in list(clients):
        try:
            await ws.send(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


async def overlay_server(ws):
    """Per-connection handler for the overlay WebSocket."""
    clients.add(ws)
    console.log("overlay", "connected " + console.paint("(%d total)" % len(clients), console.DIM))
    playing = False   # is THIS overlay currently playing a clip?
    try:
        async for raw in ws:
            try:
                m = json.loads(raw)
            except Exception:
                continue
            t = m.get("type") if isinstance(m, dict) else None
            if t == "clipstart" and not playing:
                playing = True
                await obs_duck.clip_playing_changed(+1)
            elif t == "clipend" and playing:
                playing = False
                await obs_duck.clip_playing_changed(-1)
    finally:
        clients.discard(ws)
        if playing:                       # overlay vanished mid-clip → release duck
            await obs_duck.clip_playing_changed(-1)
        console.log("overlay", console.paint("disconnected (%d left)" % len(clients), console.DIM))
