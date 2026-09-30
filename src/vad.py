"""
Voice Activity Detection (VAD) module.

Detects speech vs silence in audio chunks using energy-based analysis.
Used by the audio pipeline to determine when a user has finished speaking.
"""

import numpy as np
from loguru import logger


class VoiceActivityDetector:
    """Energy-based voice activity detector for real-time audio streams."""

    def __init__(
        self,
        silence_threshold: int = 500,
        silence_duration_s: float = 1.5,
        min_speech_duration_s: float = 0.5,
        sample_rate: int = 16000,
        chunk_size: int = 512,
    ):
        """
        Initialise the VAD.

        Args:
            silence_threshold: RMS energy threshold below which audio is considered silent.
            silence_duration_s: Seconds of continuous silence to trigger end-of-speech.
            min_speech_duration_s: Minimum speech duration to consider as valid input.
            sample_rate: Audio sample rate in Hz.
            chunk_size: Number of samples per audio chunk.
        """
        self.silence_threshold = silence_threshold
        self.silence_duration_s = silence_duration_s
        self.min_speech_duration_s = min_speech_duration_s
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        # Calculate number of silent chunks needed to trigger end-of-speech
        self._chunk_duration_s = chunk_size / sample_rate
        self._silence_chunks_required = int(
            silence_duration_s / self._chunk_duration_s
        )
        self._min_speech_chunks = int(
            min_speech_duration_s / self._chunk_duration_s
        )

        # State tracking
        self._consecutive_silent_chunks = 0
        self._total_speech_chunks = 0
        self._is_speaking = False

        logger.debug(
            f"VAD initialised: threshold={silence_threshold}, "
            f"silence_chunks={self._silence_chunks_required}, "
            f"min_speech_chunks={self._min_speech_chunks}"
        )

    def reset(self):
        """Reset VAD state for a new recording session."""
        self._consecutive_silent_chunks = 0
        self._total_speech_chunks = 0
        self._is_speaking = False

    def compute_rms_energy(self, audio_chunk: np.ndarray) -> float:
        """
        Compute the root-mean-square energy of an audio chunk.

        Args:
            audio_chunk: NumPy array of audio samples (int16 or float32).

        Returns:
            RMS energy as a float value.
        """
        if audio_chunk.dtype == np.int16:
            audio_float = audio_chunk.astype(np.float32)
        else:
            audio_float = audio_chunk

        if len(audio_float) == 0:
            return 0.0

        rms = np.sqrt(np.mean(audio_float ** 2))
        return float(rms)

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """
        Determine if an audio chunk contains speech.

        Args:
            audio_chunk: NumPy array of audio samples.

        Returns:
            True if the chunk contains speech (energy above threshold).
        """
        energy = self.compute_rms_energy(audio_chunk)
        return energy > self.silence_threshold

    def process_chunk(self, audio_chunk: np.ndarray) -> str:
        """
        Process an audio chunk and return the current VAD state.

        Args:
            audio_chunk: NumPy array of audio samples.

        Returns:
            State string: 'speech', 'silence', or 'end_of_speech'.
        """
        if self.is_speech(audio_chunk):
            self._consecutive_silent_chunks = 0
            self._total_speech_chunks += 1
            self._is_speaking = True
            return "speech"
        else:
            self._consecutive_silent_chunks += 1

            # Only trigger end-of-speech if we've had enough speech first
            if (
                self._is_speaking
                and self._total_speech_chunks >= self._min_speech_chunks
                and self._consecutive_silent_chunks >= self._silence_chunks_required
            ):
                logger.debug(
                    f"End of speech detected after {self._total_speech_chunks} "
                    f"speech chunks and {self._consecutive_silent_chunks} silent chunks"
                )
                return "end_of_speech"

            return "silence"

    def apply_noise_gate(
        self, audio_chunk: np.ndarray, gate_threshold: int = 200
    ) -> np.ndarray:
        """
        Apply a simple noise gate to an audio chunk.

        Samples with absolute value below the threshold are zeroed out.

        Args:
            audio_chunk: NumPy array of int16 audio samples.
            gate_threshold: Amplitude threshold for the gate.

        Returns:
            Gated audio chunk.
        """
        gated = audio_chunk.copy()
        gated[np.abs(gated) < gate_threshold] = 0
        return gated
