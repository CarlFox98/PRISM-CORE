"""
Console styling — makes the service window match the PRISM overlay.

Truecolor (24-bit) ANSI output using the exact palette from prism-theme.css,
with a startup banner + config panel and colored, timestamped log tags. Falls
back to plain text automatically when output isn't a terminal or NO_COLOR is set.

Usage:
    from . import console
    console.enable()
    console.banner(channel, ws_url, command, ducking)
    console.log("chat", "listening ...")
    console.shout("PixelPal", has_clip=True, live=False, game="Valorant")

Preview it standalone:  python -m prism_shoutout.console
"""

import os
import sys
import datetime

# --- PRISM palette (from prism-theme.css) -------------------------------
INK  = (234, 240, 255)   # --ink
SOFT = (169, 180, 214)   # --ink-soft
C1   = (87, 242, 228)    # --c1 teal
C2   = (108, 139, 255)   # --c2 blue
C3   = (185, 131, 255)   # --c3 purple
C4   = (255, 122, 203)   # --c4 pink
C5   = (255, 216, 107)   # --c5 gold
DIM  = (95, 94, 90)      # timestamps / rules
ERR  = (240, 120, 120)   # errors

_LETTER_RAMP = [C3, C2, C1, C4, C5]

# tag -> (color, glyph)  glyph "" means render as [tag]
_TAGS = {
    "ws":      (C2, ""),
    "cfg":     (SOFT, ""),
    "overlay": (C3, ""),
    "chat":    (C4, ""),
    "raid":    (C5, ""),
    "shout":   (C3, "◇"),
    "clip":    (C1, ""),
    "duck":    (C5, ""),
    "lookup":  (ERR, ""),
    "log":     (SOFT, ""),
}

_W = 42                 # inner width of the config box
_USE_COLOR = True
RESET = "\033[0m"
BOLD = "\033[1m"


def enable():
    """Turn on ANSI on Windows consoles and decide whether to use color."""
    global _USE_COLOR
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            # ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
        except Exception:
            pass
    if os.getenv("PRISM_FORCE_COLOR"):
        _USE_COLOR = True
    elif os.getenv("NO_COLOR") or not sys.stdout.isatty():
        _USE_COLOR = False


def paint(text, rgb, bold=False):
    if not _USE_COLOR:
        return text
    return "%s\033[38;2;%d;%d;%dm%s%s" % (BOLD if bold else "", rgb[0], rgb[1], rgb[2], text, RESET)


# --- status glyphs -------------------------------------------------------
def yes():  return paint("✓", C1)
def no():   return paint("✗", ERR)
def dot():  return paint("●", C1)
def down(): return paint("▼", C5)
def up():   return paint("▲", C1)


def _ts():
    return paint(datetime.datetime.now().strftime("%H:%M:%S"), DIM)


def _label(tag):
    color, glyph = _TAGS.get(tag, (SOFT, ""))
    raw = ("%s %s" % (glyph, tag)) if glyph else ("[%s]" % tag)
    return paint(raw.ljust(9), color, bold=(tag == "shout"))


def log(tag, msg=""):
    print("%s %s %s" % (_ts(), _label(tag), msg))


def warn(tag, msg):
    log(tag, paint(msg, C5))


def error(tag, msg):
    log(tag, paint(msg, ERR))


def shout(name, has_clip, live, game=""):
    parts = [paint(name, INK, bold=True),
             "clip " + (yes() if has_clip else no()),
             "live " + (dot() if live else no())]
    if game:
        parts.append(paint(game, SOFT))
    print("%s %s %s" % (_ts(), _label("shout"), "   ".join(parts)))


# --- startup banner ------------------------------------------------------
def _wordmark(word):
    return " ".join(paint(ch, _LETTER_RAMP[i % len(_LETTER_RAMP)], bold=True)
                     for i, ch in enumerate(word))


def _box_row(key, value, vrgb):
    plain = "  %s %s" % (key.ljust(9), value)
    pad = max(0, _W - len(plain))
    inner = "  %s %s%s" % (paint(key.ljust(9), SOFT), paint(value, vrgb), " " * pad)
    bar = paint("│", C1)
    return bar + inner + bar


def banner(channel, ws_url, command, ducking):
    top = paint("╭" + "─ PRISM Shoutout ".ljust(_W, "─") + "╮", C1)
    bottom = paint("╰" + "─" * _W + "╯", C1)
    print()
    print("    " + paint("◆ ◇ ◆", C3))
    print("  " + _wordmark("PRISM") + "   " + _wordmark("SHOUTOUT"))
    print("  " + paint("─" * (_W + 2), DIM))
    print("  " + top)
    print("  " + _box_row("channel", "#" + channel, C3))
    print("  " + _box_row("overlay", ws_url, C2))
    print("  " + _box_row("command", command, C5))
    print("  " + _box_row("ducking", "on" if ducking else "off", C1 if ducking else ERR))
    print("  " + bottom)
    print()


def _demo():
    os.environ["PRISM_FORCE_COLOR"] = "1"
    enable()
    banner("neothefox98", "ws://127.0.0.1:8777", "!so", True)
    log("ws", "overlay server ready")
    log("cfg", "secrets loaded " + yes())
    log("overlay", "connected " + paint("(1)", DIM))
    log("chat", "listening for " + paint("!so @user", C5))
    log("raid", "pixelpal raided with 42 " + paint("viewers", DIM))
    shout("PixelPal", True, False, "Valorant")
    log("clip", "playing 18.4s " + yes())
    log("duck", "lowering 4 sources " + down())
    log("duck", "restored " + up())
    shout("MidnightMocha", True, True, "Just Chatting")


if __name__ == "__main__":
    _demo()
