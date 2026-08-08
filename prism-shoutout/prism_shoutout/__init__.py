"""
PRISM Shoutout
==============
A Twitch shoutout system: a moderator (or a raid) triggers `!so @user`, the
service looks the user up on Twitch, resolves a recent clip, and drives the
PRISM overlay (prism-shoutout.html) over a local WebSocket — sliding in a card
with the user's hex avatar and an autoplaying clip, optionally ducking your
other OBS audio and posting a line in chat.

The logic is split into focused modules:

    config      - settings + secret loading
    twitch_api  - Twitch Helix auth/requests + GQL clip -> signed mp4
    clips       - clip selection (dedupe) + building the overlay payload
    obs_duck    - lowering/restoring OBS audio while a clip plays
    overlay     - the local WebSocket server the overlay connects to
    chat        - Twitch IRC reader (commands + raids) and chat posting
    service     - ties it together: do_shoutout() and run()

Run it with:  python -m prism_shoutout
"""

__version__ = "1.0.0"

from .service import run  # noqa: E402  (convenience re-export)

__all__ = ["run", "__version__"]
