#!/usr/bin/env python3
"""
PRISM Shoutout — launcher shim.

The service implementation now lives in the ``prism-shoutout/`` package in this
same folder (modular; see prism-shoutout/README.md). This thin launcher keeps
the existing Start-PRISM-Shoutout.bat working and makes the package importable.

Equivalent to:  python -m prism_shoutout
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

# make the packaged service importable
sys.path.insert(0, os.path.join(_HERE, "prism-shoutout"))

# Credentials live in the git-ignored prismenv/prism-secrets.json. Point the
# package's secret loader at it unless the environment already specifies one,
# so the service finds its secrets no matter which folder it's launched from.
os.environ.setdefault(
    "PRISM_SECRETS", os.path.join(_HERE, "prismenv", "prism-secrets.json")
)

from prism_shoutout.service import run  # noqa: E402

if __name__ == "__main__":
    run()
