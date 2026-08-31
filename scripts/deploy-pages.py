#!/usr/bin/env python3
"""
Copy the hosted overlays into github-pages/.

GitHub Pages serves a FLAT folder, while the source repo keeps shared assets in
core/ and data/. This flattens the relative paths on copy — same source-vs-
deployed split as scripts/build-obs-set.py.

    python scripts/deploy-pages.py [--dry-run]
"""
import argparse
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = os.path.join(REPO, "github-pages")

# source (relative to repo) -> name in github-pages/
FILES = {
    os.path.join("widgets", "prism-nowplaying.html"): "index.html",
    os.path.join("widgets", "prism-shoutout.html"):   "prism-shoutout.html",
    os.path.join("scenes",  "prism-thank-you.html"):  "prism-thank-you.html",
    os.path.join("data",    "prism-followers.json"):  "prism-followers.json",
}

FLATTEN = [("../core/", ""), ("../data/", ""), ("../fonts/", "fonts/")]
TEXT_EXT = (".html", ".css", ".js", ".json")

# folders copied wholesale (the overlays @import fonts/prism-fonts.css, so the
# woff2 files have to be there or the hosted page silently falls back)
DIRS = {"fonts": "fonts"}


def copy_flat(src, dst):
    if not src.lower().endswith(TEXT_EXT):
        shutil.copy2(src, dst)
        return
    body = open(src, "r", encoding="utf-8").read()
    for a, b in FLATTEN:
        body = body.replace(a, b)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(body)


def main():
    ap = argparse.ArgumentParser(description="Deploy hosted overlays into github-pages/.")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(PAGES):
        print("ERROR: github-pages/ not found next to the repo.")
        return 1

    missing = [s for s in FILES if not os.path.isfile(os.path.join(REPO, s))]
    if missing:
        print("ERROR: missing source file(s): %s" % ", ".join(missing))
        return 1

    for src, dst in FILES.items():
        print("  %-38s -> %s" % (src, dst))
        if not a.dry_run:
            copy_flat(os.path.join(REPO, src), os.path.join(PAGES, dst))

    copied_dirs = 0
    for src, dst in DIRS.items():
        src_dir = os.path.join(REPO, src)
        if not os.path.isdir(src_dir):
            print("  WARNING: %s/ not found — skipping" % src)
            continue
        names = [f for f in sorted(os.listdir(src_dir))
                 if os.path.isfile(os.path.join(src_dir, f))]
        print("  %-38s -> %s/  (%d files)" % (src + "/", dst, len(names)))
        if not a.dry_run:
            out_dir = os.path.join(PAGES, dst)
            os.makedirs(out_dir, exist_ok=True)
            # copy file by file rather than replacing the folder: the target is
            # inside a git repo, and an rmtree there churns history for
            # unchanged binaries and is one wrong path away from real damage
            for name in names:
                copy_flat(os.path.join(src_dir, name), os.path.join(out_dir, name))
            stale = [f for f in sorted(os.listdir(out_dir))
                     if os.path.isfile(os.path.join(out_dir, f)) and f not in names]
            for f in stale:
                print("    NOTE: %s/%s is no longer in the source — remove it by hand" % (dst, f))
            copied_dirs += 1

    print("\n(dry run — nothing written)" if a.dry_run
          else "\nDeployed %d file(s) and %d folder(s) into github-pages/."
               % (len(FILES), copied_dirs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
