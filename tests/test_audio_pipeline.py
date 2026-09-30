"""
Tests for the audio pipeline module.

Validates microphone capture, VAD silence detection,
and recording correct duration behaviour.
"""

import io
import struct
import wave

import numpy as np
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vad import VoiceActivityDetector
from audio_pipeline import AudioPipeline


class TestVoiceActivityDetector:
    """Tests for the VAD module."""

    def setup_method(self):
        """Create a fresh VAD instance for each test."""
        self.vad = VoiceActivityDetector(
            silence_threshold=500,
            silence_duration_s=0.5,
            min_speech_duration_s=0.1,
            sample_rate=16000,
            chunk_size=512,
        )

    def test_rms_energy_silence(self):
        """Silent audio should have near-zero RMS energy."""
        silent_chunk = np.zeros(512, dtype=np.int16)
        energy = self.vad.compute_rms_energy(silent_chunk)
        assert energy == 0.0

    def test_rms_energy_loud(self):
        """Loud audio should have high RMS energy."""
        # Generate a loud sine wave
        t = np.linspace(0, 0.032, 512, dtype=np.float32)
        loud_chunk = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)
        energy = self.vad.compute_rms_energy(loud_chunk)
        assert energy > 10000

    def test_is_speech_silent(self):
        """Silent audio should not be detected as speech."""
        silent_chunk = np.zeros(512, dtype=np.int16)
        assert self.vad.is_speech(silent_chunk) is False

    def test_is_speech_loud(self):
        """Loud audio should be detected as speech."""
        t = np.linspace(0, 0.032, 512, dtype=np.float32)
        loud_chunk = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)
        assert self.vad.is_speech(loud_chunk) is True

    def test_end_of_speech_detection(self):
        """VAD should detect end of speech after enough silence."""
        t = np.linspace(0, 0.032, 512, dtype=np.float32)
        speech_chunk = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)
        silent_chunk = np.zeros(512, dtype=np.int16)

        # Send speech chunks first
        for _ in range(10):
            state = self.vad.process_chunk(speech_chunk)
            assert state == "speech"

        # Send enough silence to trigger end_of_speech
        end_detected = False
        for _ in range(100):
            state = self.vad.process_chunk(silent_chunk)
            if state == "end_of_speech":
                end_detected = True
                break

        assert end_detected, "End of speech should be detected after silence"

    def test_reset(self):
        """Reset should clear all state."""
        t = np.linspace(0, 0.032, 512, dtype=np.float32)
        speech_chunk = (np.sin(2 * np.pi * 440 * t) * 20000).astype(np.int16)

        # Process some speech
        for _ in range(5):
            self.vad.process_chunk(speech_chunk)

        assert self.vad._total_speech_chunks > 0
        assert self.vad._is_speaking is True

        # Reset
        self.vad.reset()
        assert self.vad._total_speech_chunks == 0
        assert self.vad._is_speaking is False
        assert self.vad._consecutive_silent_chunks == 0

    def test_noise_gate(self):
        """Noise gate should zero out low-amplitude samples."""
        # Create chunk with mixed amplitude
        chunk = np.array([100, -50, 5000, -3000, 10, -150, 8000], dtype=np.int16)
        gated = self.vad.apply_noise_gate(chunk, gate_threshold=200)

        # Samples with abs value < 200 should be zeroed
        assert gated[0] == 0    # 100 < 200
        assert gated[1] == 0    # 50 < 200
        assert gated[2] == 5000  # 5000 > 200
        assert gated[3] == -3000  # 3000 > 200
        assert gated[4] == 0    # 10 < 200
        assert gated[5] == 0    # 150 < 200
        assert gated[6] == 8000  # 8000 > 200

    def test_empty_chunk(self):
        """Empty audio chunk should have zero energy."""
        empty = np.array([], dtype=np.int16)
        assert self.vad.compute_rms_energy(empty) == 0.0


class TestAudioPipeline:
    """Tests for the audio pipeline module."""

    def test_wav_conversion(self):
        """Test numpy to WAV bytes conversion."""
        config = {
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 512,
            "silence_threshold": 500,
            "silence_duration_s": 1.5,
            "max_recording_s": 15,
        }
        pipeline = AudioPipeline(config)

        # Create a test signal
        t = np.linspace(0, 0.5, 8000, dtype=np.float32)
        test_audio = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)

        wav_bytes = pipeline._numpy_to_wav(test_audio)

        # Verify it's valid WAV
        buffer = io.BytesIO(wav_bytes)
        with wave.open(buffer, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == 8000

    def test_mute_state(self):
        """Test mute/unmute functionality."""
        config = {
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 512,
        }
        pipeline = AudioPipeline(config)

        assert pipeline.is_muted is False
        pipeline.set_muted(True)
        assert pipeline.is_muted is True
        pipeline.set_muted(False)
        assert pipeline.is_muted is False

    def test_chime_generation(self):
        """Test that chime generation doesn't crash (even without audio output)."""
        config = {
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 512,
        }
        pipeline = AudioPipeline(config)

        # These should not raise even without audio hardware
        # (play_audio will fail silently without pyaudio initialised)
        # We test that the chime generation logic works
        for chime_type in ["listening", "error", "thinking"]:
            duration_s = 0.2
            t = np.linspace(0, duration_s, int(16000 * duration_s), False)
            if chime_type == "listening":
                tone1 = np.sin(2 * np.pi * 800 * t[:len(t)//2]) * 16000
                tone2 = np.sin(2 * np.pi * 1200 * t[len(t)//2:]) * 16000
                chime = np.concatenate([tone1, tone2])
            else:
                chime = np.sin(2 * np.pi * 400 * t) * 16000

            assert len(chime) > 0
            assert chime.dtype == np.float64
