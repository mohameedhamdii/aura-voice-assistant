"""
Tests for the Speech-to-Text engine module.

Validates Whisper model loading, WAV parsing, and transcription accuracy.
Note: Full transcription tests require the Whisper model to be downloaded.
"""

import io
import wave

import numpy as np
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stt_engine import STTEngine


def generate_test_wav(
    duration_s: float = 1.0,
    frequency: float = 440.0,
    sample_rate: int = 16000,
) -> bytes:
    """Generate a simple test WAV file with a sine tone."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), False)
    audio = (np.sin(2 * np.pi * frequency * t) * 16000).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())

    return buffer.getvalue()


class TestSTTEngine:
    """Tests for the STT engine."""

    def test_init_without_model(self):
        """Engine should initialise without crashing even if model is missing."""
        engine = STTEngine(
            model_path="nonexistent/model.bin",
            n_threads=2,
        )
        assert engine.is_available is False

    def test_transcribe_without_model(self):
        """Transcription should return empty string if model is not loaded."""
        engine = STTEngine(model_path="nonexistent/model.bin")
        result = engine.transcribe(generate_test_wav())
        assert result == ""

    def test_wav_parsing(self):
        """Test that WAV bytes are correctly parsed to numpy array."""
        engine = STTEngine(model_path="nonexistent/model.bin")

        wav_bytes = generate_test_wav(duration_s=0.5, sample_rate=16000)
        audio_array = engine._wav_bytes_to_numpy(wav_bytes)

        assert audio_array is not None
        assert audio_array.dtype == np.int16
        assert len(audio_array) == 8000  # 0.5s * 16000 Hz

    def test_wav_parsing_stereo(self):
        """Test stereo to mono conversion."""
        engine = STTEngine(model_path="nonexistent/model.bin")

        # Generate stereo WAV
        sample_rate = 16000
        duration_s = 0.5
        n_frames = int(sample_rate * duration_s)
        t = np.linspace(0, duration_s, n_frames, False)

        # Two-channel audio
        left = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        right = (np.sin(2 * np.pi * 880 * t) * 8000).astype(np.int16)
        stereo = np.column_stack([left, right])

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(stereo.tobytes())

        audio_array = engine._wav_bytes_to_numpy(buffer.getvalue())

        assert audio_array is not None
        # Should be mono after conversion
        assert len(audio_array.shape) == 1
        assert len(audio_array) == n_frames

    def test_wav_parsing_invalid(self):
        """Invalid data should return None."""
        engine = STTEngine(model_path="nonexistent/model.bin")
        result = engine._wav_bytes_to_numpy(b"not a wav file")
        assert result is None

    def test_model_lifecycle(self):
        """Test unload and reload methods don't crash."""
        engine = STTEngine(model_path="nonexistent/model.bin")
        engine.unload_model()
        assert engine.is_available is False
        # Reload won't work without valid model, but shouldn't crash
        engine.reload_model()

    def test_transcribe_file_missing(self):
        """Transcribing a non-existent file should return empty string."""
        engine = STTEngine(model_path="nonexistent/model.bin")
        result = engine.transcribe_file("nonexistent/audio.wav")
        assert result == ""
