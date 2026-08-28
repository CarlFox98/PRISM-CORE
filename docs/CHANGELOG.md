# Changelog

All notable changes to PRISM. Loosely follows [Keep a Changelog](https://keepachangelog.com)
and [Semantic Versioning](https://semver.org).

## [1.6.0] — 2026-08-28

### Changed
- **Restructured the repo.** Root went from 33 loose files to 2. Source is now
  `core/` (theme + config + engine), `scenes/`, `panels/`, `widgets/`, `data/`,
  `tools/` (launchers), alongside the existing `scripts/`, `fonts/`, `docs/`.
  Scenes reference shared assets as `../core/…`, so they still open correctly
  straight from disk.

### Added
- **PRISM is a switchable stream-manager scene set.** `scripts/build-obs-set.py`
  flattens and renames the source into `<OBS Assets>/overlays/prism-holo/` using
  the same scene filenames as the other sets; stream-manager's `scene_sets` is
  now config-driven (`config.json`) and lists `prism-holo`, so it can be picked
  from the dashboard and copied into `overlays/active/`.
- `scripts/deploy-pages.py` replaces the copy logic in the pages deploy so the
  hosted overlays get the same path-flattening treatment.

### Fixed
- The set builder refuses to write into the source repo, and the set folder is
  named `prism-holo` rather than `prism` — on case-insensitive Windows paths
  `overlays/prism` resolves to the `overlays/PRISM` repo, which the build's
  clear-target step would have wiped.

## [1.5.0] — 2026-08-28

### Changed
- **Self-hosted social icons.** The social pills now draw inline SVG brand
  glyphs (X, YouTube, Telegram, Steam) in `currentColor` instead of loading
  images from Google's favicon service. Set `PRISM_CONFIG.iconStyle = "favicon"`
  to restore the old images, or give a social its own `svg` path to add a brand.
- **Fonts are now vendored.** `fonts/` holds the 30 woff2 files and
  `fonts/prism-fonts.css` declares them locally, so overlays need no network
  for fonts at all. Re-run `fetch-fonts.bat` to refresh them.
- Docs and banners moved into `docs/` and `branding/`.

### Security
- The tech-difficulties overlay no longer embeds a Twitch client secret; live
  detection uses DecAPI. The secret was purged from all git history — **it was
  public, so it must be rotated.**
- `scan-secrets.sh` now matches camelCase and kebab-case key names
  (`clientSecret`, `apiKey`, `accessToken`, …). It previously only caught
  snake_case, which is how the above secret slipped past the hook and CI.

### Added
- The integrity test fails if a configured social has no inline icon.

## [1.4.0] — 2026-08-09

### Added
- **Maintenance service** — `scripts/prism-maintenance.py` runs non-destructive
  health checks (venv/deps, `prism-secrets.json` validity, secret-not-committed,
  git status vs origin, config/scene integrity, DecAPI reachability) plus light
  cleanup (repo `__pycache__`, prune old logs), writing a timestamped report to
  `maintenance-logs/`. `install-maintenance-task.bat` registers a silent weekly
  Windows Task Scheduler job (Sundays 4:00 AM via `pythonw`);
  `prism-maintenance.bat` runs it on demand; `uninstall-maintenance-task.bat`
  removes it. Logs are gitignored.

## [1.3.0] — 2026-08-07

### Added
- **DecAPI resilience.** `prism-engine.js` caches the last good avatar, follower
  count, and latest follower in `localStorage` (per channel), paints them
  instantly on load, and falls back to them during brief DecAPI outages — the
  overlay no longer blanks when the endpoint hiccups. Identical behavior when
  DecAPI is healthy.
- **Follower list refresh** — `scripts/refresh-followers.py` + `refresh-followers.bat`
  pull your real follower list from Twitch Helix (using the stream-manager
  token) and write `prism-followers.json`. Requires the `moderator:read:followers`
  scope (re-authorize stream-manager once if the token lacks it).
- **Offline fonts** — `scripts/fetch-fonts.py` + `fetch-fonts.bat` download the
  woff2 files into `fonts/` and rewrite `fonts/prism-fonts.css` to use them.

### Changed
- `prism-theme.css` and `prism-panels.css` now import fonts via the single
  `fonts/prism-fonts.css` aggregator (online by default; local after fetch).

## [1.2.0] — 2026-08-07

### Changed
- **Merged the shoutout service into the repo.** The modular `prism-shoutout/`
  Python package (previously only inside the gitignored `prismenv/`) is now
  versioned here and is the single source of truth. The old monolithic
  `prism_shoutout_service.py` is replaced by a thin launcher shim that imports
  the package; `prismenv/prism_shoutout_service.py` is now a shim to the same
  package. Removed the duplicate package copy from `prismenv/`.
- Launchers export `PRISM_SECRETS` (→ `prismenv/prism-secrets.json`) so the
  service finds credentials regardless of the working directory; added UTF-8
  setup to the top-level launcher for correct console rendering.

### Notes
- No behavior change intended — verified all package modules import and resolve
  credentials. Do one `!so` test before relying on it live.

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
