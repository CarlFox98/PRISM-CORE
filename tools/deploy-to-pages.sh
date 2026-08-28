#!/usr/bin/env bash
# Deploy the hosted overlays into github-pages/, flattening the source layout
# (core/, data/) the same way scripts/build-obs-set.py does. Then commit and
# push the separate 'streaming' repo yourself, or use tools/deploy-to-pages.bat
# which does all of it in one go.
set -eu
cd "$(git rev-parse --show-toplevel)"

python3 scripts/deploy-pages.py "$@"

echo ""
echo "Next: cd github-pages && git add -A && git commit -m 'sync hosted overlays' && git push"
