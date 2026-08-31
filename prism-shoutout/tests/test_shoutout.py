# -*- coding: utf-8 -*-
"""
Unit tests for the PRISM shoutout service.

Everything here is offline: Twitch lookups, the overlay WebSocket and chat
posting are all replaced with recorders, so the tests exercise the decision
logic and nothing else.

    python -m unittest discover -s tests -v      (from prism-shoutout/)
"""

import os
import sys
import json
import time
import asyncio
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from prism_shoutout import chat, clips, config, history, obs_duck, overlay, service  # noqa: E402

_stdout = None


def setUpModule():
    """Mute the service's console banner/logs — unittest reports on stderr."""
    global _stdout
    _stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")


def tearDownModule():
    sys.stdout.close()
    sys.stdout = _stdout


def _payload(login):
    return {"name": login.title(), "login": login, "avatar": "", "category": "Test",
            "live": False, "clip": "", "thumb": "", "clipId": "", "hold": 8000}


class ServiceTestCase(unittest.IsolatedAsyncioTestCase):
    """Base: stub the outside world and reset all module state per test."""

    def setUp(self):
        self.sent, self.controls, self.chats = [], [], []
        self.hold_ms = 8000

        # broadcast returns how many overlays received the card; the service
        # books screen time only when something is actually showing it
        self.overlays = 1

        async def broadcast(p):
            self.sent.append(p)
            return self.overlays

        async def control(a):
            self.controls.append(a)

        async def post(t):
            self.chats.append(t)

        def lookup(login):
            d = _payload(login)
            d["hold"] = self.hold_ms
            return d

        self._orig = (overlay.broadcast, overlay.control, chat.post_chat, service.lookup)
        overlay.broadcast, overlay.control, chat.post_chat, service.lookup = (
            broadcast, control, post, lookup)

        self._cfg = {k: getattr(config, k) for k in (
            "BLOCKLIST", "RAID_ALLOWLIST", "RAID_REQUIRE_APPROVAL",
            "RAID_MIN_VIEWERS", "COOLDOWN_SEC", "REPEAT_GUARD_SEC", "MAX_QUEUE_SEC",
            "SHOUTOUT_LOG", "ALLOW_SELF_SHOUTOUT", "COMMAND_ALIASES")}
        self.tmp = tempfile.mkdtemp(prefix="prism-test-")
        config.SHOUTOUT_LOG = os.path.join(self.tmp, "shoutout-log.jsonl")
        config.BLOCKLIST = []
        config.RAID_ALLOWLIST = []
        config.RAID_REQUIRE_APPROVAL = False
        config.RAID_MIN_VIEWERS = 0

        service._until.clear()
        service._screen_free_at = 0.0
        service._enabled = True
        service._pending_raid = None

    def tearDown(self):
        overlay.broadcast, overlay.control, chat.post_chat, service.lookup = self._orig
        for k, v in self._cfg.items():
            setattr(config, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def logins(self):
        return [p["login"] for p in self.sent]


class TestSafetyGates(ServiceTestCase):

    async def test_normal_shoutout_broadcasts_once(self):
        await service.do_shoutout("@SomeOne")
        self.assertEqual(self.logins(), ["someone"])

    async def test_blocklist_refuses_by_command_and_by_raid(self):
        config.BLOCKLIST = ["BadActor"]
        await service.do_shoutout("@badactor")
        await service.do_shoutout("badactor", "raid", 10)
        self.assertEqual(self.sent, [])

    async def test_blocklist_does_not_affect_others(self):
        config.BLOCKLIST = ["badactor"]
        await service.do_shoutout("someone-else")
        self.assertEqual(self.logins(), ["someone-else"])

    async def test_raid_allowlist_gates_raids_only(self):
        config.RAID_ALLOWLIST = ["friend"]
        await service.do_shoutout("stranger", "raid", 5)
        self.assertEqual(self.sent, [])
        await service.do_shoutout("friend", "raid", 5)
        self.assertEqual(self.logins(), ["friend"])
        service._until.clear()
        await service.do_shoutout("stranger")          # manual is unaffected
        self.assertIn("stranger", self.logins())

    async def test_raid_approval_holds_then_releases(self):
        config.RAID_REQUIRE_APPROVAL = True
        await service.do_shoutout("raider", "raid", 42)
        self.assertEqual(self.sent, [])
        self.assertEqual(service._pending_raid["login"], "raider")
        self.assertEqual(service._pending_raid["viewers"], 42)
        await service.control("ok")
        self.assertEqual(self.logins(), ["raider"])
        self.assertIsNone(service._pending_raid)

    async def test_second_approval_is_a_no_op(self):
        config.RAID_REQUIRE_APPROVAL = True
        await service.do_shoutout("raider", "raid", 1)
        await service.control("ok")
        await service.control("ok")
        self.assertEqual(len(self.sent), 1)

    async def test_expired_approval_is_refused(self):
        config.RAID_REQUIRE_APPROVAL = True
        await service.do_shoutout("stale", "raid", 3)
        service._pending_raid["at"] -= config.RAID_APPROVAL_TTL + 1
        await service.control("ok")
        self.assertEqual(self.sent, [])

    async def test_off_stops_commands_and_raids(self):
        await service.control("off")
        await service.do_shoutout("nope")
        await service.do_shoutout("nope2", "raid", 9)
        self.assertEqual(self.sent, [])
        await service.control("on")
        await service.do_shoutout("yes")
        self.assertEqual(self.logins(), ["yes"])

    async def test_a_broadcast_failure_never_escapes(self):
        async def boom(_):
            raise RuntimeError("overlay exploded")
        overlay.broadcast = boom
        await service.do_shoutout("kaboom")            # must not raise


class TestRepeatGuard(ServiceTestCase):

    async def test_repeat_is_refused_while_the_card_is_on_screen(self):
        self.hold_ms = 40000
        await service.do_shoutout("raider", "raid", 20)
        await service.do_shoutout("@raider")           # the mod's reflex !so
        self.assertEqual(len(self.sent), 1)

    async def test_guard_outlives_the_card(self):
        self.hold_ms = 8000
        await service.do_shoutout("dup")
        self.assertGreater(service._until["dup"],
                           time.time() + 8 + config.REPEAT_GUARD_SEC - 1)

    async def test_guard_expires(self):
        await service.do_shoutout("dup")
        service._until["dup"] = time.time() - 1
        await service.do_shoutout("dup")
        self.assertEqual(len(self.sent), 2)

    async def test_queue_time_accumulates_across_cards(self):
        self.hold_ms = 20000
        await service.do_shoutout("one")
        await service.do_shoutout("two")
        self.assertGreater(service._queue_depth(time.time()), 39)

    async def test_a_backed_up_overlay_drops_new_shoutouts(self):
        service._screen_free_at = time.time() + config.MAX_QUEUE_SEC + 10
        await service.do_shoutout("late")
        self.assertEqual(self.sent, [])

    async def test_no_overlay_means_no_screen_time_is_booked(self):
        self.overlays = 0
        self.hold_ms = 40000
        await service.do_shoutout("one")
        self.assertEqual(len(self.sent), 1)                 # still looked up
        self.assertLess(service._queue_depth(time.time()), 1)

    async def test_no_overlay_still_debounces(self):
        self.overlays = 0
        await service.do_shoutout("one")
        await service.do_shoutout("one")
        self.assertEqual(len(self.sent), 1)

    async def test_the_lookup_guard_outlasts_a_slow_lookup(self):
        # a lookup is up to five Twitch calls; a 3s guard used to let a second
        # trigger through mid-lookup and post the chat line twice
        started = []

        async def slow(login):
            started.append(login)
            await asyncio.sleep(0.05)
            return _payload(login)

        def blocking(login):
            time.sleep(0.05)
            return _payload(login)

        service.lookup = blocking
        await asyncio.gather(service.do_shoutout("dup"), service.do_shoutout("dup"))
        self.assertEqual(len(self.sent), 1)

    async def test_a_failed_lookup_can_be_retried_promptly(self):
        def boom(login):
            raise RuntimeError("twitch is down")
        service.lookup = boom
        await service.do_shoutout("flaky")
        self.assertLessEqual(service._until["flaky"], time.time() + config.COOLDOWN_SEC + 1)

    async def test_an_unknown_login_can_be_retried_promptly(self):
        service.lookup = lambda login: None
        await service.do_shoutout("ghost")
        self.assertLessEqual(service._until["ghost"], time.time() + config.COOLDOWN_SEC + 1)

    async def test_clear_does_not_release_an_in_flight_lookup(self):
        await service.do_shoutout("booked")
        service._until["inflight"] = time.time() + config.LOOKUP_GUARD_SEC
        await service.control("clear")
        self.assertNotIn("booked", service._until)          # its card was dropped
        self.assertIn("inflight", service._until)           # still being looked up

    async def test_the_guard_table_is_hard_bounded(self):
        now = time.time()
        for i in range(service._MAX_GUARDS + 400):
            service._until["u%d" % i] = now + 3600          # all still live
        service._prune(now)
        self.assertLessEqual(len(service._until), service._MAX_GUARDS)

    async def test_clear_releases_the_reservation(self):
        self.hold_ms = 40000
        await service.do_shoutout("one")
        await service.control("clear")
        self.assertEqual(self.controls, ["clear"])
        self.assertLess(service._queue_depth(time.time()), 1)
        await service.do_shoutout("one")               # allowed again
        self.assertEqual(len(self.sent), 2)


class TestRaidCard(ServiceTestCase):

    async def test_a_raid_is_flagged_with_its_viewer_count(self):
        await service.do_shoutout("raider", "raid", 42)
        self.assertTrue(self.sent[0]["raid"])
        self.assertEqual(self.sent[0]["raiders"], 42)

    async def test_a_manual_shoutout_is_not_a_raid(self):
        await service.do_shoutout("someone")
        self.assertFalse(self.sent[0]["raid"])
        self.assertEqual(self.sent[0]["raiders"], 0)

    async def test_an_approved_raid_keeps_its_raid_identity(self):
        config.RAID_REQUIRE_APPROVAL = True
        await service.do_shoutout("raider", "raid", 17)
        await service.control("ok")
        self.assertTrue(self.sent[0]["raid"])
        self.assertEqual(self.sent[0]["raiders"], 17)

    async def test_small_raids_are_ignored(self):
        config.RAID_MIN_VIEWERS = 5
        await service.do_shoutout("tiny", "raid", 4)
        self.assertEqual(self.sent, [])
        await service.do_shoutout("big", "raid", 5)
        self.assertEqual(self.logins(), ["big"])

    async def test_the_threshold_does_not_gate_a_manual_shoutout(self):
        config.RAID_MIN_VIEWERS = 50
        await service.do_shoutout("@someone")
        self.assertEqual(self.logins(), ["someone"])

    async def test_a_raid_gets_the_raid_chat_line(self):
        await service.do_shoutout("raider", "raid", 42)
        self.assertIn("raid", self.chats[0].lower())
        self.assertIn("42 viewers", self.chats[0])

    async def test_one_viewer_is_singular(self):
        await service.do_shoutout("solo", "raid", 1)
        self.assertIn("1 viewer)", self.chats[0])

    def test_viewers_phrase(self):
        self.assertEqual(service._viewers_phrase(0), "")
        self.assertEqual(service._viewers_phrase(None), "")
        self.assertEqual(service._viewers_phrase(1), "1 viewer")
        self.assertEqual(service._viewers_phrase(9), "9 viewers")


class TestInputNormalising(ServiceTestCase):
    """Mods paste links as often as they type @names."""

    async def test_a_pasted_channel_url_resolves_to_the_login(self):
        for typed in ("https://twitch.tv/PixelWitch",
                      "http://www.twitch.tv/pixelwitch",
                      "twitch.tv/pixelwitch/",
                      "@PixelWitch",
                      "  pixelwitch  "):
            self.sent[:] = []
            service._until.clear()
            await service.do_shoutout(typed)
            self.assertEqual(self.logins(), ["pixelwitch"], typed)

    async def test_a_url_with_query_junk_still_resolves(self):
        await service.do_shoutout("https://twitch.tv/someone?tt_medium=mobile")
        self.assertEqual(self.logins(), ["someone"])

    async def test_the_broadcaster_is_skipped_by_default(self):
        await service.do_shoutout("@" + config.CHANNEL)
        self.assertEqual(self.sent, [])

    async def test_self_shoutout_can_be_allowed(self):
        config.ALLOW_SELF_SHOUTOUT = True
        await service.do_shoutout("@" + config.CHANNEL)
        self.assertEqual(self.logins(), [config.CHANNEL])

    def test_aliases_are_recognised(self):
        config.COMMAND_ALIASES = ["!shoutout", "!SO2"]
        cmds = chat.commands()
        self.assertIn(config.COMMAND.lower(), cmds)
        self.assertIn("!shoutout", cmds)
        self.assertIn("!so2", cmds)

    def test_blank_aliases_are_ignored(self):
        config.COMMAND_ALIASES = ["", "  ", None]
        self.assertEqual(chat.commands(), {config.COMMAND.lower()})

    async def test_the_guard_dict_is_pruned(self):
        for i in range(300):
            service._until["user%d" % i] = time.time() - 1
        await service.do_shoutout("fresh")
        self.assertLess(len(service._until), 300)

    def test_clip_memory_is_bounded(self):
        clips._last_clips.clear()
        for i in range(clips._MAX_TRACKED_LOGINS + 25):
            clips._seen("login%d" % i).append("c%d" % i)
        self.assertLessEqual(len(clips._last_clips), clips._MAX_TRACKED_LOGINS)

    def test_eviction_is_lru_not_first_seen(self):
        # your regulars are the earliest keys; first-seen eviction would drop
        # exactly the streamers whose rotation matters most
        clips._last_clips.clear()
        clips._seen("regular").append("c0")
        for i in range(clips._MAX_TRACKED_LOGINS - 1):
            clips._seen("filler%d" % i).append("c%d" % i)
        clips._seen("regular")                              # touch it again
        for i in range(20):
            clips._seen("newcomer%d" % i).append("n%d" % i)
        self.assertIn("regular", clips._last_clips)


class TestShoutoutLog(ServiceTestCase):
    """The log is what lets clip rotation survive a restart."""

    async def test_a_shoutout_is_recorded(self):
        await service.do_shoutout("@SomeOne")
        with open(config.SHOUTOUT_LOG, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["login"], "someone")
        self.assertEqual(row["name"], "Someone")
        self.assertEqual(row["source"], "command")
        self.assertEqual(row["category"], "Test")
        self.assertFalse(row["hasClip"])
        self.assertIn("ts", row)

    async def test_clip_ids_are_recorded_and_read_back(self):
        service.lookup = lambda login: dict(_payload(login), clipId="clip-" + login,
                                            clip="http://x/c.mp4")
        await service.do_shoutout("alpha")
        await service.do_shoutout("bravo")
        self.assertEqual(history.recent_clips(),
                         {"alpha": ["clip-alpha"], "bravo": ["clip-bravo"]})

    async def test_the_raid_flag_is_recorded(self):
        await service.do_shoutout("raider", "raid", 12)
        with open(config.SHOUTOUT_LOG, encoding="utf-8") as f:
            line = f.read()
        self.assertIn('"source": "raid"', line)
        self.assertIn('"raiders": 12', line)

    async def test_a_blocked_shoutout_is_not_logged(self):
        config.BLOCKLIST = ["nope"]
        await service.do_shoutout("nope")
        self.assertFalse(os.path.isfile(config.SHOUTOUT_LOG))

    async def test_logging_off_writes_nothing(self):
        config.SHOUTOUT_LOG = ""
        await service.do_shoutout("someone")
        self.assertEqual(len(self.sent), 1)    # the shoutout still happens
        self.assertEqual(os.listdir(self.tmp), [])

    async def test_an_unwritable_log_never_costs_a_shoutout(self):
        config.SHOUTOUT_LOG = os.path.join(self.tmp, "no", "\0bad", "x.jsonl")
        await service.do_shoutout("someone")
        self.assertEqual(len(self.sent), 1)

    def test_priming_restores_the_rotation(self):
        clips._last_clips.clear()
        clips.prime({"streamer": ["a", "b", "c", "d", "e"]})
        seen = clips._seen("streamer")
        self.assertEqual(len(seen), config.CLIP_HISTORY)
        self.assertIn("e", seen)               # the most recent survive

    def test_a_primed_clip_is_avoided_on_the_next_pick(self):
        clips._last_clips.clear()
        pool = [{"id": "old", "created_at": "2026-08-02T00:00:00Z"},
                {"id": "new", "created_at": "2026-08-30T00:00:00Z"}]
        clips.prime({"s": ["new"]})
        self.assertEqual(clips.pick_recent(pool, "s")["id"], "old")


class TestDuckTargetCache(unittest.IsolatedAsyncioTestCase):
    """Re-probing every OBS input on every clip cost ~2N round-trips."""

    def setUp(self):
        self._req = obs_duck._req
        self._sources = config.DUCK_SOURCES
        config.DUCK_SOURCES = []          # explicit sources short-circuit discovery
        self.calls = []
        obs_duck._targets["names"] = None
        obs_duck._targets["at"] = 0.0

        async def fake_req(rtype, data=None, _retry=True):
            self.calls.append(rtype)
            if rtype == "GetInputList":
                return {"responseData": {"inputs": [
                    {"inputName": "Mic/Aux"}, {"inputName": "Desktop Audio"}]}}
            return {"requestStatus": {"result": True},
                    "responseData": {"inputVolumeMul": 1.0}}

        obs_duck._req = fake_req

    def tearDown(self):
        obs_duck._req = self._req
        config.DUCK_SOURCES = self._sources
        obs_duck._targets["names"] = None

    async def test_the_second_lookup_does_not_touch_obs(self):
        first = await obs_duck._duck_targets()
        n_after_first = len(self.calls)
        second = await obs_duck._duck_targets()
        self.assertEqual(first, second)
        self.assertEqual(len(self.calls), n_after_first)     # no new requests

    async def test_an_expired_cache_reprobes(self):
        await obs_duck._duck_targets()
        n = len(self.calls)
        obs_duck._targets["at"] -= config.DUCK_TARGET_TTL + 1
        await obs_duck._duck_targets()
        self.assertGreater(len(self.calls), n)

    async def test_a_reconnect_invalidates_the_cache(self):
        await obs_duck._duck_targets()
        await obs_duck._drop()
        self.assertIsNone(obs_duck._targets["names"])


class TestClipSelection(unittest.TestCase):
    """The pure selection logic — this is where the 'same clip every time' bug lived."""

    def setUp(self):
        clips._last_clips.clear()

    @staticmethod
    def clip(i, created, views=0):
        return {"id": "c%d" % i, "created_at": created, "view_count": views, "duration": 12.0}

    def test_recent_pick_stays_inside_the_pool(self):
        pool = [self.clip(i, "2026-08-%02dT00:00:00Z" % (i + 1)) for i in range(20)]
        newest = {c["id"] for c in sorted(
            pool, key=lambda c: c["created_at"], reverse=True)[:config.CLIP_RECENT_POOL]}
        for _ in range(40):
            self.assertIn(clips.pick_recent(pool, "x")["id"], newest)

    def test_recent_pick_rotates_rather_than_repeating(self):
        pool = [self.clip(i, "2026-08-%02dT00:00:00Z" % (i + 1)) for i in range(8)]
        picks = [clips.pick_recent(pool, "y")["id"] for _ in range(config.CLIP_HISTORY + 1)]
        self.assertEqual(len(set(picks[:config.CLIP_HISTORY + 1])),
                         config.CLIP_HISTORY + 1)

    def test_popular_pick_stays_inside_the_top_n(self):
        pool = [self.clip(i, "2026-08-01T00:00:00Z", views=i) for i in range(20)]
        top = {c["id"] for c in sorted(
            pool, key=lambda c: c["view_count"], reverse=True)[:config.CLIP_TOP_N]}
        for _ in range(40):
            self.assertIn(clips.pick_popular_random(pool, "z")["id"], top)

    def test_empty_pools_return_none(self):
        self.assertIsNone(clips.pick_recent([], "x"))
        self.assertIsNone(clips.pick_popular_random([], "x"))

    def test_hold_tracks_the_clip_and_is_clamped(self):
        self.assertEqual(clips._hold_ms(0, ""), config.NOCLIP_HOLD_MS)
        self.assertEqual(clips._hold_ms(0, "http://x/c.mp4"), config.HOLD_MS)
        self.assertEqual(clips._hold_ms(20.0, "http://x/c.mp4"), 21400)
        self.assertEqual(clips._hold_ms(2.0, "http://x/c.mp4"), 7400)     # floor 6s
        self.assertEqual(clips._hold_ms(120.0, "http://x/c.mp4"), 41400)  # ceiling 40s


class TestDuckLevels(unittest.TestCase):
    """You talk over a shoutout, so the mic must be able to stay up."""

    def setUp(self):
        self._levels = config.DUCK_LEVELS
        config.DUCK_LEVELS = {"Mic/Aux": 0.90, "Desktop Audio": 0.15}

    def tearDown(self):
        config.DUCK_LEVELS = self._levels

    def test_unlisted_sources_use_the_default(self):
        self.assertEqual(obs_duck.keep_for("Game Capture"), config.DUCK_KEEP)

    def test_an_exact_name_wins(self):
        self.assertEqual(obs_duck.keep_for("Mic/Aux"), 0.90)
        self.assertEqual(obs_duck.keep_for("Desktop Audio"), 0.15)

    def test_names_match_case_insensitively(self):
        self.assertEqual(obs_duck.keep_for("mic/aux"), 0.90)

    def test_an_empty_map_falls_back_everywhere(self):
        config.DUCK_LEVELS = {}
        self.assertEqual(obs_duck.keep_for("anything"), config.DUCK_KEEP)


class TestPayload(unittest.TestCase):
    """lookup() assembles what the overlay reads — including the audio settings."""

    def setUp(self):
        self._orig = (clips.helix_get, clips.clip_mp4)

        def helix_get(url, params):
            if url.endswith("/users"):
                return [{"id": "1", "login": "someone", "display_name": "SomeOne",
                         "profile_image_url": "http://img/a.png"}]
            if url.endswith("/channels"):
                return [{"game_name": "Valorant"}]
            if url.endswith("/streams"):
                return []
            if url.endswith("/clips"):
                return [{"id": "c1", "created_at": "2026-08-30T00:00:00Z",
                         "view_count": 9, "duration": 20.0,
                         "thumbnail_url": "http://t/x-preview-480x272.jpg"}]
            return []

        clips.helix_get = helix_get
        clips.clip_mp4 = lambda slug: ("http://cdn/clip.mp4", 20.0)
        clips._last_clips.clear()

    def tearDown(self):
        clips.helix_get, clips.clip_mp4 = self._orig

    def test_payload_carries_the_audio_settings(self):
        d = clips.lookup("@SomeOne")
        self.assertEqual(d["volume"], config.CLIP_VOLUME)
        self.assertEqual(d["fadeMs"], config.CLIP_FADE_IN_MS)

    def test_payload_carries_identity_and_clip(self):
        d = clips.lookup("someone")
        self.assertEqual(d["login"], "someone")
        self.assertEqual(d["name"], "SomeOne")
        self.assertEqual(d["category"], "Valorant")
        self.assertFalse(d["live"])
        self.assertEqual(d["clip"], "http://cdn/clip.mp4")
        self.assertEqual(d["hold"], 21400)

    def test_an_unknown_login_returns_none(self):
        clips.helix_get = lambda url, params: []
        self.assertIsNone(clips.lookup("ghost"))


class TestChatParsing(unittest.TestCase):

    def test_tags_are_split_off(self):
        tags, rest = chat.parse_tags("@mod=1;badges=moderator/1 :u!u@u PRIVMSG #c :!so @x")
        self.assertEqual(tags["mod"], "1")
        self.assertTrue(rest.startswith(":u!u@u PRIVMSG"))

    def test_untagged_lines_survive(self):
        tags, rest = chat.parse_tags("PING :tmi.twitch.tv")
        self.assertEqual(tags, {})
        self.assertEqual(rest, "PING :tmi.twitch.tv")

    def test_privilege_check(self):
        self.assertTrue(chat.is_privileged({"mod": "1"}))
        self.assertTrue(chat.is_privileged({"badges": "broadcaster/1"}))
        self.assertTrue(chat.is_privileged({"badges": "moderator/1,partner/1"}))
        self.assertFalse(chat.is_privileged({"badges": "subscriber/12"}))
        self.assertFalse(chat.is_privileged({}))

    def test_viewer_count_parsing_is_forgiving(self):
        self.assertEqual(chat._int("42"), 42)
        self.assertEqual(chat._int(None), 0)
        self.assertEqual(chat._int("lots"), 0)

    def test_bare_words_are_controls_but_at_names_are_not(self):
        self.assertEqual(chat.route("skip"), ("control", "skip"))
        self.assertEqual(chat.route("OK"), ("control", "ok"))
        self.assertEqual(chat.route("  clear  "), ("control", "clear"))
        # the streamer literally called "skip" is still reachable
        self.assertEqual(chat.route("@skip"), ("shoutout", "@skip"))
        self.assertEqual(chat.route("someone"), ("shoutout", "someone"))
        self.assertEqual(chat.route("@someone"), ("shoutout", "@someone"))

    def test_routing_falls_back_when_controls_are_unavailable(self):
        # no control callback wired up: a bare word is a target, not a command
        self.assertEqual(chat.route("skip", has_control=False), ("shoutout", "skip"))

    def test_routing_respects_the_master_switch(self):
        prev = config.CONTROLS_ENABLED
        config.CONTROLS_ENABLED = False
        try:
            self.assertEqual(chat.route("skip"), ("shoutout", "skip"))
        finally:
            config.CONTROLS_ENABLED = prev

    def test_routing_handles_junk(self):
        self.assertEqual(chat.route(""), ("shoutout", ""))
        self.assertEqual(chat.route(None), ("shoutout", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
