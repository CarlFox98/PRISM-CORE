# PRISM Shoutout

A Twitch shoutout system for OBS. A moderator types **`!so @username`** in chat
(or someone **raids** the channel) and a PRISM card slides onto the screen with
that streamer's hex avatar, their last category, and an **autoplaying recent
clip** — then it gracefully fades out. Optionally it lowers your other OBS audio
while the clip plays and posts a shoutout line in chat.

<p align="center"><em>Two pieces: a hosted HTML overlay + a small local Python service.</em></p>

---

## How it works

| Piece | What it is | Where it runs |
|-------|------------|---------------|
| `prism-shoutout.html` | the on-screen overlay card | **hosted** (e.g. GitHub Pages) → OBS Browser Source |
| `prism_shoutout` (package) | watches chat, does Twitch lookups, drives the overlay | on your PC (Python) |

The service watches Twitch chat over IRC. On `!so @user` (from a mod/broadcaster)
or a raid, it looks the user up via the **Twitch Helix API**, resolves a recent
**clip** to a signed MP4 (via Twitch's GQL, so it autoplays without a mature
gate), and pushes a payload to the overlay over a local WebSocket
(`ws://127.0.0.1:8777`). The overlay renders the card and reports when the clip
actually starts/stops, which drives optional **OBS audio ducking**.

```
Twitch chat ──IRC──▶ chat.py ──▶ service.do_shoutout ──▶ clips.lookup ──Helix/GQL──▶ Twitch
                                        │
                                        ├──▶ overlay.broadcast ──WS──▶ prism-shoutout.html (OBS)
                                        │                                   │ clipstart/clipend
                                        │                                   ▼
                                        └──▶ chat.post_chat            obs_duck (lower/raise OBS audio)
```

See [`docs/architecture.md`](docs/architecture.md) for the module breakdown.

---

## Requirements

- Python 3.9+
- A Twitch application (Client ID + Secret) — the same credentials your SYSFOX
  app uses are fine
- OBS with a Browser Source (and, for ducking, obs-websocket v5 enabled)

```bash
pip install -r requirements.txt
```

---

## Setup

### 1. Configure secrets

Copy the example and fill in your values:

```bash
cp prism-secrets.example.json prism-secrets.json
```

```json
{
  "CHANNEL": "YourTwitchLogin",
  "CLIENT_ID": "your_twitch_app_client_id",
  "CLIENT_SECRET": "your_twitch_app_client_secret",
  "OBS_WS_PASSWORD": "your_obs_websocket_password",
  "BOT_USERNAME": "",
  "BOT_OAUTH": ""
}
```

`prism-secrets.json` is git-ignored and **never committed**. You can also supply
any of these as environment variables of the same name (env vars win over the
file). Full list in [`docs/configuration.md`](docs/configuration.md).

### 2. Host the overlay

The overlay must be **hosted** (not opened as a local file) so the Twitch clip
can autoplay — the embed requires a real domain as its "parent". Add
`prism-shoutout.html` to any static host (e.g. your GitHub Pages repo):

```
git add prism-shoutout.html
git commit -m "PRISM shoutout overlay"
git push
```

Example live URL: `https://<you>.github.io/streaming/prism-shoutout.html`

### 3. Add it to OBS

Add a **Browser Source** → the hosted URL, **1920×1080**, placed above your
scene. It's transparent and idle until a shout fires, and auto-connects to the
service on `ws://127.0.0.1:8777`.

> To preview the card design any time, open the overlay with `?demo` on the URL.

The overlay is self-contained apart from `../fonts/prism-fonts.css`, which
`scripts/deploy-pages.py` rewrites and ships alongside the hosted copy — nothing
is fetched from Google at load time.

### 4. Run the service

From this folder:

```bash
python -m prism_shoutout
```

or double-click **`run.bat`**. You'll see `[chat] listening…` and, once OBS
loads the overlay, `[overlay] connected`. Have a mod (or you) type
`!so @someone` and the card appears. Keep the window open while you stream.

---

## Options at a glance

- **Mods only** by default (`MODS_ONLY`). The broadcaster is always allowed.
- **`!so` accepts** `@name`, `name`, or a pasted `twitch.tv/name` link, and
  answers to `COMMAND_ALIASES` (`!shoutout`) as well.
- **Raids** auto-shout the raider (`RAID_SHOUTOUT`), gated by `BLOCKLIST`,
  `RAID_ALLOWLIST` and — if you turn it on — `RAID_REQUIRE_APPROVAL`, which
  holds the card until a mod types `!so ok`.
- **Mod controls:** `!so skip`, `!so clear`, `!so off` / `!so on`, `!so ok`,
  `!so status`. A bare word is a control; `!so @skip` still shouts out a
  streamer called *skip*.
- **Card states:** a plain shoutout is teal, a streamer who is **live right
  now** is magenta, and a **raid** is gold with the viewer count in the eyebrow
  ("Raid · 42 viewers") and a warmer glow on the hex.
- **Chat posting** is on by default but only fires if `BOT_USERNAME` + `BOT_OAUTH`
  are set; otherwise the card shows silently.
- **Clip choice:** random among the **newest `CLIP_RECENT_POOL`** clips within
  `CLIP_RECENT_DAYS` (7); if there are none that recent, a **random pick among
  the most popular** clips within `CLIP_POPULAR_DAYS` (30). Both avoid the last
  `CLIP_HISTORY` shown so repeats rotate, then fall back to a "no clip" card.
- **Clip volume:** clips play up to `CLIP_VOLUME` (0.85) and fade in over
  `CLIP_FADE_IN_MS`, so they arrive together with the duck instead of on top of it.
- **Audio ducking:** lowers every OBS audio source except those in
  `DUCK_EXCLUDE` while a clip plays, then fades them back. `DUCK_LEVELS` sets
  per-source amounts — keep your mic up, drop the game hard. Requires
  obs-websocket and `OBS_WS_PASSWORD`.

Every setting lives in [`prism_shoutout/config.py`](prism_shoutout/config.py) and
is documented in [`docs/configuration.md`](docs/configuration.md).

---

## Project layout

```
prism-shoutout/
├── prism_shoutout/          # the package
│   ├── __init__.py
│   ├── __main__.py          # python -m prism_shoutout
│   ├── config.py            # settings + secret loading
│   ├── twitch_api.py        # Helix auth/requests + GQL clip -> mp4
│   ├── clips.py             # clip selection + overlay payload
│   ├── obs_duck.py          # OBS audio ducking
│   ├── overlay.py           # overlay WebSocket server
│   ├── chat.py              # Twitch IRC reader + posting
│   ├── console.py           # PRISM-themed console output (banner + colored logs)
│   └── service.py           # do_shoutout() + run()
├── prism-shoutout.html      # the overlay (host this)
├── windows-terminal/        # optional PRISM Terminal profile fragment
├── prism-secrets.example.json
├── requirements.txt
├── run.bat
├── LICENSE
├── README.md
└── docs/
    ├── architecture.md
    ├── configuration.md
    ├── terminal-theme.md
    └── troubleshooting.md
```

The service prints a PRISM‑themed banner and color‑coded logs. Preview the theme
with `python -m prism_shoutout.console`, and see
[`docs/terminal-theme.md`](docs/terminal-theme.md) for the optional Windows
Terminal profile (acrylic transparency, JetBrains Mono, iridescent scheme).

> **Note for this install:** the code also ships with a one-line launcher,
> `prism_shoutout_service.py`, in the parent `prismenv` folder so the original
> `Start-PRISM-Shoutout.bat` keeps working without changes. It just imports and
> runs this package.

---

## Troubleshooting

Common issues (overlay not connecting, clips not playing, ducking not working,
the "same clip every time" bug) are covered in
[`docs/troubleshooting.md`](docs/troubleshooting.md).

---

## License

[MIT](LICENSE) © 2026 NeoTheFox
