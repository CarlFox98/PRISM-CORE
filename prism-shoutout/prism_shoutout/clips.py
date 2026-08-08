"""
Clip selection and overlay-payload assembly.

``lookup(login)`` is the main entry: given a Twitch login it returns the dict
the overlay expects (name, avatar, category, live flag, clip mp4, hold time),
or ``None`` if the user doesn't exist.

Clip selection is two-tier:
  1. PRIMARY  — random among the newest ``CLIP_RECENT_POOL`` clips created
                within ``CLIP_RECENT_DAYS`` (7d), i.e. recent but rotating.
  2. FALLBACK — if there are none that recent, randomly pick among the most
                POPULAR clips within ``CLIP_POPULAR_DAYS`` (30d).

Both tiers avoid the last ``CLIP_HISTORY`` clips already shown for that
streamer, so repeated shoutouts rotate instead of replaying one clip.
"""

import random
import datetime
from collections import deque

from . import config
from . import console
from .twitch_api import helix_get, clip_mp4

# login -> deque of recently shown clip ids (so we don't repeat them)
_last_clips = {}


def _seen(login):
    """Per-streamer deque of recently shown clip ids."""
    return _last_clips.setdefault(login, deque(maxlen=config.CLIP_HISTORY))


def pick_recent(clips, login):
    """PRIMARY: random among the newest CLIP_RECENT_POOL clips (by date).

    Biased to recent but rotates, and skips ones shown in the last CLIP_HISTORY
    so an active channel doesn't get stuck looping just its newest few.
    """
    if not clips:
        return None
    ordered = sorted(clips, key=lambda c: c.get("created_at", ""), reverse=True)
    pool = ordered[: config.CLIP_RECENT_POOL]
    seen = _seen(login)
    choices = [c for c in pool if c.get("id") not in seen] or pool
    chosen = random.choice(choices)
    seen.append(chosen.get("id"))
    return chosen


def pick_popular_random(clips, login):
    """FALLBACK: random among the most-viewed clips, skipping recent repeats."""
    if not clips:
        return None
    ranked = sorted(clips, key=lambda c: c.get("view_count", 0) or 0, reverse=True)
    top = ranked[: config.CLIP_TOP_N]
    seen = _seen(login)
    choices = [c for c in top if c.get("id") not in seen] or top
    chosen = random.choice(choices)
    seen.append(chosen.get("id"))
    return chosen


def _fetch_clips(uid, days):
    """Clips created within the last ``days`` (both date bounds sent to Twitch).

    NOTE: Twitch's Get Clips treats a started_at with no ended_at as a 1-week
    window starting at that date, so we always send BOTH bounds to get the real
    window we asked for.
    """
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    since = (now_dt - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    until = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return helix_get(
        "https://api.twitch.tv/helix/clips",
        {"broadcaster_id": uid, "first": 100, "started_at": since, "ended_at": until},
    )


def _select_clip(uid, login):
    """Two-tier pick: newest in the last 7d, else popular-random in the last 30d."""
    recent = _fetch_clips(uid, config.CLIP_RECENT_DAYS)
    chosen = pick_recent(recent, login)
    if chosen:
        return chosen
    popular = _fetch_clips(uid, config.CLIP_POPULAR_DAYS)
    return pick_popular_random(popular, login)


def _resolve_clip(uid, login):
    """Return (clip_id, mp4_url, thumb, duration_sec) for the chosen clip."""
    clip_id, mp4_url, clip_thumb, clip_dur = "", "", "", 0.0
    try:
        c = _select_clip(uid, login)
        if c:
            clip_id = c.get("id", "")
            clip_thumb = c.get("thumbnail_url", "")
            clip_dur = float(c.get("duration", 0) or 0)
            # get the real signed MP4 so it autoplays (no mature gate)
            mp4_url, gql_dur = clip_mp4(clip_id)
            if gql_dur:
                clip_dur = gql_dur
            # last-ditch fallback: the legacy thumbnail->mp4 trick (older clips)
            if not mp4_url and "-preview-" in clip_thumb:
                mp4_url = clip_thumb.split("-preview-")[0] + ".mp4"
    except Exception as e:
        console.error("clip", "lookup error: " + str(e))
    return clip_id, mp4_url, clip_thumb, clip_dur


def _hold_ms(clip_dur, mp4_url):
    """How long the card should stay up: clip length (clamped) or a fallback."""
    if clip_dur:
        return int(min(max(clip_dur, 6.0), 40.0) * 1000) + 1400
    if mp4_url:
        return config.HOLD_MS
    return config.NOCLIP_HOLD_MS


def lookup(login):
    """Return a shoutout payload dict for a Twitch login, or None."""
    login = login.lstrip("@").strip().lower()
    if not login:
        return None
    users = helix_get("https://api.twitch.tv/helix/users", {"login": login})
    if not users:
        return None
    u = users[0]
    uid = u["id"]

    # last streamed category
    game = ""
    try:
        chans = helix_get("https://api.twitch.tv/helix/channels", {"broadcaster_id": uid})
        if chans:
            game = chans[0].get("game_name") or ""
    except Exception:
        pass

    # are they live right now? if so, use their *current* game
    live = False
    try:
        streams = helix_get("https://api.twitch.tv/helix/streams", {"user_id": uid})
        if streams:
            live = True
            game = streams[0].get("game_name") or game
    except Exception:
        pass

    clip_id, mp4_url, clip_thumb, clip_dur = _resolve_clip(uid, login)

    return {
        "name": u.get("display_name") or login,
        "login": u.get("login") or login,
        "avatar": u.get("profile_image_url", ""),
        "category": game,
        "live": live,          # currently streaming? -> overlay shows LIVE NOW
        "clip": mp4_url,       # direct signed mp4 (preferred)
        "thumb": clip_thumb,   # fallback image
        "clipId": clip_id,     # (kept for reference)
        "hold": _hold_ms(clip_dur, mp4_url),
    }
