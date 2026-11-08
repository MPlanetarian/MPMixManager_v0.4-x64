#!/usr/bin/env python3
"""Latency on the MP Gui status strip must not stay on the audio-interface row."""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANAGER = ROOT / "Mix_Archive_Manager.sh"

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _visible(line: str) -> str:
    return ANSI.sub("", line)


def _width(line: str) -> int:
    n = 0
    for ch in _visible(line):
        o = ord(ch)
        wide = (
            0x1100 <= o <= 0x115F
            or 0x2E80 <= o <= 0xA4CF
            or 0x1F300 <= o <= 0x1FAFF
            or 0x2600 <= o <= 0x27BF
        )
        n += 2 if wide else 1
    return n


def _reflow(raw: str) -> str:
    text = MANAGER.read_text(encoding="utf-8")
    start = text.index("_reflow_audio_iface_display() {")
    end = text.index("\nget_active_audio_interface_display() {", start)
    fn = text[start:end]
    script = f"""
{fn}
BOLD=$'\\033[1m'
CYAN=$'\\033[38;2;0;193;228m'
NC=$'\\033[0m'
_CACHED_AUDIO_IFACE_DISPLAY=$(cat)
_reflow_audio_iface_display
printf '%s' "$_CACHED_AUDIO_IFACE_DISPLAY"
"""
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        input=raw.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.decode())
    return proc.stdout.decode()


class AudioIfaceHeaderReflowTest(unittest.TestCase):
    def test_manager_reflows_before_drawing_and_after_cache_load(self):
        text = MANAGER.read_text(encoding="utf-8")
        self.assertIn("_reflow_audio_iface_display;", text)
        load = text.split("load_header_cache() {", 1)[1].split("\n}", 1)[0]
        self.assertIn("_reflow_audio_iface_display", load)

    def test_one_line_cache_moves_latency_to_the_next_line(self):
        # The live header cache is this shape: one row, Latency on the right.
        raw = (
            "  \033[1m\033[38;2;0;193;228m🎧 Audio Interface:\033[0m "
            "GA102 High Definition Audio Controller Digital Stereo "
            "(HDMI - HISENSE) [BenQ G2400W]\033[0m  "
            "\033[1m\033[38;2;102;102;255m│\033[0m  "
            "\033[1m\033[38;2;0;193;228m⚡ Latency:\033[0m "
            "\033[38;2;0;229;255m21.3ms (1024 @ 48kHz)\033[0m  "
            "\033[1m\033[38;2;102;102;255m│\033[0m  "
            "\033[1m\033[38;2;0;193;228m🎛️ Engine:\033[0m PipeWire"
        )
        out = _reflow(raw)
        lines = out.split("\n")
        self.assertGreaterEqual(len(lines), 2)
        self.assertNotIn("Latency", _visible(lines[0]))
        self.assertIn("Audio Interface", _visible(lines[0]))
        self.assertIn("GA102", _visible(lines[0]))
        self.assertTrue(lines[1].startswith("  "))
        self.assertIn("Latency:", _visible(lines[1]))
        self.assertIn("21.3ms", _visible(lines[1]))
        self.assertIn("Engine:", _visible(lines[1]))
        self.assertLess(_width(lines[1]), 80)
        again = _reflow(out)
        self.assertEqual(again.split("\n")[0], lines[0])
        self.assertIn("Latency:", _visible(again.split("\n")[1]))

    def test_literal_cache_escapes_move_latency_off_the_interface_row(self):
        raw = (
            r"  \033[1m\033[38;2;91;134;187m🎧 Audio Interface:\033[0m "
            r"GA102 High Definition Audio Controller Digital Stereo "
            r"(HDMI - HISENSE) [BenQ G2400W]\033[0m  "
            r"\033[1m\033[38;2;21;83;158m│\033[0m  "
            r"\033[1m\033[38;2;91;134;187m⚡ Latency:\033[0m "
            r"\033[38;2;92;184;92m21.3ms (1024 @ 48kHz)\033[0m  "
            r"\033[1m\033[38;2;21;83;158m│\033[0m  "
            r"\033[1m\033[38;2;91;134;187m🎛️ Engine:\033[0m PipeWire"
        )
        out = _reflow(raw)
        lines = out.split("\n")
        self.assertGreaterEqual(len(lines), 2)
        self.assertNotIn("Latency", lines[0])
        self.assertIn("Latency:", lines[1])
        self.assertIn("Engine:", lines[1])


if __name__ == "__main__":
    unittest.main()
