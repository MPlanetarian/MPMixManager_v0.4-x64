#!/usr/bin/env python3
"""MP Gui and MP Liquid Player stop at four windows.

Every launch path shares scripts/mp_instance_limit.py: the desktop shortcuts,
the global shortcut keys, the tray icon, the console menu, VR Mode, and the
Liquid Glass hosts themselves. These tests pin the count, the atomic claim,
the role split, and one path through each launcher.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mp_instance_limit as limiter


class LimiterCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(setattr, os.environ, "MP_INSTANCE_STATE_DIR", os.environ.get("MP_INSTANCE_STATE_DIR", ""))
        os.environ["MP_INSTANCE_STATE_DIR"] = self._tmp.name

    def table(self, *cmdlines):
        return [(100 + index, cmdline) for index, cmdline in enumerate(cmdlines)]


class TestRoleDetection(LimiterCase):
    def test_the_cap_covers_gui_and_player_only(self):
        self.assertEqual(limiter.MAX_INSTANCES, 4)
        self.assertEqual(
            limiter.role_from_cmdline("python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py"),
            limiter.ROLE_PLAYER,
        )
        self.assertEqual(
            limiter.role_from_cmdline("python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --manager"),
            limiter.ROLE_GUI,
        )
        self.assertEqual(
            limiter.role_from_cmdline("python3 /opt/MP_Audio_Player_Liquid_Glass.py --manager --theme dracula"),
            limiter.ROLE_GUI,
        )

    def test_other_windows_and_helper_runs_are_not_counted(self):
        for cmdline in (
            "bash /opt/Mix_Archive_Manager.sh",
            "python3 /opt/MP_Liquid_Visualizer.py --preset random",
            "bash /opt/scripts/mp_system_tray.py",
            "python3 /opt/MP_Audio_Player.py --interactive",
            # The console viewer and embed checks draw no capped window.
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --tracklist /tmp/a.txt",
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --embed-check",
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --self-test",
            # pgrep, pkill, and grep lines only mention the host as a pattern.
            "pgrep -af MP_Audio_Player_Liquid_Glass",
            "grep MP_Audio_Player_Liquid_Glass_openGL.py",
            "python3 /opt/scripts/mp_instance_limit.py check player",
        ):
            self.assertIsNone(limiter.role_from_cmdline(cmdline), cmdline)

    def test_the_manager_host_is_not_a_player_instance(self):
        table = self.table(
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --manager",
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py",
        )
        self.assertEqual(limiter.role_pids(limiter.ROLE_GUI, table), {100})
        self.assertEqual(limiter.role_pids(limiter.ROLE_PLAYER, table), {101})


class TestCap(LimiterCase):
    def test_four_windows_are_allowed_and_a_fifth_is_not(self):
        hosts = self.table(
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "python3 /opt/MP_Audio_Player_Liquid_Glass.py",
            "python3 /opt/MP_Audio_Player_Liquid_Glass_macOS.py",
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
        )
        with patch.object(limiter, "process_table", return_value=hosts):
            self.assertEqual(limiter.instance_count(limiter.ROLE_PLAYER), 4)
            self.assertTrue(limiter.at_limit(limiter.ROLE_PLAYER))
            self.assertFalse(limiter.claim_instance(limiter.ROLE_PLAYER, pid=999))

    def test_three_windows_leave_a_slot_for_a_fourth(self):
        hosts = self.table(
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py",
        )
        with patch.object(limiter, "process_table", return_value=hosts), \
             patch.object(limiter, "_pid_alive", return_value=True):
            self.assertEqual(limiter.instance_count(limiter.ROLE_PLAYER), 3)
            self.assertTrue(limiter.claim_instance(limiter.ROLE_PLAYER, pid=998))
            # The claim now fills the fourth slot.
            self.assertEqual(limiter.instance_count(limiter.ROLE_PLAYER), 4)
            self.assertTrue(limiter.at_limit(limiter.ROLE_PLAYER))
            self.assertFalse(limiter.claim_instance(limiter.ROLE_PLAYER, pid=999))

    def test_gui_and_player_counters_are_separate(self):
        hosts = self.table(
            *["python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py"] * 4,
            "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py --manager",
        )
        with patch.object(limiter, "process_table", return_value=hosts), \
             patch.object(limiter, "_pid_alive", return_value=True):
            self.assertTrue(limiter.at_limit(limiter.ROLE_PLAYER))
            self.assertFalse(limiter.at_limit(limiter.ROLE_GUI))
            self.assertTrue(limiter.claim_instance(limiter.ROLE_GUI, pid=997))

    def test_two_launches_cannot_take_the_last_slot(self):
        hosts = self.table(
            *["python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py"] * 3,
        )
        with patch.object(limiter, "process_table", return_value=hosts), \
             patch.object(limiter, "_pid_alive", return_value=True):
            self.assertTrue(limiter.claim_instance(limiter.ROLE_PLAYER, pid=501))
            self.assertFalse(limiter.claim_instance(limiter.ROLE_PLAYER, pid=502))
            self.assertEqual(limiter.instance_count(limiter.ROLE_PLAYER), 4)

    def test_claiming_twice_for_one_process_stays_one_slot(self):
        with patch.object(limiter, "process_table", return_value=[]), \
             patch.object(limiter, "_pid_alive", return_value=True):
            self.assertTrue(limiter.claim_instance(limiter.ROLE_PLAYER, pid=777))
            self.assertTrue(limiter.claim_instance(limiter.ROLE_PLAYER, pid=777))
            self.assertEqual(limiter.instance_count(limiter.ROLE_PLAYER), 1)
            limiter.release_instance(limiter.ROLE_PLAYER, pid=777)
            self.assertEqual(limiter.instance_count(limiter.ROLE_PLAYER), 0)

    def test_a_dead_claim_does_not_keep_a_slot(self):
        with patch.object(limiter, "process_table", return_value=[]):
            limiter.state_dir()
            claim = limiter._claim_file(limiter.ROLE_PLAYER, 424242)
            claim.write_text("424242\n", encoding="utf-8")
            # 424242 is not a live pid, so the stale claim is dropped.
            self.assertEqual(limiter.instance_count(limiter.ROLE_PLAYER), 0)
            self.assertFalse(claim.exists())

    def test_a_host_counts_itself_without_taking_two_slots(self):
        cmdline = "python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py"
        hosts = [(4242, cmdline), (4243, cmdline), (4244, cmdline), (4245, cmdline)]
        with patch.object(limiter, "process_table", return_value=hosts):
            # A host that is already running may claim for itself; a new pid
            # still gets the refusal.
            self.assertTrue(limiter.claim_instance(limiter.ROLE_PLAYER, pid=4245))
            self.assertFalse(limiter.claim_instance(limiter.ROLE_PLAYER, pid=4246))
            self.assertEqual(limiter.instance_count(limiter.ROLE_PLAYER), 4)

    def test_the_console_manager_is_never_counted(self):
        with patch.object(limiter, "process_table", return_value=[]):
            self.assertEqual(limiter.instance_count("manager"), 0)


class TestCommandLine(LimiterCase):
    def test_check_reports_the_limit_with_exit_code_three(self):
        hosts = self.table(*["python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py"] * 4)
        with patch.object(limiter, "process_table", return_value=hosts):
            self.assertEqual(limiter.main(["check", "player"]), 3)
            self.assertEqual(limiter.main(["check", "gui"]), 0)

    def test_claim_and_status_commands(self):
        with patch.object(limiter, "process_table", return_value=[]), \
             patch.object(limiter, "_pid_alive", return_value=True), \
             patch("sys.stdout"):
            self.assertEqual(limiter.main(["claim", "gui", "--pid", "8080"]), 0)
            self.assertEqual(limiter.instance_count("gui"), 1)
            self.assertEqual(limiter.main(["release", "gui", "--pid", "8080"]), 0)
            self.assertEqual(limiter.instance_count("gui"), 0)
            self.assertEqual(limiter.main(["status"]), 0)

    def test_count_prints_a_number_for_one_role(self):
        hosts = self.table("python3 /opt/MP_Audio_Player_Liquid_Glass_OpenGL.py")
        with patch.object(limiter, "process_table", return_value=hosts):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "mp_instance_limit.py"), "count", "player"],
                capture_output=True,
                text=True,
                env={**os.environ, "MP_INSTANCE_STATE_DIR": self._tmp.name},
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "0")


class TestLaunchersSourceTheCap(unittest.TestCase):
    """Every user-facing launch path goes through the shared limiter."""

    def test_linux_desktop_launchers_claim_a_slot(self):
        gui = (ROOT / "MP_Gui.sh").read_text(encoding="utf-8")
        player = (ROOT / "scripts" / "launch_liquid_glass.sh").read_text(encoding="utf-8")
        shortcut = (ROOT / "scripts" / "launch-liquid-glass").read_text(encoding="utf-8")
        for text, role in ((gui, "gui"), (player, "player"), (shortcut, "player")):
            self.assertIn("mp_instance_limit.sh", text)
            self.assertIn(f"mp_instance_claim {role}", text)
            self.assertIn(f"mp_instance_notify_limit {role}", text)

    def test_windows_launchers_check_the_cap(self):
        gui = (ROOT / "scripts" / "launch_mp_gui.bat").read_text(encoding="utf-8")
        player = (ROOT / "scripts" / "launch_liquid_glass.bat").read_text(encoding="utf-8")
        self.assertIn("mp_instance_limit.py\" check gui", gui)
        self.assertIn("mp_instance_limit.py\" notify gui", gui)
        self.assertIn("mp_instance_limit.py\" check player", player)
        self.assertIn("mp_instance_limit.py\" notify player", player)

    def test_windows_tray_stops_at_four_windows(self):
        tray = (ROOT / "scripts" / "windows_tray.ps1").read_text(encoding="utf-8")
        self.assertIn("$script:maxCappedInstances = 4", tray)
        self.assertIn("Test-MpRoleAtLimit", tray)
        self.assertIn("Show-MpLimitBalloon", tray)
        # The console manager keeps its focus-first behaviour.
        self.assertIn('-and (Show-MpWindow -TitlePart $titles[$Role])', tray)

    def test_gui_and_player_hosts_guard_themselves(self):
        for name in (
            "MP_Audio_Player_Liquid_Glass.py",
            "MP_Audio_Player_Liquid_Glass_OpenGL.py",
            "MP_Audio_Player_Liquid_Glass_macOS.py",
            "MP_Audio_Player_Liquid_Glass_OpenGL_macOS.py",
        ):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("host_allowed", text, name)
            self.assertIn("4 is the maximum", text, name)

    def test_console_menu_and_vr_mode_obey_the_cap(self):
        manager = (ROOT / "Mix_Archive_Manager.sh").read_text(encoding="utf-8")
        self.assertIn("_mp_instance_limit_reached gui", manager)
        self.assertIn("_mp_instance_limit_reached player", manager)
        self.assertIn("_mp_instance_announce_limit", manager)
        vr = (ROOT / "scripts" / "bigscreen_vr.py").read_text(encoding="utf-8")
        self.assertIn("player_launch_allowed", vr)

    def test_shell_helper_reports_the_four_window_limit(self):
        helper = (ROOT / "scripts" / "mp_instance_limit.sh").read_text(encoding="utf-8")
        self.assertIn("MP_INSTANCE_MAX=4", helper)
        self.assertIn("mp_instance_claim", helper)
        self.assertIn("mp_instance_focus", helper)


class TestShellCap(unittest.TestCase):
    def test_claim_blocks_the_fifth_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "MP_INSTANCE_STATE_DIR": tmp}
            helper = (
                'source "$PWD/scripts/mp_instance_limit.sh"; '
                'mp_instance_claim player "$MP_FAKE_PID" || exit 3'
            )
            # A claim belongs to a live pid, so hold four launchers open.
            launchers = [subprocess.Popen(["sleep", "60"]) for _ in range(4)]
            self.addCleanup(lambda: [proc.kill() for proc in launchers])
            for proc in launchers:
                result = subprocess.run(
                    ["bash", "-c", helper],
                    cwd=str(ROOT),
                    env={**env, "MP_FAKE_PID": str(proc.pid)},
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run(
                ["bash", "-c", helper],
                cwd=str(ROOT),
                env={**env, "MP_FAKE_PID": str(os.getpid())},
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
