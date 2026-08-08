#!/usr/bin/env bash
# ============================================================
#  PRISM — secret scanner
#  Blocks credentials from being committed. Used by the
#  pre-commit hook (staged files) and by CI (all tracked files).
#
#  Usage:
#    scripts/scan-secrets.sh [file ...]   # scan given files
#    scripts/scan-secrets.sh              # scan all git-tracked files
#  Exit 0 = clean, 1 = a likely secret was found.
# ============================================================
set -u

if [ "$#" -gt 0 ]; then
  files="$*"
else
  files="$(git ls-files)"
fi

fail=0

# 1) Never allow the real secrets file (or any *.secret) to be committed.
for f in $files; do
  case "$f" in
    prism-secrets.json|*/prism-secrets.json|*.secret)
      echo "BLOCKED: $f must never be committed (it holds real credentials)."
      fail=1 ;;
  esac
done

# 2) Content patterns. A "secret" = a real quoted literal (>=12 chars) assigned to
#    a secret-named key, or an oauth: token. Placeholders/examples are ignored.
SECRET_KEY='(client_secret|secret_key|api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd)'
# value literal right after : or = (whitespace only between), 12+ non-space chars
VALUE='["'"'"'][^"'"'"']{12,}["'"'"']'
PLACEHOLDER='your_|example|changeme|change_me|xxxx|<[a-z]|_here|placeholder|\*\*\*'

for f in $files; do
  # skip binaries, example files, this script, and the docs that describe patterns
  case "$f" in
    *.png|*.jpg|*.jpeg|*.gif|*.ico|*.woff|*.woff2|*.ttf|*.zip|*.mp3|*.mp4) continue ;;
    *.example.json|*example*|scripts/scan-secrets.sh|.githooks/*|*.md) continue ;;
  esac
  [ -f "$f" ] || continue

  # secret-keyed literal assignment (case-insensitive), excluding placeholders
  hits=$(grep -EnI -i "${SECRET_KEY}[\"' ]*[:=][ ]*${VALUE}" "$f" 2>/dev/null \
          | grep -EvI -i "${PLACEHOLDER}" || true)
  # oauth token that isn't a run of the same placeholder char
  oauth=$(grep -EnI -i 'oauth:[a-z0-9]{20,}' "$f" 2>/dev/null \
          | grep -EviI 'x{10}|oauth:xxxx' || true)

  if [ -n "$hits" ] || [ -n "$oauth" ]; then
    echo "POSSIBLE SECRET in $f:"
    [ -n "$hits" ]  && echo "$hits"  | sed 's/^/  /'
    [ -n "$oauth" ] && echo "$oauth" | sed 's/^/  /'
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo ""
  echo "✗ Secret scan failed. Move credentials into prism-secrets.json (gitignored)"
  echo "  or an environment variable, then use the _secret()/config loader instead."
  exit 1
fi
echo "✓ Secret scan clean ($(echo $files | wc -w) files)."
exit 0
