# Troubleshooting

Startup prints useful lines: `[ws] overlay server on …`, `[cfg] secrets loaded
from …`, `[chat] listening in #… `, and `[overlay] connected` once OBS loads the
source. Use those to see how far it got.

## The overlay card never appears

- **Is the service running?** You need the Python service **and** OBS open at the
  same time. Look for `[overlay] connected` in the console — if you never see it,
  OBS hasn't loaded the source or can't reach `ws://127.0.0.1:8777`.
- **Is the overlay hosted?** Opening `prism-shoutout.html` as a local `file://`
  breaks Twitch clip autoplay. Host it (GitHub Pages, etc.) and point the OBS
  Browser Source at the hosted URL.
- **Right channel?** `CHANNEL` must be your Twitch login. The reader logs
  `listening in #<channel>`.
- **Permission?** With `MODS_ONLY = True`, only mods/broadcaster trigger `!so`.
  Test from your own (broadcaster) account or a mod account.
- Preview the card independent of Twitch by opening the overlay with `?demo`.

## The same clip plays every time / it never rotates

This was a real bug that is now fixed: the clip query passed only `started_at`,
and Twitch interprets that as a **1-week** window from that date, so the pool
often collapsed to a single old clip. The code now passes both `started_at` and
`ended_at` and remembers the last few clips per streamer (`CLIP_HISTORY`).

Selection is two-tier: random among the newest `CLIP_RECENT_POOL` clips within
`CLIP_RECENT_DAYS` (7), then a random pick among the most popular within
`CLIP_POPULAR_DAYS` (30). If you still see repeats:

- The streamer may genuinely have only one clip in the last 7 days, so the
  primary tier keeps returning it until a newer clip exists. Widen
  `CLIP_RECENT_DAYS`, raise `CLIP_RECENT_POOL`, or lean on the popularity
  fallback.
- Inactive streamers (no clips in the last 30 days) intentionally show the
  "no clip" card — widen `CLIP_POPULAR_DAYS` if you want to reach older clips.
- For the fallback tier, increase `CLIP_TOP_N` (bigger random pool) or
  `CLIP_HISTORY` (avoid more recent repeats).

## Clips don't play (card shows the avatar but no video)

- The console prints `[clip] no playable video …` when Twitch's GQL returns no
  signed MP4. Some clips (very new, deleted, or region-locked) can't be resolved;
  the overlay falls back to a thumbnail or a "no clip" card.
- Confirm the overlay is hosted on a real domain (autoplay requirement).

## "Twitch rejected the app credentials"

- `CLIENT_ID` / `CLIENT_SECRET` are wrong or mismatched. Use the **same** pair
  from your Twitch application (the ones SYSFOX uses). Regenerating the secret in
  the Twitch dev console invalidates the old one everywhere.
- Remember env vars override `prism-secrets.json` — a stale env var can shadow a
  correct file value.

## Audio ducking doesn't work

- Enable **OBS → Tools → WebSocket Server Settings**, set a password, and put it
  in `OBS_WS_PASSWORD`.
- The console prints `[duck] couldn't lower OBS audio …` if it can't connect —
  usually a wrong password or the server being off.
- Put your shoutout Browser Source's exact name in `DUCK_EXCLUDE` so the clip's
  own audio isn't lowered.
- If audio ever seems stuck low, `MAX_DUCK_SEC` force-restores it, and the
  service also restores levels on exit (Ctrl+C / closing the window).

## Chat line isn't posted

- Posting requires **both** `BOT_USERNAME` and `BOT_OAUTH` (an `oauth:…` token
  for that account). Without them the card still shows; it just stays silent.

## Port already in use

- Another instance may still be running on `8777`. Close old console windows, or
  change `WS_PORT` (and the overlay's WebSocket URL) if something else needs the
  port.

## Where are my secrets loaded from?

On startup the service prints `[cfg] secrets loaded from <path>`. If that's not
the file you expected, check the search order in
[`configuration.md`](configuration.md) — an env var or a `prism-secrets.json` in
the current working directory can take precedence.
