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
        txt = open(os.path.join(REPO, "prism-config.js"), encoding="utf-8").read()
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
          check_git, check_integrity, check_reachability, cleanup]


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
