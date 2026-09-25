#!/usr/bin/env python3
"""
Deploy the PRISM chat overlay into stream-manager's static folder.

PRISM keeps sources organised for humans (chat/, core/); the deployed
overlay is a FLAT folder that stream-manager serves, so this script
flattens and rewrites the same way build-obs-set.py does for scene sets.
Source of truth stays here; the copy under static/ is generated.

    <OBS Assets>/overlays/PRISM/chat/prism-chat.html   -> static/chat/chat.html
    <OBS Assets>/overlays/PRISM/core/prism-chat.js     -> static/chat/prism-chat.js
    <OBS Assets>/overlays/PRISM/core/prism-chat-base.css -> static/chat/prism-chat-base.css

OBS points at one URL that never changes and is not tied to a set:

    http://localhost:5000/static/chat/chat.html

    python scripts/deploy-chat.py
    python scripts/deploy-chat.py --to "C:\\path\\to\\stream-manager-main"
    python scripts/deploy-chat.py --dry-run
"""
import argparse
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# source -> deployed name (flat)
FILES = {
    os.path.join("chat", "prism-chat.html"): "chat.html",
    os.path.join("core", "prism-chat.js"): "prism-chat.js",
    os.path.join("core", "prism-chat-base.css"): "prism-chat-base.css",
}
# The sources reference siblings already, so nothing to rewrite today; kept
# for the same reason build-obs-set.py keeps it — a ../core/ creeping in
# should flatten rather than 404.
FLATTEN = [("../core/", ""), ("../chat/", ""), ("./core/", "")]
TEXT_EXT = (".html", ".css", ".js")


def default_target():
    """Guess stream-manager from the usual layout next to OBS Assets."""
    guesses = [
        os.path.expanduser(r"~\Desktop\Streaming\stream-manager-main\stream-manager-main"),
        os.path.expanduser("~/Desktop/Streaming/stream-manager-main/stream-manager-main"),
    ]
    for g in guesses:
        if os.path.isdir(os.path.join(g, "static")):
            return g
    return None


def copy_one(src, dst, dry):
    with open(src, "rb") as f:
        raw = f.read()
    if src.lower().endswith(TEXT_EXT):
        text = raw.decode("utf-8")
        for a, b in FLATTEN:
            text = text.replace(a, b)
        raw = text.encode("utf-8")
    if dry:
        return len(raw)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(raw)
    return len(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", help="stream-manager folder (the one containing static/)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    target = args.to or default_target()
    if not target or not os.path.isdir(os.path.join(target, "static")):
        print("Could not find stream-manager's static/ folder.")
        print("Pass it explicitly:  python scripts/deploy-chat.py --to <folder>")
        return 1

    out = os.path.join(target, "static", "chat")
    print(f"PRISM chat -> {out}")
    missing = [s for s in FILES if not os.path.isfile(os.path.join(REPO, s))]
    if missing:
        print("MISSING source files: " + ", ".join(missing))
        return 1

    for src_rel, dst_name in sorted(FILES.items()):
        n = copy_one(os.path.join(REPO, src_rel), os.path.join(out, dst_name), args.dry_run)
        print(f"  {'would copy' if args.dry_run else 'copied'}  {src_rel:<28} -> chat/{dst_name}  ({n} bytes)")

    print("\nOBS browser source URL:")
    print("  http://localhost:5000/static/chat/chat.html")
    print("  optional: ?anchor=top  ?align=right  ?max=8  ?ageout=90")
    if shutil.which("python") is None:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
