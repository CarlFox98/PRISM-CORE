# PRISM fonts

Both `prism-theme.css` and `prism-panels.css` import **`prism-fonts.css`** from
this folder, so fonts are configured in one place.

- **Out of the box:** `prism-fonts.css` just imports the fonts from Google —
  identical to before, works online.
- **Go offline:** run `fetch-fonts.bat` (or `python scripts/fetch-fonts.py`) on
  your machine. It downloads the `.woff2` files into this folder and rewrites
  `prism-fonts.css` to use them locally. Commit the `.woff2` files + the updated
  `prism-fonts.css` and the overlays no longer need any network for fonts.

Fonts used: **Space Grotesk** (400/500/600/700) and **JetBrains Mono**
(500/600/700), served by Google Fonts under the Open Font License.
