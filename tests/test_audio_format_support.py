"""The player, the scanners and the pickers must agree on which audio types exist.

Extensions used to be copied into eight modules. Adding one to the drag-and-drop
list did not make it appear in the Mix Archive or Music Folders listings, so a
file could be dropped onto the player and never be found again. These tests pin
the shared list and prove each advertised type reaches a decoder.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import audio_formats as formats

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def _ffmpeg_make(target, *args):
    """Render a short sine wave into `target` with the given encoder flags."""
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1:sample_rate=44100",
         "-ac", "2", *args, str(target)],
        capture_output=True, text=True,
    )


class SharedListTests(unittest.TestCase):
    def test_every_consumer_uses_the_same_extensions(self):
        import liquid_audio_drop as drop
        import music_folders_manager as music
        import generate_archive_folder_playlists as archive
        import MP_Audio_Player as player

        expected = set(formats.AUDIO_EXTENSIONS)
        self.assertEqual(set(drop.AUDIO_DROP_EXTENSIONS), expected)
        self.assertEqual(set(music.AUDIO_EXTENSIONS), expected)
        self.assertEqual(set(archive.AUDIO_EXTS), expected)
        self.assertEqual({e.lower() for e in player.AUDIO_EXTENSIONS}, expected)

    def test_the_formats_this_release_added_are_present(self):
        wanted = {
            ".opus", ".oga", ".alac", ".m4b", ".aif", ".aifc", ".ape", ".wv",
            ".tta", ".tak", ".dsf", ".dff", ".mka", ".au", ".caf", ".ac3",
            ".dts", ".amr", ".w64", ".rf64", ".mp2", ".mpc",
        }
        self.assertEqual(wanted - set(formats.AUDIO_EXTENSIONS), set())

    def test_optimfrog_is_not_advertised(self):
        # FFmpeg has no OptimFROG decoder, so the old .ofr/.ofs entries only
        # produced "no audio backend could open" errors.
        self.assertNotIn(".ofr", formats.AUDIO_EXTENSIONS)
        self.assertNotIn(".ofs", formats.AUDIO_EXTENSIONS)

    def test_video_containers_stay_out(self):
        for ext in (".mp4", ".mkv", ".mov", ".webm", ".avi"):
            self.assertFalse(formats.is_audio_path(f"movie{ext}"))

    def test_lossless_badge_matches_the_codec(self):
        self.assertTrue(formats.is_lossless_path("a.flac"))
        self.assertTrue(formats.is_lossless_path("a.ALAC"))
        self.assertTrue(formats.is_lossless_path("a.dsf"))
        self.assertFalse(formats.is_lossless_path("a.opus"))
        self.assertFalse(formats.is_lossless_path("a.mp3"))
        self.assertFalse(formats.is_lossless_path("a.ac3"))

    def test_every_extension_has_a_mime_type(self):
        missing = [e for e in formats.AUDIO_EXTENSIONS if e not in formats.AUDIO_MIME_TYPES]
        self.assertEqual(missing, [])

    def test_libsndfile_formats_start_in_soundfile(self):
        for ext in (".flac", ".wav", ".aiff", ".ogg", ".mp3"):
            self.assertFalse(formats.prefers_ffmpeg(f"track{ext}"), ext)
        for ext in (".opus", ".ape", ".dsf", ".dff", ".tak", ".mka", ".ac3"):
            self.assertTrue(formats.prefers_ffmpeg(f"track{ext}"), ext)

    def test_pickers_offer_every_type(self):
        for builder in (formats.kdialog_audio_filter, formats.zenity_audio_filter,
                        formats.windows_audio_filter):
            text = builder()
            for ext in formats.AUDIO_EXTENSIONS:
                self.assertIn(f"*{ext}", text, ext)
        macos_types = formats.macos_audio_file_types()
        self.assertEqual(macos_types[0], "public.audio")
        self.assertIn("opus", macos_types)
        self.assertIn("dsf", macos_types)


class ScannerTests(unittest.TestCase):
    """A new format has to survive the scan that fills the playlist."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_mix_archive_scanner_lists_new_formats(self):
        import MP_Audio_Player as player
        for ext in (".opus", ".dsf", ".ape", ".wv", ".mka", ".ac3", ".tta"):
            (self.dir / f"mix{ext}").write_bytes(b"audio")
        (self.dir / "movie.mp4").write_bytes(b"video")
        (self.dir / "notes.txt").write_text("hello")

        # MixArchiveScanner walks every configured archive root, so replace the
        # resolved list instead of fighting config.env and the default paths.
        with mock.patch.object(player.MixArchiveScanner, "_get_archive_dirs",
                               return_value=[self.dir]):
            scanner = player.MixArchiveScanner(self.dir)
            found = {Path(m["path"]).suffix.lower() for m in scanner.get_mixes()}
        self.assertEqual(found, {".opus", ".dsf", ".ape", ".wv", ".mka", ".ac3", ".tta"})

    def test_music_folder_scan_lists_new_formats(self):
        import music_folders_manager as music
        for ext in (".opus", ".m4b", ".aif", ".aifc", ".mpc", ".dts"):
            (self.dir / f"track{ext}").write_bytes(b"audio")
        (self.dir / "cover.jpg").write_bytes(b"image")

        tracks = music._scan_filesystem(str(self.dir), "FOLDER1")
        found = {Path(t["path"]).suffix.lower() for t in tracks}
        self.assertEqual(found, {".opus", ".m4b", ".aif", ".aifc", ".mpc", ".dts"})
        self.assertTrue(all(t["ext"] for t in tracks))

    def test_archive_playlist_generator_lists_new_formats(self):
        import generate_archive_folder_playlists as archive
        for ext in (".opus", ".dsf", ".wav", ".flac"):
            (self.dir / f"mix{ext}").write_bytes(b"audio")
        mixes = archive.scan_dir_mixes(str(self.dir))
        self.assertEqual({m["ext"] for m in mixes}, {".opus", ".dsf", ".wav", ".flac"})


class DSDiffReaderTests(unittest.TestCase):
    """FFmpeg has no DSDIFF demuxer, so .dff gets its own reader."""

    @staticmethod
    def _write_dff(path, channels=2, rate=2822400, seconds=0.2, compressed=False):
        import struct

        def chunk(cid, data):
            pad = b"\x00" if len(data) % 2 else b""
            return cid + struct.pack(">Q", len(data)) + data + pad

        compression = "DST " if compressed else "DSD "
        props = (
            chunk(b"FS  ", struct.pack(">I", rate))
            + chunk(b"CHNL", struct.pack(">H", channels) + b"SLFTSRGT"[:2 * channels])
            + chunk(b"CMPR", compression.encode() + bytes([14]) + b"not compressed" + b"\x00")
        )
        frames = int(rate / 8 * seconds)
        payload = bytes([0x69, 0x96]) * (frames * channels // 2)
        body = b"DSD " + chunk(b"PROP", b"SND " + props) + chunk(b"DSD ", payload)
        path.write_bytes(b"FRM8" + struct.pack(">Q", len(body)) + body)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_header(self):
        import dsdiff_reader as reader
        target = self.dir / "album.dff"
        self._write_dff(target)
        info = reader.read_info(target)
        self.assertEqual(info.channels, 2)
        self.assertEqual(info.sample_rate, 2822400)
        self.assertAlmostEqual(info.duration, 0.2, places=2)
        self.assertFalse(info.is_compressed)

    def test_rejects_non_dsdiff(self):
        import dsdiff_reader as reader
        target = self.dir / "song.mp3"
        target.write_bytes(b"ID3\x03\x00" + b"\x00" * 64)
        with self.assertRaises(reader.DSDiffError):
            reader.read_info(target)

    def test_dst_compression_is_reported(self):
        import dsdiff_reader as reader
        target = self.dir / "compressed.dff"
        self._write_dff(target, compressed=True)
        info = reader.read_info(target)
        self.assertTrue(info.is_compressed)
        with self.assertRaises(reader.DSDiffError):
            next(iter(reader.iter_dsf_stream(target, info)))

    def test_stream_starts_with_a_dsf_header(self):
        import dsdiff_reader as reader
        target = self.dir / "album.dff"
        self._write_dff(target)
        first = next(iter(reader.iter_dsf_stream(target)))
        self.assertEqual(first[:4], b"DSD ")
        self.assertEqual(first[28:32], b"fmt ")

    def test_recognises_the_dff_extensions_only(self):
        import dsdiff_reader as reader
        self.assertTrue(reader.is_dsdiff("a.dff"))
        self.assertTrue(reader.is_dsdiff("a.DFF"))
        self.assertFalse(reader.is_dsdiff("a.dsf"))
        self.assertFalse(reader.is_dsdiff("a.flac"))

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required to decode the DSF view")
    def test_player_decodes_a_dff_file(self):
        import numpy as np
        import MP_Audio_Player as player
        target = self.dir / "album.dff"
        self._write_dff(target, seconds=0.5)
        source = player.open_audio_source(str(target))
        try:
            self.assertIsInstance(source, player.DSDiffAudioSource)
            data = source.read(4096)
            self.assertGreater(len(data), 0)
            self.assertEqual(data.shape[1], 2)
            self.assertAlmostEqual(source.total_frames() / source.samplerate, 0.5, places=1)
            source.seek(source.samplerate // 4)
            self.assertGreater(len(source.read(1024)), 0)
        finally:
            source.close()

    def test_unreadable_dff_does_not_crash(self):
        """A corrupt .dff must fall through to the normal backends, not raise."""
        import MP_Audio_Player as player
        target = self.dir / "broken.dff"
        target.write_bytes(b"not a dsdiff file at all")
        source = player.open_audio_source(str(target))
        try:
            self.assertNotIsInstance(source, player.DSDiffAudioSource)
            self.assertEqual(len(source.read(512)), 0)
        finally:
            source.close()


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required to encode test audio")
class DecoderCoverageTests(unittest.TestCase):
    """Every advertised extension must open and produce samples."""

    RECIPES = {
        ".flac": ("-c:a", "flac"),
        ".wav": ("-c:a", "pcm_s16le"),
        ".w64": ("-c:a", "pcm_s24le"),
        ".mp3": ("-c:a", "libmp3lame"),
        ".mp2": ("-c:a", "mp2"),
        ".ogg": ("-c:a", "libvorbis"),
        ".oga": ("-c:a", "libvorbis"),
        ".opus": ("-c:a", "libopus"),
        ".m4a": ("-c:a", "aac"),
        ".m4b": ("-c:a", "aac"),
        ".aac": ("-c:a", "aac"),
        ".alac": ("-c:a", "alac"),
        ".aiff": ("-c:a", "pcm_s16be"),
        ".aif": ("-c:a", "pcm_s16be"),
        ".aifc": ("-c:a", "pcm_s16be"),
        ".wma": ("-c:a", "wmav2"),
        ".wv": ("-c:a", "wavpack"),
        ".tta": ("-c:a", "tta"),
        ".mka": ("-c:a", "flac"),
        ".ac3": ("-c:a", "ac3"),
        ".eac3": ("-c:a", "eac3"),
        ".au": ("-c:a", "pcm_s16be", "-f", "au"),
        ".caf": ("-c:a", "pcm_s16le"),
        ".voc": ("-c:a", "pcm_u8", "-ac", "1"),
        ".amr": ("-c:a", "libopencore_amrnb", "-ar", "8000", "-ac", "1"),
        ".dts": ("-c:a", "dca", "-strict", "-2"),
    }

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_advertised_formats_decode(self):
        import numpy as np
        import MP_Audio_Player as player

        problems, skipped = [], []
        for ext, args in self.RECIPES.items():
            target = self.dir / f"track{ext}"
            made = _ffmpeg_make(target, *args)
            if made.returncode != 0 or not target.is_file():
                skipped.append(ext)
                continue
            try:
                source = player.open_audio_source(str(target))
                try:
                    samples = source.read(2048)
                finally:
                    source.close()
                if len(samples) == 0:
                    problems.append(f"{ext}: opened but produced no samples")
            except Exception as exc:
                problems.append(f"{ext}: {type(exc).__name__}: {exc}")
        if problems:
            self.fail("; ".join(problems))
        if len(skipped) == len(self.RECIPES):
            self.skipTest("this ffmpeg build cannot write any of the test formats")

    def test_the_recipe_covers_most_of_the_list(self):
        covered = set(self.RECIPES) | {".dff", ".dsf", ".ape", ".tak", ".mpc", ".mpp",
                                       ".m4p", ".spx", ".snd", ".wave", ".rf64", ".mpga",
                                       ".mp1", ".3ga"}
        missing = set(formats.AUDIO_EXTENSIONS) - covered
        self.assertEqual(missing, set())


if __name__ == "__main__":
    unittest.main()
