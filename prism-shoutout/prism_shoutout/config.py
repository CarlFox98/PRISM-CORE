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
MODS_ONLY      = True      # only mods / broadcaster can trigger it
RAID_SHOUTOUT  = True      # auto-shoutout whoever raids the channel
COOLDOWN_SEC   = 3         # ignore repeat !so for the same user within N sec

# --------------------------------------------------------------------------
# Card timing
# --------------------------------------------------------------------------
HOLD_MS        = 18000     # how long a card WITH a clip stays on screen (fallback)
NOCLIP_HOLD_MS = 8000      # shorter stay when the user has no clip to show

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
# Chat posting (optional)
# --------------------------------------------------------------------------
CHAT_SEND    = True
BOT_USERNAME = secret("BOT_USERNAME")
BOT_OAUTH    = secret("BOT_OAUTH")   # "oauth:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

CHAT_TEMPLATE      = "◇ Shoutout to @{name}! They were last seen streaming {game}. Show some love → twitch.tv/{login}"
CHAT_TEMPLATE_LIVE = "◇ @{name} is LIVE right now playing {game}! Go show some love → twitch.tv/{login}"
NOTFOUND_TEMPLATE  = "◇ Couldn't find a Twitch channel called @{login} to shout out."

# --------------------------------------------------------------------------
# OBS audio ducking (optional) — lowers other OBS audio while a clip plays
# --------------------------------------------------------------------------
DUCK_ENABLED    = True
OBS_WS_URL      = os.getenv("OBS_WS_URL", "ws://127.0.0.1:4455")  # OBS -> Tools -> WebSocket Server Settings
OBS_WS_PASSWORD = secret("OBS_WS_PASSWORD")                        # the password shown in that same window
DUCK_KEEP       = 0.30           # fraction of volume kept while a clip plays (0.30 = ~70% attenuation)
DUCK_SOURCES    = []             # explicit source names to lower; empty = auto (all except DUCK_EXCLUDE)
DUCK_EXCLUDE    = ["PRISM Shoutout"]  # never lower these (put your shoutout browser source here)
DUCK_FADE_MS    = 320            # how long the volume ramps down / back up
MAX_DUCK_SEC    = 65             # hard safety: audio is never held down longer than this
