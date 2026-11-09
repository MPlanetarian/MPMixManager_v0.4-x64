#!/usr/bin/env python3
"""A configured mix archive is played ahead of the bundled sample track."""

import unittest

import MP_Audio_Player as player


class MixArchiveLatestTests(unittest.TestCase):
    def test_latest_mix_skips_bundled_sample_when_archive_has_mixes(self):
        scanner = player.MixArchiveScanner.__new__(player.MixArchiveScanner)
        sample = str(player.get_base_dir() / "MP_SAMPLES" / "sample.flac")
        archive = r"B:\MIX_ARCHIVE\FLAC_CONVERTED_OUTPUTS\new_mix.flac"
        scanner.mixes = [
            {"path": sample, "name": "sample"},
            {"path": archive, "name": "archive"},
        ]
        self.assertEqual(scanner.get_latest_mix()["path"], archive)

    def test_latest_mix_uses_sample_when_that_is_the_only_track(self):
        scanner = player.MixArchiveScanner.__new__(player.MixArchiveScanner)
        sample = str(player.get_base_dir() / "MP_SAMPLES" / "sample.flac")
        scanner.mixes = [{"path": sample, "name": "sample"}]
        self.assertEqual(scanner.get_latest_mix()["name"], "sample")

    def test_empty_archive_has_no_latest_mix(self):
        scanner = player.MixArchiveScanner.__new__(player.MixArchiveScanner)
        scanner.mixes = []
        self.assertIsNone(scanner.get_latest_mix())


if __name__ == "__main__":
    unittest.main()
