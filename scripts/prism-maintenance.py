#!/usr/bin/env python3
"""
PRISM maintenance — weekly health check + cleanup.

Runs a series of non-destructive checks and light housekeeping, writes a
timestamped log to maintenance-logs/, and prints a summary. Designed to be run
by Windows Task Scheduler (silently, via pythonw) or by hand. Standard library
only; every check is isolated so the run never crashes the scheduler.

Exit code is always 0 (a failed CHECK is logged, not raised) unless --strict.
"""
import datetime as _dt
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGDIR = os.path.join(REPO, "maintenance-logs")
KEEP_LOGS = 12

RESULTS = []  # (level, name, detail)


def add(level, name, detail=""):
    RESULTS.append((level, name, detail))


def run(cmd, cwd=REPO, timeout=90):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def _channel():
    try:
        txt = open(os.path.join(REPO, "core", "prism-config.js"), encoding="utf-8").read()
        m = re.search(r"channel:\s*[\"']([^\"']+)[\"']", txt)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "NeoTheFox98"


# ----------------------------- checks --------------------------------
def check_python():
    add("OK", "Python", sys.version.split()[0])


def check_deps():
    missing = []
    for m in ("requests", "websockets"):
        try:
            __import__(m)
        except Exception:  # noqa: BLE001
            missing.append(m)
    if missing:
        add("WARN", "Shoutout deps", "missing: %s (pip install -r prism-shoutout/requirements.txt)"
            % ", ".join(missing))
    else:
        add("OK", "Shoutout deps", "requests, websockets present")


def check_secrets():
    p = os.path.join(REPO, "prismenv", "prism-secrets.json")
    if not os.path.isfile(p):
        add("WARN", "Secrets file", "prismenv/prism-secrets.json not found")
        return
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        add("FAIL", "Secrets file", "invalid JSON: %s" % e)
        return
    empty = [k for k in ("CLIENT_ID", "CLIENT_SECRET") if not d.get(k)]
    add("WARN" if empty else "OK", "Secrets file",
        ("missing/empty: " + ", ".join(empty)) if empty else "present & valid")


def check_secret_not_tracked():
    code, out = run(["git", "ls-files"])
    if code != 0:
        add("WARN", "Secret not committed", "git unavailable; skipped")
        return
    tracked = [l for l in out.splitlines() if l.endswith("prism-secrets.json")]
    add("FAIL" if tracked else "OK", "Secret not committed",
        ("TRACKED: " + ", ".join(tracked)) if tracked else "gitignored")


def check_git():
    if not shutil.which("git"):
        add("WARN", "Git repo", "git not on PATH")
        return
    run(["git", "fetch", "--quiet", "origin"])
    _, porc = run(["git", "status", "--porcelain"])
    _, head = run(["git", "rev-parse", "HEAD"])
    _, orig = run(["git", "rev-parse", "origin/main"])
    parts = ["uncommitted changes" if porc.strip() else "clean"]
    behind = head.strip() and orig.strip() and head.strip() != orig.strip()
    if behind:
        _, cnt = run(["git", "rev-list", "--count", "HEAD..origin/main"])
        parts.append("behind origin by %s (run: git pull --ff-only)" % cnt.strip())
    else:
        parts.append("up to date with origin")
    add("WARN" if behind else "OK", "Git repo", "; ".join(parts))


def check_integrity():
    if not shutil.which("node"):
        add("WARN", "Integrity test", "node not on PATH; skipped")
        return
    code, out = run(["node", "scripts/test-socials.mjs"])
    last = out.splitlines()[-1] if out else ""
    add("OK" if code == 0 else "FAIL", "Integrity test", last)


def check_reachability():
    ch = _channel()
    try:
        req = urllib.request.Request("https://decapi.me/twitch/followcount/" + ch,
                                     headers={"User-Agent": "PRISM-maintenance"})
        t0 = _dt.datetime.now()
        body = urllib.request.urlopen(req, timeout=10).read().decode().strip()
        ms = int((_dt.datetime.now() - t0).total_seconds() * 1000)
        if body.isdigit():
            add("OK", "DecAPI reachable", "followcount=%s (%d ms)" % (body, ms))
        else:
            add("WARN", "DecAPI reachable", "unexpected response: %s" % body[:40])
    except Exception as e:  # noqa: BLE001
        add("WARN", "DecAPI reachable", "unreachable: %s" % e)


def check_version():
    """VERSION must match the newest CHANGELOG entry, and exist only once."""
    vpath = os.path.join(REPO, "VERSION")
    if not os.path.isfile(vpath):
        add("WARN", "Version", "VERSION file missing")
        return
    ver = open(vpath, encoding="utf-8").read().strip()
    dupes = [p for p in glob.glob(os.path.join(REPO, "*", "VERSION")) if os.path.isfile(p)]
    changelog = None
    for c in (os.path.join(REPO, "docs", "CHANGELOG.md"), os.path.join(REPO, "CHANGELOG.md")):
        if os.path.isfile(c):
            changelog = c
            break
    latest = None
    if changelog:
        m = re.search(r"^##\s*\[([0-9][^\]]*)\]", open(changelog, encoding="utf-8").read(), re.M)
        latest = m.group(1) if m else None
    problems = []
    if dupes:
        problems.append("duplicate VERSION file(s): %s"
                        % ", ".join(os.path.relpath(d, REPO) for d in dupes))
    if latest and latest != ver:
        problems.append("VERSION=%s but newest changelog entry is %s" % (ver, latest))
    add("WARN" if problems else "OK", "Version",
        "; ".join(problems) if problems else "%s (matches changelog, single source)" % ver)


def check_fonts():
    """If fonts are vendored, every url() in the aggregator must resolve."""
    css = os.path.join(REPO, "fonts", "prism-fonts.css")
    if not os.path.isfile(css):
        add("WARN", "Fonts", "fonts/prism-fonts.css missing")
        return
    body = open(css, encoding="utf-8").read()
    if "googleapis" in body:
        add("OK", "Fonts", "online mode (Google import) — run fetch-fonts to vendor them")
        return
    refs = re.findall(r"url\('([^']+)'\)", body)
    missing = [r for r in refs if not os.path.isfile(os.path.join(REPO, "fonts", r))]
    add("FAIL" if missing else "OK", "Fonts",
        ("missing %d file(s): %s" % (len(missing), ", ".join(missing[:3])))
        if missing else "local, %d files all present" % len(refs))


def check_pages_sync():
    """Hosted github-pages copies must match the canonical source files."""
    pages = os.path.join(REPO, "github-pages")
    if not os.path.isdir(pages):
        add("OK", "Hosted overlays", "no github-pages/ folder here; skipped")
        return
    pairs = [(os.path.join("widgets", "prism-nowplaying.html"), "index.html"),
             (os.path.join("widgets", "prism-shoutout.html"), "prism-shoutout.html"),
             (os.path.join("scenes", "prism-thank-you.html"), "prism-thank-you.html"),
             (os.path.join("data", "prism-followers.json"), "prism-followers.json")]
    drift, missing = [], []
    for src, dst in pairs:
        s, d = os.path.join(REPO, src), os.path.join(pages, dst)
        if not os.path.isfile(s):
            continue
        if not os.path.isfile(d):
            missing.append(dst)
        else:
            src_txt = open(s, encoding="utf-8").read()
            for a, b in (("../core/", ""), ("../data/", ""), ("../fonts/", "fonts/")):
                src_txt = src_txt.replace(a, b)
            if src_txt != open(d, encoding="utf-8").read():
                drift.append(dst)
    problems = []
    if missing:
        problems.append("missing: " + ", ".join(missing))
    if drift:
        problems.append("stale: " + ", ".join(drift))
    add("WARN" if problems else "OK", "Hosted overlays",
        ("; ".join(problems) + " — run deploy-to-pages.bat") if problems
        else "all %d in sync with source" % len(pairs))


def check_launchers():
    """Every path a tools/*.bat points at must still exist (catches moves)."""
    tools = os.path.join(REPO, "tools")
    if not os.path.isdir(tools):
        add("WARN", "Launchers", "tools/ not found")
        return
    broken, checked = [], 0
    for name in sorted(os.listdir(tools)):
        if not name.lower().endswith(".bat"):
            continue
        body = open(os.path.join(tools, name), encoding="utf-8", errors="ignore").read()
        for ref in set(re.findall(r"%~dp0\.\.\\([A-Za-z0-9_\\.-]+)", body)):
            checked += 1
            if not os.path.exists(os.path.join(REPO, ref.replace("\\", os.sep))):
                broken.append("%s -> %s" % (name, ref))
    add("WARN" if broken else "OK", "Launchers",
        ("broken: " + "; ".join(broken)) if broken
        else "%d referenced path(s) all exist" % checked)


def check_obs_set():
    """The built OBS scene set should match the current source."""
    parent = os.path.abspath(os.path.join(REPO, ".."))
    out = os.path.join(parent, "prism-holo")
    if not os.path.isdir(out):
        add("OK", "OBS scene set", "not built here — run scripts/build-obs-set.py")
        return
    pairs = {"prism-starting-soon.html": "starting-soon.html",
             "prism-be-right-back.html": "be-right-back.html",
             "prism-stream-ending.html": "stream-ending.html",
             "prism-tech-difficulties.html": "tech-difficulties.html"}
    stale = []
    for src, dst in pairs.items():
        s = os.path.join(REPO, "scenes", src)
        d = os.path.join(out, dst)
        if not os.path.isfile(s):
            continue
        if not os.path.isfile(d):
            stale.append(dst + " (missing)")
            continue
        txt = open(s, encoding="utf-8").read()
        for a, b in (("../core/", ""), ("../data/", ""), ("../fonts/", "fonts/")):
            txt = txt.replace(a, b)
        if txt != open(d, encoding="utf-8").read():
            stale.append(dst)
    add("WARN" if stale else "OK", "OBS scene set",
        ("stale: %s — run scripts/build-obs-set.py" % ", ".join(stale)) if stale
        else "in sync with source")


def cleanup():
    targets = (glob.glob(os.path.join(REPO, "__pycache__"))
               + glob.glob(os.path.join(REPO, "scripts", "__pycache__"))
               + glob.glob(os.path.join(REPO, "prism-shoutout", "**", "__pycache__"), recursive=True))
    removed = 0
    for t in targets:
        shutil.rmtree(t, ignore_errors=True)
        removed += 1
    pruned = 0
    logs = sorted(glob.glob(os.path.join(LOGDIR, "maintenance-*.log")))
    for old in logs[:-KEEP_LOGS]:
        try:
            os.remove(old)
            pruned += 1
        except Exception:  # noqa: BLE001
            pass
    add("OK", "Cleanup", "removed %d __pycache__ dir(s); pruned %d old log(s)" % (removed, pruned))


CHECKS = [check_python, check_deps, check_secrets, check_secret_not_tracked,
          check_git, check_integrity, check_version, check_fonts,
          check_pages_sync, check_obs_set, check_launchers,
          check_reachability, cleanup]


def main():
    strict = "--strict" in sys.argv
    for fn in CHECKS:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            add("FAIL", fn.__name__, "unexpected error: %s" % e)

    ts = _dt.datetime.now()
    counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    for lvl, _, _ in RESULTS:
        counts[lvl] = counts.get(lvl, 0) + 1
    header = "PRISM maintenance — %s" % ts.strftime("%Y-%m-%d %H:%M:%S")
    lines = [header, "=" * len(header)]
    for lvl, name, detail in RESULTS:
        lines.append("[%-4s] %-20s %s" % (lvl, name, detail))
    summary = "Summary: %d OK, %d WARN, %d FAIL" % (counts["OK"], counts["WARN"], counts["FAIL"])
    lines += ["", summary]
    report = "\n".join(lines)

    os.makedirs(LOGDIR, exist_ok=True)
    logpath = os.path.join(LOGDIR, "maintenance-%s.log" % ts.strftime("%Y%m%d-%H%M%S"))
    try:
        open(logpath, "w", encoding="utf-8").write(report + "\n")
    except Exception:  # noqa: BLE001
        pass

    print(report)
    print("\nlog: %s" % logpath)
    if strict and counts["FAIL"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
