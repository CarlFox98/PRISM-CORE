#!/usr/bin/env python3
"""
Refresh prism-followers.json with your REAL Twitch follower list.

Uses a Twitch user access token (e.g. the one your stream-manager already
caches in .twitch_user_token.json) plus your app's Client ID. The token MUST
include the ``moderator:read:followers`` scope — Twitch requires it for both
the follower list and the total count. If your current token predates that
scope, re-authorize (see the printed message) once and re-run.

Runs on YOUR machine (Twitch isn't reachable from the build sandbox). No
third-party dependencies — standard library only.

Usage (see refresh-followers.bat for a filled-in launcher):
    python scripts/refresh-followers.py \
        --token  "<path>\\.twitch_user_token.json" \
        --env    "<path>\\.env"            # reads TWITCH_CLIENT_ID/SECRET \
        --out    "prism-followers.json"
"""
import argparse
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HELIX = "https://api.twitch.tv/helix/channels/followers"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"


def _parse_env(path):
    """Minimal .env reader → dict (KEY=VALUE, ignores comments/blank lines)."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _http(method, url, headers=None, data=None):
    req = urllib.request.Request(url, method=method, headers=headers or {},
                                 data=data.encode() if isinstance(data, str) else data)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def _refresh_token(tok, client_id, client_secret):
    """Try to refresh the access token in-place; returns True on success."""
    if not (tok.get("refresh_token") and client_id and client_secret):
        return False
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
        "client_id": client_id,
        "client_secret": client_secret,
    })
    status, data = _http("POST", TOKEN_URL, data=body)
    if status == 200 and data.get("access_token"):
        tok["access_token"] = data["access_token"]
        if data.get("refresh_token"):
            tok["refresh_token"] = data["refresh_token"]
        return True
    return False


def fetch_followers(token_path, client_id, client_secret):
    with open(token_path, "r", encoding="utf-8") as f:
        tok = json.load(f)
    broadcaster = str(tok.get("user_id") or "")
    login = tok.get("login") or ""
    if not broadcaster:
        sys.exit("Token file has no user_id — re-authorize stream-manager and retry.")

    def _headers():
        return {"Client-ID": client_id, "Authorization": "Bearer " + tok["access_token"]}

    names, total, cursor, tried_refresh = [], None, None, False
    while True:
        q = {"broadcaster_id": broadcaster, "first": "100"}
        if cursor:
            q["after"] = cursor
        status, data = _http("GET", HELIX + "?" + urllib.parse.urlencode(q), headers=_headers())

        if status == 401 and not tried_refresh:
            tried_refresh = True
            if _refresh_token(tok, client_id, client_secret):
                try:
                    with open(token_path, "w", encoding="utf-8") as f:
                        json.dump(tok, f, indent=2)
                except Exception:
                    pass
                continue
        if status in (401, 403):
            sys.exit(
                "\nTwitch rejected the request (%d). Your token is missing the\n"
                "  moderator:read:followers\n"
                "scope. Add it to your stream-manager auth scopes and re-run its\n"
                "device-code login once, then run this again.\n" % status)
        if status != 200:
            sys.exit("Twitch API error %d: %s" % (status, json.dumps(data)[:200]))

        total = data.get("total", total)
        for row in data.get("data", []):
            names.append(row.get("user_name") or row.get("user_login"))
        cursor = (data.get("pagination") or {}).get("cursor")
        if not cursor:
            break

    return login, total, [n for n in names if n]


def main():
    ap = argparse.ArgumentParser(description="Refresh prism-followers.json from Twitch.")
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    ap.add_argument("--token", default=os.getenv("PRISM_TWITCH_TOKEN", ""))
    ap.add_argument("--env", default=os.getenv("PRISM_TWITCH_ENV", ""))
    ap.add_argument("--client-id", default=os.getenv("TWITCH_CLIENT_ID", ""))
    ap.add_argument("--client-secret", default=os.getenv("TWITCH_CLIENT_SECRET", ""))
    ap.add_argument("--out", default=os.path.join(repo, "prism-followers.json"))
    a = ap.parse_args()

    if not a.token or not os.path.isfile(a.token):
        sys.exit("--token <path to .twitch_user_token.json> is required (file not found).")

    env = _parse_env(a.env)
    client_id = a.client_id or env.get("TWITCH_CLIENT_ID", "")
    client_secret = a.client_secret or env.get("TWITCH_CLIENT_SECRET", "")
    if not client_id:
        sys.exit("No Client ID — pass --client-id or --env <path to .env with TWITCH_CLIENT_ID>.")

    login, total, names = fetch_followers(a.token, client_id, client_secret)

    payload = {
        "channel": login,
        "generated": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "count": total if total is not None else len(names),
        "followers": names,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("Wrote %d follower names (total=%s) -> %s" % (len(names), total, a.out))


if __name__ == "__main__":
    main()
