"""Tests for the tray's Start / Stop MP Web Audio entry.

Covers the three pieces the user asked for:

* the menu row labels itself Stop while the companion serves and Start while
  it does not;
* only Linux is wired up, and the platform dispatch is a case table;
* stopping/restarting the companion tells connected dashboards, which then
  refresh themselves so the phone resumes the stream.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mp_system_tray as tray
import mp_web_service as web


class TestLabels(unittest.TestCase):
    def test_fresh_install_reads_start(self):
        with patch.object(web, "companion_running", return_value=False):
            self.assertEqual(web.menu_label(), "Start MP Web Audio")

    def test_running_service_reads_stop(self):
        with patch.object(web, "companion_running", return_value=True):
            self.assertEqual(web.menu_label(), "Stop MP Web Audio")

    def test_tray_menu_has_the_option_before_close_all(self):
        ids = [ident for ident, _label in tray.MENU_ENTRIES]
        self.assertIn("web-audio", ids)
        self.assertEqual(ids[-1], "close-all")
        self.assertLess(ids.index("web-audio"), ids.index("close-all"))

    def test_tray_label_follows_the_service_state(self):
        with patch.object(web, "companion_running", return_value=True):
            self.assertEqual(tray.web_audio_label(), "Stop MP Web Audio")
        with patch.object(web, "companion_running", return_value=False):
            self.assertEqual(tray.web_audio_label(), "Start MP Web Audio")


class TestPlatformCase(unittest.TestCase):
    def test_only_linux_is_wired(self):
        self.assertEqual(set(web._TOGGLE_CASES), {"Linux"})

    def test_darwin_and_windows_are_rejected(self):
        for name in ("Darwin", "Windows", "FreeBSD"):
            with patch.object(web, "companion_running", return_value=False):
                result = web.toggle_companion(name)
            self.assertFalse(result["supported"], name)
            self.assertEqual(result["action"], "unsupported", name)

    def test_platform_detection(self):
        self.assertEqual(web._platform_case_name(), "Linux")


class TestToggle(unittest.TestCase):
    def test_running_service_is_stopped(self):
        with patch.object(web, "companion_running", side_effect=[True, True]), \
             patch.object(web, "stop_companion", return_value=True) as stop, \
             patch.object(web, "start_companion") as start:
            result = web.toggle_companion("Linux")
        self.assertEqual(result["action"], "stop")
        self.assertEqual(stop.call_count, 1)
        self.assertEqual(start.call_count, 0)
        self.assertTrue(result["success"])
        self.assertEqual(result["label"], "Start MP Web Audio")

    def test_stopped_service_is_started(self):
        with patch.object(web, "companion_running", side_effect=[False, False, True]), \
             patch.object(web, "stop_companion") as stop, \
             patch.object(web, "start_companion", return_value=True) as start:
            result = web.toggle_companion("Linux")
        self.assertEqual(result["action"], "start")
        self.assertEqual(start.call_count, 1)
        self.assertEqual(stop.call_count, 0)
        self.assertTrue(result["success"])
        self.assertEqual(result["label"], "Stop MP Web Audio")

    def test_stop_tells_clients_before_the_port_closes(self):
        order = []
        state = {"running": True}

        def fake_running():
            return state["running"]

        def fake_script(action):
            order.append(action)
            if action == "stop":
                state["running"] = False
            return True

        with patch.object(web, "companion_running", side_effect=fake_running), \
             patch.object(web, "announce", side_effect=lambda *a, **k: order.append("announce") or True) as note, \
             patch.object(web, "ANNOUNCE_SETTLE_SECONDS", 0), \
             patch.object(web, "_via_script", side_effect=fake_script):
            self.assertTrue(web.stop_companion())
        self.assertEqual(note.call_count, 1)
        self.assertEqual(order[0], "announce")
        self.assertIn("stop", order)

    def test_toggle_reports_an_error_when_the_action_fails(self):
        with patch.object(web, "companion_running", return_value=True), \
             patch.object(web, "_toggle_linux", return_value=None):
            result = web.toggle_companion("Linux")
        self.assertEqual(result["action"], "error")
        self.assertTrue(result["supported"])


class TestAnnounce(unittest.TestCase):
    def test_announce_posts_the_default_message(self):
        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["body"] = request.data
            captured["method"] = request.method
            return FakeResponse()

        with patch.object(web.urllib.request, "urlopen", side_effect=fake_urlopen):
            self.assertTrue(web.announce(port=8888))

        self.assertTrue(captured["url"].endswith("/api/announce"))
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(
            json.loads(captured["body"])["message"],
            "MP Audio Web Companion has been restarted",
        )

    def test_announce_failure_is_not_fatal(self):
        with patch.object(web.urllib.request, "urlopen", side_effect=OSError("down")):
            self.assertFalse(web.announce())


class TestCompanionAnnouncements(unittest.TestCase):
    """The server side of the notice: instance ids and the one-shot message."""

    def setUp(self):
        from scripts import mix_web_companion as companion

        self.companion = companion

    def tearDown(self):
        self.companion._announce_message = None
        self.companion._announce_at = 0.0

    def test_a_fresh_instance_id_is_reported(self):
        self.assertTrue(self.companion.INSTANCE_ID)
        self.assertNotIn(" ", self.companion.INSTANCE_ID)

    def test_announcement_is_returned_once_set(self):
        self.assertIsNone(self.companion.current_announcement())
        queued = self.companion.set_announcement(
            "MP Audio Web Companion has been restarted"
        )
        self.assertIsNotNone(queued)
        current = self.companion.current_announcement()
        self.assertEqual(
            current["message"], "MP Audio Web Companion has been restarted"
        )

    def test_empty_announcement_is_ignored(self):
        self.assertIsNone(self.companion.set_announcement("   "))
        self.assertIsNone(self.companion.current_announcement())

    def test_announcement_expires(self):
        self.companion.set_announcement("restarted")
        with patch.object(self.companion, "ANNOUNCE_TTL_SECONDS", 0):
            self.assertIsNone(self.companion.current_announcement())


class TestPageRestartNotice(unittest.TestCase):
    """The dashboard must display the notice and reload itself."""

    def setUp(self):
        from scripts import mix_web_companion as companion

        self.page = companion.render_html_page(
            companion.THEMES["cosmic_supernova"]
        )

    def test_notice_banner_exists(self):
        self.assertIn('id="restartNotice"', self.page)
        self.assertIn('id="restartNoticeText"', self.page)
        self.assertIn("MP Audio Web Companion has been restarted", self.page)

    def test_page_tracks_the_instance_id_and_reconnects(self):
        self.assertIn("serverInstance", self.page)
        self.assertIn("data.instance !== serverInstance", self.page)
        # Resuming in place keeps the tap gesture; a reload is the fallback.
        self.assertIn("reattachToRestartedServer", self.page)
        self.assertIn("reloadForFreshInstance", self.page)
        self.assertIn("window.location.reload()", self.page)

    def test_page_recovers_from_a_media_error(self):
        self.assertIn("mediaRecoveryUsed", self.page)
        self.assertIn("addEventListener('error'", self.page)

    def test_page_observes_the_announcement_payload(self):
        self.assertIn("observeAnnouncement", self.page)
        self.assertIn("data.announcement", self.page)

    def test_page_shows_the_notice_when_the_connection_drops(self):
        self.assertIn("noteServerGone", self.page)
        self.assertIn("statusFailureCount", self.page)


class TestTrayAction(unittest.TestCase):
    def test_action_routes_to_the_toggle(self):
        with patch.object(tray, "toggle_web_audio", return_value={"supported": True}) as toggle:
            self.assertEqual(tray.perform_menu_action(ROOT, "web-audio"), 0)
        self.assertEqual(toggle.call_count, 1)

    def test_unsupported_platform_returns_an_error_code(self):
        with patch.object(tray, "toggle_web_audio", return_value={"supported": False}), \
             patch("sys.stderr"):
            self.assertEqual(tray.perform_menu_action(ROOT, "web-audio"), 1)

    def test_tray_imports_the_service_module(self):
        source = (ROOT / "scripts" / "mp_system_tray.py").read_text(encoding="utf-8")
        self.assertIn("import mp_web_service", source)
        self.assertIn("aboutToShow", source)
        self.assertIn('action_id == "web-audio"', source)

    def test_linux_cli_handles_the_action_flag(self):
        """--action must not fall through to starting the tray GUI."""
        source = (ROOT / "scripts" / "mp_system_tray.py").read_text(encoding="utf-8")
        linux_main = source[source.index("def main("):]
        self.assertIn('if "--action" in args:', linux_main)
        self.assertIn("perform_menu_action", linux_main)


if __name__ == "__main__":
    unittest.main()
