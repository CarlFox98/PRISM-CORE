"""
OBS audio ducking.

Talks to OBS's built-in obs-websocket (v5). Ducking is driven by the overlay
itself: when a clip actually starts playing it reports ``clipstart`` (and
``clipend`` when it finishes/errors). We fade the other audio sources down on
the first active clip and fade them back up when the last one ends.

Each source keeps its own fraction of its volume while a clip plays
(``DUCK_LEVELS``, falling back to ``DUCK_KEEP``), so your mic can stay up while
game audio and music drop hard. The saved level and the fraction used are kept
together so the fade back up starts from where the fade down left off.

One obs-websocket connection is held open and reused. Opening and
authenticating a fresh socket for every duck down and up put two handshakes in
the path of something that has to feel instant, and gave every clip start a new
chance to fail. The discovered source list is cached for ``DUCK_TARGET_TTL``
too — your OBS inputs do not change between shoutouts, and re-probing them cost
roughly 2N round-trips before the fade could even start.

Public API used by the rest of the app:
    clip_playing_changed(delta)  - overlay started (+1) / ended (-1) a clip
    emergency_restore()          - instant, no-fade restore on shutdown
    has_saved()                  - whether any ducked levels still need restoring
    close()                      - drop the held connection (on shutdown)
"""

import json
import time
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

# the held obs-websocket connection, and the cached list of what to lower
_conn = {"ws": None}
_targets = {"names": None, "at": 0.0}


def has_saved():
    return bool(_duck.get("saved"))


def keep_for(name):
    """Fraction of its volume this source keeps while a clip plays."""
    levels = config.DUCK_LEVELS or {}
    if name in levels:
        return float(levels[name])
    low = name.lower()
    for k, v in levels.items():
        if k.lower() == low:
            return float(v)
    return float(config.DUCK_KEEP)


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


async def _obs():
    """The held connection, opening it on first use."""
    if _conn["ws"] is None:
        _conn["ws"] = await _obs_connect()
        _targets["names"] = None        # a new socket may be a new OBS session
    return _conn["ws"]


async def _drop():
    """Forget the held connection (and its cached source list)."""
    ws, _conn["ws"] = _conn["ws"], None
    _targets["names"] = None
    if ws is not None:
        try:
            await ws.close()
        except Exception:
            pass


async def close():
    """Close the held connection. Called on shutdown."""
    await _drop()


async def _obs_req(ws, rtype, data=None):
    rid = "prism-%d" % random.randint(1, 1 << 30)
    await ws.send(json.dumps({"op": 6, "d": {
        "requestType": rtype, "requestId": rid, "requestData": data or {}}}))
    while True:
        m = json.loads(await ws.recv())
        if m.get("op") == 7 and m["d"].get("requestId") == rid:
            return m["d"]


async def _req(rtype, data=None, _retry=True):
    """Send a request on the held connection, reconnecting once if it has died.

    Deliberately does not inspect the socket's state — that attribute moved
    between websockets releases. Trying and reconnecting works on all of them.

    The timeout matters more than it looks: because the connection is now held
    open, a half-open socket (OBS frozen, laptop resumed, plugin restarted
    without an RST) is a realistic steady state, and a bare ``recv`` would hang
    forever while holding ``_duck_lock`` — which would strand the watchdog that
    exists to un-duck your audio. A hang is not an exception, so we make it one.

    Callers must hold ``_duck_lock``: one socket, and ``_obs_req`` reads until
    it sees its own reply, so two concurrent callers would steal each other's
    responses (newer websockets raises ConcurrencyError instead, which is no
    better — it would tear the socket down mid-fade).
    """
    try:
        return await asyncio.wait_for(_obs_req(await _obs(), rtype, data),
                                      timeout=config.OBS_REQ_TIMEOUT)
    except Exception:
        await _drop()
        if _retry:
            return await _req(rtype, data, _retry=False)
        raise


async def _duck_targets():
    """Which sources to lower. Cached — your OBS inputs don't change per clip."""
    if config.DUCK_SOURCES:
        return list(config.DUCK_SOURCES)
    now = time.monotonic()
    if _targets["names"] is not None and (now - _targets["at"]) < config.DUCK_TARGET_TTL:
        return list(_targets["names"])
    out = []
    resp = await _req("GetInputList")
    for inp in resp.get("responseData", {}).get("inputs", []):
        n = inp.get("inputName")
        if not n or n in config.DUCK_EXCLUDE:
            continue
        v = await _req("GetInputVolume", {"inputName": n})
        if v.get("requestStatus", {}).get("result"):   # audio-capable input
            out.append(n)
    _targets["names"], _targets["at"] = out, now
    return list(out)


async def _fade(plan, ms):
    """Ramp a set of (name, from_mul, to_mul) volumes over ``ms`` in small steps."""
    steps = max(1, int(ms / 40))
    for i in range(1, steps + 1):
        f = i / steps
        for n, a, b in plan:
            await _req("SetInputVolume",
                       {"inputName": n, "inputVolumeMul": max(a + (b - a) * f, 0.0)})
        if i < steps:
            await asyncio.sleep(ms / steps / 1000.0)


# --------------------------------------------------------------------------
# duck down / up
# --------------------------------------------------------------------------
async def _duck_down():
    _duck["saved"] = {}
    plan = []
    for n in await _duck_targets():
        keep = keep_for(n)
        if keep >= 0.999:              # explicitly "leave this one alone"
            continue
        v = await _req("GetInputVolume", {"inputName": n})
        mul = v.get("responseData", {}).get("inputVolumeMul")
        if mul is None:
            continue
        _duck["saved"][n] = (mul, keep)
        plan.append((n, mul, max(mul * keep, 0.0)))
    await _fade(plan, config.DUCK_FADE_MS)


async def _duck_up():
    if not _duck["saved"]:
        return
    plan = [(n, mul * keep, mul) for n, (mul, keep) in _duck["saved"].items()]
    await _fade(plan, config.DUCK_FADE_MS)
    # Only on success. Clearing this in a ``finally`` meant a failed restore
    # erased the very levels we need to get back to, and left has_saved()
    # False so every later safety net skipped itself.
    _duck["saved"] = {}


async def _duck_safety():
    """Force audio back up if a clipend was lost, or if a restore failed."""
    try:
        await asyncio.sleep(config.MAX_DUCK_SEC)
    except asyncio.CancelledError:
        return
    for attempt in range(3):
        if attempt:
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                return
        async with _duck_lock:
            if not (_duck["active"] > 0 or _duck["saved"]):
                return                       # someone else got there first
            console.warn("duck", "safety timeout — restoring audio")
            _duck["active"] = 0
            try:
                await _duck_up()
                console.log("duck", "restored " + console.up())
                return
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
                # _duck_down saves the original levels BEFORE it starts fading,
                # so a failure part-way through can leave sources lowered with
                # nothing scheduled to raise them. Put them back now; if that
                # fails too, arm the watchdog so it retries.
                if _duck["saved"]:
                    try:
                        await _duck_up()
                        console.log("duck", "restored after a failed duck " + console.up())
                    except Exception as e2:
                        console.error("duck", "restore after failed duck also failed: " + str(e2))
                        if _duck_watchdog:
                            _duck_watchdog.cancel()
                        _duck_watchdog = asyncio.create_task(_duck_safety())
                return
            console.log("duck", "lowering %d sources %s" % (len(_duck["saved"]), console.down()))
            if _duck_watchdog:
                _duck_watchdog.cancel()
            _duck_watchdog = asyncio.create_task(_duck_safety())
        elif was > 0 and now == 0:
            try:
                await _duck_up()
                console.log("duck", "restored " + console.up())
            except Exception as e:
                console.error("duck", "couldn't restore OBS audio: " + str(e))
            # cancel the watchdog only once the levels are actually back —
            # if the restore failed it is the only thing that will retry
            if not _duck["saved"] and _duck_watchdog:
                _duck_watchdog.cancel()
                _duck_watchdog = None


async def emergency_restore():
    """Instant (no-fade) restore, used on shutdown so levels never stay low.

    Takes ``_duck_lock`` like every other user of the socket: at shutdown an
    overlay handler can still be mid-fade in its own ``finally``, and two
    coroutines on one connection either steal each other's replies or tear the
    socket down under one another.
    """
    global _duck_watchdog
    async with _duck_lock:
        if _duck_watchdog:
            _duck_watchdog.cancel()
            _duck_watchdog = None
        if not _duck["saved"]:
            return
        try:
            for n, (mul, _keep) in _duck["saved"].items():
                await _req("SetInputVolume", {"inputName": n, "inputVolumeMul": mul})
            _duck["saved"] = {}
            console.log("duck", "audio restored on exit " + console.up())
        except Exception as e:
            console.error("duck", "exit restore failed: " + str(e))
