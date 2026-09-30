"""
Text-to-Speech Engine module.

Converts text responses to spoken audio using Piper TTS (offline, VITS-based).
Handles audio resampling and streaming playback via ALSA.
"""

import io
import subprocess
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

try:
    import piper
    HAS_PIPER = True
except ImportError:
    HAS_PIPER = False
    logger.warning(
        "piper-tts not installed. TTS will be unavailable. "
        "Install with: pip install piper-tts"
    )

try:
    from scipy.signal import resample_poly
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class TTSEngine:
    """
    Text-to-speech engine using Piper TTS.

    Generates spoken audio from text using a VITS-based neural TTS model
    running entirely offline on the Raspberry Pi 5.
    """

    def __init__(
        self,
        model_path: str = "models/piper/en_US-lessac-medium.onnx",
        voice: str = "en_US-lessac-medium",
        sample_rate: int = 22050,
        output_sample_rate: int = 16000,
    ):
        """
        Initialise the TTS engine.

        Args:
            model_path: Path to the Piper ONNX voice model.
            voice: Voice name identifier.
            sample_rate: Native sample rate of the TTS model output.
            output_sample_rate: Target sample rate for speaker output.
        """
        self.model_path = Path(model_path)
        self.voice = voice
        self.sample_rate = sample_rate
        self.output_sample_rate = output_sample_rate
        self._voice_model = None
        self._is_speaking = False
        self._interrupted = False

        if HAS_PIPER:
            self._load_model()

    def _load_model(self):
        """Load the Piper TTS voice model."""
        if not self.model_path.exists():
            logger.error(
                f"Piper model not found at {self.model_path}. "
                f"Run scripts/download_models.sh to download models."
            )
            return

        try:
            logger.info(f"Loading Piper TTS model from {self.model_path}...")
            start_time = time.time()

            # Load the voice model
            self._voice_model = piper.PiperVoice.load(
                str(self.model_path),
                config_path=str(self.model_path) + ".json",
            )

            load_time = time.time() - start_time
            logger.info(f"Piper TTS model loaded in {load_time:.1f}s")

        except Exception as e:
            logger.error(f"Failed to load Piper TTS model: {e}")
            self._voice_model = None

    def synthesize(self, text: str) -> Optional[bytes]:
        """
        Synthesize speech from text.

        Args:
            text: Text to convert to speech.

        Returns:
            Raw PCM audio bytes (int16) at the output sample rate, or None on failure.
        """
        if self._voice_model is None:
            logger.error("TTS model not loaded")
            return None

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return None

        try:
            start_time = time.time()

            # Synthesize audio
            audio_buffer = io.BytesIO()
            with wave.open(audio_buffer, "wb") as wav_file:
                self._voice_model.synthesize(text, wav_file)

            # Read back the WAV data
            audio_buffer.seek(0)
            with wave.open(audio_buffer, "rb") as wav_file:
                raw_data = wav_file.readframes(wav_file.getnframes())
                native_rate = wav_file.getframerate()

            audio_array = np.frombuffer(raw_data, dtype=np.int16)

            # Resample if needed
            if native_rate != self.output_sample_rate:
                audio_array = self._resample(
                    audio_array, native_rate, self.output_sample_rate
                )

            synthesis_time = time.time() - start_time
            duration_s = len(audio_array) / self.output_sample_rate
            rtf = synthesis_time / duration_s if duration_s > 0 else 0

            logger.info(
                f"TTS synthesis: {len(text)} chars -> {duration_s:.1f}s audio "
                f"(took {synthesis_time:.1f}s, RTF={rtf:.2f}x)"
            )

            return audio_array.astype(np.int16).tobytes()

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return None

    def speak(self, text: str, audio_pipeline=None):
        """
        Synthesize and play speech through the audio pipeline.

        Args:
            text: Text to speak.
            audio_pipeline: AudioPipeline instance for playback. If None,
                            uses aplay subprocess as fallback.
        """
        if not text or not text.strip():
            return

        self._is_speaking = True
        self._interrupted = False

        try:
            # Synthesize audio
            audio_data = self.synthesize(text)
            if audio_data is None:
                return

            if self._interrupted:
                logger.info("TTS interrupted before playback")
                return

            # Play through audio pipeline or fallback
            if audio_pipeline is not None:
                audio_pipeline.play_audio(audio_data, self.output_sample_rate)
            else:
                self._play_with_aplay(audio_data)

        except Exception as e:
            logger.error(f"TTS playback error: {e}")
        finally:
            self._is_speaking = False

    def _play_with_aplay(self, audio_data: bytes):
        """
        Fallback playback using aplay subprocess.

        Args:
            audio_data: Raw PCM audio bytes (int16).
        """
        try:
            # Create WAV in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.output_sample_rate)
                wf.writeframes(audio_data)

            # Play via aplay
            process = subprocess.Popen(
                ["aplay", "-q", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process.communicate(input=wav_buffer.getvalue())

        except FileNotFoundError:
            logger.error("aplay not found. Install alsa-utils.")
        except Exception as e:
            logger.error(f"aplay playback error: {e}")

    def _resample(
        self, audio: np.ndarray, source_rate: int, target_rate: int
    ) -> np.ndarray:
        """
        Resample audio from source to target sample rate.

        Args:
            audio: NumPy array of audio samples.
            source_rate: Original sample rate.
            target_rate: Target sample rate.

        Returns:
            Resampled audio array.
        """
        if source_rate == target_rate:
            return audio

        if HAS_SCIPY:
            # Use scipy for high-quality resampling
            from math import gcd
            common = gcd(source_rate, target_rate)
            up = target_rate // common
            down = source_rate // common
            resampled = resample_poly(audio.astype(np.float64), up, down)
            return resampled.astype(np.int16)
        else:
            # Simple linear interpolation fallback
            duration = len(audio) / source_rate
            target_length = int(duration * target_rate)
            indices = np.linspace(0, len(audio) - 1, target_length)
            resampled = np.interp(indices, np.arange(len(audio)), audio.astype(np.float64))
            return resampled.astype(np.int16)

    def interrupt(self):
        """Interrupt current speech playback."""
        self._interrupted = True
        self._is_speaking = False
        logger.info("TTS playback interrupted")

    @property
    def is_speaking(self) -> bool:
        """Check if the TTS engine is currently speaking."""
        return self._is_speaking

    @property
    def is_available(self) -> bool:
        """Check if the TTS engine is ready."""
        return self._voice_model is not None

    def unload_model(self):
        """Unload the model from memory."""
        self._voice_model = None
        logger.info("TTS model unloaded")

    def reload_model(self):
        """Reload the TTS model."""
        if HAS_PIPER:
            self._load_model()
