# Changelog

All notable changes to PRISM. Loosely follows [Keep a Changelog](https://keepachangelog.com)
and [Semantic Versioning](https://semver.org).

## [1.7.0] — 2026-08-31

Shoutout hardening pass — worked from the Aug 2026 audit of the feature.

### Added
- **Shoutout safety gates.** A raid used to reach the screen with nothing in
  front of it: no blocklist, no threshold, no human. There are now three gates
  in `config.py` — `BLOCKLIST` (never shouted, by command or raid),
  `RAID_ALLOWLIST` (if set, only these are auto-shouted on raid) and
  `RAID_REQUIRE_APPROVAL`, which parks the raid and waits for a mod to type
  `!so ok` (lapsing after `RAID_APPROVAL_TTL`).
- **Mod controls.** `!so skip` retires the card on screen, `!so clear` also
  drops the queue behind it, `!so off` / `!so on` stop and resume shoutouts
  (raids included), `!so ok` approves a pending raid and `!so status` prints
  the state. `skip` and `clear` are pushed to the overlay over the existing
  WebSocket, so they land mid-clip — killing the service is no longer the only
  way out of a bad card. A bare word is a control; `!so @skip` still shouts out
  a streamer called *skip*.

- **A repeat guard that outlives the card.** The same login is now refused
  while its card is queued or on screen, plus `REPEAT_GUARD_SEC` (30s) after it
  leaves, and the overlay refuses new work once it is `MAX_QUEUE_SEC` backed up.
  The overlay independently drops a login it is already showing or holding, and
  caps the queue at five.
- **Clip volume is configurable.** `CLIP_VOLUME` (0.85) and `CLIP_FADE_IN_MS`
  ride along in the card payload; the overlay ramps the clip up to that ceiling
  instead of snapping to 1.0 at a fixed 250ms. With the fade matched to
  `DUCK_FADE_MS` the clip now arrives together with the duck rather than on top
  of it — that overlap used to be the loudest moment of the card.
- **Per-source duck levels.** `DUCK_LEVELS` sets how much each OBS input keeps
  while a clip plays, falling back to `DUCK_KEEP`. One flat level dropped your
  mic along with the game, which is backwards — you talk over the clip.
- **Raids look like raids.** The payload carries `raid` and `raiders`, and the
  card has a third state next to `.live`: gold eyebrow reading "Raid · 42
  viewers", gold pulse, warmer glow on the hex. The viewer count used to be
  printed to the console and thrown away. Raids also get their own chat line
  (`CHAT_TEMPLATE_RAID`, with a `{viewers}` placeholder).
- **`RAID_MIN_VIEWERS`** (2) ignores drive-by raids, which previously earned the
  same full-length card and audio duck as a five-hundred-viewer one.
- **Card polish.** A time-remaining rail along the card's bottom edge, drawn in
  the PRISM spectrum; a staggered reveal so the card assembles (hex, clip, then
  the text) instead of arriving as one block; and a `prefers-reduced-motion`
  block for anyone opening the overlay outside OBS.
- **The no-clip card uses the streamer's offline banner.** `offline_image_url`
  was already in the `/users` response and was being discarded; inactive
  streamers got a grey play icon on exactly the shoutouts that needed the most
  help. The label now sits as a caption so the art reads.
- **A shoutout log.** `SHOUTOUT_LOG` records one JSONL line per shoutout, and
  the service reads it back at startup to restore clip rotation — previously
  nothing was persisted, so a restart forgot what it had shown and could replay
  the same clip. Best-effort: a log that can't be written never costs a shoutout.
- `COMMAND_ALIASES` (`!shoutout`), and `!so` now accepts a pasted
  `twitch.tv/name` link as well as `@name` — mods paste links.
- `ALLOW_SELF_SHOUTOUT` (off): `!so @yourself` no longer plays your own clip to
  your own chat.
- The console warns when more than one overlay is connected, since every one of
  them plays the clip and the audio doubles up.
- **Tests.** `tests/test_shoutout.py` (59 cases) covers the safety gates, the
  repeat guard and the clip-selection logic where the "same clip every time"
  bug lived; `scripts/test-shoutout-overlay.mjs` drives the overlay's queue in a
  stubbed DOM via a new inert `window.PRISM_SHOUTOUT` test hook.

### Changed
- **One held obs-websocket connection instead of two handshakes per shoutout.**
  `_duck_down` and `_duck_up` each opened, authenticated and closed their own
  socket, putting a round-trip in the path of something that has to feel
  instant. The connection is now held and reopened only when a request fails —
  deliberately without inspecting socket state, which moved between
  `websockets` releases.
- **The duck no longer re-discovers your OBS inputs on every clip.** It probed
  `GetInputList` plus a `GetInputVolume` per input, then read every volume
  again — roughly 2N sequential round-trips before the fade could start. The
  list is cached for `DUCK_TARGET_TTL` (60s) and dropped on reconnect.
- CI now byte-compiles `prism-shoutout/prism_shoutout/*.py` and runs both test
  suites. It previously compiled only the launcher shim and `scripts/`, so a
  syntax error in the ten modules that are the actual service passed CI.

### Fixed
- **A failed *restore* no longer leaves your mix down either.** The first pass
  fixed the failed duck-*down* path and left the mirror image: `_duck_up`
  cleared the saved levels in a `finally`, so a restore that failed erased the
  very levels it needed, and the watchdog had already been cancelled. Levels are
  now cleared on success only, the watchdog is cancelled only once they are
  actually back, and it retries.
- **The OBS socket is only ever used under `_duck_lock`.** `emergency_restore`
  ran unlocked, and `server.close()` only *schedules* the overlay shutdown — so
  at exit it could race a handler still releasing its duck on the same held
  connection, tearing the socket down mid-fade. The service now awaits
  `server.wait_closed()` first.
- **`OBS_REQ_TIMEOUT` on every OBS request.** Holding the connection open made a
  half-open socket a realistic state, where a bare `recv` hangs forever holding
  the lock — stranding the watchdog that exists to un-duck your audio.
- **The overlay no longer cuts the following card short.** A clip that errored
  during the 700ms exit window armed a hold timer that outlived its own card and
  fired partway through the next one, retiring it early and pulling an extra
  card off the queue. Covered by a regression test.
- **Screen time is no longer booked for a card nothing received.** With OBS
  closed, `broadcast` still returned and the service reserved the card's
  duration, so after a few `!so` it began refusing shoutouts because of a queue
  that did not exist. `broadcast` now reports how many overlays took the card.
- **The mid-lookup guard covers the lookup.** It was 3 seconds against a lookup
  of up to five Twitch calls, so a slow Twitch let a second trigger through and
  posted the chat line twice.
- `!so clear` releases only the guards from booked cards, not shoutouts still
  mid-lookup; a malformed payload can no longer strand the overlay with
  `busy` stuck true; repeated `!so skip` no longer postpones the exit.
- **A failed duck no longer leaves your mix down.** `_duck_down()` saves the
  original levels *before* it fades, so if the OBS socket dropped mid-fade the
  handler zeroed `active` and returned, leaving sources lowered with nothing
  scheduled to raise them — audible for the rest of the stream. It now restores
  on that path, and arms the watchdog to retry if the restore fails too.
- **A clip that fails mid-play no longer holds a dead frame.** The service sizes
  the card from the clip's duration before anyone knows the MP4 plays, so a
  signed URL that 404'd two seconds in left a still thumbnail on screen for up
  to 41 seconds. The overlay now caps what is left at `NOCLIP_HOLD_MS`.
- **A missing avatar no longer paints a broken image inside the hex.** `ava.src`
  was set to `''`, which resolves against the page URL; the hex now falls back
  to the first letter of the name, and the same fallback covers an avatar URL
  that fails to load.
- **Long display names no longer wrap mid-word.** The identity column was 330px
  in a 1080px card — roughly 55px of the available width was going unused while
  a 13-character name wrapped and shoved the rest of the column around. The
  column is now 376px and the name is measured and fitted to it.
- **The overlay no longer loads fonts from Google.** v1.5.0 vendored the fonts
  so overlays need no network; the shoutout card missed that pass and still
  blocked on a Google request as OBS loaded the source — the one moment where a
  slow response shows a flash of fallback type on stream. It now imports
  `../fonts/prism-fonts.css`, and `scripts/deploy-pages.py` copies `fonts/` into
  the hosted folder (it rewrote the path but never shipped the files).
  *The thank-you, webcam-frame and now-playing overlays still need this pass.*
- `prism_shoutout.__version__` read `1.0.0` while the repo was at 1.6.1; it now
  reads the `VERSION` file so it can't drift again.
- `service._until` and `clips._last_clips` are bounded — both grew for the life
  of the process. `_until` has a hard cap as well as expiry (a raid train holds
  hundreds of live guards), and clip memory evicts least-recently-used rather
  than first-seen, which had it forgetting your regulars first.
- `do_shoutout` is wrapped end to end. `overlay.broadcast` and `chat.post_chat`
  sat outside the try, so a failure in either killed the task silently with an
  unretrieved-exception warning and no console line.

## [1.6.1] — 2026-08-28

### Fixed
- `tools/deploy-to-pages.sh` still used the pre-restructure flat copy logic; it
  now calls `scripts/deploy-pages.py` like the .bat does.
- `scripts/refresh-followers.py` wrote to the repo root instead of
  `data/prism-followers.json`.
- Docs (`README`, shoutout and now-playing guides) updated for the new layout.
- Dropped a stale `.gitignore` entry for a deleted one-time script.

### Added
- Maintenance checks: **Launchers** (every path a `tools/*.bat` points at must
  exist — catches a future move breaking them) and **OBS scene set** (flags a
  `prism-holo` build that has drifted from source).
- CI now byte-compiles everything in `scripts/`, not just the service shim.

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
