"""
Shoutout history — an append-only JSONL log.

The service used to keep everything in memory, which meant clip rotation reset
on every restart (so the same clip replayed after a relaunch) and there was no
record of who got shouted out on a given night.

The log is best-effort: every function here swallows its own errors, because a
failed write must never cost you a shoutout. Set ``config.SHOUTOUT_LOG`` to ""
to turn it off entirely.
"""

import io
import json
import os
import datetime
from collections import OrderedDict

from . import config
from . import console

# how much of the tail to read back when rehydrating clip history
_READ_TAIL_BYTES = 512 * 1024


def path():
    return (config.SHOUTOUT_LOG or "").strip()


def append(entry):
    """Add one line to the log. Never raises."""
    p = path()
    if not p:
        return
    try:
        entry = dict(entry)
        entry.setdefault("ts", datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
        d = os.path.dirname(os.path.abspath(p))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with io.open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        console.warn("log", "couldn't write the shoutout log: " + str(e))


def _tail_lines():
    """The last chunk of the log, as decoded lines. Never raises."""
    p = path()
    if not p or not os.path.isfile(p):
        return []
    try:
        size = os.path.getsize(p)
        with io.open(p, "rb") as f:
            if size > _READ_TAIL_BYTES:
                f.seek(size - _READ_TAIL_BYTES)
                f.readline()                       # drop the partial first line
            raw = f.read()
        return raw.decode("utf-8", "replace").splitlines()
    except Exception as e:
        console.warn("log", "couldn't read the shoutout log: " + str(e))
        return []


def recent_clips():
    """login -> the clip ids most recently shown for them, oldest first."""
    out = OrderedDict()
    for line in _tail_lines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        login, clip_id = e.get("login"), e.get("clipId")
        if not login or not clip_id:
            continue
        ids = out.setdefault(login, [])
        if clip_id in ids:
            ids.remove(clip_id)
        ids.append(clip_id)
    return out


def load_into_clips(clips_module):
    """Prime the in-memory clip rotation from the log, so restarts don't repeat."""
    seen = recent_clips()
    if not seen:
        return 0
    clips_module.prime(seen)
    return len(seen)
