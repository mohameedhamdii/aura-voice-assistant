"""
Speech-to-Text Engine module.

Transcribes recorded speech to text using whisper.cpp via pywhispercpp bindings.
Optimised for Raspberry Pi 5 with INT8 quantized models.
"""

import io
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

try:
    from pywhispercpp.model import Model as WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False
    logger.warning(
        "pywhispercpp not installed. STT will be unavailable. "
        "Install with: pip install pywhispercpp"
    )


class STTEngine:
    """
    Speech-to-text engine using whisper.cpp.

    Loads the model once at startup and keeps it in memory for fast
    repeated inference. Supports base.en and small.en models.
    """

    def __init__(
        self,
        model_path: str = "models/whisper/ggml-base.en.bin",
        n_threads: int = 4,
        language: str = "en",
        use_gpu: bool = False,
    ):
        """
        Initialise the STT engine.

        Args:
            model_path: Path to the GGML whisper model file.
            n_threads: Number of CPU threads for inference.
            language: Language code for transcription.
            use_gpu: Whether to use GPU acceleration (requires compatible setup).
        """
        self.model_path = Path(model_path)
        self.n_threads = n_threads
        self.language = language
        self.use_gpu = use_gpu
        self._model = None

        if HAS_WHISPER:
            self._load_model()

    def _load_model(self):
        """Load the whisper model into memory."""
        if not self.model_path.exists():
            logger.error(
                f"Whisper model not found at {self.model_path}. "
                f"Run scripts/download_models.sh to download models."
            )
            return

        try:
            logger.info(f"Loading Whisper model from {self.model_path}...")
            start_time = time.time()

            self._model = WhisperModel(
                str(self.model_path),
                n_threads=self.n_threads,
                language=self.language,
                print_realtime=False,
                print_progress=False,
            )

            load_time = time.time() - start_time
            logger.info(f"Whisper model loaded in {load_time:.1f}s")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self._model = None

    def transcribe(self, audio_data: bytes) -> str:
        """
        Transcribe audio data to text.

        Args:
            audio_data: WAV-formatted audio bytes (16 kHz, 16-bit mono).

        Returns:
            Transcribed text string, or empty string on failure.
        """
        if self._model is None:
            logger.error("Whisper model not loaded")
            return ""

        try:
            start_time = time.time()

            # Convert WAV bytes to numpy array
            audio_array = self._wav_bytes_to_numpy(audio_data)
            if audio_array is None:
                return ""

            # Ensure audio is float32 normalised to [-1, 1]
            if audio_array.dtype == np.int16:
                audio_float = audio_array.astype(np.float32) / 32768.0
            else:
                audio_float = audio_array.astype(np.float32)

            # Run transcription
            segments = self._model.transcribe(audio_float)

            # Collect all text segments
            text_parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    text_parts.append(text)

            transcribed_text = " ".join(text_parts).strip()

            inference_time = time.time() - start_time
            audio_duration = len(audio_float) / 16000
            rtf = inference_time / audio_duration if audio_duration > 0 else 0

            logger.info(
                f"Transcription complete: '{transcribed_text}' "
                f"({inference_time:.1f}s, RTF={rtf:.2f}x)"
            )

            return transcribed_text

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def transcribe_file(self, wav_path: str) -> str:
        """
        Transcribe a WAV file to text.

        Args:
            wav_path: Path to the WAV file.

        Returns:
            Transcribed text string.
        """
        path = Path(wav_path)
        if not path.exists():
            logger.error(f"Audio file not found: {wav_path}")
            return ""

        with open(path, "rb") as f:
            audio_data = f.read()

        return self.transcribe(audio_data)

    def _wav_bytes_to_numpy(self, wav_bytes: bytes) -> Optional[np.ndarray]:
        """
        Convert WAV bytes to a NumPy array.

        Args:
            wav_bytes: WAV file contents as bytes.

        Returns:
            NumPy array of audio samples, or None on error.
        """
        try:
            buffer = io.BytesIO(wav_bytes)
            with wave.open(buffer, "rb") as wf:
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                n_frames = wf.getnframes()
                raw_data = wf.readframes(n_frames)

            # Convert to numpy based on sample width
            if sample_width == 2:
                audio_array = np.frombuffer(raw_data, dtype=np.int16)
            elif sample_width == 4:
                audio_array = np.frombuffer(raw_data, dtype=np.int32)
            else:
                logger.error(f"Unsupported sample width: {sample_width}")
                return None

            # Convert stereo to mono if needed
            if n_channels > 1:
                audio_array = audio_array.reshape(-1, n_channels)
                audio_array = audio_array.mean(axis=1).astype(audio_array.dtype)

            return audio_array

        except Exception as e:
            logger.error(f"Failed to parse WAV data: {e}")
            return None

    @property
    def is_available(self) -> bool:
        """Check if the STT engine is ready for transcription."""
        return self._model is not None

    def unload_model(self):
        """Unload the model from memory to free RAM."""
        self._model = None
        logger.info("Whisper model unloaded")

    def reload_model(self):
        """Reload the model (e.g., after LLM inference to reclaim memory)."""
        if HAS_WHISPER:
            self._load_model()
