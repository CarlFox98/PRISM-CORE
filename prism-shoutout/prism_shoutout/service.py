"""
Service orchestration.

``do_shoutout(login)`` is the one action everything funnels into: it looks the
user up, pushes the card to the overlay, and (optionally) posts in chat, with a
per-user cooldown. ``run()`` starts the overlay WebSocket server and the chat
reader and blocks until interrupted, restoring OBS audio on the way out.
"""

import time
import asyncio
import logging

import websockets

from . import config
from . import obs_duck
from . import overlay
from . import chat
from . import console
from .clips import lookup

# quiet the harmless "did not receive a valid HTTP request" tracebacks that
# appear when something probes the WS port with a non-websocket connection
logging.getLogger("websockets").setLevel(logging.CRITICAL)

# login -> last-fired timestamp (cooldown)
_recent = {}


async def do_shoutout(login):
    """Look up a user and drive the overlay + optional chat post."""
    now = time.time()
    if now - _recent.get(login, 0) < config.COOLDOWN_SEC:
        return
    _recent[login] = now
    try:
        data = await asyncio.to_thread(lookup, login)
    except Exception as e:
        console.error("lookup", str(e))
        return
    if not data:
        console.error("shout", "user not found: " + login)
        await chat.post_chat(config.NOTFOUND_TEMPLATE.format(login=login.lstrip("@").strip()))
        return
    console.shout(data["name"], bool(data.get("clip")), data.get("live"), data["category"] or "")
    # ducking is triggered by the overlay's clipstart/clipend, not here
    await overlay.broadcast(data)
    tmpl = config.CHAT_TEMPLATE_LIVE if data.get("live") else config.CHAT_TEMPLATE
    await chat.post_chat(tmpl.format(
        name=data["name"], login=data["login"], game=data["category"] or "content"))


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
    try:
        await chat.chat_reader(do_shoutout)
    finally:
        server.close()


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
