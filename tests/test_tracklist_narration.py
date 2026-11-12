#!/usr/bin/env python3
"""
Tests for "Read Tracklist Out Loud with MP Harmony Agent"
(Tracklist Suite option 9).

Covers:
- The menu entry exists in the Tracklist Management Suite.
- The narration helper is defined and the module imports cleanly.
- Tracklist parsing and narration cleanup remove agent meta-commentary.
- Stephen Hawking is the default voice and every MP Harmony voice is offered.
- Recordings land in MP_TRACKLISTS_VOICED under the primary MIX_ARCHIVE folder.
"""

import importlib.util
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANAGER = REPO_ROOT / "Mix_Archive_Manager.sh"
NARRATOR = REPO_ROOT / "scripts" / "mp_tracklist_narrator.py"


def load_narrator():
    spec = importlib.util.spec_from_file_location("mp_tracklist_narrator", NARRATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTracklistNarrationMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = MANAGER.read_text(encoding="utf-8", errors="replace")
        start = cls.suite.index("manage_tracklist_suite() {")
        cls.suite_body = cls.suite[start:start + 6000]

    def test_menu_offers_read_out_loud_option(self):
        self.assertRegex(
            self.suite_body,
            r'"9\|Read Tracklist Out Loud with MP Harmony Agent',
        )

    def test_menu_option_is_routed(self):
        self.assertIn("9|narrate|read-aloud|read-aloud-tracklist|tts) narrate_tracklist_with_harmony", self.suite_body)

    def test_narrator_helper_is_defined_at_top_level(self):
        self.assertRegex(self.suite, r"(?m)^narrate_tracklist_with_harmony\(\) \{")
        self.assertRegex(self.suite, r"(?m)^_collect_narrator_tracklists\(\) \{")

    def test_helper_uses_primary_archive_voiced_folder(self):
        start = self.suite.index("narrate_tracklist_with_harmony() {")
        body = self.suite[start:start + 7000]
        self.assertIn("MP_TRACKLISTS_VOICED", body)
        self.assertIn('${MIX_ARCHIVE_DIR:-$SCRIPT_DIR/MIX_ARCHIVE}', body)

    def test_script_syntax_is_valid(self):
        res = subprocess.run(["bash", "-n", str(MANAGER)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)


class TestTracklistNarratorModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = load_narrator()

    def test_default_voice_is_stephen_hawking(self):
        self.assertEqual(self.n.DEFAULT_VOICE, "stephen_hawking_matrix")
        self.assertIn("stephen_hawking_matrix", self.n.VOICE_IDS)

    def test_all_harmony_voices_are_available(self):
        expected = {
            "morpheus", "morpheus_construct", "morpheus_redpill", "morpheus_dojo",
            "morpheus_system", "agent_smith", "neo", "trinity", "oracle", "zion",
            "stephen_hawking_matrix",
        }
        self.assertEqual(expected, self.n.VOICE_IDS)

    def test_voice_listing_marks_hawking_default(self):
        res = subprocess.run(
            [sys.executable, str(NARRATOR), "--list-voices"],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("stephen_hawking_matrix", res.stdout)
        self.assertIn("(default)", res.stdout)

    def test_tracklist_entries_are_parsed(self):
        text = (
            "RELEASE INFO\nTitle: Stream of Frequency 137\nArtist: MPlanetarian\n"
            "=== TRACKLIST ===\n"
            "01. Above & Beyond - Sun & Moon\n"
            "02. Armin van Buuren - Blue Fear\n"
        )
        self.assertEqual(
            self.n.track_entries(text),
            ["Above & Beyond - Sun & Moon", "Armin van Buuren - Blue Fear"],
        )
        self.assertEqual(self.n.release_info(text), ("Stream of Frequency 137", "MPlanetarian"))

    def test_clean_narration_drops_agent_boilerplate(self):
        raw = (
            "No tools were invoked. The requested podcast narration is: "
            "Welcome to Stream of Frequency 137. First, Above & Beyond with Sun & Moon. "
            "Thanks for listening."
        )
        cleaned = self.n.clean_narration(raw)
        self.assertTrue(cleaned.startswith("Welcome to Stream of Frequency 137."))
        self.assertNotIn("No tools were invoked", cleaned)
        self.assertNotIn("The requested", cleaned)

    def test_clean_narration_strips_markers_and_markdown(self):
        raw = "<<<NARRATION>>>**Welcome** to the mix. Track one, Artist, Title.<<<END>>>"
        cleaned = self.n.clean_narration(raw)
        self.assertEqual(cleaned, "Welcome to the mix. Track one, Artist, Title.")

    def test_narration_validation_rejects_summaries(self):
        entries = ["Above & Beyond - Sun & Moon", "Armin van Buuren - Blue Fear"]
        summary = (
            "I reviewed the supplied tracklist and produced the requested TTS narration. "
            "It welcomes listeners and reads the sole listed track. No tools were used."
        )
        self.assertFalse(self.n.looks_like_narration(self.n.clean_narration(summary), entries))

    def test_fallback_narration_reads_every_track(self):
        text = (
            "Title: Stream of Frequency 137\nArtist: MPlanetarian\n"
            "01. Above & Beyond - Sun & Moon\n"
            "02. Armin van Buuren - Blue Fear\n"
        )
        narration = self.n.fallback_narration(text, "Stream of Frequency 137")
        self.assertIn("Stream of Frequency 137", narration)
        self.assertIn("Above & Beyond", narration)
        self.assertIn("Armin van Buuren", narration)
        self.assertIn("Track 2", narration)

    def test_long_narration_splits_for_tts(self):
        narration = ". ".join(f"Track {i} Artist and Title" for i in range(1, 400)) + "."
        chunks = self.n.split_for_tts(narration, limit=1200)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks).replace("  ", " "), narration.replace("  ", " "))

    def test_voiced_folder_name(self):
        self.assertEqual(self.n.VOICED_FOLDER, "MP_TRACKLISTS_VOICED")

    def test_archive_root_walk_up_from_flac_folder(self):
        base = Path("/tmp/opencode/narr_root_test")
        flac = base / "FLAC_CONVERTED_OUTPUTS"
        flac.mkdir(parents=True, exist_ok=True)
        self.assertEqual(self.n.resolve_archive_root(flac / "Mix.txt"), base)

    def test_slugify_keeps_readable_file_names(self):
        self.assertEqual(
            self.n.slugify("Stream of Frequency 137 (Strange Conspiracy Part 3)"),
            "Stream_of_Frequency_137_Strange_Conspiracy_Part_3",
        )


class TestTracklistNarrationIntegration(unittest.TestCase):
    """Live check against the running MP Harmony Agent; skipped when it is offline."""

    def setUp(self):
        n = load_narrator()
        self.n = n
        self.base = n.harmony_base_url()
        if not n.harmony_is_up(self.base):
            self.skipTest("MP Harmony Agent is not running on port 11435")

    def test_speech_endpoint_returns_hawking_wav(self):
        audio = self.n.synthesize_via_agent(
            self.base, "Tracklist narration smoke test.", "stephen_hawking_matrix", 1.0
        )
        self.assertTrue(audio.startswith(b"RIFF"), "expected WAV audio bytes")
        self.assertGreater(len(audio), 1000)


if __name__ == "__main__":
    unittest.main()
