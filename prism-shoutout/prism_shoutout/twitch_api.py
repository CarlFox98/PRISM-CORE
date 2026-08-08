"""
Twitch API access.

Two things live here:

  * Helix (the official REST API) — app-token auth + a small GET helper used to
    look up users, channels, streams and clips.
  * GQL (Twitch's internal GraphQL) — used only to turn a clip slug into the
    real *signed mp4* URL that the Twitch site itself plays, so the overlay can
    autoplay it without a mature-content gate.
"""

import time
import json
import urllib.parse

import requests

from . import config
from . import console

# --------------------------------------------------------------------------
# Helix app-token auth
# --------------------------------------------------------------------------
_token = {"v": None, "exp": 0}


def app_token():
    """Return a cached client-credentials app token, refreshing when stale."""
    if _token["v"] and time.time() < _token["exp"] - 60:
        return _token["v"]
    # send creds in the POST body (not the URL) so the secret never lands in logs
    r = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    if r.status_code in (400, 401, 403):
        raise RuntimeError(
            "Twitch rejected the app credentials (%d). Use the SAME Client Secret "
            "that SYSFOX currently uses (not a new one)." % r.status_code
        )
    r.raise_for_status()
    d = r.json()
    _token["v"] = d["access_token"]
    _token["exp"] = time.time() + d.get("expires_in", 3600)
    return _token["v"]


def _headers():
    return {"Client-ID": config.CLIENT_ID, "Authorization": "Bearer " + app_token()}


def helix_get(url, params):
    """GET a Helix endpoint and return its ``data`` list (retries once on 401)."""
    r = requests.get(url, headers=_headers(), params=params, timeout=10)
    if r.status_code == 401:
        _token["v"] = None  # force a token refresh, then retry
        r = requests.get(url, headers=_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("data", [])


# --------------------------------------------------------------------------
# GQL: resolve a clip slug to a signed, playable mp4
# --------------------------------------------------------------------------
GQL_URL       = "https://gql.twitch.tv/gql"
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"   # Twitch's public web client id

_CLIP_INLINE_Q = (
    'query($slug: ID!){ clip(slug: $slug){ durationSeconds '
    'playbackAccessToken(params: {platform: "web", playerBackend: "mediaplayer", playerType: "site"}){ signature value } '
    'videoQualities{ quality sourceURL } } }'
)


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


def clip_mp4(slug):
    """Ask Twitch's GQL for the clip's real signed mp4 (what the site loads)."""
    if not slug:
        return "", 0.0
    try:
        r = requests.post(
            GQL_URL,
            json={"query": _CLIP_INLINE_Q, "variables": {"slug": slug}},
            headers={"Client-ID": GQL_CLIENT_ID},
            timeout=10,
        )
        j = r.json()
        url, dur = _extract_clip((j.get("data") or {}).get("clip"))
        if not url:
            console.warn("clip", "no playable video (%s)" % r.status_code)
        return url, dur
    except Exception as e:
        console.warn("clip", "gql lookup failed: " + str(e))
        return "", 0.0
