# PRISM

[![PRISM CI](https://github.com/CarlFox98/PRISM-CORE/actions/workflows/ci.yml/badge.svg)](https://github.com/CarlFox98/PRISM-CORE/actions/workflows/ci.yml)

The overlay system for the Twitch channel
[**NeoTheFox98**](https://twitch.tv/NeoTheFox98): full-screen scenes, an in-game
layout, chat styling and widgets, all rendered at **1920×1080**, fed by live
Twitch data, and ready to drop into OBS as Browser Sources.

PRISM 2.0 ships **three switchable scene sets**. Pick one from the Stream
Manager dashboard (Overview → Overlay Scene Set):

| Set | Look | Source |
|-----|------|--------|
| **PRISM Signal** (`prism-signal`) | Sci-fi HUD: grid, scanlines, notched panels, terminal readouts. Cyan + magenta. | `themes/signal/` |
| **PRISM Soft Holo** (`prism-soft`) | Pastel iridescence, sticker cards, paw marks. Sora + Nunito. | `themes/soft/` |
| **PRISM Holo** (`prism-holo`) | The 1.x holo-glass look, unchanged. | `scenes/` |

## Repository layout

```
core/      prism-config.js, prism-engine.js, shared scene modules, holo css
themes/    2.0 sets: signal/ and soft/ (scenes + theme css + chat css)
scenes/    the 1.x holo scenes             panels/   standalone Twitch info panels
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

## OBS scene sets

Each PRISM set is a folder next to Stream Manager's `modern/` and `retro/`.
Build them with:

```
python scripts/build-obs-set.py                     # all three
python scripts/build-obs-set.py --set prism-signal  # just one
```

Then pick a set in the Stream Manager dashboard. It copies that folder into
`overlays/active/`, which OBS serves as `http://localhost:5000/overlays/active/<scene>.html`.
Your OBS sources never change; after switching, refresh the browser sources.

For the dashboard to offer a set, its name must be in stream-manager's
`config.json` → `"scene_sets"` (restart Stream Manager after editing it):

```json
"scene_sets": ["modern", "retro", "prism-holo", "prism-signal", "prism-soft"]
```

Every set provides the same scene names: `starting-soon`, `be-right-back`,
`stream-ending`, `tech-difficulties`, `webcam-frame`, `wallpaper`,
`chat-preview`, `thank-you`. The 2.0 sets add **`gameplay`**, which the other
sets don't have, so a `gameplay.html` source shows nothing while `modern`,
`retro` or `prism-holo` is active.

No set folder is named plain `prism`: Windows paths are case-insensitive, so
`overlays/prism` would collide with the `overlays/PRISM` source repo.

### Scenes in the 2.0 sets

| Scene | What it shows | Options |
|-------|---------------|---------|
| `starting-soon` | Countdown, today's category (from Twitch), socials, follower goal | `?timer=10`, or the ⚙ button (OBS: Interact) |
| `be-right-back` | Paused state, current category, latest follower | |
| `stream-ending` | Follower total, newest follower, socials | |
| `tech-difficulties` | Status tiles (OBS link, desktop audio), stream status. Shows "We're back" and switches OBS to *Starting Soon* once the channel is live again | `window.PRISM_TECHCHECK` in the page to change port/password/scene |
| `webcam-frame` | Frame that follows the browser source's size (size the source to the camera) | `?demo` |
| `wallpaper` | Idle background: Stream Manager wins and quotes, reacts to events | |
| `gameplay` | Frame layer over the game: webcam window (560×315 at 40,725), latest follower, goal, slots for now-playing + shoutout | `?demo` shows the slots |
| `thank-you` | Thank-a-follower card | Space / `?auto` / `?hidebar` / `?demo` |
| `chat-preview` | Preview of the set's chat CSS | |

The chat itself is styled by pasting `prism-chat-signal.css` or
`prism-chat-soft.css` (in the set folder) into SoundAlerts or the chat
source's Custom CSS. Switching sets doesn't change pasted CSS.

The shoutout card and the now-playing widget are separate sources (Stream
Manager and GitHub Pages), but they still follow the set: each set ships
`shoutout-theme.css` and `nowplaying-theme.css`, which both widgets load from
`/overlays/active/` and re-read every minute. The holo set's copies are empty,
so the widgets show their built-in look there. After changing the now-playing
widget, run `tools\deploy-to-pages.bat` and push the `streaming` repo.

## Design system

Identity and live data are shared by every set; each set's look lives in its
own theme css (`themes/signal/signal.css`, `themes/soft/soft.css`, or
`core/prism-theme.css` for holo). The 2.0 sets follow two rules: nothing on
stream below 22px (labels) or 24px (content), and one thing moves continuously
per scene.

| File | Role |
|------|------|
| `prism-config.js` | **Single source of truth** — channel name, socials, follower goal (`goal` + `goalStep`), Spotify client id, avatar fallback. Change identity here and every scene in every set follows. |
| `prism-theme.css` | Shared look for the full-screen scenes (palette `--c1`…`--c5`, backdrop, motes, holo components). |
| `prism-engine.js` | Particle motes + live Twitch data via DecAPI (no secrets), and renders socials from config. Degrades gracefully offline; respects `prefers-reduced-motion`. |
| `prism-panels.css` | Shared look for the standalone Twitch info panels. |

Live-data hooks: add `class="js-avatar"`, `js-followcount`, `js-goal-fill`,
`js-goal-now`, `js-goal-target`, `js-goal-left`, `js-goal-segments`,
`js-latest`, `js-game`, `js-title` or `js-name` to any element and the engine
fills it. Socials render into any `<div class="socials" data-prism-socials></div>`
(`data-prism-socials="named"` adds each network's name).

**Goal stepping:** with `goalStep: 25`, once the follower goal is reached the
next multiple of 25 is shown, so the bar never sits pinned at 100%.

Shared scene modules in `core/` (used by the 2.0 sets): `prism-countdown.js`,
`prism-techcheck.js`, `prism-thankyou.js`, `prism-wallpaper.js`,
`prism-chat-demo.js`. Each documents its markup hooks at the top.

## Holo scenes (1.x) — `scenes/` (load `../core/prism-theme.css` + `prism-config.js` + `prism-engine.js`)

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

2.0 sets: edit the `:root` tokens at the top of `themes/signal/signal.css` or
`themes/soft/soft.css`, then rebuild the sets. Holo: edit the palette variables
`--c1`…`--c5` at the top of `prism-theme.css` and `prism-panels.css`. Edit `prism-config.js` to
change identity (channel, socials, goal).

## Development

Clone, then enable the guards once:

```
git config core.hooksPath .githooks     # blocks secrets from being committed
```

Checks (also run in CI on every push via `.github/workflows/ci.yml`):

```
node scripts/test-socials.mjs      # config, scene load order, and every 2.0 set's files
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

It checks Python, that no secret file is tracked by git, whether the repo is
behind `origin`, the config/scene integrity test, the 32 shoutout overlay
checks, that VERSION matches the changelog, the local fonts, whether the hosted
overlays and every built scene set match their source, the launchers, and
DecAPI reachability. Then it clears stray `__pycache__` and prunes old logs. Every
run writes a timestamped report to `maintenance-logs/` (gitignored). It's
read-only apart from that housekeeping — it never pulls, pushes, or edits code.

## License

Released under the [MIT License](LICENSE) © 2026 NeoTheFox98 (CarlFox98). Fork
it, swap your identity in `prism-config.js`, and make it yours.
