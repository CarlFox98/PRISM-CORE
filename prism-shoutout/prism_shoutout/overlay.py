"""
Overlay WebSocket server.

The hosted overlay (prism-shoutout.html, loaded in OBS as a Browser Source)
connects here. We push shoutout payloads to it with ``broadcast``, mod actions
with ``control`` (skip / clear), and listen for the ``clipstart`` / ``clipend``
events it emits so OBS audio ducking can follow the real playback state.
"""

import json

from . import obs_duck
from . import console

# connected overlay websockets
clients = set()


async def _send(msg):
    """Send a raw JSON string to every overlay. Returns how many received it."""
    sent, dead = 0, []
    for ws in list(clients):
        try:
            await ws.send(msg)
            sent += 1
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)
    return sent


async def broadcast(payload):
    """Send a shoutout payload to every connected overlay.

    Returns the number of overlays that actually received it, so the service
    doesn't book screen time for a card nothing is showing.
    """
    if not clients:
        console.log("overlay", console.paint("(no overlay connected yet)", console.DIM))
        return 0
    return await _send(json.dumps(payload))


async def control(action):
    """Send a mod control ("skip" / "clear") to every connected overlay."""
    if not clients:
        console.log("overlay", console.paint("(no overlay connected)", console.DIM))
    await _send(json.dumps({"type": "control", "action": action}))


async def overlay_server(ws):
    """Per-connection handler for the overlay WebSocket."""
    clients.add(ws)
    if len(clients) > 1:
        # every connected overlay plays the same clip, so a browser tab left
        # open next to the OBS source doubles the audio
        console.warn("overlay", "%d overlays connected — they will ALL play the clip "
                                "(close the spare one)" % len(clients))
    else:
        console.log("overlay", "connected " + console.paint("(1 total)", console.DIM))
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
