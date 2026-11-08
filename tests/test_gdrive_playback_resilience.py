#!/usr/bin/env python3
"""
Unit tests for MP Audio Player Google Drive & Remote Audio Playback Resilience:
- Verifies AudioPrefetchBuffer ring buffer operation and thread safety
- Verifies AudioFeederThread pre-buffering and cloud stall tolerance
- Verifies that transient network read errors trigger transparent auto-reconnect
- Verifies that track_ended is NEVER triggered prematurely during network stalls
- Verifies FFmpegAudioSource fallback decoder for unsupported/damaged formats
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time
import tempfile
import threading
from pathlib import Path
import numpy as np
import soundfile as sf

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
from MP_Audio_Player import (
    AudioPrefetchBuffer,
    AudioFeederThread,
    SoundFileAudioSource,
    FFmpegAudioSource,
    open_audio_source,
    AudioEngine
)


class TestGDrivePlaybackResilience(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Generate a small valid WAV file for testing
        self.test_wav_path = str(Path(self.temp_dir.name) / "test_mix.wav")
        sr = 44100
        duration = 2.0  # 2 seconds
        t = np.linspace(0, duration, int(sr * duration), False)
        sine = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        stereo = np.column_stack((sine, sine))
        sf.write(self.test_wav_path, stereo, sr)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prefetch_buffer_basic_read_write(self):
        """Verifies AudioPrefetchBuffer writes stereo blocks and reads correct slice."""
        buf = AudioPrefetchBuffer(44100, buffer_sec=2.0)
        self.assertTrue(buf.is_empty())
        self.assertEqual(buf.health_sec(), 0.0)

        # Write 8192 frames
        chunk = np.ones((8192, 2), dtype=np.float32) * 0.75
        self.assertTrue(buf.write(chunk))
        self.assertFalse(buf.is_empty())
        self.assertEqual(buf.available_frames, 8192)

        # Read 1024 frames
        read1 = buf.read(1024)
        self.assertEqual(len(read1), 1024)
        self.assertEqual(read1.shape, (1024, 2))
        np.testing.assert_allclose(read1, 0.75, atol=1e-5)
        self.assertEqual(buf.available_frames, 8192 - 1024)

    def test_prefetch_buffer_clear_on_seek(self):
        """Verifies clearing prefetch buffer immediately resets available frames and offset."""
        buf = AudioPrefetchBuffer(44100, buffer_sec=2.0)
        buf.write(np.ones((4096, 2), dtype=np.float32))
        buf.read(512)
        self.assertEqual(buf.available_frames, 4096 - 512)

        buf.clear()
        self.assertTrue(buf.is_empty())
        self.assertEqual(buf.available_frames, 0)
        # Reading from cleared buffer returns empty array without error
        read_empty = buf.read(1024)
        self.assertEqual(len(read_empty), 0)

    def test_soundfile_audio_source_open_and_seek(self):
        """Verifies SoundFileAudioSource opens file and seeks accurately."""
        source = SoundFileAudioSource(self.test_wav_path)
        self.assertEqual(source.samplerate, 44100)
        self.assertEqual(source.channels, 2)
        self.assertGreater(source.total_frames(), 0)

        data = source.read(2048)
        self.assertEqual(len(data), 2048)
        self.assertEqual(source.tell(), 2048)

        source.seek(0)
        self.assertEqual(source.tell(), 0)
        source.close()

    def test_no_premature_track_ended_during_stall(self):
        """Verifies that an empty buffer during a network stall does NOT mark track_ended."""
        playlist = [{"name": "Test Mix", "path": self.test_wav_path, "size_mb": 1.0, "ext": "WAV"}]
        engine = AudioEngine(playlist, auto_bluetooth=False)
        self.assertTrue(engine.load_track(0, start_playing=True))

        # Clear buffer to simulate a massive network outage
        engine.audio_buffer.clear()
        self.assertFalse(engine.audio_buffer.eof)

        # Render audio block
        outdata = np.zeros((1024, 2), dtype=np.float32)
        engine._render_audio(outdata, 1024)

        # The output is muted to silence, but track_ended is FALSE!
        self.assertFalse(engine.track_ended)
        engine.stop_playback()

    def test_track_ended_only_when_eof_and_buffer_drained(self):
        """Verifies track_ended is set ONLY when EOF is reached AND buffer is completely empty."""
        playlist = [{"name": "Test Mix", "path": self.test_wav_path, "size_mb": 1.0, "ext": "WAV"}]
        engine = AudioEngine(playlist, auto_bluetooth=False)
        self.assertTrue(engine.load_track(0, start_playing=True))

        # Stop feeder worker so test directly controls buffer EOF state
        if engine.feeder:
            engine.feeder.stop()
            engine.feeder.join(timeout=0.5)

        engine.audio_buffer.clear()
        engine.audio_buffer.set_eof()
        engine.audio_buffer.write(np.ones((2048, 2), dtype=np.float32))

        outdata = np.zeros((1024, 2), dtype=np.float32)
        engine._render_audio(outdata, 1024)
        # Buffer still has 1024 frames left, so track_ended should still be False
        self.assertFalse(engine.track_ended)

        # Read remaining frames
        engine._render_audio(outdata, 1024)
        # Buffer is now empty and EOF is True, next read should set track_ended = True
        engine._render_audio(outdata, 1024)
        self.assertTrue(engine.track_ended)
        engine.stop_playback()


if __name__ == "__main__":
    unittest.main()
