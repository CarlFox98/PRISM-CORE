#!/usr/bin/env python3
"""
PRISM Shoutout Service
======================
Watches your Twitch chat for a moderator running:  !so @username
and drives the PRISM shoutout overlay (prism-shoutout.html).

For each shout it looks up (via the Twitch Helix API, using your SYSFOX
app's Client ID / Secret):
  - the user's display name + profile image
  - the category they last streamed
  - their most recent clip
then pushes that to the overlay over a local WebSocket, so the overlay
slides in a PRISM card with the hex avatar + an autoplaying clip.

It can also (optionally) post the shout-out line in Twitch chat.

--------------------------------------------------------------------
SETUP
--------------------------------------------------------------------
1.  pip install websockets requests
2.  Fill in CHANNEL / CLIENT_ID / CLIENT_SECRET below (or set them as
    environment variables of the same name). The Client ID/Secret are
    your existing SYSFOX Twitch application credentials.
3.  Run:  python prism_shoutout_service.py
4.  In OBS add the hosted overlay (prism-shoutout.html) as a Browser
    Source; it auto-connects to this service on ws://127.0.0.1:8777.

(Optional) to also POST the shout in chat, set CHAT_SEND = True and
provide BOT_USERNAME + BOT_OAUTH (an oauth token for the account that
should send the message, format "oauth:xxxxxxxx").
--------------------------------------------------------------------
"""
import os, re, json, time, asyncio, datetime, random, logging, urllib.parse, hashlib, base64
import requests
import websockets

# quiet the harmless "did not receive a valid HTTP request" tracebacks that
# appear when something probes the WS port with a non-websocket connection
logging.getLogger("websockets").setLevel(logging.CRITICAL)

# --------------------------- CREDENTIALS -----------------------------
# Secrets are NEVER hardcoded here — this file is public. They load from
# prism-secrets.json (gitignored) or environment variables. Expected keys:
#   CLIENT_ID, CLIENT_SECRET, OBS_WS_PASSWORD, BOT_USERNAME, BOT_OAUTH
def _load_secrets():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "prism-secrets.json"),
              os.path.join(here, "prismenv", "prism-secrets.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}
_SECRETS = _load_secrets()
def _secret(name, default=""):
    v = os.getenv(name)
    if v:
        return v
    v = _SECRETS.get(name)
    return v if v else default

# ----------------------------- CONFIG --------------------------------
CHANNEL        = os.getenv("CHANNEL", "NeoTheFox98").lower()
CLIENT_ID      = _secret("CLIENT_ID")          # SYSFOX app Client ID  (from prism-secrets.json / env)
CLIENT_SECRET  = _secret("CLIENT_SECRET")      # SYSFOX app Client Secret (from prism-secrets.json / env)

WS_HOST        = "127.0.0.1"
WS_PORT        = 8777
COMMAND        = "!so"            # the chat command
MODS_ONLY      = True             # only mods / broadcaster can trigger
RAID_SHOUTOUT  = True             # auto-shoutout whoever raids the channel
HOLD_MS        = 18000            # how long a card WITH a clip stays on screen
NOCLIP_HOLD_MS = 8000             # shorter stay when the user has no clip to show
CLIP_LOOKBACK_DAYS = 90           # prefer the newest clip within this window
COOLDOWN_SEC   = 3                # ignore repeat !so for the same user within N sec

# Optional: also post the shout-out in Twitch chat
CHAT_SEND      = True
BOT_USERNAME   = _secret("BOT_USERNAME")
BOT_OAUTH      = _secret("BOT_OAUTH")   # "oauth:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
CHAT_TEMPLATE  = "◇ Shoutout to @{name}! They were last seen streaming {game}. Show some love → twitch.tv/{login}"
CHAT_TEMPLATE_LIVE = "◇ @{name} is LIVE right now playing {game}! Go show some love → twitch.tv/{login}"
NOTFOUND_TEMPLATE  = "◇ Couldn't find a Twitch channel called @{login} to shout out."

# Optional: duck (lower) your other OBS audio while a shoutout clip plays
DUCK_ENABLED   = True
OBS_WS_URL     = os.getenv("OBS_WS_URL", "ws://127.0.0.1:4455")   # OBS -> Tools -> WebSocket Server Settings
OBS_WS_PASSWORD= _secret("OBS_WS_PASSWORD")                 # the password shown in that same window (from prism-secrets.json / env)
DUCK_KEEP      = 0.30            # fraction of volume kept while a clip plays
                                 # 0.30 = ~70% attenuation. Use 0.50 for -50%, 0.25 for -75%.
DUCK_SOURCES   = []              # specific audio source names to lower. Empty = auto:
                                 # every audio source EXCEPT the ones in DUCK_EXCLUDE.
DUCK_EXCLUDE   = ["PRISM Shoutout"]   # never lower these — put your shoutout browser source
                                      # name here so the clip itself stays at full volume.
DUCK_FADE_MS   = 320             # how long the volume ramps down / back up (smooth, not a jump)
MAX_DUCK_SEC   = 65              # hard safety: audio is never held down longer than this
# ---------------------------------------------------------------------

IRC = "wss://irc-ws.chat.twitch.tv:443"
clients = set()          # connected overlay websockets
_recent = {}             # login -> last-fired timestamp (cooldown)
_last_clip = {}          # login -> last clip id shown (so we don't repeat it)
CLIP_TOP_N = 5           # choose randomly among the strongest N clips

# ============================ Twitch API =============================
_token = {"v": None, "exp": 0}

def _app_token():
    if _token["v"] and time.time() < _token["exp"] - 60:
        return _token["v"]
    # send creds in the POST body (not the URL) so the secret never lands in logs
    r = requests.post("https://id.twitch.tv/oauth2/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"}, timeout=10)
    if r.status_code in (400, 401, 403):
        raise RuntimeError("Twitch rejected the app credentials (%d). Use the SAME "
                           "Client Secret that SYSFOX currently uses (not a new one)." % r.status_code)
    r.raise_for_status()
    d = r.json()
    _token["v"] = d["access_token"]
    _token["exp"] = time.time() + d.get("expires_in", 3600)
    return _token["v"]

def _headers():
    return {"Client-ID": CLIENT_ID, "Authorization": "Bearer " + _app_token()}

def _get(url, params):
    r = requests.get(url, headers=_headers(), params=params, timeout=10)
    if r.status_code == 401:
        _token["v"] = None
        r = requests.get(url, headers=_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("data", [])

# --- resolve a clip slug to a playable, signed MP4 URL (via Twitch's GQL) ------
GQL_URL       = "https://gql.twitch.tv/gql"
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"   # Twitch's public web client id

def _extract_clip(clip):
    """Pull a signed, playable mp4 url + duration out of a GQL clip node."""
    if not clip:
        return "", 0.0
    quals = clip.get("videoQualities") or []
    tok = clip.get("playbackAccessToken") or {}
    dur = float(clip.get("durationSeconds") or 0)
    if not quals or not tok or not tok.get("signature"):
        return "", dur
    pick = next((q for q in quals if str(q.get("quality")) == "720"), quals[0])
    url = pick["sourceURL"] + "?sig=" + tok["signature"] + "&token=" + urllib.parse.quote(tok["value"])
    return url, dur

_CLIP_INLINE_Q = (
    'query($slug: ID!){ clip(slug: $slug){ durationSeconds '
    'playbackAccessToken(params: {platform: "web", playerBackend: "mediaplayer", playerType: "site"}){ signature value } '
    'videoQualities{ quality sourceURL } } }'
)

def clip_mp4(slug):
    """Ask Twitch's GQL for the clip's real signed mp4 (what the site itself loads)."""
    if not slug:
        return "", 0.0
    try:
        r = requests.post(GQL_URL, json={"query": _CLIP_INLINE_Q, "variables": {"slug": slug}},
                          headers={"Client-ID": GQL_CLIENT_ID}, timeout=10)
        j = r.json()
        url, dur = _extract_clip((j.get("data") or {}).get("clip"))
        if not url:
            print("[clip] no playable video (%s): %s" % (r.status_code, json.dumps(j)[:220]))
        return url, dur
    except Exception as e:
        print("[clip] gql lookup failed:", e)
        return "", 0.0

def _pick_clip(clips, login):
    """Choose a good clip: strongest by views, randomized, not the last one shown."""
    if not clips:
        return None
    ranked = sorted(clips, key=lambda c: c.get("view_count", 0) or 0, reverse=True)
    top = ranked[:CLIP_TOP_N]
    last = _last_clip.get(login)
    choices = [c for c in top if c.get("id") != last] or top
    chosen = random.choice(choices)
    _last_clip[login] = chosen.get("id")
    return chosen

def lookup(login):
    """Return a shoutout payload dict for a Twitch login, or None."""
    login = login.lstrip("@").strip().lower()
    if not login:
        return None
    users = _get("https://api.twitch.tv/helix/users", {"login": login})
    if not users:
        return None
    u = users[0]
    uid = u["id"]

    # last streamed category
    game = ""
    try:
        chans = _get("https://api.twitch.tv/helix/channels", {"broadcaster_id": uid})
        if chans:
            game = chans[0].get("game_name") or ""
    except Exception:
        pass

    # are they live right now? if so, use their *current* game
    live = False
    try:
        streams = _get("https://api.twitch.tv/helix/streams", {"user_id": uid})
        if streams:
            live = True
            game = streams[0].get("game_name") or game
    except Exception:
        pass

    # most recent clip (prefer recent window, fall back to all-time top)
    clip_id, mp4_url, clip_thumb, clip_dur = "", "", "", 0.0
    try:
        since = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=CLIP_LOOKBACK_DAYS)
                 ).strftime("%Y-%m-%dT%H:%M:%SZ")
        clips = _get("https://api.twitch.tv/helix/clips",
                     {"broadcaster_id": uid, "first": 40, "started_at": since})
        if not clips:
            clips = _get("https://api.twitch.tv/helix/clips",
                         {"broadcaster_id": uid, "first": 40})
        c = _pick_clip(clips, login)
        if c:
            clip_id = c.get("id", "")
            clip_thumb = c.get("thumbnail_url", "")
            clip_dur = float(c.get("duration", 0) or 0)
            # get the real signed MP4 for this clip so it autoplays (no mature gate)
            mp4_url, gql_dur = clip_mp4(clip_id)
            if gql_dur:
                clip_dur = gql_dur
            # last-ditch fallback: the legacy thumbnail->mp4 trick (older clips)
            if not mp4_url and "-preview-" in clip_thumb:
                mp4_url = clip_thumb.split("-preview-")[0] + ".mp4"
    except Exception as e:
        print("[clip] lookup error:", e)

    # keep the card up roughly for the clip's length (clamped); shorter if no clip
    if clip_dur:
        hold = int(min(max(clip_dur, 6.0), 40.0) * 1000) + 1400
    elif mp4_url:
        hold = HOLD_MS
    else:
        hold = NOCLIP_HOLD_MS

    return {
        "name": u.get("display_name") or login,
        "login": u.get("login") or login,
        "avatar": u.get("profile_image_url", ""),
        "category": game,
        "live": live,          # currently streaming? -> overlay shows LIVE NOW
        "clip": mp4_url,       # direct signed mp4 (preferred)
        "thumb": clip_thumb,   # fallback image
        "clipId": clip_id,     # (unused by overlay now, kept for reference)
        "hold": hold,
    }

# ============================ Overlay push ===========================
async def broadcast(payload):
    if not clients:
        print("[overlay] (no overlay connected yet)")
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
    clients.add(ws)
    print("[overlay] connected (%d total)" % len(clients))
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
                await clip_playing_changed(+1)
            elif t == "clipend" and playing:
                playing = False
                await clip_playing_changed(-1)
    finally:
        clients.discard(ws)
        if playing:                       # overlay vanished mid-clip → release duck
            await clip_playing_changed(-1)
        print("[overlay] disconnected (%d left)" % len(clients))

# ============================ Chat posting ===========================
async def post_chat(text):
    if not (CHAT_SEND and BOT_USERNAME and BOT_OAUTH):
        return
    try:
        async with websockets.connect(IRC) as w:
            await w.send("PASS " + BOT_OAUTH)
            await w.send("NICK " + BOT_USERNAME.lower())
            await w.send("JOIN #" + CHANNEL)
            await asyncio.sleep(0.6)
            await w.send("PRIVMSG #%s :%s" % (CHANNEL, text))
            await asyncio.sleep(0.4)
    except Exception as e:
        print("[chat] send failed:", e)

# ========================== OBS audio duck ===========================
# Talks to OBS's built-in obs-websocket (v5). Ducking is driven by the
# overlay itself: when a clip actually starts playing it reports "clipstart",
# and "clipend" when it finishes/errors. We fade the other audio sources down
# on the first active clip and fade them back up when the last one ends.
_duck = {"saved": {}, "active": 0}   # active = overlay connections currently playing a clip
_duck_lock = asyncio.Lock()
_duck_watchdog = None

async def _obs_connect():
    ws = await websockets.connect(OBS_WS_URL, max_size=None)
    hello = json.loads(await ws.recv())            # op 0 (Hello)
    ident = {"op": 1, "d": {"rpcVersion": 1}}
    auth = hello.get("d", {}).get("authentication")
    if auth:
        sec = base64.b64encode(hashlib.sha256(
            (OBS_WS_PASSWORD + auth["salt"]).encode()).digest()).decode()
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
    if DUCK_SOURCES:
        return list(DUCK_SOURCES)
    out = []
    resp = await _obs_req(ws, "GetInputList")
    for inp in resp.get("responseData", {}).get("inputs", []):
        n = inp.get("inputName")
        if not n or n in DUCK_EXCLUDE:
            continue
        v = await _obs_req(ws, "GetInputVolume", {"inputName": n})
        if v.get("requestStatus", {}).get("result"):   # audio-capable input
            out.append(n)
    return out

async def _fade(ws, plan, ms):
    """Ramp a set of (name, from_mul, to_mul) volumes over `ms` in small steps."""
    steps = max(1, int(ms / 40))
    for i in range(1, steps + 1):
        f = i / steps
        for n, a, b in plan:
            await _obs_req(ws, "SetInputVolume",
                           {"inputName": n, "inputVolumeMul": max(a + (b - a) * f, 0.0)})
        if i < steps:
            await asyncio.sleep(ms / steps / 1000.0)

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
            plan.append((n, mul, max(mul * DUCK_KEEP, 0.0)))
        await _fade(ws, plan, DUCK_FADE_MS)
    finally:
        await ws.close()

async def _duck_up():
    if not _duck["saved"]:
        return
    ws = await _obs_connect()
    try:
        plan = [(n, mul * DUCK_KEEP, mul) for n, mul in _duck["saved"].items()]
        await _fade(ws, plan, DUCK_FADE_MS)
    finally:
        await ws.close()
        _duck["saved"] = {}

async def _duck_safety():
    """If a clipend is ever lost, force audio back up after MAX_DUCK_SEC."""
    try:
        await asyncio.sleep(MAX_DUCK_SEC)
    except asyncio.CancelledError:
        return
    async with _duck_lock:
        if _duck["active"] > 0 or _duck["saved"]:
            print("[duck] safety timeout — restoring audio")
            _duck["active"] = 0
            try:
                await _duck_up()
            except Exception as e:
                print("[duck] safety restore failed:", e)

async def clip_playing_changed(delta):
    """Called when an overlay starts (+1) or ends (-1) a clip."""
    global _duck_watchdog
    if not DUCK_ENABLED:
        return
    async with _duck_lock:
        was = _duck["active"]
        _duck["active"] = max(0, was + delta)
        now = _duck["active"]
        if was == 0 and now > 0:
            try:
                await _duck_down()
            except Exception as e:
                print("[duck] couldn't lower OBS audio (OBS WebSocket on + password set?):", e)
                _duck["active"] = 0
                return
            if _duck_watchdog:
                _duck_watchdog.cancel()
            _duck_watchdog = asyncio.create_task(_duck_safety())
        elif was > 0 and now == 0:
            if _duck_watchdog:
                _duck_watchdog.cancel()
                _duck_watchdog = None
            try:
                await _duck_up()
            except Exception as e:
                print("[duck] couldn't restore OBS audio:", e)

async def _emergency_restore():
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
        print("[duck] audio restored on exit")
    except Exception as e:
        print("[duck] exit restore failed:", e)

# ============================ Shoutout flow ==========================
async def do_shoutout(login):
    now = time.time()
    if now - _recent.get(login, 0) < COOLDOWN_SEC:
        return
    _recent[login] = now
    try:
        data = await asyncio.to_thread(lookup, login)
    except Exception as e:
        print("[lookup] error:", e)
        return
    if not data:
        print("[shoutout] user not found:", login)
        await post_chat(NOTFOUND_TEMPLATE.format(login=login.lstrip("@").strip()))
        return
    print("[shoutout] %s  mp4=%s  live=%s  game=%s" % (
        data["name"], data.get("clip") or "(none)", data.get("live"), data["category"] or "-"))
    await broadcast(data)   # ducking is now triggered by the overlay's clipstart/clipend
    tmpl = CHAT_TEMPLATE_LIVE if data.get("live") else CHAT_TEMPLATE
    await post_chat(tmpl.format(
        name=data["name"], login=data["login"], game=data["category"] or "content"))

# ============================ Chat reader ============================
TAG_RE = re.compile(r"^@([^ ]+) ")

def parse_tags(line):
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
    if not MODS_ONLY:
        return True
    if tags.get("mod") == "1":
        return True
    badges = tags.get("badges", "")
    return ("broadcaster/" in badges) or ("moderator/" in badges)

async def chat_reader():
    while True:
        try:
            async with websockets.connect(IRC) as w:
                await w.send("CAP REQ :twitch.tv/tags twitch.tv/commands")
                await w.send("NICK justinfan%d" % random.randint(10000, 99999))
                await w.send("JOIN #" + CHANNEL)
                print("[chat] listening in #%s for '%s @user'" % (CHANNEL, COMMAND))
                async for raw in w:
                    for line in raw.split("\r\n"):
                        if not line:
                            continue
                        if line.startswith("PING"):
                            await w.send("PONG :tmi.twitch.tv")
                            continue
                        tags, rest = parse_tags(line)
                        # auto-shoutout on raid (a USERNOTICE with msg-id=raid)
                        if "USERNOTICE" in rest and RAID_SHOUTOUT and tags.get("msg-id") == "raid":
                            raider = tags.get("msg-param-login") or tags.get("login")
                            if raider:
                                print("[raid] %s raided with %s viewer(s) — shouting out" % (
                                    raider, tags.get("msg-param-viewerCount", "?")))
                                asyncio.create_task(do_shoutout(raider))
                            continue
                        if "PRIVMSG" not in rest:
                            continue
                        try:
                            text = rest.split(" :", 1)[1]
                        except IndexError:
                            continue
                        parts = text.strip().split()
                        if not parts or parts[0].lower() != COMMAND:
                            continue
                        if not is_privileged(tags):
                            continue
                        if len(parts) >= 2:
                            asyncio.create_task(do_shoutout(parts[1]))
        except Exception as e:
            print("[chat] reconnecting after error:", e)
            await asyncio.sleep(3)

# ================================ Main ===============================
async def main():
    if not CLIENT_SECRET:
        print("!! Set CLIENT_SECRET (your SYSFOX app secret) before running.")
    server = await websockets.serve(overlay_server, WS_HOST, WS_PORT)
    print("[ws] overlay server on ws://%s:%d" % (WS_HOST, WS_PORT))
    await chat_reader()
    server.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        # make sure audio never stays ducked if we were stopped mid-clip
        if _duck.get("saved"):
            try:
                asyncio.run(_emergency_restore())
            except Exception:
                pass
