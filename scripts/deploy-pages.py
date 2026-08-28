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

    print("\n(dry run — nothing written)" if a.dry_run
          else "\nDeployed %d file(s) into github-pages/." % len(FILES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
