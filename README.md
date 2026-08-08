# PRISM

[![PRISM CI](https://github.com/CarlFox98/PRISM-CORE/actions/workflows/ci.yml/badge.svg)](https://github.com/CarlFox98/PRISM-CORE/actions/workflows/ci.yml)

A cohesive **holo-glass / iridescent** overlay system for the Twitch channel
[**NeoTheFox98**](https://twitch.tv/NeoTheFox98). Every scene, panel, and widget
shares one design language — a five-colour prism palette, animated gradient
borders, drifting light motes, and live Twitch data — all rendered at
**1920×1080** and ready to drop into OBS as Browser Sources.

## Design system

Two shared cores drive everything, so retheming or re-pointing identity happens
in one place instead of every file:

| File | Role |
|------|------|
| `prism-config.js` | **Single source of truth** — channel name, socials, follower goal, Spotify client id, avatar fallback. Change identity here and every scene follows. |
| `prism-theme.css` | Shared look for the full-screen scenes (palette `--c1`…`--c5`, backdrop, motes, holo components). |
| `prism-engine.js` | Particle motes + live Twitch data via DecAPI (no secrets), and renders socials from config. Degrades gracefully offline; respects `prefers-reduced-motion`. |
| `prism-panels.css` | Shared look for the standalone Twitch info panels. |

Live-data hooks: add `class="js-avatar"`, `js-followcount`, `js-goal-fill`,
`js-goal-now`, `js-goal-target`, or `js-latest` to any element and the engine
fills it. Socials render into any `<div class="socials" data-prism-socials></div>`.

## Scenes (full-screen, load `prism-theme.css` + `prism-config.js` + `prism-engine.js`)

- `prism-starting-soon.html` — countdown (configurable via `?timer=` or the gear)
- `prism-be-right-back.html`
- `prism-stream-ending.html`
- `prism-tech-difficulties.html`
- `prism-wallpaper.html`
- `prism-webcam-frame.html`
- `prism-chat-preview.html` — styled with `prism-chat-holo-iridescent.css`
- `prism-thank-you.html` — random-follower shout (reads `prism-followers.json`)

## Info panels (standalone, load `prism-panels.css`)

`prism-about.html` · `prism-rules.html` · `prism-schedule.html` ·
`prism-setup.html` · `prism-faq.html`
PNG exports for Twitch upload live in `twitch-panels/`.

## Widgets

- **`prism-nowplaying.html`** — standalone Spotify now-playing card. Self-hosted
  OAuth; see `PRISM-NOWPLAYING-README.md`. Its Spotify client id must match
  `spotifyClientId` in `prism-config.js`.
- **`prism-shoutout.html` + the `prism-shoutout/` package** — a mod types
  `!so @user` in chat and a PRISM card slides in with the streamer's avatar,
  last category, and an autoplaying recent clip. The service is the modular
  [`prism-shoutout/`](prism-shoutout/README.md) Python package;
  `prism_shoutout_service.py` at the repo root is a thin launcher shim for it.
  See `PRISM-SHOUTOUT-README.md`; launch with `Start-PRISM-Shoutout.bat`.

## Local setup (shoutout service)

The service code lives in the `prism-shoutout/` package (versioned here). Its
virtual environment (`prismenv/`) is **not** in the repo — recreate it once:

```
py -m venv prismenv
prismenv\Scripts\python.exe -m pip install -r prism-shoutout\requirements.txt
```

Then copy `prism-secrets.example.json` to `prismenv\prism-secrets.json`, fill in
your Twitch app credentials, and run `Start-PRISM-Shoutout.bat`. The launchers
set `PRISM_SECRETS` to that file, so the service finds it no matter where it's
started from. **Secrets stay local and are gitignored** — nothing is ever
committed. Verify them any time with `prismenv\PRISM-Check.bat`.

## Hosting

Overlays that must autoplay clips or complete Spotify OAuth (shoutout,
now-playing, thank-you) are served over HTTPS from GitHub Pages via the separate
[`CarlFox98/streaming`](https://github.com/CarlFox98/streaming) repo (the local
`github-pages/` working copy is gitignored here). All other scenes and panels run
fine as local `file://` Browser Sources.

## Retheming

Edit the palette variables `--c1`…`--c5` at the top of `prism-theme.css` and
`prism-panels.css` to retune the entire set at once. Edit `prism-config.js` to
change identity (channel, socials, goal).

## Development

Clone, then enable the guards once:

```
git config core.hooksPath .githooks     # blocks secrets from being committed
```

Checks (also run in CI on every push via `.github/workflows/ci.yml`):

```
node scripts/test-socials.mjs      # config + scene load-order integrity
bash scripts/scan-secrets.sh       # credential scan
node --check prism-config.js prism-engine.js
```

To update the **hosted** overlays (now-playing, shoutout, thank-you), edit the
source files here, run `deploy-to-pages.bat` to copy them into `github-pages/`,
then push that separate `streaming` repo. This keeps the hosted copies from
drifting from source.

Versioning follows [SemVer](https://semver.org); see [CHANGELOG.md](CHANGELOG.md).

The shoutout **service** is the modular `prism-shoutout/` package (its own
[README](prism-shoutout/README.md) and `docs/`). Both `prism_shoutout_service.py`
(repo root) and `prismenv/prism_shoutout_service.py` are thin shims that import
this one package, so there's a single source of truth. `run.bat` inside the
package runs it directly via `python -m prism_shoutout`.

## License

Released under the [MIT License](LICENSE) © 2026 NeoTheFox98 (CarlFox98). Fork
it, swap your identity in `prism-config.js`, and make it yours.
