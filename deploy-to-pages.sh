#!/usr/bin/env bash
# Copy the canonical overlays into github-pages/ so the hosted copies never
# drift from source. Then commit/push the separate 'streaming' repo yourself.
set -eu
cd "$(git rev-parse --show-toplevel)"
[ -d github-pages ] || { echo "github-pages/ not found"; exit 1; }

cp -v prism-nowplaying.html github-pages/index.html
cp -v prism-shoutout.html   github-pages/prism-shoutout.html
cp -v prism-thank-you.html  github-pages/prism-thank-you.html
cp -v prism-followers.json  github-pages/prism-followers.json

echo ""
echo "Deployed. Next: cd github-pages && git add -A && git commit -m 'sync overlays' && git push"
