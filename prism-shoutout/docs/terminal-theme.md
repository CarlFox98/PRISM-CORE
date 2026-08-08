# Console look & feel

The service styles its own output — a PRISM banner, a config panel, and
color‑coded, timestamped log tags — using the exact palette from
`prism-theme.css` (cyan `#57F2E4`, blue `#6C8BFF`, purple `#B983FF`, pink
`#FF7ACB`, gold `#FFD86B` on near‑black `#0B0E18`).

## Preview it without starting the service

```
python -m prism_shoutout.console
```

That prints a sample banner and log lines so you can see the theme.

## Colors just work

The launchers set `chcp 65001` (UTF‑8, so the `◇`, box‑drawing, and arrow glyphs
render) and `PRISM_FORCE_COLOR=1`. On Windows 10/11 the console understands the
24‑bit ANSI the service emits, so you get full color with no extra setup. Set
`NO_COLOR=1` to disable color (e.g. when logging to a file).

## Optional: the "PRISM Shoutout" Windows Terminal profile

For the full treatment — iridescent scheme, acrylic transparency, JetBrains Mono,
padding — install the fragment in `windows-terminal/prism.fragment.json`. It adds
a **PRISM** color scheme and a **PRISM Shoutout** profile that launches the
service directly.

**Install (drop‑in, recommended):**

1. Open this folder in File Explorer:
   `%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\PRISM\`
   (create the `Fragments\PRISM` folders if they don't exist).
2. Copy `prism.fragment.json` into it.
3. Restart Windows Terminal. Open the new tab dropdown (the `˅` next to `+`) and
   pick **PRISM Shoutout** — it launches the service in the themed profile.

**Notes**

- The profile uses `Cascadia Mono` (ships with Windows Terminal, no install
  needed). Prefer the overlay's exact font? Install JetBrains Mono and set
  `"face": "JetBrains Mono"` in the fragment.
- Tweak `opacity` (0–100) and `useAcrylic` for more/less transparency, or
  `padding` for breathing room.
- The commandline points at your absolute `Start-PRISM-Shoutout.bat`. If you move
  the project, update that path in the fragment.
- This profile is optional — `Start-PRISM-Shoutout.bat` already gives you the
  full colored output in whatever console opens it.
