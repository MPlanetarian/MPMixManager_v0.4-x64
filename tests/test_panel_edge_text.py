#!/usr/bin/env python3
"""Status lines and long menu rows must end on the header panel's right border."""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _width(text: str) -> int:
    import unicodedata

    total = 0
    for ch in ANSI.sub("", text):
        if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
            continue
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def _run(script: str) -> str:
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.decode("utf-8", "replace")[-2000:])
    return proc.stdout.decode("utf-8", "replace")


class PanelEdgeTextTest(unittest.TestCase):
    def test_header_lines_stop_on_the_panel_border(self):
        script = r"""
        source ./Mix_Archive_Manager.sh >/dev/null 2>&1 || true
        set_theme_colors retro_linux_memories
        _TERM_COLS=120
        _TERM_LINES=40
        MIX_ARCHIVE_CONFIGURED=true
        MIX_ARCHIVE_DIR=/tmp
        _CACHED_OS_BADGE="${BOLD}${CYAN}🐧 OS:${NC} Bazzite Linux 44.20261012.0 (Kinoite) (${BOLD}7.3.0-mplanetarian-dreamworlds-ultra-v1${NC})"
        _CACHED_OS_UPDATE_STATUS="${GREEN}Up to date${NC}"
        _CACHED_INTERNET_STATUS=online
        _CACHED_PERF_DISPLAY="  ${BOLD}${CYAN}⚡ CPU Load:${NC} 1.0  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}🧠 RAM:${NC} 1G/2G  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}💾 Mix Drive Free:${NC} 10G free"
        _CACHED_PLANETS_DISPLAY="  ${BOLD}${CYAN}🪐 Planets:${NC} Venus ♀ (+8° ESE) • Mars ♂ (+54° SSE) • Jupiter ♃ (+52° SSE) • Uranus ♅ (+25° W)  ${DIM}(Above Horizon • Swansea, UK)${NC}"
        _CACHED_ALARM_CLOCK_STATUS="  ${BOLD}${CYAN}⏰ Morning Alarm Clock:${NC} ${GREEN}Armed & Ready${NC}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}🔔 Next Alarm:${NC} ${WHITE}11:00${NC} ${DIM}(Daily, 100% ramp)${NC}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}🎵 Sound:${NC} ${YELLOW}Archive FLAC Mix${NC} ${DIM}(+1 more)${NC}"
        _CACHED_AUDIO_IFACE_DISPLAY="  ${BOLD}${CYAN}🎧 Audio Interface:${NC} Short${NC}"$'\n'"  ${BOLD}${CYAN}⚡ Latency:${NC} ${GREEN}21ms${NC}  ${BOLD}${BLUE}│${NC}  ${BOLD}${CYAN}🎛️ Engine:${NC} PipeWire"
        render_main_header 116 >/dev/null
        printf '%b\n' "$_RENDERED_MAIN_HEADER"
        """
        lines = _run(script).splitlines()
        self.assertGreaterEqual(len(lines), 8)
        edge = 118
        for idx, line in enumerate(lines, 1):
            self.assertLessEqual(_width(line), edge, f"line {idx} passes the header border: {ANSI.sub('', line)}")
        visible = [ANSI.sub("", line) for line in lines]
        self.assertIn("Shell:", visible[3])
        self.assertIn("Network:", visible[3])
        self.assertIn("Bash", visible[3])
        planets = next(line for line in visible if "Planets:" in line)
        alarm = next(line for line in visible if "Morning Alarm Clock:" in line)
        self.assertLessEqual(_width(planets), edge)
        self.assertLessEqual(_width(alarm), edge)
        self.assertIn("Sound:", alarm)

    def test_menu_options_2_and_3_stop_on_the_panel_border(self):
        script = r"""
        source ./Mix_Archive_Manager.sh >/dev/null 2>&1 || true
        edge=118
        fit2=$(_fit_menu_extra "2" "Play Tracks from MUSIC Folders using MP Audio Player" "(Music Library • Local Drives & SMB Shares • Add / Remove Folders)" "$edge")
        fit3=$(_fit_menu_extra "3" "MP Audio Player (Liquid Glass Mode)" "(Liquid glass window • OpenGL [Default - All GPUs] or Vulkan • light theme reflections)" "$edge")
        fit1=$(_fit_menu_extra "1" "Play DJ Mixes (MP Audio Player - Mix Archive Mode)" "(Built-in Player, Custom Animated EQ, FLAC/WAV/MP3)" "$edge")
        printf '2|%s\n' "$fit2"
        printf '3|%s\n' "$fit3"
        printf '1|%s\n' "$fit1"
        """
        rows = {}
        for line in _run(script).splitlines():
            key, extra = line.split("|", 1)
            rows[key] = extra
        labels = {
            "2": "Play Tracks from MUSIC Folders using MP Audio Player",
            "3": "MP Audio Player (Liquid Glass Mode)",
            "1": "Play DJ Mixes (MP Audio Player - Mix Archive Mode)",
        }
        for key, label in labels.items():
            row = f"     [{key:>2}] {label}  {rows[key]}"
            self.assertLessEqual(_width(row), 118, row)
        self.assertIn("...", rows["2"])
        self.assertIn("...", rows["3"])
        self.assertNotIn("...", rows["1"])
        self.assertTrue(rows["1"].endswith("FLAC/WAV/MP3)"))


if __name__ == "__main__":
    unittest.main()
