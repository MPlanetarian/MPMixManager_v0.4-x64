#!/usr/bin/env python3
"""The macOS console tab must keep one title while the menu redraws."""

import io
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANAGER_SH = os.path.join(SCRIPT_DIR, "Mix_Archive_Manager.sh")

FUNCTIONS = [
    "apply_manager_console_tab_title",
    "_lock_macos_console_tab_title",
    "toggle_manager_fullscreen",
    "ensure_manager_windowed",
    "ensure_manager_fullscreen",
    "_read_audio_volume_cache",
    "_write_audio_volume_cache",
    "_vol_refresh_running",
    "_spawn_volume_refresh",
    "get_audio_volume_and_mute",
    "_format_system_uptime_text",
    "_s4_hardware_connected",
    "get_manager_uptime",
]


def _extract_functions(path):
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    wanted = set(FUNCTIONS)
    chunks = []
    index = 0
    while index < len(lines):
        line = lines[index]
        name = line.split("(", 1)[0]
        if name in wanted and line.startswith(name + "()"):
            while index < len(lines):
                chunks.append(lines[index])
                if lines[index] == "}\n":
                    index += 1
                    break
                index += 1
            chunks.append("\n")
        else:
            index += 1
    missing = [name for name in FUNCTIONS if not any(chunk.startswith(name + "()") for chunk in chunks)]
    if missing:
        raise AssertionError("missing functions: " + ", ".join(missing))
    return "".join(chunks)


class TestMacOSConsoleTabTitle(unittest.TestCase):
    def test_menu_redraw_does_not_rename_the_tab(self):
        extracted = _extract_functions(MANAGER_SH)
        with tempfile.TemporaryDirectory() as home:
            bash = r'''
set -u
export HOME="$TEST_HOME"
export VERSION="0.4.3 Stable (Liquid)"
export OS_TYPE=macos
BOLD="" CYAN="" NC="" BLUE="" GREEN="" YELLOW="" RED="" MAGENTA="" DIM="" WHITE=""
export TERM_PROGRAM=Apple_Terminal
now="${EPOCHSECONDS:-$(date +%s)}"
_SYSTEM_BOOT_EPOCH=$(( now - 90061 ))
_MENU_CURSOR_LOCK=1
_LAST_VOL_CHECK="$now"
_CACHED_VOL_STATUS="42%"
UP_FLAG="$HOME/uptime.flag"
OSA_FLAG="$HOME/osa.flag"
uptime() { printf '%s\n' called >> "$UP_FLAG"; printf '%s\n' "up 9 days"; }
osascript() { printf '%s\n' called >> "$OSA_FLAG"; printf '%s\n' "output volume:1, output muted:false"; }
tty() { return 1; }
get_manager_uptime >/dev/null
get_manager_uptime >/dev/null
[ ! -e "$UP_FLAG" ] || exit 11
[ ! -e "$OSA_FLAG" ] || exit 12
vol_out="$(get_audio_volume_and_mute)"
[ "$vol_out" = "42%" ] || exit 14
[ ! -e "$OSA_FLAG" ] || exit 15
if [ -r /proc/uptime ]; then
    printf '%s\n' PROC_UPTIME
else
    case "$_MANAGER_UPTIME_LINE" in
        *"1d 1h 1m"*) printf '%s\n' UPTIME_FORMAT_OK ;;
        *) printf '%s\n' "BAD_UPTIME $_MANAGER_UPTIME_LINE"; exit 13 ;;
    esac
fi
_LAST_SET_TITLE=""
_TAB_TITLE_LOCKED=""
_IS_FULLSCREEN=0
ensure_manager_windowed > "$HOME/title1"
ensure_manager_windowed > "$HOME/title2"
OS_TYPE=linux
_LAST_SET_TITLE=""
_TAB_TITLE_LOCKED=""
ensure_manager_windowed > "$HOME/linux_title"
printf '%s\n' NO_SPAWN_OK
'''
            script = extracted + "\n" + bash
            env = os.environ.copy()
            env["TEST_HOME"] = home
            result = subprocess.run(
                ["bash", "-c", script],
                cwd=SCRIPT_DIR,
                capture_output=True,
                env=env,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
            )
            self.assertIn(b"NO_SPAWN_OK", result.stdout)
            if b"PROC_UPTIME" not in result.stdout:
                self.assertIn(b"UPTIME_FORMAT_OK", result.stdout)
            title = "MP Mix Archive Manager [v0.4.3 Stable (Liquid)]"
            with open(os.path.join(home, "title1"), "rb") as handle:
                first = handle.read()
            with open(os.path.join(home, "title2"), "rb") as handle:
                second = handle.read()
            with open(os.path.join(home, "linux_title"), "rb") as handle:
                linux_title = handle.read()
            payload = title.encode()
            self.assertEqual(first.count(payload), 3)
            self.assertIn(b"\033]0;" + payload + b"\007", first)
            self.assertIn(b"\033]1;" + payload + b"\007", first)
            self.assertIn(b"\033]2;" + payload + b"\007", first)
            self.assertNotIn(b"\033[10;", first)
            self.assertNotIn(b"\033[9;", first)
            self.assertEqual(second, b"")
            self.assertIn(b"\033[10;0t\033[9;0t", linux_title)
            self.assertIn(b"\033]0;" + payload + b"\007", linux_title)

    def test_player_repeats_do_not_rewrite_the_title(self):
        home = tempfile.mkdtemp()
        env_home = os.environ.get("HOME")
        os.environ["HOME"] = home
        sys.path.insert(0, SCRIPT_DIR)
        try:
            import MP_Audio_Player as player
            player._LAST_TERMINAL_TITLE = ""
            buffer = io.StringIO()
            old = sys.stdout
            sys.stdout = buffer
            try:
                player._set_terminal_title("MP Mini Audio Player")
                player._set_terminal_title("MP Mini Audio Player")
                player._set_terminal_title("MP Micro Audio Player")
            finally:
                sys.stdout = old
        finally:
            if env_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = env_home
            sys.path.remove(SCRIPT_DIR)
        text = buffer.getvalue()
        self.assertEqual(text.count("MP Mini Audio Player"), 1)
        self.assertEqual(text.count("MP Micro Audio Player"), 1)
        self.assertEqual(text.count("\033]0;"), 2)

    def test_overlay_swallows_osc_and_keeps_ed0(self):
        sys.path.insert(0, SCRIPT_DIR)
        try:
            from MP_Audio_Player_Liquid_Glass_OpenGL_macOS import TerminalOverlay
        finally:
            if SCRIPT_DIR in sys.path:
                sys.path.remove(SCRIPT_DIR)
        overlay = TerminalOverlay(cols=12, rows=4)
        overlay.feed(b"\033]0;SECRET TITLE\007Hello")
        flat = "".join("".join(row) for row in overlay.grid)
        self.assertNotIn("SECRET", flat)
        self.assertNotIn("0;", flat)
        self.assertTrue(flat.startswith("Hello"))
        overlay.cursor_row = 2
        overlay.cursor_col = 3
        overlay.grid[0][0] = "A"
        overlay.feed(b"\033[J")
        self.assertEqual(overlay.grid[0][0], "A")
        self.assertEqual(overlay.cursor_row, 2)
        self.assertEqual(overlay.cursor_col, 3)
        self.assertEqual(overlay.grid[2][3], " ")
        self.assertEqual(overlay.grid[3][0], " ")
        overlay.grid[1][1] = "B"
        overlay.cursor_row = 1
        overlay.cursor_col = 1
        overlay.feed(b"\033[2J")
        self.assertEqual(overlay.grid[1][1], " ")
        self.assertEqual(overlay.cursor_row, 1)
        self.assertEqual(overlay.cursor_col, 1)
        overlay.feed(b"\033]0;PART")
        overlay.feed(b"IAL\007Z")
        flat = "".join("".join(row) for row in overlay.grid)
        self.assertNotIn("PARTIAL", flat)
        self.assertIn("Z", flat)

    def test_overlay_darkens_body_text_on_light_glass_only(self):
        sys.path.insert(0, SCRIPT_DIR)
        try:
            from MP_Audio_Player_Liquid_Glass_OpenGL_macOS import TerminalOverlay
        finally:
            if SCRIPT_DIR in sys.path:
                sys.path.remove(SCRIPT_DIR)

        light = TerminalOverlay(cols=8, rows=2)
        light.set_ink("cyber_neon", on_light_glass=True)
        darkened = light.ink_for_cell((255, 255, 255), None)
        self.assertTrue(all(channel < 80 for channel in darkened))
        self.assertEqual(light.ink_for_cell((255, 255, 255), (20, 20, 40)), (255, 255, 255))
        light.feed(b"\033[38;2;255;255;255mW")
        self.assertEqual(light.colors[0][0], (255, 255, 255))
        light.feed(b"\033[38;5;196mR")
        self.assertEqual(light.colors[0][1], (255, 0, 0))

        charcoal = TerminalOverlay(cols=4, rows=1)
        charcoal.set_ink("retro_linux_memories", on_light_glass=True)
        self.assertEqual(charcoal.ink_for_cell((255, 255, 255), None), (255, 255, 255))

        visualizer = TerminalOverlay(cols=4, rows=1)
        visualizer.set_ink("cyber_neon", on_light_glass=False)
        self.assertEqual(visualizer.ink_for_cell((255, 255, 255), None), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
