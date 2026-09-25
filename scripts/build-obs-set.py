#!/usr/bin/env python3
"""
Build PRISM into stream-manager scene sets.

stream-manager serves switchable overlay sets from:
    <OBS Assets>/overlays/<set>/     e.g. modern/, retro/
and copies the chosen one into overlays/active/, which OBS points at as
    http://localhost:5000/overlays/active/<scene>.html

That means a set has to be a FLAT, self-contained folder of scene .html files
using the shared scene names. PRISM's source repo is organised for humans
(scenes/, core/, ...), so this script flattens and renames it into the set
folder — the same source-vs-deployed split used for github-pages.

Re-runnable and destructive only inside the target set folder.

PRISM ships three sets, each its own folder next to modern/ and retro/:

    prism-holo     the 1.x holo-glass scenes      (source: scenes/)
    prism-signal   2.0 Signal — sci-fi HUD        (source: themes/signal/)
    prism-soft     2.0 Soft Holo — pastel/sticker (source: themes/soft/)

Each name must also be listed in stream-manager's config.json "scene_sets"
for the dashboard to offer it (restart Stream Manager after editing that).

    python scripts/build-obs-set.py                    # builds all three
    python scripts/build-obs-set.py --set prism-signal # just one
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
SET_NAME = "prism-holo"          # the default for --out, kept for old habits


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
# (1.x holo set; its scenes live in scenes/ with a prism- prefix.)
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

# The shoutout card and the now-playing widget restyle themselves from
# /overlays/active/<widget>-theme.css. Holo's are empty on purpose: switching
# back to holo then clears a 2.0 theme instead of leaving it applied.
HOLO_THEMES = {
    "theme-holo-shoutout.css":   "shoutout-theme.css",
    "theme-holo-nowplaying.css": "nowplaying-theme.css",
    # Unlike the two above, holo's chat skin is NOT empty: the chat overlay is
    # PRISM's own markup, so holo gets a proper look rather than the 1.x sheet's
    # guesses about SoundAlerts' DOM.
    "theme-holo-chat.css":       "chat-theme.css",
}

# 2.0 sets: every file in themes/<name>/ is copied (scenes are already named
# canonically, plus the theme's css and chat-theme.css), together with these
# shared files. Nothing to add here for chat: the whole theme folder ships.
THEME_SCENES = ["starting-soon.html", "be-right-back.html", "stream-ending.html",
                "tech-difficulties.html", "webcam-frame.html", "wallpaper.html",
                "chat-preview.html", "thank-you.html", "gameplay.html"]
THEME_ASSETS = [
    "prism-config.js", "prism-engine.js", "prism-countdown.js", "prism-techcheck.js",
    "prism-wallpaper.js", "prism-thankyou.js", "prism-chat-demo.js", "prism-followers.json",
]
SETS = {
    "prism-holo":   None,        # built from SCENES/ASSETS above
    "prism-signal": "signal",
    "prism-soft":   "soft",
}


# The source repo keeps shared assets in core/ and data/ and references them
# as ../core/x. A scene set is FLAT, so those prefixes are rewritten on copy.
# Theme files sit one level deeper (themes/<name>/), so their ../../ forms are
# rewritten first.
FLATTEN = [("../../core/", ""), ("../../data/", ""), ("../../fonts/", "fonts/"),
           ("../core/", ""), ("../data/", ""), ("../fonts/", "fonts/")]
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


def plan_set(name):
    """(files, dirs, missing) for one set: lists of (src, dst-name)."""
    files, missing = [], []
    theme = SETS[name]
    if theme is None:
        for src, dst in SCENES.items():
            p = find(src)
            (files.append((p, dst)) if p else missing.append(src))
        for asset in ASSETS:
            p = find(asset)
            (files.append((p, asset)) if p else missing.append(asset))
        for src, dst in HOLO_THEMES.items():
            p = find(src)
            (files.append((p, dst)) if p else missing.append(src))
    else:
        tdir = os.path.join(REPO, "themes", theme)
        for sc in THEME_SCENES:
            if not os.path.isfile(os.path.join(tdir, sc)):
                missing.append("themes/%s/%s" % (theme, sc))
        if os.path.isdir(tdir):
            for fn in sorted(os.listdir(tdir)):
                p = os.path.join(tdir, fn)
                if os.path.isfile(p):
                    files.append((p, fn))
        for asset in THEME_ASSETS:
            p = find(asset)
            (files.append((p, asset)) if p else missing.append(asset))
    dirs = []
    for d in ASSET_DIRS:
        p = find_dir(d)
        (dirs.append((p, d)) if p else missing.append(d + "/"))
    return files, dirs, missing


def build(name, out, dry):
    if _same_or_inside(out, REPO):
        print("ERROR: refusing to build into '%s' — that is the PRISM source repo.\n"
              "       Choose a set folder with a different name (e.g. %s)." % (out, name))
        return 1
    if os.path.isdir(os.path.join(out, ".git")):
        print("ERROR: refusing to clear '%s' — it contains a git repository." % out)
        return 1
    files, dirs, missing = plan_set(name)
    if missing:
        print("ERROR (%s): could not find: %s" % (name, ", ".join(missing)))
        return 1
    print("PRISM -> scene set: %s" % out)
    for s_, d in files:
        print("  %-38s -> %s" % (os.path.relpath(s_, REPO), d))
    for s_, d in dirs:
        print("  %-38s -> %s/" % (os.path.relpath(s_, REPO) + "/", d))
    if dry:
        print("  (dry run — nothing written)\n")
        return 0
    os.makedirs(out, exist_ok=True)
    # clear only what we own, so a stray file in the set folder can't linger
    for entry in os.listdir(out):
        p = os.path.join(out, entry)
        if entry == ".active-set":
            continue
        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
    for s_, d in files:
        copy_flat(s_, os.path.join(out, d))
    for s_, d in dirs:
        shutil.copytree(s_, os.path.join(out, d))
        # the fonts css is text too — nothing to rewrite today, but keep it consistent
    n = sum(1 for _, d in files if d.endswith(".html"))
    print("  wrote %d scene file(s) + assets.\n" % n)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Build PRISM into stream-manager scene sets.")
    ap.add_argument("--set", choices=sorted(SETS), default=None,
                    help="build only this set (default: all)")
    ap.add_argument("--out", default=None,
                    help="target folder — only with --set (default: <overlays>/<set>)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    names = [a.set] if a.set else list(SETS)
    if a.out and not a.set:
        print("ERROR: --out needs --set (it names ONE set's folder).")
        return 1
    ov = None
    if not a.out:
        ov = overlays_dir()
        if not ov:
            print("ERROR: couldn't find the stream-manager overlays/ folder next to this repo.\n"
                  "       Pass it explicitly, e.g.  --set prism-signal --out \"...\\overlays\\prism-signal\"")
            return 1
    rc = 0
    for name in names:
        out = a.out or os.path.join(ov, name)
        rc = build(name, out, a.dry_run) or rc
    if rc == 0 and not a.dry_run:
        print("Done. Switch sets from the stream-manager dashboard (each name must be in its\n"
              "config.json \"scene_sets\"), then refresh your OBS browser sources.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
