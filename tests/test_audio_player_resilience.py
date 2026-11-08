#!/usr/bin/env python3
"""
Unit and regression tests for MP Audio Player resilience and recovery:
- Prevents premature stops on large FLAC mixes (e.g. 1.4 GB / 48kHz Airbase mixes).
- Verifies AudioResampler handles empty/partial input buffers without position runaway.
- Verifies AudioFeederThread does not mark EOF on transient I/O stalls before end of track.
- Verifies AudioEngine.play() recovers and reloads cleanly after stop_playback().
- Verifies dead daemon detection, stale socket cleanup, and auto-recovery.
- Verifies seamless switching between mixes of differing sample rates (48kHz <-> 44.1kHz).
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time
import tempfile
import threading
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player
from MP_Audio_Player import (
    AudioPrefetchBuffer,
    AudioFeederThread,
    AudioResampler,
    SoundFileAudioSource,
    AudioEngine,
    is_player_daemon_running,
    _cleanup_stale_daemon_files,
    PID_FILE,
    SOCKET_PATH,
    PORT_FILE,
    STATE_FILE
)


class TestAudioPlayerResilience(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # 1. Standard 44.1kHz stereo test wav
        self.mix_44k_path = str(Path(self.temp_dir.name) / "test_44k.wav")
        sr1 = 44100
        dur1 = 2.0
        t1 = np.linspace(0, dur1, int(sr1 * dur1), False)
        sine1 = (np.sin(2 * np.pi * 440 * t1) * 0.4).astype(np.float32)
        stereo1 = np.column_stack((sine1, sine1))
        sf.write(self.mix_44k_path, stereo1, sr1)

        # 2. 48kHz 24-bit test mix simulating Airbase FLAC
        self.mix_48k_path = str(Path(self.temp_dir.name) / "test_airbase_48k.flac")
        sr2 = 48000
        dur2 = 2.5
        t2 = np.linspace(0, dur2, int(sr2 * dur2), False)
        sine2 = (np.sin(2 * np.pi * 880 * t2) * 0.5).astype(np.float32)
        stereo2 = np.column_stack((sine2, sine2))
        sf.write(self.mix_48k_path, stereo2, sr2, subtype="PCM_24")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resampler_handles_zero_frames_without_runaway(self):
        """Verifies AudioResampler handles empty read_func without index runaway."""
        resampler = AudioResampler()

        # Mock read_func returning 0 frames
        mock_read = MagicMock(return_value=np.zeros((0, 2), dtype=np.float32))

        # Request 1024 frames while source is temporarily starved (48000 -> 44100: speed_ratio = 48000/44100)
        speed_ratio = 48000.0 / 44100.0
        output = resampler.process(mock_read, 1024, speed_ratio)
        self.assertEqual(len(output), 0)
        self.assertEqual(resampler.in_pos, 0.0)

        # Next read has actual data
        chunk = np.ones((4096, 2), dtype=np.float32) * 0.5
        mock_read.return_value = chunk
        output2 = resampler.process(mock_read, 1024, speed_ratio)
        self.assertEqual(len(output2), 1024)
        self.assertGreater(resampler.in_pos, 0.0)

    def test_feeder_does_not_flag_eof_on_transient_stall(self):
        """Verifies feeder treats empty read as transient stall if well before total_frames."""
        source = MagicMock()
        source.total_frames.return_value = 5000000  # Large file (e.g. Airbase)
        source.samplerate = 48000
        source.channels = 2

        # Simulate read returning empty for 2 tries then real data
        call_count = [0]
        def fake_read(n):
            call_count[0] += 1
            if call_count[0] <= 2:
                return np.zeros((0, 2), dtype=np.float32)
            source.tell.return_value = 65536
            return np.ones((n, 2), dtype=np.float32)

        source.read.side_effect = fake_read
        source.tell.return_value = 0

        engine_mock = MagicMock()
        engine_mock._try_reopen_source.return_value = True

        buf = AudioPrefetchBuffer(48000, buffer_sec=2.0)
        feeder = AudioFeederThread(source, buf, engine_mock)
        feeder.start()

        # Let feeder loop run through transient stalls
        time.sleep(0.4)
        feeder.stop()
        feeder.join(timeout=1.0)

        # Buffer must NOT have been marked as EOF
        self.assertFalse(buf.eof)
        self.assertGreater(buf.available_frames, 0)

    def test_audio_engine_reloads_and_recovers_after_stop(self):
        """Verifies that calling play() after stop_playback() properly restores playback."""
        playlist = [
            {"name": "Airbase 48k", "path": self.mix_48k_path, "size_mb": 2.0, "ext": "FLAC"},
            {"name": "Mix 44k", "path": self.mix_44k_path, "size_mb": 1.0, "ext": "WAV"}
        ]
        engine = AudioEngine(playlist, auto_bluetooth=False)

        # Load first mix and start playback
        self.assertTrue(engine.load_track(0, start_playing=True))
        self.assertEqual(engine.state, "playing")
        self.assertIsNotNone(engine.feeder)

        # User or timeout stops playback
        engine.stop_playback()
        self.assertEqual(engine.state, "stopped")
        self.assertIsNone(engine.feeder)
        self.assertIsNone(engine.audio_source)

        # Previously, play() would stay stuck/silent because feeder was None.
        # With the fix, play() detects state=='stopped' and re-initializes track!
        engine.play()
        self.assertEqual(engine.state, "playing")
        self.assertIsNotNone(engine.feeder)
        self.assertIsNotNone(engine.audio_source)

        # Switch to 44.1k mix
        self.assertTrue(engine.load_track(1, start_playing=True))
        self.assertEqual(engine.current_index, 1)
        self.assertEqual(engine.state, "playing")

        engine.stop_playback()

    def test_dead_daemon_and_stale_socket_cleanup(self):
        """Verifies _cleanup_stale_daemon_files removes stale files without crashing."""
        pid_file = PID_FILE
        sock_file = SOCKET_PATH
        port_file = PORT_FILE

        # Create dummy stale files
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("99999999")
        port_file.write_text("55555")
        try:
            sock_file.write_text("")
        except Exception:
            pass

        # Cleanup should cleanly wipe them
        _cleanup_stale_daemon_files()
        self.assertFalse(pid_file.exists())
        self.assertFalse(port_file.exists())
        self.assertFalse(sock_file.exists())

        # is_player_daemon_running should return False
        self.assertFalse(is_player_daemon_running())

    def test_audio_arg_uses_first_existing_path_line(self):
        """A launcher that joins several paths with newlines must still open the real mix."""
        good = Path(self.temp_dir.name) / "real_mix.flac"
        good.write_text("x")
        raw = f"{good}\n/tmp/vert{{}}vert{{}}\n/tmp/echo\n{good}"
        found = MP_Audio_Player._existing_audio_path(raw)
        self.assertEqual(found, str(good.resolve()))
        self.assertEqual(MP_Audio_Player._existing_audio_path(""), "")
        self.assertEqual(MP_Audio_Player._existing_audio_path("no-such-file.flac"), "")

    def test_daemon_lock_is_exclusive_across_processes(self):
        """A second playback daemon must not start, or both rewrite the status file and the playlist flickers."""
        lock = Path(self.temp_dir.name) / "mp_player.lock"
        with patch.object(MP_Audio_Player, "DAEMON_LOCK_FILE", lock):
            self.assertTrue(MP_Audio_Player._acquire_daemon_lock())
            try:
                script = (
                    "import sys\n"
                    f"sys.path.insert(0, {str(BASE_DIR)!r})\n"
                    "import MP_Audio_Player\n"
                    f"MP_Audio_Player.DAEMON_LOCK_FILE = __import__('pathlib').Path({str(lock)!r})\n"
                    "sys.exit(0 if not MP_Audio_Player._acquire_daemon_lock() else 1)\n"
                )
                proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
            finally:
                MP_Audio_Player._release_daemon_lock()

    def test_choose_daemon_owner_prefers_the_visible_player(self):
        with patch.object(MP_Audio_Player, "_pid_alive", return_value=True):
            owner = MP_Audio_Player._choose_daemon_owner([10, 20, 30], prefer_pid=20, pid_file_pid=10, ipc_pid=30)
            self.assertEqual(owner, 20)
            owner = MP_Audio_Player._choose_daemon_owner([10, 30], prefer_pid=None, pid_file_pid=10, ipc_pid=30)
            self.assertEqual(owner, 10)
            owner = MP_Audio_Player._choose_daemon_owner([30], prefer_pid=99, pid_file_pid=10, ipc_pid=None)
            self.assertEqual(owner, 30)


if __name__ == "__main__":
    unittest.main()
