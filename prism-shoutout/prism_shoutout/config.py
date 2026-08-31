"""
Configuration and secret loading.

Secrets (Twitch app credentials, OBS WebSocket password, optional bot creds)
are NEVER hard-coded here. They are read, in order of priority, from:

    1. environment variables of the same name
    2. a local ``prism-secrets.json`` file (git-ignored)

``prism-secrets.json`` is searched for in several sensible locations so the
service works whether it's launched from the repo folder, from the parent
``prismenv`` folder (via the .bat launcher), or with an explicit path in the
``PRISM_SECRETS`` environment variable.

Everything else in this file is plain, editable configuration.
"""

import os
import json
from pathlib import Path

# --------------------------------------------------------------------------
# Secret loading
# --------------------------------------------------------------------------
_PKG_DIR = Path(__file__).resolve().parent          # .../prism_shoutout
_REPO_ROOT = _PKG_DIR.parent                         # .../prism-shoutout
_SECRETS_NAME = "prism-secrets.json"


def _secret_file_candidates():
    """Ordered list of places prism-secrets.json might live."""
    seen, out = set(), []
    explicit = os.getenv("PRISM_SECRETS")
    raw = [
        Path(explicit) if explicit else None,   # explicit override
        Path.cwd() / _SECRETS_NAME,              # current working directory
        _REPO_ROOT / _SECRETS_NAME,              # repo root (next to the package)
        _REPO_ROOT.parent / _SECRETS_NAME,       # parent (e.g. the prismenv folder)
    ]
    for p in raw:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _load_secrets():
    for path in _secret_file_candidates():
        try:
            if path.is_file():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f), path
        except Exception:
            continue
    return {}, None


_SECRETS, SECRETS_PATH = _load_secrets()


def secret(name, default=""):
    """env var > prism-secrets.json > default."""
    return os.getenv(name) or _SECRETS.get(name) or default


# --------------------------------------------------------------------------
# Channel / Twitch app credentials  (secrets)
# --------------------------------------------------------------------------
CHANNEL       = (os.getenv("CHANNEL") or _SECRETS.get("CHANNEL") or "NeoTheFox98").lower()
CLIENT_ID     = secret("CLIENT_ID")        # your SYSFOX app Client ID
CLIENT_SECRET = secret("CLIENT_SECRET")    # your SYSFOX app Client Secret

# --------------------------------------------------------------------------
# Overlay WebSocket server (the overlay HTML connects here)
# --------------------------------------------------------------------------
WS_HOST = "127.0.0.1"
WS_PORT = 8777

# --------------------------------------------------------------------------
# Trigger behavior
# --------------------------------------------------------------------------
COMMAND        = "!so"     # the chat command that fires a shoutout
COMMAND_ALIASES = ["!shoutout"]   # other spellings that mean the same thing
ALLOW_SELF_SHOUTOUT = False       # let !so target your own channel
MODS_ONLY      = True      # only mods / broadcaster can trigger it
RAID_SHOUTOUT  = True      # auto-shoutout whoever raids the channel
COOLDOWN_SEC   = 3         # debounce: ignore a repeat !so within N seconds

# A card can hold the screen for up to ~41s, so a 3-second debounce is not
# enough on its own — a raid followed by a mod's reflex "!so @raider" used to
# queue a second identical card. The same login is refused while its card is
# queued or on screen, plus this many seconds after it leaves.
REPEAT_GUARD_SEC = 30

# Refuse new shoutouts once the overlay is this far backed up (seconds of
# queued card time). Keeps a burst of !so from buying minutes of cards.
MAX_QUEUE_SEC    = 120

# A lookup is up to five sequential Twitch calls at 10s each, so the guard held
# during it has to outlast that — a 3-second one let a second trigger through
# mid-lookup and post the chat line twice.
LOOKUP_GUARD_SEC = 60

# --------------------------------------------------------------------------
# Who may be shouted out  (safety)
# --------------------------------------------------------------------------
# Logins listed here are NEVER shouted out — by command or by raid. Lowercase.
BLOCKLIST = []

# If this list is non-empty, ONLY these logins get an automatic raid shoutout.
# A manual !so is unaffected. Lowercase.
RAID_ALLOWLIST = []

# Hold raid shoutouts until a mod approves one. Nothing reaches the screen on
# its own: the service announces the pending raid and waits for "!so ok".
# Turn this on if you are being raid-bombed.
RAID_REQUIRE_APPROVAL = False
RAID_APPROVAL_TTL     = 120    # seconds a pending raid stays approvable

# Ignore raids smaller than this. A one-viewer drive-by used to get the same
# full-length card and the same audio duck as a five-hundred-viewer raid.
RAID_MIN_VIEWERS      = 2

# --------------------------------------------------------------------------
# Mod controls  (subcommands of COMMAND — mods/broadcaster only)
# --------------------------------------------------------------------------
#   !so skip    drop the card that is on screen right now
#   !so clear   drop the on-screen card AND everything queued behind it
#   !so off     stop firing shoutouts (raids included) until !so on
#   !so on      resume
#   !so ok      approve a pending raid (see RAID_REQUIRE_APPROVAL)
#   !so status  print the current state to the service console
#
# A bare word is read as a control. Prefix with @ to shout out someone whose
# name collides with one — "!so @skip" still shouts out the streamer "skip".
CONTROLS_ENABLED = True

# --------------------------------------------------------------------------
# Card timing
# --------------------------------------------------------------------------
HOLD_MS        = 18000     # how long a card WITH a clip stays on screen (fallback)
NOCLIP_HOLD_MS = 8000      # shorter stay when the user has no clip to show

# --------------------------------------------------------------------------
# Clip playback volume
# --------------------------------------------------------------------------
# Twitch clips vary wildly in loudness, so playing every one at full scale
# either buries the clip or clips your mix. This is the ceiling the overlay
# ramps up to; it fades in over CLIP_FADE_IN_MS so the clip arrives together
# with the duck rather than on top of it.
CLIP_VOLUME      = 0.85    # 0.0-1.0
CLIP_FADE_IN_MS  = 320     # match DUCK_FADE_MS to have them move as one

# --------------------------------------------------------------------------
# Clip selection
# --------------------------------------------------------------------------
# Two-tier strategy:
#   1. PRIMARY   — the most RECENT clip created within CLIP_RECENT_DAYS.
#   2. FALLBACK  — if there are none that recent, randomly pick among the most
#                  POPULAR clips (by views) created within CLIP_POPULAR_DAYS.
CLIP_RECENT_DAYS  = 7     # primary window: clips created within this many days
CLIP_RECENT_POOL  = 8     # primary: randomize among the newest N clips (by date) in that window
CLIP_POPULAR_DAYS = 30    # fallback window: random among most-viewed within this many days
CLIP_TOP_N        = 5     # fallback: choose randomly among the strongest N clips
CLIP_HISTORY      = 3     # remember this many recent clips per streamer to avoid repeats

# --------------------------------------------------------------------------
# Shoutout log (optional)
# --------------------------------------------------------------------------
# An append-only JSONL record of every shoutout. It also lets clip rotation
# survive a restart — without it the service forgets what it has shown and can
# replay the same clip after a relaunch. Set to "" to turn it off.
SHOUTOUT_LOG = str(_REPO_ROOT / "shoutout-log.jsonl")

# --------------------------------------------------------------------------
# Chat posting (optional)
# --------------------------------------------------------------------------
CHAT_SEND    = True
BOT_USERNAME = secret("BOT_USERNAME")
BOT_OAUTH    = secret("BOT_OAUTH")   # "oauth:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

CHAT_TEMPLATE      = "◇ Shoutout to @{name}! They were last seen streaming {game}. Show some love → twitch.tv/{login}"
CHAT_TEMPLATE_RAID = "◇ Thank you for the raid, @{name}! ({viewers}) They were last streaming {game} → twitch.tv/{login}"
CHAT_TEMPLATE_LIVE = "◇ @{name} is LIVE right now playing {game}! Go show some love → twitch.tv/{login}"
NOTFOUND_TEMPLATE  = "◇ Couldn't find a Twitch channel called @{login} to shout out."

# --------------------------------------------------------------------------
# OBS audio ducking (optional) — lowers other OBS audio while a clip plays
# --------------------------------------------------------------------------
DUCK_ENABLED    = True
OBS_WS_URL      = os.getenv("OBS_WS_URL", "ws://127.0.0.1:4455")  # OBS -> Tools -> WebSocket Server Settings
OBS_WS_PASSWORD = secret("OBS_WS_PASSWORD")                        # the password shown in that same window
DUCK_KEEP       = 0.30           # default fraction of volume kept while a clip plays
# Per-source overrides, by exact OBS input name (case-insensitive fallback).
# You usually talk OVER a shoutout clip, so your mic should barely move while
# game audio and music drop hard:
#     DUCK_LEVELS = {"Mic/Aux": 0.90, "Game Capture": 0.15, "Spotify": 0.10}
# 1.0 leaves a source alone entirely (same effect as listing it in DUCK_EXCLUDE).
# Names must match your OBS Audio Mixer EXACTLY. Anything not listed uses
# DUCK_KEEP -- that currently covers "Twitch Goals" and the two alert sources,
# which drop to 30% while a clip plays. Add them here at 1.0 if you would
# rather a sub alert stayed at full volume over a shoutout.
DUCK_LEVELS     = {
    "Mic/Aux":      0.90,   # you talk over the clip -- barely move it
    "Game Capture": 0.15,
    "Spotify":      0.10,
    "Discord":      0.35,
}
DUCK_SOURCES    = []             # explicit source names to lower; empty = auto (all except DUCK_EXCLUDE)
# Never lower these. MUST match the OBS source name exactly, or the service
# ducks the shoutout overlay itself and the clip you are playing goes quiet.
DUCK_EXCLUDE    = ["PRISM Shoutout"]
DUCK_FADE_MS    = 320            # how long the volume ramps down / back up
MAX_DUCK_SEC    = 65             # hard safety: audio is never held down longer than this
DUCK_TARGET_TTL = 60             # seconds to reuse the discovered source list before re-probing OBS
OBS_REQ_TIMEOUT = 6              # seconds before a request on the held socket is abandoned
