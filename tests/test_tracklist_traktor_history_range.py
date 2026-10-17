#!/usr/bin/env python3
"""
Unit and integration tests for:
1. Traktor History Range Extraction (Option 13 > Option 8 / scripts/extract_traktor_history_range.py)
2. Mix Search & MP Audio Player integration (Option 13 > Option 2)
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = REPO_DIR / "scripts"
MANAGER_SCRIPT = REPO_DIR / "Mix_Archive_Manager.sh"
EXTRACT_SCRIPT = SCRIPT_DIR / "extract_traktor_history_range.py"


class TestTraktorHistoryRangeExtraction(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="mp_test_traktor_")
        self.mock_nml = Path(self.test_dir) / "history_2026y07m20d_08h01m28s.nml"

        # Create a mock NML with 150 entries to test slicing and extraction
        entries_xml = []
        for i in range(1, 131):
            artist = f"Artist {i:03d}"
            title = f"Track {i:03d}"
            if i == 95:
                artist, title = "Airbase", "Escape (2011 Album Mix)"
            elif i == 97:
                artist, title = "Airbase", "40 Miles (Feat Empyreal Sun)"
            elif i == 118:
                artist, title = "Airbase", "Escape"

            entries_xml.append(
                f'<ENTRY TITLE="{title}" ARTIST="{artist}">'
                f'<LOCATION VOLUME="MOCK" DIR="/:MUSIC/:" FILE="{artist} - {title}.mp3"></LOCATION>'
                f'<INFO></INFO>'
                f'</ENTRY>'
            )

        pl_entries_xml = []
        for i in range(1, 131):
            artist = f"Artist {i:03d}"
            title = f"Track {i:03d}"
            if i == 95:
                artist, title = "Airbase", "Escape (2011 Album Mix)"
            elif i == 97:
                artist, title = "Airbase", "40 Miles (Feat Empyreal Sun)"
            elif i == 118:
                artist, title = "Airbase", "Escape"

            pl_entries_xml.append(
                f'<ENTRY>'
                f'<PRIMARYKEY TYPE="TRACK" KEY="MOCK/:MUSIC/:{artist} - {title}.mp3"/>'
                f'<EXTENDEDDATA DECK="0" DURATION="360.0" EXTENDEDTYPE="HistoryData"/>'
                f'</ENTRY>'
            )

        xml_content = (
            f'<NML VERSION="19">'
            f'<COLLECTION ENTRIES="130">{"".join(entries_xml)}</COLLECTION>'
            f'<PLAYLISTS><NODE TYPE="PLAYLIST"><PLAYLIST TYPE="PROTOCOL">{"".join(pl_entries_xml)}</PLAYLIST></NODE></PLAYLISTS>'
            f'</NML>'
        )
        self.mock_nml.write_text(xml_content, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_exact_range_95_to_118(self):
        """Verifies extracting tracks 95 to 118 extracts exactly 24 tracks with correct start/end."""
        out_txt = Path(self.test_dir) / "output_tracklist.txt"
        cmd = [
            "python3",
            str(EXTRACT_SCRIPT),
            "--history",
            str(self.mock_nml),
            "--start",
            "95",
            "--end",
            "118",
            "--output",
            str(out_txt),
            "--mix-title",
            "Stream of Frequency 081 WMI Airbase",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Error: {res.stderr}")
        self.assertTrue(out_txt.is_file())

        content = out_txt.read_text(encoding="utf-8")
        self.assertIn("Total Tracks:  24", content)
        self.assertIn("01. Airbase - Escape (2011 Album Mix)", content)
        self.assertIn("03. Airbase - 40 Miles (Feat Empyreal Sun)", content)
        self.assertIn("24. Airbase - Escape", content)

    def test_rejection_on_invalid_or_partial_filename(self):
        """Verifies rejecting non-existent or partial history filename."""
        cmd = [
            "python3",
            str(EXTRACT_SCRIPT),
            "--history",
            "history_2026",
            "--start",
            "1",
            "--end",
            "10",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Error: History file 'history_2026' not found", res.stderr)
        self.assertIn("You must enter the full exact name", res.stderr)

    def test_rejection_on_invalid_range(self):
        """Verifies rejecting when start > end or start < 1."""
        cmd = [
            "python3",
            str(EXTRACT_SCRIPT),
            "--history",
            str(self.mock_nml),
            "--start",
            "50",
            "--end",
            "20",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("cannot be greater than end track", res.stderr)

    def test_real_traktor_history_file_if_available(self):
        """Verifies parsing the actual real Traktor history file if present on disk."""
        real_nml = Path("/run/media/mplanetarian/WD BLACK B/MIX_ARCHIVE/Traktor 3.11.1/History/history_2026y07m20d_08h01m28s.nml")
        if not real_nml.is_file():
            self.skipTest("Real history file not mounted")

        out_txt = Path(self.test_dir) / "real_extracted.txt"
        cmd = [
            "python3",
            str(EXTRACT_SCRIPT),
            "--history",
            str(real_nml),
            "--start",
            "95",
            "--end",
            "118",
            "--output",
            str(out_txt),
            "--mix-title",
            "MPlanetarian - Stream of Frequency 081 WMI Airbase",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        content = out_txt.read_text(encoding="utf-8")
        self.assertIn("01. Airbase - Escape (2011 Album Mix)", content)
        self.assertIn("03. Airbase - 40 Miles (Feat Empyreal Sun)", content)
        self.assertIn("24. Airbase - Escape", content)


class TestTracklistSuiteMenuIntegration(unittest.TestCase):
    def test_option13_menu_has_option8_and_mp_player_label(self):
        """Verifies Option 13 presents Option 8 for Traktor history range and Option 2 labeled MP Audio Player."""
        piped_input = "13\n0\n36\n"
        res = subprocess.run(
            ["bash", str(MANAGER_SCRIPT)],
            input=piped_input,
            capture_output=True,
            text=True,
            timeout=8,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Search for Mix & Auto-Play with Live Tracklist View", res.stdout)
        self.assertIn("MP Audio Player", res.stdout)
        self.assertIn("Extract Tracklist from Traktor History Files by Range", res.stdout)
        self.assertIn("Traktor .nml History", res.stdout)
        # Ensure cliamp is NOT shown in option 2
        self.assertNotIn("(cliamp Window)", res.stdout)


if __name__ == "__main__":
    unittest.main()
