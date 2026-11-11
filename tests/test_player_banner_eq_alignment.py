#!/usr/bin/env python3
"""The mini EQ keeps a fixed 8-column slot in the player banner.

mp_player_state.json once stored the EQ as JSON \\uXXXX escapes. Bash counted
each escape as six characters, so the banner padded for a shorter row and the
Controls text drifted. The field is now decoded and padded to a fixed width,
which keeps every banner row on the panel's right border.
"""

import subprocess
import unittest
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "Mix_Archive_Manager.sh"


def _width(text: str) -> int:
    return sum(
        0 if unicodedata.combining(c) else (2 if unicodedata.east_asian_width(c) in ("W", "F") else 1)
        for c in text
    )


def _run(script: str) -> str:
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", script],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return proc.stdout


class MiniEqFieldTest(unittest.TestCase):
    def test_json_escapes_decode_to_single_glyphs(self):
        out = _run(
            r"""
            eval "$(sed -n '/^_json_decode() {/,/^}/p' Mix_Archive_Manager.sh)"
            _json_decode '\u2581\u2586\u2584 \u2581   '
            """
        )
        self.assertEqual(out, "\u2581\u2586\u2584 \u2581   ")

    def test_surrogate_pair_decodes_to_one_glyph(self):
        out = _run(
            r"""
            eval "$(sed -n '/^_json_decode() {/,/^}/p' Mix_Archive_Manager.sh)"
            _json_decode '\ud83c\udfa7 Music'
            """
        )
        self.assertEqual(out, "\U0001f3a7 Music")

    def test_escaped_and_plain_json_decode_alike(self):
        out = _run(
            r"""
            eval "$(sed -n '/^_json_decode() {/,/^}/p' Mix_Archive_Manager.sh)"
            _json_decode 'C:\\Users\\new'
            """
        )
        self.assertEqual(out, "C:\\Users\\new")

    def test_eq_field_is_always_eight_columns(self):
        cases = [
            r"\u2581\u2586\u2584 \u2581   ",
            "",
            "        ",
            r"\u2581\u2581\u2581\u2581\u2581\u2581\u2581\u2581",
            r"\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588",
            r"\u2013 Caf\u00e9 \u2764",
            "plain",
        ]
        script = (
            'eval "$(sed -n \'/^_json_decode() {/,/^}/p\' Mix_Archive_Manager.sh)"\n'
            "MP_PLAYER_EQ_COLS=8\n"
            'eval "$(sed -n \'/^_mp_player_eq_field() {/,/^}/p\' Mix_Archive_Manager.sh)"\n'
            "raws=(" + " ".join(f"'{c}'" for c in cases) + ")\n"
            'for raw in "${raws[@]}"; do printf "%s|" "$(_mp_player_eq_field "$raw")"; done\n'
        )
        fields = _run(script).rstrip("\n").split("|")[:-1]
        self.assertEqual(len(fields), len(cases))
        for raw, field in zip(cases, fields):
            self.assertEqual(_width(field), 8, f"raw={raw!r} field={field!r}")

    def test_eq_field_never_keeps_raw_escapes(self):
        out = _run(
            r"""
            eval "$(sed -n '/^_json_decode() {/,/^}/p' Mix_Archive_Manager.sh)"
            MP_PLAYER_EQ_COLS=8
            eval "$(sed -n '/^_mp_player_eq_field() {/,/^}/p' Mix_Archive_Manager.sh)"
            _mp_player_eq_field '\u2581\u2586\u2584 \u2581   '
            """
        )
        self.assertNotIn("\\u", out)
        self.assertNotIn("\\U", out)


class BannerStateTest(unittest.TestCase):
    def test_state_reader_decodes_title_and_eq(self):
        """A JSON-escaped state file still yields real glyphs and 8 EQ columns."""
        out = _run(
            r"""
            export HOME="$(mktemp -d)"
            mkdir -p "$HOME/.config/mix-manager"
            python3 - "$HOME/.config/mix-manager/mp_player_state.json" <<'PY'
import json, sys
json.dump({
    "running": True, "state": "playing", "path": "/tmp/x.flac", "pid": 0,
    "title": "Caf\u00e9 \u2014 Sunrise.flac", "mini_eq": "\u2581\u2586\u2584 \u2581   ",
}, open(sys.argv[1], "w", encoding="utf-8"))
PY
            _CACHED_PLAYER_CHECK_TIME=-10
            _CACHED_PLAYER_ACTIVE_RES=1
            eval "$(sed -n '/^_json_decode() {/,/^}/p' Mix_Archive_Manager.sh)"
            MP_PLAYER_EQ_COLS=8
            eval "$(sed -n '/^_mp_player_eq_field() {/,/^}/p' Mix_Archive_Manager.sh)"
            eval "$(sed -n '/^get_mp_audio_player_track_info() {/,/^}/p' Mix_Archive_Manager.sh)"
            is_system_pid_alive() { return 0; }
            get_mp_audio_player_track_info || true
            printf 'TITLE=%s\n' "$MP_PLAYER_TITLE"
            printf 'EQ=%s\n' "$MP_PLAYER_MINI_EQ"
            rm -rf "$HOME"
            """
        )
        rows = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        self.assertEqual(rows["TITLE"], "Caf\u00e9 \u2014 Sunrise.flac")
        self.assertEqual(rows["EQ"], "\u2581\u2586\u2584 \u2581   ")
        self.assertEqual(_width(rows["EQ"]), 8)

    def test_player_writes_real_utf8_state(self):
        text = (ROOT / "MP_Audio_Player.py").read_text(encoding="utf-8")
        self.assertIn("ensure_ascii=False", text)


if __name__ == "__main__":
    unittest.main()
