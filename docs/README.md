# PRISM

[![PRISM CI](https://github.com/CarlFox98/PRISM-CORE/actions/workflows/ci.yml/badge.svg)](https://github.com/CarlFox98/PRISM-CORE/actions/workflows/ci.yml)

A cohesive **holo-glass / iridescent** overlay system for the Twitch channel
[**NeoTheFox98**](https://twitch.tv/NeoTheFox98). Every scene, panel, and widget
shares one design language — a five-colour prism palette, animated gradient
borders, drifting light motes, and live Twitch data — all rendered at
**1920×1080** and ready to drop into OBS as Browser Sources.

## Repository layout

```
core/      shared theme, panels css, chat css, prism-config.js, prism-engine.js
scenes/    full-screen OBS scenes          panels/   standalone Twitch info panels
widgets/   now-playing + shoutout overlays data/     follower list, secrets example
fonts/     vendored woff2 + aggregator     tools/    .bat/.sh launchers
scripts/   python/node tooling             docs/     README, CHANGELOG, LICENSE
branding/  banners
```

> The shoutout **service** (the Python half) now lives in
> [stream-manager](https://github.com/CarlFox98/stream-manager) as
> `stream_manager/shoutout.py`. This repo keeps the **overlay**
> (`widgets/prism-shoutout.html`) and its headless test
> (`scripts/test-shoutout-overlay.mjs`).

Scenes reference shared assets as `../core/…`, so they open correctly straight
from disk. The two deploy steps (`scripts/build-obs-set.py` and
`scripts/deploy-pages.py`) flatten those paths when they emit a deployed copy.

## OBS scene set

PRISM is a switchable set for the local stream-manager. Build it with:

```
python scripts/build-obs-set.py        # writes <OBS Assets>/overlays/prism-holo/
```

Then pick **prism-holo** in the stream-manager dashboard; it copies the set into
`overlays/active/`, which OBS serves. The set folder is deliberately *not* named
`prism` — Windows paths are case-insensitive, so `overlays/prism` would collide
with the `overlays/PRISM` source repo.

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

## Scenes — `scenes/` (load `../core/prism-theme.css` + `prism-config.js` + `prism-engine.js`)

- `prism-starting-soon.html` — countdown (configurable via `?timer=` or the gear)
- `prism-be-right-back.html`
- `prism-stream-ending.html`
- `prism-tech-difficulties.html`
- `prism-wallpaper.html`
- `prism-webcam-frame.html`
- `prism-chat-preview.html` — styled with `../core/prism-chat-holo-iridescent.css`
- `prism-thank-you.html` — random-follower shout (reads `../data/prism-followers.json`)

## Info panels — `panels/` (standalone, load `../core/prism-panels.css`)

`prism-about.html` · `prism-rules.html` · `prism-schedule.html` ·
`prism-setup.html` · `prism-faq.html`
PNG exports for Twitch upload live in `twitch-panels/`.

## Widgets — `widgets/`

- **`prism-nowplaying.html`** — standalone Spotify now-playing card. Self-hosted
  OAuth; see `PRISM-NOWPLAYING-README.md`. Its Spotify client id must match
  `spotifyClientId` in `prism-config.js`.
- **`prism-shoutout.html`** — a mod types `!so @user` in chat and a PRISM card
  slides in with the streamer's avatar, last category, and an autoplaying recent
  clip. Gold "Raid · N viewers" variant for raids; falls back to the streamer's
  offline banner when there's no clip. It connects to the driving service over
  `ws://127.0.0.1:8777` and is driven by Stream Manager's `shoutout` module —
  see [Shoutout service](#shoutout-service) below. Test it headlessly with
  `node scripts/test-shoutout-overlay.mjs`, or open it with `?demo`.

## Shoutout service

The Python service that watches chat, resolves clips and drives the card was
**merged into [stream-manager](https://github.com/CarlFox98/stream-manager)**
(Sept 2026) and now ships as `stream_manager/shoutout.py`, started with the rest
of Stream Manager. Its credentials, config and log live there too
(`data/shoutout-log.jsonl`).

What stays in this repo is the presentation half:

| Here | There |
|------|-------|
| `widgets/prism-shoutout.html` — the card | chat reader, `!so` and mod controls |
| `scripts/test-shoutout-overlay.mjs` — 32 headless checks | Twitch lookups, clip selection, chat commands |

**There are two cards, not one, and OBS loads the other one.** Stream Manager
ships its own copy at `static/interactive/shoutout.html`, served over HTTP and
fed by a long-poll on `/api/effects/shoutout`; that is what the OBS scenes
actually load. The card here is the WebSocket build (`ws://127.0.0.1:8777`),
which nothing currently serves — it is kept as the reference implementation and
as the thing the harness is written against.

So a change to the card has to be made **in both files**, and the harness is
transport-agnostic so it can prove it:

```bash
node scripts/test-shoutout-overlay.mjs            # this repo's copy
node scripts/test-shoutout-overlay.mjs "<stream-manager>/static/interactive/shoutout.html"
```

Both must pass the same 32 checks. Audio ducking is **not** implemented on
either side — Stream Manager dropped it deliberately; see the note above
`set_clip_playing()` there before reaching for it again.

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
node --check core/prism-config.js core/prism-engine.js
```

To update the **hosted** overlays (now-playing, shoutout, thank-you), edit the
source files here, run `tools\deploy-to-pages.bat` to copy them into `github-pages/`,
then push that separate `streaming` repo. This keeps the hosted copies from
drifting from source.

Helper scripts (run on your machine):

- `tools\refresh-followers.bat` — pull your real follower list from Twitch into
  `prism-followers.json` (needs the `moderator:read:followers` scope).
- `tools\fetch-fonts.bat` — download the fonts into `fonts/` for fully offline overlays.

The engine also caches last-good avatar / follower count / latest follower in
`localStorage`, so brief DecAPI outages don't blank the overlay.

Versioning follows [SemVer](https://semver.org); see [CHANGELOG.md](CHANGELOG.md).

The shoutout **service** lives in stream-manager (see
[Shoutout service](#shoutout-service)); only the overlay is versioned here. Run
`node scripts/test-shoutout-overlay.mjs` after touching
`widgets/prism-shoutout.html` — it drives the card through a stubbed DOM on a
controlled clock and covers the queue rules and every way a clip can die. Pass a
path to run it against Stream Manager's copy of the card, which is the one OBS
loads; both are expected to pass.

## Maintenance service

A weekly health check + cleanup you can set and forget:

```
tools\install-maintenance-task.bat     # register the silent weekly Windows task (Sun 4 AM)
tools\prism-maintenance.bat            # run it now, in a window, to see the report
tools\uninstall-maintenance-task.bat   # remove the scheduled task
```

It verifies the venv/deps, that `prism-secrets.json` is valid and *not* tracked
by git, whether the repo is behind `origin`, the config/scene integrity test, and
DecAPI reachability — then clears stray `__pycache__` and prunes old logs. Every
run writes a timestamped report to `maintenance-logs/` (gitignored). It's
read-only apart from that housekeeping — it never pulls, pushes, or edits code.

## License

Released under the [MIT License](LICENSE) © 2026 NeoTheFox98 (CarlFox98). Fork
it, swap your identity in `prism-config.js`, and make it yours.
