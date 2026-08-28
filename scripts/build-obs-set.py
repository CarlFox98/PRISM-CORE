#!/usr/bin/env python3
"""
Build PRISM into a stream-manager scene set.

stream-manager serves switchable overlay sets from:
    <OBS Assets>/overlays/<set>/     e.g. modern/, retro/
and copies the chosen one into overlays/active/, which OBS points at as
    http://localhost:5000/overlays/active/<scene>.html

That means a set has to be a FLAT, self-contained folder of scene .html files
using the shared scene names. PRISM's source repo is organised for humans
(scenes/, core/, ...), so this script flattens and renames it into the set
folder — the same source-vs-deployed split used for github-pages.

Re-runnable and destructive only inside the target set folder.

    python scripts/build-obs-set.py            # writes ../prism/
    python scripts/build-obs-set.py --dry-run
"""
import argparse
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# NOTE: the set folder must NOT be called "prism" — Windows paths are
# case-insensitive, so overlays/prism would resolve to the overlays/PRISM
# source repo itself and this script would wipe it. Keep a distinct name.
SET_NAME = "prism-holo"


def overlays_dir():
    """The stream-manager overlays/ folder — the parent that holds the sets."""
    parent = os.path.abspath(os.path.join(REPO, ".."))
    markers = ("modern", "retro", "active")
    if any(os.path.isdir(os.path.join(parent, m)) for m in markers):
        return parent
    return None


def _same_or_inside(target, other):
    """True if target is `other` or lives inside it (case-insensitive)."""
    t = os.path.normcase(os.path.realpath(target))
    o = os.path.normcase(os.path.realpath(other))
    return t == o or t.startswith(o + os.sep)

# PRISM source file -> canonical scene name used by the other sets (modern/).
SCENES = {
    "prism-starting-soon.html":     "starting-soon.html",
    "prism-be-right-back.html":     "be-right-back.html",
    "prism-stream-ending.html":     "stream-ending.html",
    "prism-tech-difficulties.html": "tech-difficulties.html",
    "prism-webcam-frame.html":      "webcam-frame.html",
    "prism-wallpaper.html":         "wallpaper.html",
    "prism-chat-preview.html":      "chat-preview.html",
    "prism-thank-you.html":         "thank-you.html",
}

# Shared assets the scenes reference by relative name — copied as-is so the
# set folder works standalone once stream-manager copies it into active/.
ASSETS = [
    "prism-theme.css",
    "prism-config.js",
    "prism-engine.js",
    "prism-chat-holo-iridescent.css",
    "prism-followers.json",
]
ASSET_DIRS = ["fonts"]


# The source repo keeps shared assets in core/ and data/ and references them
# as ../core/x. A scene set is FLAT, so those prefixes are rewritten on copy.
FLATTEN = [("../core/", ""), ("../data/", ""), ("../fonts/", "fonts/")]
TEXT_EXT = (".html", ".css", ".js", ".json")


def copy_flat(src, dst):
    """Copy a file, rewriting source-layout relative paths for a flat folder."""
    if not src.lower().endswith(TEXT_EXT):
        shutil.copy2(src, dst)
        return
    with open(src, "r", encoding="utf-8") as f:
        body = f.read()
    for a, b in FLATTEN:
        body = body.replace(a, b)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(body)


def find(name):
    """Locate a source file whether the repo is flat or restructured."""
    for sub in ("", "scenes", "panels", "widgets", "core", "data"):
        p = os.path.join(REPO, sub, name) if sub else os.path.join(REPO, name)
        if os.path.isfile(p):
            return p
    return None


def find_dir(name):
    for sub in ("", "core"):
        p = os.path.join(REPO, sub, name) if sub else os.path.join(REPO, name)
        if os.path.isdir(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description="Build PRISM into a stream-manager scene set.")
    ap.add_argument("--out", default=None,
                    help="target set folder (default: <overlays>/%s)" % SET_NAME)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not a.out:
        ov = overlays_dir()
        if not ov:
            print("ERROR: couldn't find the stream-manager overlays/ folder next to this repo.\n"
                  "       Pass it explicitly, e.g.  --out \"...\\overlays\\%s\"" % SET_NAME)
            return 1
        a.out = os.path.join(ov, SET_NAME)

    # Safety: never write into (or clear) the source repo itself. On Windows
    # "prism" and "PRISM" are the same folder, so this guard is load-bearing.
    if _same_or_inside(a.out, REPO):
        print("ERROR: refusing to build into '%s' — that is the PRISM source repo.\n"
              "       Choose a set folder with a different name (e.g. %s)." % (a.out, SET_NAME))
        return 1
    if os.path.isdir(os.path.join(a.out, ".git")):
        print("ERROR: refusing to clear '%s' — it contains a git repository." % a.out)
        return 1

    plan, missing = [], []
    for src, dst in SCENES.items():
        p = find(src)
        (plan.append((p, os.path.join(a.out, dst))) if p else missing.append(src))
    for asset in ASSETS:
        p = find(asset)
        (plan.append((p, os.path.join(a.out, asset))) if p else missing.append(asset))
    dirs = []
    for d in ASSET_DIRS:
        p = find_dir(d)
        (dirs.append((p, os.path.join(a.out, d))) if p else missing.append(d + "/"))

    if missing:
        print("ERROR: could not find: %s" % ", ".join(missing))
        return 1

    print("PRISM -> scene set: %s" % a.out)
    for s, d in plan:
        print("  %-34s -> %s" % (os.path.relpath(s, REPO), os.path.basename(d)))
    for s, d in dirs:
        print("  %-34s -> %s/" % (os.path.relpath(s, REPO) + "/", os.path.basename(d)))

    if a.dry_run:
        print("\n(dry run — nothing written)")
        return 0

    os.makedirs(a.out, exist_ok=True)
    # clear only what we own, so a stray file in the set folder can't linger
    for entry in os.listdir(a.out):
        p = os.path.join(a.out, entry)
        if entry == ".active-set":
            continue
        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)

    for s, d in plan:
        copy_flat(s, d)
    for s, d in dirs:
        shutil.copytree(s, d)

    n = len(plan) + sum(len(files) for _, _, files in os.walk(dirs[0][1])) if dirs else len(plan)
    print("\nWrote %d scene file(s) + assets. Switch to it from the stream-manager dashboard." % len(SCENES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
