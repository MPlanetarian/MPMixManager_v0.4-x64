#!/usr/bin/env python3
"""
Unit tests for find_duplicate_mixes.py
Tests fingerprint hashing, episode matching, quarantine logic, and safe deletion.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.find_duplicate_mixes import (
    fast_audio_hash,
    extract_episode_id,
    format_size,
    scan_for_duplicates,
    handle_duplicates,
)


class TestFindDuplicateMixes(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="mp_test_dups_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_format_size(self):
        self.assertEqual(format_size(512), "512.00 B")
        self.assertEqual(format_size(1024), "1.00 KB")
        self.assertEqual(format_size(1024 * 1024 * 2.5), "2.50 MB")
        self.assertEqual(format_size(1024 * 1024 * 1024 * 4), "4.00 GB")

    def test_extract_episode_id(self):
        self.assertEqual(extract_episode_id("State_of_Frequency_042.wav"), "Episode_042")
        self.assertEqual(extract_episode_id("SOF-007_Master.flac"), "Episode_007")
        self.assertEqual(extract_episode_id("Mix 031 Remaster.mp3"), "Episode_031")
        self.assertEqual(extract_episode_id("Frequency_099.aiff"), "Episode_099")
        self.assertEqual(extract_episode_id("Show_123_Live.wav"), "Episode_123")
        self.assertIsNone(extract_episode_id("ambient_loop_nomatch.wav"))

    def test_fast_audio_hash_consistency(self):
        sample_path = os.path.join(self.test_dir, "sample.wav")
        payload = b"RIFF" + b"\x55" * 100000
        with open(sample_path, "wb") as f:
            f.write(payload)

        h1, s1 = fast_audio_hash(sample_path)
        h2, s2 = fast_audio_hash(sample_path)
        self.assertEqual(h1, h2)
        self.assertEqual(s1, len(payload))
        self.assertIsNotNone(h1)

    def test_scan_for_duplicates_exact(self):
        orig = os.path.join(self.test_dir, "Mix_042.flac")
        copy = os.path.join(self.test_dir, "Mix_042_copy.flac")
        diff = os.path.join(self.test_dir, "Mix_043.flac")

        with open(orig, "wb") as f:
            f.write(b"fLaC" + b"\x01" * 8192)
        shutil.copyfile(orig, copy)
        with open(diff, "wb") as f:
            f.write(b"fLaC" + b"\x02" * 8192)

        exact_dups, _ = scan_for_duplicates([self.test_dir])
        self.assertEqual(len(exact_dups), 1)
        self.assertEqual(len(exact_dups[0]), 2)
        # Verify canonical sorting (shorter name Mix_042.flac is index 0)
        self.assertEqual(exact_dups[0][0], orig)
        self.assertEqual(exact_dups[0][1], copy)

    def test_scan_for_duplicates_episode_multi_render(self):
        r1 = os.path.join(self.test_dir, "SOF_031_renderA.wav")
        r2 = os.path.join(self.test_dir, "SOF_031_renderB.wav")

        with open(r1, "wb") as f:
            f.write(b"RIFF" + b"\xAA" * 5000)
        with open(r2, "wb") as f:
            f.write(b"RIFF" + b"\xBB" * 5000)

        exact_dups, ep_dups = scan_for_duplicates([self.test_dir])
        self.assertEqual(len(exact_dups), 0)
        self.assertEqual(len(ep_dups), 1)
        self.assertEqual(len(ep_dups[0]), 2)

    def test_handle_duplicates_quarantine(self):
        orig = os.path.join(self.test_dir, "SOF_001.flac")
        copy1 = os.path.join(self.test_dir, "SOF_001_copy1.flac")
        copy2 = os.path.join(self.test_dir, "SOF_001_copy2.flac")

        with open(orig, "wb") as f:
            f.write(b"fLaC" + b"\x10" * 4096)
        shutil.copyfile(orig, copy1)
        shutil.copyfile(orig, copy2)

        exact_dups, _ = scan_for_duplicates([self.test_dir])
        quarantine_dir = os.path.join(self.test_dir, "QUARANTINE")

        count = handle_duplicates(exact_dups, action="quarantine", quarantine_dir=quarantine_dir)
        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(orig))
        self.assertFalse(os.path.exists(copy1))
        self.assertFalse(os.path.exists(copy2))
        self.assertEqual(len(os.listdir(quarantine_dir)), 2)

    def test_handle_duplicates_delete(self):
        orig = os.path.join(self.test_dir, "Track_A.mp3")
        copy = os.path.join(self.test_dir, "Track_A_copy.mp3")

        with open(orig, "wb") as f:
            f.write(b"ID3" + b"\x00" * 2048)
        shutil.copyfile(orig, copy)

        exact_dups, _ = scan_for_duplicates([self.test_dir])

        # Test cancellation
        with patch("builtins.input", return_value="NO"):
            c = handle_duplicates(exact_dups, action="delete")
            self.assertEqual(c, 0)
            self.assertTrue(os.path.exists(orig))
            self.assertTrue(os.path.exists(copy))

        # Test confirmation
        with patch("builtins.input", return_value="DELETE"):
            c = handle_duplicates(exact_dups, action="delete")
            self.assertEqual(c, 1)
            self.assertTrue(os.path.exists(orig))
            self.assertFalse(os.path.exists(copy))


if __name__ == "__main__":
    unittest.main()
