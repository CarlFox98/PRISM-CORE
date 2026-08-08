"""
OBS audio ducking.

Talks to OBS's built-in obs-websocket (v5). Ducking is driven by the overlay
itself: when a clip actually starts playing it reports ``clipstart`` (and
``clipend`` when it finishes/errors). We fade the other audio sources down on
the first active clip and fade them back up when the last one ends.

Public API used by the rest of the app:
    clip_playing_changed(delta)  - overlay started (+1) / ended (-1) a clip
    emergency_restore()          - instant, no-fade restore on shutdown
    has_saved()                  - whether any ducked levels still need restoring
"""

import json
import base64
import random
import hashlib
import asyncio

import websockets

from . import config
from . import console

# active = overlay connections currently playing a clip
_duck = {"saved": {}, "active": 0}
_duck_lock = asyncio.Lock()
_duck_watchdog = None


def has_saved():
    return bool(_duck.get("saved"))


# --------------------------------------------------------------------------
# obs-websocket v5 plumbing
# --------------------------------------------------------------------------
async def _obs_connect():
    ws = await websockets.connect(config.OBS_WS_URL, max_size=None)
    hello = json.loads(await ws.recv())            # op 0 (Hello)
    ident = {"op": 1, "d": {"rpcVersion": 1}}
    auth = hello.get("d", {}).get("authentication")
    if auth:
        sec = base64.b64encode(hashlib.sha256(
            (config.OBS_WS_PASSWORD + auth["salt"]).encode()).digest()).decode()
        ident["d"]["authentication"] = base64.b64encode(hashlib.sha256(
            (sec + auth["challenge"]).encode()).digest()).decode()
    await ws.send(json.dumps(ident))
    if json.loads(await ws.recv()).get("op") != 2:  # op 2 (Identified)
        await ws.close()
        raise RuntimeError("OBS refused the connection — check the WebSocket password.")
    return ws


async def _obs_req(ws, rtype, data=None):
    rid = "prism-%d" % random.randint(1, 1 << 30)
    await ws.send(json.dumps({"op": 6, "d": {
        "requestType": rtype, "requestId": rid, "requestData": data or {}}}))
    while True:
        m = json.loads(await ws.recv())
        if m.get("op") == 7 and m["d"].get("requestId") == rid:
            return m["d"]


async def _duck_targets(ws):
    if config.DUCK_SOURCES:
        return list(config.DUCK_SOURCES)
    out = []
    resp = await _obs_req(ws, "GetInputList")
    for inp in resp.get("responseData", {}).get("inputs", []):
        n = inp.get("inputName")
        if not n or n in config.DUCK_EXCLUDE:
            continue
        v = await _obs_req(ws, "GetInputVolume", {"inputName": n})
        if v.get("requestStatus", {}).get("result"):   # audio-capable input
            out.append(n)
    return out


async def _fade(ws, plan, ms):
    """Ramp a set of (name, from_mul, to_mul) volumes over ``ms`` in small steps."""
    steps = max(1, int(ms / 40))
    for i in range(1, steps + 1):
        f = i / steps
        for n, a, b in plan:
            await _obs_req(ws, "SetInputVolume",
                           {"inputName": n, "inputVolumeMul": max(a + (b - a) * f, 0.0)})
        if i < steps:
            await asyncio.sleep(ms / steps / 1000.0)


# --------------------------------------------------------------------------
# duck down / up
# --------------------------------------------------------------------------
async def _duck_down():
    ws = await _obs_connect()
    try:
        _duck["saved"] = {}
        plan = []
        for n in await _duck_targets(ws):
            v = await _obs_req(ws, "GetInputVolume", {"inputName": n})
            mul = v.get("responseData", {}).get("inputVolumeMul")
            if mul is None:
                continue
            _duck["saved"][n] = mul
            plan.append((n, mul, max(mul * config.DUCK_KEEP, 0.0)))
        await _fade(ws, plan, config.DUCK_FADE_MS)
    finally:
        await ws.close()


async def _duck_up():
    if not _duck["saved"]:
        return
    ws = await _obs_connect()
    try:
        plan = [(n, mul * config.DUCK_KEEP, mul) for n, mul in _duck["saved"].items()]
        await _fade(ws, plan, config.DUCK_FADE_MS)
    finally:
        await ws.close()
        _duck["saved"] = {}


async def _duck_safety():
    """If a clipend is ever lost, force audio back up after MAX_DUCK_SEC."""
    try:
        await asyncio.sleep(config.MAX_DUCK_SEC)
    except asyncio.CancelledError:
        return
    async with _duck_lock:
        if _duck["active"] > 0 or _duck["saved"]:
            console.warn("duck", "safety timeout — restoring audio")
            _duck["active"] = 0
            try:
                await _duck_up()
            except Exception as e:
                console.error("duck", "safety restore failed: " + str(e))


async def clip_playing_changed(delta):
    """Called when an overlay starts (+1) or ends (-1) a clip."""
    global _duck_watchdog
    if not config.DUCK_ENABLED:
        return
    async with _duck_lock:
        was = _duck["active"]
        _duck["active"] = max(0, was + delta)
        now = _duck["active"]
        if was == 0 and now > 0:
            try:
                await _duck_down()
            except Exception as e:
                console.error("duck", "couldn't lower OBS audio (OBS WebSocket on + password set?): " + str(e))
                _duck["active"] = 0
                return
            console.log("duck", "lowering %d sources %s" % (len(_duck["saved"]), console.down()))
            if _duck_watchdog:
                _duck_watchdog.cancel()
            _duck_watchdog = asyncio.create_task(_duck_safety())
        elif was > 0 and now == 0:
            if _duck_watchdog:
                _duck_watchdog.cancel()
                _duck_watchdog = None
            try:
                await _duck_up()
                console.log("duck", "restored " + console.up())
            except Exception as e:
                console.error("duck", "couldn't restore OBS audio: " + str(e))


async def emergency_restore():
    """Instant (no-fade) restore, used on shutdown so levels never stay low."""
    if not _duck["saved"]:
        return
    try:
        ws = await _obs_connect()
        try:
            for n, mul in _duck["saved"].items():
                await _obs_req(ws, "SetInputVolume", {"inputName": n, "inputVolumeMul": mul})
        finally:
            await ws.close()
        console.log("duck", "audio restored on exit " + console.up())
    except Exception as e:
        console.error("duck", "exit restore failed: " + str(e))
