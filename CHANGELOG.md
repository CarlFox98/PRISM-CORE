# Changelog

All notable changes to PRISM. Loosely follows [Keep a Changelog](https://keepachangelog.com)
and [Semantic Versioning](https://semver.org).

## [1.1.0] — 2026-08-07

### Added
- **CI** — GitHub Actions workflow (`.github/workflows/ci.yml`) runs JS syntax
  checks, a config/scene integrity test, Python service compile, and a secret scan
  on every push and PR.
- **Secret guard** — `scripts/scan-secrets.sh` plus a `.githooks/pre-commit` hook
  block credentials (and `prism-secrets.json`) from ever being committed.
  Enable locally with `git config core.hooksPath .githooks`.
- **Deploy script** — `deploy-to-pages.bat` / `.sh` copy the canonical overlays
  into `github-pages/` so hosted copies can't drift from source.
- **`prism-secrets.example.json`** at the repo root, plus this `CHANGELOG.md` and
  a `VERSION` marker.

### Changed
- Now-playing widget resolves its Spotify client id from `?cid=` →
  `window.PRISM_CONFIG.spotifyClientId` → built-in fallback, so `prism-config.js`
  is the single documented source.

### Security
- Continues 1.0.0's fix: no credentials are hardcoded; all load via the
  `_secret()` / config loader from `prism-secrets.json` or env.

## [1.0.0] — 2026-08-07

### Added
- `prism-config.js` — single source of truth for channel, socials, follower goal,
  Spotify client id, and avatar; `prism-engine.js` renders socials from it.
- Root `.gitignore`, `README.md`, MIT `LICENSE`; first public release as
  [CarlFox98/PRISM-CORE](https://github.com/CarlFox98/PRISM-CORE).

### Changed
- Centralized scene identity; scenes load `prism-config.js` before `prism-engine.js`.
- Removed duplicate overlay copies from `prismenv/`.

### Security
- Removed hardcoded Twitch Client Secret and OBS WebSocket password from the
  shoutout service; purged from git history.
