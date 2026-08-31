"""
Service orchestration.

``do_shoutout(login, source, viewers)`` is the one action everything funnels
into: it checks the safety gates, looks the user up, pushes the card to the
overlay, and (optionally) posts in chat, with a per-user cooldown.
``control(word)`` handles the mod subcommands (skip / clear / off / on / ok).
``run()`` starts the overlay WebSocket server and the chat reader and blocks
until interrupted, restoring OBS audio on the way out.
"""

import re
import time
import asyncio
import logging

import websockets

from . import config
from . import obs_duck
from . import overlay
from . import chat
from . import clips
from . import console
from . import history
from .clips import lookup

# quiet the harmless "did not receive a valid HTTP request" tracebacks that
# appear when something probes the WS port with a non-websocket connection
logging.getLogger("websockets").setLevel(logging.CRITICAL)

# login -> unix ts before which a repeat shoutout is refused
_until = {}

# estimated ts at which the overlay finishes everything it has been sent, so
# the repeat guard can outlive a card that is still queued behind others
_screen_free_at = 0.0

# logins whose guard came from a booked card (as opposed to an in-flight
# lookup), so "!so clear" releases exactly those and nothing else
_reserved = set()

# hard ceiling on the guard table, independent of expiry
_MAX_GUARDS = 512

# runtime state the mod controls flip
_enabled = True          # "!so off" / "!so on"
_pending_raid = None     # {"login":…, "viewers":…, "at":…} awaiting "!so ok"


# mods paste channel links as often as they type @names
_URL_RE = re.compile(r"^(?:https?://)?(?:www\.)?twitch\.tv/([^/?#\s]+)", re.I)


def _norm(login):
    """Normalise whatever chat typed into a bare lowercase Twitch login."""
    v = (login or "").strip()
    m = _URL_RE.match(v)
    if m:
        v = m.group(1)
    return v.lstrip("@").strip().lower()


def _blocked(login):
    return login in {b.strip().lower() for b in config.BLOCKLIST}


def _prune(now):
    """Keep the guard table bounded — by expiry first, then by hard cap."""
    if len(_until) < 256:
        return
    for k in [k for k, v in _until.items() if v <= now]:
        _until.pop(k, None)
        _reserved.discard(k)
    # a long raid train can hold hundreds of guards that are all still live,
    # so expiry alone is not a bound: drop the soonest to lapse
    if len(_until) > _MAX_GUARDS:
        doomed = sorted(_until.items(), key=lambda kv: kv[1])[:len(_until) - _MAX_GUARDS]
        for k, _ in doomed:
            _until.pop(k, None)
            _reserved.discard(k)


def _viewers_phrase(n):
    """"42 viewers" / "1 viewer" / "" when Twitch didn't tell us."""
    if not n:
        return ""
    return "%d viewer%s" % (n, "" if n == 1 else "s")


def _queue_depth(now):
    """Seconds of card time the overlay still has to get through."""
    return max(0.0, _screen_free_at - now)


def _reserve_screen(login, hold_ms):
    """Book a card's screen time and guard its login until well after it leaves."""
    global _screen_free_at
    now = time.time()
    start = max(now, _screen_free_at)
    _screen_free_at = start + (hold_ms / 1000.0) + 0.7      # + the exit fade
    _until[login] = _screen_free_at + config.REPEAT_GUARD_SEC
    _reserved.add(login)


def _release_screen():
    """A mod cleared the overlay — stop reserving time we are no longer using."""
    global _screen_free_at
    _screen_free_at = time.time()
    # only the guards that came from booked cards; a shoutout still mid-lookup
    # keeps its guard, or "!so clear" would let it run a second lookup
    for k in list(_reserved):
        _until.pop(k, None)
    _reserved.clear()


def _hold_raid(login, viewers):
    """Park a raid shoutout until a mod types "!so ok"."""
    global _pending_raid
    _pending_raid = {"login": login, "viewers": viewers, "at": time.time()}
    console.warn("raid", "%s (%s viewer(s)) is waiting for approval — a mod can type %s" % (
        login, viewers or "?", console.paint(config.COMMAND + " ok", console.C5)))


async def do_shoutout(login, source="command", viewers=0):
    """Public entry point. Never raises — a failure here must not kill the task."""
    try:
        await _shoutout(_norm(login), source, viewers)
    except Exception as e:
        console.error("shout", "failed for %s: %s" % (login, e))


async def _shoutout(login, source, viewers):
    """Safety gates, then look the user up and drive the overlay + chat."""
    if not login:
        return
    if not _enabled:
        console.log("shout", console.paint("shoutouts are off — ignoring " + login, console.DIM))
        return
    if _blocked(login):
        console.warn("shout", "blocklisted — refusing " + login)
        return
    if login == config.CHANNEL and not config.ALLOW_SELF_SHOUTOUT:
        console.log("shout", console.paint("that's you — skipping the self-shoutout", console.DIM))
        return
    if source == "raid":
        allow = {a.strip().lower() for a in config.RAID_ALLOWLIST}
        if allow and login not in allow:
            console.warn("raid", "not on RAID_ALLOWLIST — skipping " + login)
            return
        if viewers < config.RAID_MIN_VIEWERS:
            console.log("raid", console.paint(
                "%s raided with %d — under RAID_MIN_VIEWERS (%d), skipping"
                % (login, viewers, config.RAID_MIN_VIEWERS), console.DIM))
            return
        if config.RAID_REQUIRE_APPROVAL:
            _hold_raid(login, viewers)
            return

    now = time.time()
    _prune(now)
    if now < _until.get(login, 0.0):
        console.log("shout", console.paint(
            "%s is still on screen or just left — ignoring the repeat" % login, console.DIM))
        return
    depth = _queue_depth(now)
    if depth > config.MAX_QUEUE_SEC:
        console.warn("shout", "overlay is %ds backed up — dropping %s" % (int(depth), login))
        return
    # Guard for the whole lookup, not just COOLDOWN_SEC — a lookup is up to
    # five Twitch calls and can outlast a 3-second window, which used to let a
    # second trigger through and post the chat line twice.
    _until[login] = now + config.LOOKUP_GUARD_SEC
    try:
        data = await asyncio.to_thread(lookup, login)
    except Exception as e:
        _until[login] = now + config.COOLDOWN_SEC      # let them retry promptly
        console.error("lookup", str(e))
        return
    if not data:
        _until[login] = now + config.COOLDOWN_SEC      # probably a typo
        console.error("shout", "user not found: " + login)
        await chat.post_chat(config.NOTFOUND_TEMPLATE.format(login=login))
        return
    # a raid gets its own card state and its own chat line
    is_raid = source in ("raid", "approved")
    data["raid"] = is_raid
    data["raiders"] = viewers if is_raid else 0

    console.shout(data["name"], bool(data.get("clip")), data.get("live"), data["category"] or "")
    # ducking is triggered by the overlay's clipstart/clipend, not here
    shown = await overlay.broadcast(data)
    if shown:
        _reserve_screen(login, data.get("hold") or config.HOLD_MS)
    else:
        # nothing is displaying this card, so don't book screen time for it —
        # with OBS closed the service used to rate-limit itself against a queue
        # that did not exist
        _until[login] = time.time() + config.COOLDOWN_SEC
    history.append({
        "login": data["login"], "name": data["name"], "source": source,
        "raiders": viewers if is_raid else 0, "live": bool(data.get("live")),
        "category": data.get("category") or "", "clipId": data.get("clipId") or "",
        "hasClip": bool(data.get("clip")),
    })
    if is_raid:
        tmpl = config.CHAT_TEMPLATE_RAID
    elif data.get("live"):
        tmpl = config.CHAT_TEMPLATE_LIVE
    else:
        tmpl = config.CHAT_TEMPLATE
    await chat.post_chat(tmpl.format(
        name=data["name"], login=data["login"], game=data["category"] or "content",
        viewers=_viewers_phrase(viewers)))


async def control(action):
    """Handle a mod subcommand. See config.CONTROLS_ENABLED for the list."""
    global _enabled, _pending_raid
    try:
        if action in ("skip", "clear"):
            await overlay.control(action)
            if action == "clear":
                _release_screen()
            console.log("shout", "skipped the current card" if action == "skip"
                        else "cleared the card and the queue")
        elif action in ("off", "on"):
            _enabled = (action == "on")
            console.warn("cfg", "shoutouts are now " + ("ON" if _enabled else "OFF"))
        elif action == "ok":
            pending, _pending_raid = _pending_raid, None
            if not pending:
                console.warn("raid", "nothing is waiting for approval")
            elif time.time() - pending["at"] > config.RAID_APPROVAL_TTL:
                console.warn("raid", "approval expired for " + pending["login"])
            else:
                console.log("raid", "approved " + console.paint(pending["login"], console.INK, bold=True))
                await _shoutout(pending["login"], "approved", pending["viewers"])
        elif action == "status":
            console.log("cfg", "shoutouts %s  ·  pending raid: %s" % (
                console.paint("on", console.C1) if _enabled else console.paint("off", console.C5),
                _pending_raid["login"] if _pending_raid else "none"))
    except Exception as e:
        console.error("shout", "control '%s' failed: %s" % (action, e))


async def _main():
    console.enable()
    ws_url = "ws://%s:%d" % (config.WS_HOST, config.WS_PORT)
    console.banner(config.CHANNEL, ws_url, config.COMMAND, config.DUCK_ENABLED)
    if not config.CLIENT_SECRET:
        console.warn("cfg", "Set CLIENT_SECRET before running (env var or prism-secrets.json).")
    server = await websockets.serve(overlay.overlay_server, config.WS_HOST, config.WS_PORT)
    console.log("ws", "overlay server ready")
    if config.SECRETS_PATH:
        console.log("cfg", "secrets loaded " + console.yes() + " " + console.paint(str(config.SECRETS_PATH), console.DIM))
    # restore clip rotation from the log so a restart doesn't replay clips
    try:
        n = history.load_into_clips(clips)
        if n:
            console.log("log", "clip history restored for %d streamer(s)" % n)
    except Exception as e:
        console.warn("log", "couldn't restore clip history: " + str(e))
    try:
        await chat.chat_reader(do_shoutout, control)
    finally:
        # wait for the overlay handlers to finish: server.close() only schedules
        # the shutdown, and a handler still in its finally is releasing the duck
        server.close()
        try:
            await asyncio.wait_for(server.wait_closed(), timeout=3)
        except Exception:
            pass
        if obs_duck.has_saved():
            try:
                await obs_duck.emergency_restore()
            except Exception:
                pass
        await obs_duck.close()


def run():
    """Blocking entry point. Used by ``python -m prism_shoutout`` and the launcher."""
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print()
        console.log("cfg", console.paint("shutting down — bye ◇", console.C3))
    finally:
        # make sure audio never stays ducked if we were stopped mid-clip
        if obs_duck.has_saved():
            try:
                asyncio.run(obs_duck.emergency_restore())
            except Exception:
                pass
