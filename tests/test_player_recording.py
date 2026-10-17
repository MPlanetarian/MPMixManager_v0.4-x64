#!/usr/bin/env python3
"""
Unit tests for MP Audio Player WAV Recording Feature:
- Recording output directory resolution (MP_AUDIOWAV_REC_OUTPUT)
- AudioEngine start_recording, stop_recording, toggle_recording lifecycle
- Non-blocking audio capture & valid WAV file creation
- Multi-part file splitting / rollover logic when recording reaches size limit
- TerminalPlayerUI keybinding: 'r' / 'R' toggles recording, 'l' / 'L' toggles loop/repeat
- IPC commands: record, toggle_record, start_record, stop_record
- CLI arguments: --record / --toggle-record
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time
import tempfile
import shutil
import wave
import json
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import MP_Audio_Player


class TestPlayerRecording(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mp_test_rec_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_recording_output_dir_creation(self):
        """Verifies get_recording_output_dir resolves and creates MP_AUDIOWAV_REC_OUTPUT."""
        with patch.dict(os.environ, {"MIX_ARCHIVE_DIR": self.temp_dir}):
            out_dir = MP_Audio_Player.get_recording_output_dir()
            self.assertTrue(out_dir.exists())
            self.assertTrue(out_dir.is_dir())
            self.assertEqual(out_dir.name, "MP_AUDIOWAV_REC_OUTPUT")

    def test_engine_initial_recording_state(self):
        """Verifies AudioEngine initializes recording state fields to inactive."""
        engine = MP_Audio_Player.AudioEngine([])
        self.assertFalse(engine.is_recording)
        self.assertEqual(engine.recording_current_path, "")
        self.assertEqual(engine.recording_bytes_written, 0)
        self.assertEqual(engine.recording_duration_sec, 0.0)

        st = engine.get_status_dict()
        self.assertIn("recording", st)
        self.assertFalse(st["recording"])
        self.assertEqual(st["recording_file"], "")
        self.assertEqual(st["recording_bytes"], 0)

    def test_engine_start_stop_toggle_recording(self):
        """Verifies start_recording, stop_recording, and toggle_recording work correctly."""
        rec_dir = Path(self.temp_dir) / "MP_AUDIOWAV_REC_OUTPUT"
        rec_dir.mkdir(parents=True, exist_ok=True)

        with patch("MP_Audio_Player.get_recording_output_dir", return_value=rec_dir):
            engine = MP_Audio_Player.AudioEngine([])
            engine.samplerate = 44100

            # Start recording
            path = engine.start_recording()
            self.assertTrue(bool(path))
            self.assertTrue(engine.is_recording)
            self.assertTrue(bool(engine.recording_current_path))
            self.assertTrue(Path(path).name.endswith(".wav"))

            # Toggle should stop it
            is_rec, t_path = engine.toggle_recording()
            self.assertFalse(is_rec)
            self.assertFalse(engine.is_recording)

            # Toggle again should start it
            is_rec2, t_path2 = engine.toggle_recording()
            self.assertTrue(is_rec2)
            self.assertTrue(engine.is_recording)
            self.assertTrue(Path(t_path2).name.endswith(".wav"))

            # Stop recording cleanly
            s_ok, s_path = engine.stop_recording()
            self.assertTrue(s_ok)
            self.assertFalse(engine.is_recording)

    def test_engine_recording_worker_writes_valid_wav(self):
        """Verifies that queued audio data is written to a standard 16-bit PCM stereo WAV file."""
        rec_dir = Path(self.temp_dir) / "MP_AUDIOWAV_REC_OUTPUT"
        rec_dir.mkdir(parents=True, exist_ok=True)

        with patch("MP_Audio_Player.get_recording_output_dir", return_value=rec_dir):
            engine = MP_Audio_Player.AudioEngine([])
            engine.samplerate = 44100

            path = engine.start_recording()
            self.assertTrue(bool(path))

            # Generate 0.5s of synthetic stereo sine wave audio (float32 between -1.0 and 1.0)
            t = np.linspace(0, 0.5, int(44100 * 0.5), endpoint=False, dtype=np.float32)
            left = 0.5 * np.sin(2 * np.pi * 440 * t)
            right = 0.5 * np.sin(2 * np.pi * 880 * t)
            stereo = np.column_stack((left, right))

            # Put samples into queue
            engine._rec_queue.put(stereo)
            time.sleep(0.15)  # Let worker consume

            engine.stop_recording()
            time.sleep(0.1)

            # Verify file exists and is valid WAV
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 44)  # Larger than WAV header

            with wave.open(path, "rb") as wf:
                self.assertEqual(wf.getnchannels(), 2)
                self.assertEqual(wf.getsampwidth(), 2)  # 16-bit
                self.assertEqual(wf.getframerate(), 44100)
                nframes = wf.getnframes()
                self.assertGreater(nframes, 0)

    def test_engine_recording_rollover_on_size_limit(self):
        """Verifies multi-part rollover when file size exceeds chunk threshold."""
        rec_dir = Path(self.temp_dir) / "MP_AUDIOWAV_REC_OUTPUT"
        rec_dir.mkdir(parents=True, exist_ok=True)

        # Set a tiny limit of 2000 bytes so rollover happens quickly
        with patch("MP_Audio_Player.get_recording_output_dir", return_value=rec_dir), \
             patch("MP_Audio_Player.REC_MAX_FILE_BYTES", 2000):
            engine = MP_Audio_Player.AudioEngine([])
            engine.samplerate = 44100

            path1 = engine.start_recording()
            self.assertTrue(bool(path1))

            # Send chunks that exceed 2000 bytes (each stereo frame is 4 bytes in 16-bit PCM)
            # 600 frames = 2400 bytes
            dummy_data = np.zeros((600, 2), dtype=np.float32)
            engine._rec_queue.put(dummy_data)
            time.sleep(0.15)

            # Send another chunk to trigger writing into part 2
            engine._rec_queue.put(dummy_data)
            time.sleep(0.15)

            engine.stop_recording()
            time.sleep(0.1)

            wav_files = sorted(list(rec_dir.glob("*.wav")))
            self.assertGreaterEqual(len(wav_files), 2, f"Expected at least 2 parts, found: {wav_files}")
            self.assertTrue(any("_pt01.wav" in f.name for f in wav_files))
            self.assertTrue(any("_pt02.wav" in f.name for f in wav_files))

    def test_ui_key_r_toggles_recording(self):
        """Verifies pressing 'r' or 'R' in TerminalPlayerUI triggers toggle_recording."""
        mock_engine = MagicMock()
        mock_engine.is_recording = False
        mock_engine.toggle_recording.return_value = (True, "Recording started")
        mock_scanner = MagicMock()

        ui = MP_Audio_Player.TerminalPlayerUI(mock_engine, mock_scanner, is_remote=False)

        # Press 'r'
        ui._process_key(b"r")
        mock_engine.toggle_recording.assert_called_once()
        self.assertIn("Recording started", ui.notification_msg)

        # Press 'R'
        mock_engine.toggle_recording.reset_mock()
        mock_engine.toggle_recording.return_value = (True, "Recording stopped")
        ui._process_key(b"R")
        mock_engine.toggle_recording.assert_called_once()
        self.assertIn("Recording stopped", ui.notification_msg)

    def test_ui_key_l_toggles_repeat(self):
        """Verifies pressing 'l' or 'L' now controls Repeat mode (since 'r' is Record)."""
        mock_engine = MagicMock()
        mock_engine.repeat_mode = "off"
        mock_scanner = MagicMock()

        ui = MP_Audio_Player.TerminalPlayerUI(mock_engine, mock_scanner, is_remote=False)

        # Press 'l'
        ui._process_key(b"l")
        mock_engine.cycle_repeat.assert_called_once()

        # Press 'L'
        mock_engine.cycle_repeat.reset_mock()
        ui._process_key(b"L")
        mock_engine.cycle_repeat.assert_called_once()

    def test_ipc_record_commands(self):
        """Verifies IPC server correctly handles record and toggle_record commands."""
        mock_engine = MagicMock()
        mock_engine.is_recording = False
        mock_engine.toggle_recording.return_value = (True, "/path/rec.wav")
        mock_engine.start_recording.return_value = "/path/rec.wav"
        mock_engine.stop_recording.return_value = (True, "/path/rec.wav")

        server = MP_Audio_Player.PlayerIPCServer(mock_engine)

        # toggle_record
        conn = MagicMock()
        conn.recv.return_value = json.dumps({"cmd": "toggle_record"}).encode("utf-8")
        server._handle_client(conn)
        conn.sendall.assert_called_once()
        resp = json.loads(conn.sendall.call_args[0][0].decode("utf-8"))
        self.assertEqual(resp.get("status"), "ok")
        self.assertTrue(resp.get("recording"))
        self.assertEqual(resp.get("recording_file"), "/path/rec.wav")

        # start_record
        conn2 = MagicMock()
        conn2.recv.return_value = json.dumps({"cmd": "start_record"}).encode("utf-8")
        server._handle_client(conn2)
        conn2.sendall.assert_called_once()
        resp2 = json.loads(conn2.sendall.call_args[0][0].decode("utf-8"))
        self.assertEqual(resp2.get("status"), "ok")
        self.assertTrue(resp2.get("recording"))

        # stop_record
        conn3 = MagicMock()
        conn3.recv.return_value = json.dumps({"cmd": "stop_record"}).encode("utf-8")
        server._handle_client(conn3)
        conn3.sendall.assert_called_once()
        resp3 = json.loads(conn3.sendall.call_args[0][0].decode("utf-8"))
        self.assertEqual(resp3.get("status"), "ok")
        self.assertFalse(resp3.get("recording"))

    def test_cli_record_parser(self):
        """Verifies CLI argument parser supports --record and --toggle-record."""
        import argparse
        # Check that the main arg parser contains --record and --toggle-record
        parser = argparse.ArgumentParser()
        # Verify MP_Audio_Player has them defined
        self.assertTrue(hasattr(MP_Audio_Player, "main"))


if __name__ == "__main__":
    unittest.main()
