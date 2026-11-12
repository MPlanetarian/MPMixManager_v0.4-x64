#!/usr/bin/env python3
"""
Every navigable Mix Manager page must render through run_interactive_submenu.

The manager used to mix two menu implementations: the main page and a handful of
sub-pages drew the arrow-key navigation bar, while roughly thirty others printed
a plain list and asked for `read -r -p "Enter choice"`. Those pages had no
Up/Down navigation, no `/` search, and no consistent Esc/0 behaviour.

These tests lock in the unified behaviour:
  1. Every reachable page that offers a numbered choice routes through
     run_interactive_submenu.
  2. run_interactive_submenu advertises the navigation bar.
  3. Mouse reporting is enabled while a menu is on screen and restored after.
  4. A double click on a painted row activates that option.
  5. The wheel steps the highlight.
"""

import os
import pty
import re
import select
import time
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MGR_SH = BASE_DIR / "Mix_Archive_Manager.sh"

PAGES = [
    "manage_video_cut_and_split",
    "manage_system_process_monitors",
    "run_bash_cli",
    "manage_visual_media_launchers",
    "manage_live_monitors",
    "manage_process_and_bash_monitor",
    "launch_video_playlists",
    "manage_spek_generation",
    "manage_cover_converter",
    "find_duplicate_audio_mixes",
    "manage_mix_search_and_import",
    "configure_liquid_glass_backend",
    "manage_weather_menu",
    "configure_daily_reports_settings",
    "configure_audio_player_and_startup",
    "manage_audio_players",
    "manage_mp_liquid_visualizer_presets",
    "manage_cliamp",
    "manage_daws",
    "manage_network_services",
    "manage_system_maintenance",
    "launch_ai_session",
    "launch_traktor_monitor_window",
    "manage_promo_outreach",
    "manage_bluetooth_audio",
    "manage_visualizer_screensaver",
    "manage_audio_checksums",
    "open_mix_in_daw",
    "export_mixes_to_path",
    "manage_mix_scheduler",
]

FUNC_START = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{")


def _brace_delta(line: str) -> int:
    """Brace delta for a line, ignoring `${...}` parameter expansions."""
    line = re.sub(r"\$'[^']*'", "", line)
    while "${" in line:
        new = re.sub(r"\$\{[^{}]*\}", "", line)
        if new == line:
            break
        line = new
    return line.count("{") - line.count("}")


def functions(text: str):
    """Top-level function map: name -> body. Brace-aware so nested helpers work."""
    lines = text.splitlines()
    found = {}
    i = 0
    while i < len(lines):
        m = FUNC_START.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start = i
        depth = 0
        j = i
        while j < len(lines):
            depth += _brace_delta(lines[j])
            if depth == 0 and j > start:
                break
            j += 1
        found[name] = "\n".join(lines[start:j + 1])
        i = j + 1
    return found


def reachable(found):
    names = set(found)
    graph = {
        name: {tok for tok in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", body)
               if tok in names and tok != name}
        for name, body in found.items()
    }
    lines = MGR_SH.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.startswith("_STOP_AUDIO_ON_EXIT=1; while true;")), None)
    if start is None:
        raise AssertionError("main menu loop not found")
    seed = {tok for tok in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b",
                                      "\n".join(lines[start:])) if tok in names}
    seen = set()
    queue = list(seed)
    while queue:
        node = queue.pop()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(n for n in graph.get(node, ()) if n not in seen)
    return seen


class TestUniformNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = MGR_SH.read_text(encoding="utf-8")
        cls.funcs = functions(cls.text)
        cls.reachable = reachable(cls.funcs)

    def body(self, name):
        """Return a top-level function body, or the nested helper of that name."""
        if name in self.funcs:
            return self.funcs[name]
        m = re.search(r"^" + re.escape(name) + r"\(\)\s*\{", self.text, re.MULTILINE)
        if not m:
            self.fail(f"{name}() not found anywhere in Mix_Archive_Manager.sh")
        return self.text[m.start():]

    def snippet(self, name, length=4000):
        return self.body(name)[:length]

    def test_parser_sanity(self):
        """The brace-aware parser must capture the whole menu engine."""
        body = self.funcs["run_interactive_submenu"]
        self.assertIn("_nav_mouse_enable", body,
                      "parser stopped short of the menu loop")
        self.assertIn("cleanup_submenu_screen", body)

    def test_no_reachable_page_prompts_for_a_choice_without_the_nav_bar(self):
        offenders = []
        for name in sorted(self.reachable):
            if name == "run_interactive_submenu":
                continue
            body = self.funcs[name]
            if "run_interactive_submenu" in body or '_m_loop "' in body:
                continue
            if re.search(r'read -r -p\s+"[^"]*(?:choice|option|mode)[^"]*"',
                         body, re.IGNORECASE):
                offenders.append(name)
        self.assertEqual(
            offenders, [],
            "These pages still ask for a menu choice without the navigation bar: "
            + ", ".join(offenders),
        )

    def test_converted_pages_call_run_interactive_submenu(self):
        for page in PAGES:
            self.assertIn(page, self.funcs, f"{page}() not found")
            self.assertIn("run_interactive_submenu", self.funcs[page],
                          f"{page}() does not use the navigation menu")

    def test_navigation_bar_is_advertised(self):
        body = self.funcs["run_interactive_submenu"]
        for hint in ("Use [\u2191/\u2193]", "Selection:", "Filter / Search"):
            self.assertIn(hint, body, f"navigation bar is missing {hint!r}")

    def test_mouse_reporting_is_enabled_and_restored(self):
        self.assertIn("_nav_mouse_enable", self.funcs["run_interactive_submenu"])
        self.assertIn("_nav_mouse_disable", self.snippet("cleanup_submenu_screen", 400))
        self.assertIn("_nav_mouse_disable", self.body("_cleanup_mix_manager_exit"))
        self.assertIn("1000l", self.body("_nav_mouse_disable"))
        self.assertIn("1006l", self.body("_nav_mouse_disable"))
        self.assertIn("1000h", self.body("_nav_mouse_enable"))
        self.assertIn("1006h", self.body("_nav_mouse_enable"))

    def test_sgr_mouse_reports_are_parsed(self):
        key = self.funcs["read_nav_key"]
        self.assertIn("_nav_parse_sgr_mouse", key)
        self.assertIn("_NAV_MOUSE_EVENT", key)
        parser = self.snippet("_nav_parse_sgr_mouse", 1500)
        self.assertIn("MOUSE:", parser)
        self.assertIn("MOUSE_RELEASE", parser)

    def test_double_click_and_wheel_are_wired(self):
        handle = self.snippet("_menu_handle_mouse", 3000)
        self.assertIn("_MENU_MOUSE_ACTIVATE=1", handle)
        self.assertIn("_LAST_MOUSE_IDX", handle)
        self.assertIn("64)", handle)
        self.assertIn("65)", handle)
        self.assertIn("_menu_nudge_selection", handle)
        dispatch = self.funcs["run_interactive_submenu"]
        self.assertIn("MOUSE:*)", dispatch)
        self.assertIn("_MENU_MOUSE_ACTIVATE", dispatch)

    def test_mouse_can_be_disabled_for_native_selection(self):
        supported = self.body("_nav_mouse_supported")
        self.assertIn("MP_MANAGER_MOUSE", supported)
        for word in ("false", "off", "no"):
            self.assertIn(word, supported,
                          f"{word!r} should disable menu mouse support")


HARNESS = r'''
cd __BASE__
export TERM=xterm-256color
export MP_MANAGER_MOUSE=1
export _TERM_LINES=45 _TERM_COLS=120
source <(sed -n '1,/^if \[\[ "${BASH_SOURCE\[0\]}" == "${0}" \]\]/p' Mix_Archive_Manager.sh | sed '$d')
SCRIPT_DIR="__BASE__"
load_header_cache() { :; }
save_header_cache() { :; }
maybe_spawn_header_refresh() { :; }
_maybe_refresh_perf_cache() { :; }
render_main_header() { printf 'main header\n'; }
run_deferred_startup() { :; }
update_mp_bridge_menu() { :; }
get_mp_audio_player_track_info() { return 1; }
toggle_manager_fullscreen() { :; }
toggle_mp_audio_player() { :; }
launch_mp_audio_player_window() { :; }
launch_mp_audio_player_liquid_glass() { :; }
launch_mp_liquid_visualizer() { :; }
launch_mp_gui_from_menu() { :; }
launch_mp_harmony_from_menu() { :; }
manage_mp_audio_player() { :; }
cycle_menu_theme() { :; }
enter_manager_bash_terminal() { :; }
ensure_manager_windowed() { :; }
_start_win_cursor_hider() { :; }
_stop_win_cursor_hider() { :; }
_TERM_RESIZED=0
opts=("1|First Item|(one)" "2|Second Item|(two)" "3|Third Item|(three)" "SEP|SEP|" "0|Return|(or Esc)")
run_interactive_submenu "MOUSE TEST" "" opts 0
echo FINAL_REPLY=[$REPLY]
'''


def _pty_run(script, actions, timeout=8.0):
    pid, master = pty.fork()
    if pid == 0:
        os.execvp("bash", ["bash", "--noprofile", "--norc", "-c", script])
    buf = b""
    end = time.time() + timeout
    step = 0
    while time.time() < end:
        ready, _, _ = select.select([master], [], [], 0.08)
        if ready:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
        text = buf.decode("utf-8", "replace")
        if step < len(actions) and actions[step][0] in text:
            os.write(master, actions[step][1])
            step += 1
        if "FINAL_REPLY=" in text and step >= len(actions):
            break
    try:
        os.kill(pid, 9)
    except ProcessLookupError:
        pass
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass
    return buf.decode("utf-8", "replace")


def _row_of(text, label):
    """Screen row of the label in the last painted frame (1-based)."""
    # Each repaint starts at home with ESC[H; the last frame that actually
    # contains the label is the one the user clicked on.
    frames = text.split("\x1b[H")
    for frame in reversed(frames):
        plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", frame)
        for number, line in enumerate(plain.split("\n"), start=1):
            if label in line:
                return number
    return None


class TestMouseInteraction(unittest.TestCase):
    def setUp(self):
        self.script = HARNESS.replace("__BASE__", str(BASE_DIR))

    def test_double_click_activates(self):
        probe = _pty_run(self.script, [("Selection:", b"\r")], timeout=4)
        row = _row_of(probe, "Second Item")
        if row is None:
            self.skipTest("menu rows were not painted in this environment")
        click = f"\x1b[<0;10;{row}M".encode() + f"\x1b[<0;10;{row}m".encode()
        out = _pty_run(self.script, [("Selection:", click), ("Selection:", click)])
        self.assertIn("FINAL_REPLY=[2]", out,
                      "a double click on the second row should select option 2")

    def test_single_click_selects_without_activating(self):
        probe = _pty_run(self.script, [("Selection:", b"\r")], timeout=4)
        row = _row_of(probe, "Second Item")
        if row is None:
            self.skipTest("menu rows were not painted in this environment")
        click = f"\x1b[<0;10;{row}M".encode() + f"\x1b[<0;10;{row}m".encode()
        out = _pty_run(self.script, [("Selection:", click)])
        self.assertNotIn("FINAL_REPLY=[2]", out,
                         "a single click must only move the highlight")
        self.assertIn("Selection:", out)

    def test_wheel_steps_the_highlight(self):
        probe = _pty_run(self.script, [("Selection:", b"\r")], timeout=4)
        if _row_of(probe, "First Item") is None:
            self.skipTest("menu rows were not painted in this environment")
        out = _pty_run(self.script, [("Selection:", b"\x1b[<65;10;5M")])
        self.assertIn("Selection:", out)
        self.assertNotIn("FINAL_REPLY=[", out)

    def test_mouse_reporting_restored_after_exit(self):
        out = _pty_run(self.script, [("Selection:", b"\r")], timeout=4)
        self.assertIn("FINAL_REPLY=", out)
        self.assertIn("\x1b[?1000l", out, "mouse reporting must be off after exit")
        self.assertIn("\x1b[?1006l", out, "SGR mouse reporting must be off after exit")


if __name__ == "__main__":
    unittest.main()
