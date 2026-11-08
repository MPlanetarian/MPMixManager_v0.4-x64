#!/usr/bin/env python3
"""
Unit and Integration Tests for Traktor Kontrol S4 Hardware MIDI Support
MP Mix Archive Manager v0.4.0
"""

import os, sys, time, json, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure scripts directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

import traktor_s4_midi
from traktor_s4_midi import (
    TraktorS4MidiController,
    detect_traktor_s4_port,
    is_daemon_running,
    CONFIG_DIR,
    PID_FILE,
    STATE_FILE,
)


class TestTraktorS4MidiController(unittest.TestCase):
    def setUp(self):
        self.controller = TraktorS4MidiController(port="hw:0,0")

    def test_port_detection(self):
        detected, port, details = detect_traktor_s4_port()
        self.assertIsInstance(detected, bool)
        self.assertIsInstance(port, str)
        self.assertIn("hw:", port)

    def test_pitch_cc_scaling_center_deadband(self):
        # Center values must firmly snap to 0%
        self.assertEqual(self.controller.scale_pitch_cc_to_percent(64), 0)
        self.assertEqual(self.controller.scale_pitch_cc_to_percent(63), 0)
        self.assertEqual(self.controller.scale_pitch_cc_to_percent(65), 0)
        self.assertEqual(self.controller.scale_pitch_cc_to_percent(62), 0)
        self.assertEqual(self.controller.scale_pitch_cc_to_percent(66), 0)

    def test_pitch_cc_scaling_extremes(self):
        # 0 -> -20%, 127 -> +20%
        self.assertEqual(self.controller.scale_pitch_cc_to_percent(0), -20)
        self.assertEqual(self.controller.scale_pitch_cc_to_percent(127), 20)

    def test_pitch_bend_scaling(self):
        # Center 8192 -> 0%
        self.assertEqual(self.controller.scale_pitch_bend_to_percent(0, 64), 0)
        # Min 0 -> -20%
        self.assertEqual(self.controller.scale_pitch_bend_to_percent(0, 0), -20)
        # Max 16383 -> +20%
        self.assertEqual(self.controller.scale_pitch_bend_to_percent(127, 127), 20)

    @patch("traktor_s4_midi.send_player_ipc")
    def test_deck_a_pitch_bend_event(self, mock_ipc):
        # 0xE0 = Pitch bend on channel 1 (Left Deck)
        desc, action = self.controller.process_midi_event(0xE0, 0, 96) # Above center
        self.assertIn("Pitch Bend Ch 1", desc)
        self.assertIn("DJ Pitch", action)
        mock_ipc.assert_called_with("set_pitch", percent=unittest.mock.ANY)

    @patch("traktor_s4_midi.send_player_ipc")
    def test_deck_b_pitch_fader_cc(self, mock_ipc):
        # CC 15 on Channel 2 = Right Deck pitch fader
        desc, action = self.controller.process_midi_event(0xB1, 15, 100)
        self.assertIn("CC 15", desc)
        self.assertIn("DJ Pitch", action)
        mock_ipc.assert_called_with("set_pitch", percent=unittest.mock.ANY)

    @patch("traktor_s4_midi.send_player_ipc")
    def test_play_pause_button(self, mock_ipc):
        # Note On 0, Vel 127
        desc, action = self.controller.process_midi_event(0x90, 0, 127)
        self.assertIn("Play / Pause", action)
        mock_ipc.assert_called_with("toggle")

    @patch("traktor_s4_midi.send_player_ipc")
    def test_cue_button(self, mock_ipc):
        # Note On 2, Vel 127
        desc, action = self.controller.process_midi_event(0x90, 2, 127)
        self.assertIn("CUE", action)
        mock_ipc.assert_called_with("seek_to", position=0.0)

    @patch("traktor_s4_midi.send_player_ipc")
    def test_sync_pitch_reset(self, mock_ipc):
        # Note On 6 (Left Deck Sync)
        desc, action = self.controller.process_midi_event(0x90, 6, 127)
        self.assertIn("Sync", action)
        mock_ipc.assert_called_with("reset_pitch")

    @patch("traktor_s4_midi.send_player_ipc")
    def test_pitch_nudge_buttons(self, mock_ipc):
        # Note On 8 (Pitch +)
        desc, action = self.controller.process_midi_event(0x90, 8, 127)
        self.assertIn("Pitch Nudge Up", action)
        mock_ipc.assert_called_with("pitch_up", step=1)

        # Note On 9 (Pitch -)
        desc, action = self.controller.process_midi_event(0x90, 9, 127)
        self.assertIn("Pitch Nudge Down", action)
        mock_ipc.assert_called_with("pitch_down", step=1)

    @patch("traktor_s4_midi.send_player_ipc")
    def test_browse_encoder(self, mock_ipc):
        # CC 42 clockwise (val > 64)
        self.controller.last_turn_time = 0.0
        desc, action = self.controller.process_midi_event(0xB0, 42, 65)
        self.assertIn("Next Track", action)
        mock_ipc.assert_called_with("next")

        # CC 42 counter-clockwise (val < 64)
        self.controller.last_turn_time = 0.0
        desc, action = self.controller.process_midi_event(0xB0, 42, 63)
        self.assertIn("Previous Track", action)
        mock_ipc.assert_called_with("prev")

    @patch("traktor_s4_midi.send_player_ipc")
    def test_channel_volume_fader(self, mock_ipc):
        # CC 8 (Channel A Fader) at 64 (~50%)
        desc, action = self.controller.process_midi_event(0xB0, 8, 64)
        self.assertIn("Volume: 50%", action)
        mock_ipc.assert_called_with("set_volume", volume=50)

    @patch("traktor_s4_midi.send_player_ipc")
    def test_loop_seek_buttons(self, mock_ipc):
        # Note 16 (Loop In) -> Seek -10s
        desc, action = self.controller.process_midi_event(0x90, 16, 127)
        self.assertIn("Quick Seek -10s", action)
        mock_ipc.assert_called_with("seek", seconds=-10.0)

        # Note 17 (Loop Out) -> Seek +10s
        desc, action = self.controller.process_midi_event(0x90, 17, 127)
        self.assertIn("Quick Seek +10s", action)
        mock_ipc.assert_called_with("seek", seconds=10.0)

    @patch("traktor_s4_midi.send_player_ipc")
    def test_recording_toggle(self, mock_ipc):
        # Note 32 (Loop Recorder REC)
        desc, action = self.controller.process_midi_event(0x90, 32, 127)
        self.assertIn("Loop Recorder REC", action)
        mock_ipc.assert_called_with("toggle_record")


if __name__ == "__main__":
    unittest.main()
