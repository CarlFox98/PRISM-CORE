"""
Twitch IRC chat: reading commands and (optionally) posting.

``chat_reader(handler)`` connects anonymously to Twitch IRC, watches for the
``!so @user`` command from privileged users and for raids, and calls
``handler(login)`` for each shoutout to perform.

``post_chat(text)`` optionally posts a line back to chat using the configured
bot account.
"""

import re
import random
import asyncio

import websockets

from . import config
from . import console

IRC = "wss://irc-ws.chat.twitch.tv:443"

TAG_RE = re.compile(r"^@([^ ]+) ")


def parse_tags(line):
    """Split an IRCv3 line into its tag dict and the remainder."""
    m = TAG_RE.match(line)
    if not m:
        return {}, line
    tags = {}
    for kv in m.group(1).split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            tags[k] = v
    return tags, line[m.end():]


def is_privileged(tags):
    """True if the sender may trigger a shoutout (mod/broadcaster, or MODS_ONLY off)."""
    if not config.MODS_ONLY:
        return True
    if tags.get("mod") == "1":
        return True
    badges = tags.get("badges", "")
    return ("broadcaster/" in badges) or ("moderator/" in badges)


async def post_chat(text):
    """Optionally post a line in chat as the configured bot account."""
    if not (config.CHAT_SEND and config.BOT_USERNAME and config.BOT_OAUTH):
        return
    try:
        async with websockets.connect(IRC) as w:
            await w.send("PASS " + config.BOT_OAUTH)
            await w.send("NICK " + config.BOT_USERNAME.lower())
            await w.send("JOIN #" + config.CHANNEL)
            await asyncio.sleep(0.6)
            await w.send("PRIVMSG #%s :%s" % (config.CHANNEL, text))
            await asyncio.sleep(0.4)
    except Exception as e:
        console.warn("chat", "send failed: " + str(e))


async def chat_reader(handler):
    """Watch chat forever; call ``handler(login)`` for each shoutout to run."""
    while True:
        try:
            async with websockets.connect(IRC) as w:
                await w.send("CAP REQ :twitch.tv/tags twitch.tv/commands")
                await w.send("NICK justinfan%d" % random.randint(10000, 99999))
                await w.send("JOIN #" + config.CHANNEL)
                console.log("chat", "listening in #%s for %s" % (
                    config.CHANNEL, console.paint(config.COMMAND + " @user", console.C5)))
                async for raw in w:
                    for line in raw.split("\r\n"):
                        if not line:
                            continue
                        if line.startswith("PING"):
                            await w.send("PONG :tmi.twitch.tv")
                            continue
                        tags, rest = parse_tags(line)
                        # auto-shoutout on raid (a USERNOTICE with msg-id=raid)
                        if "USERNOTICE" in rest and config.RAID_SHOUTOUT and tags.get("msg-id") == "raid":
                            raider = tags.get("msg-param-login") or tags.get("login")
                            if raider:
                                console.log("raid", "%s raided with %s %s" % (
                                    console.paint(raider, console.INK, bold=True),
                                    tags.get("msg-param-viewerCount", "?"),
                                    console.paint("viewer(s) — shouting out", console.DIM)))
                                asyncio.create_task(handler(raider))
                            continue
                        if "PRIVMSG" not in rest:
                            continue
                        try:
                            text = rest.split(" :", 1)[1]
                        except IndexError:
                            continue
                        parts = text.strip().split()
                        if not parts or parts[0].lower() != config.COMMAND:
                            continue
                        if not is_privileged(tags):
                            continue
                        if len(parts) >= 2:
                            asyncio.create_task(handler(parts[1]))
        except Exception as e:
            console.warn("chat", "reconnecting after error: " + str(e))
            await asyncio.sleep(3)
