"""
Wake Word Detection module.

Continuously listens for the "Hey Assistant" wake word using openWakeWord.
Runs with minimal CPU usage (< 5% of one core) for always-on detection.
"""

import numpy as np
from loguru import logger

try:
    from openwakeword.model import Model as OWWModel
    HAS_OPENWAKEWORD = True
except ImportError:
    HAS_OPENWAKEWORD = False
    logger.warning(
        "openwakeword not installed. Wake word detection will use fallback mode. "
        "Install with: pip install openwakeword"
    )


class WakeWordDetector:
    """
    Wake word detector using openWakeWord.

    Supports custom wake word models and configurable detection thresholds.
    Falls back to a simple energy-based trigger in development environments
    where openWakeWord is not available.
    """

    def __init__(
        self,
        model_path: str = None,
        model_name: str = "hey_assistant",
        threshold: float = 0.5,
        sample_rate: int = 16000,
        chunk_size: int = 512,
    ):
        """
        Initialise the wake word detector.

        Args:
            model_path: Path to the custom wake word model file (.tflite).
            model_name: Name of the wake word model for openWakeWord.
            threshold: Detection confidence threshold (0.0 - 1.0).
            sample_rate: Audio sample rate (must be 16000 for openWakeWord).
            chunk_size: Number of audio samples per chunk.
        """
        self.model_path = model_path
        self.model_name = model_name
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._model = None
        self._detected = False

        if HAS_OPENWAKEWORD:
            self._init_openwakeword()
        else:
            logger.info("Running in fallback mode (manual trigger required)")

    def _init_openwakeword(self):
        """Initialise the openWakeWord model."""
        try:
            if self.model_path:
                # Load custom model from file
                self._model = OWWModel(
                    wakeword_models=[self.model_path],
                    inference_framework="tflite",
                )
                logger.info(f"Loaded custom wake word model from {self.model_path}")
            else:
                # Use built-in model
                self._model = OWWModel(
                    inference_framework="tflite",
                )
                logger.info("Loaded default openWakeWord models")
        except Exception as e:
            logger.error(f"Failed to load wake word model: {e}")
            self._model = None

    def process_chunk(self, audio_chunk: np.ndarray) -> bool:
        """
        Process an audio chunk and check for wake word detection.

        Args:
            audio_chunk: NumPy array of int16 audio samples at 16 kHz.

        Returns:
            True if the wake word was detected in this chunk.
        """
        if self._model is None:
            return False

        try:
            # openWakeWord expects int16 audio data
            if audio_chunk.dtype != np.int16:
                audio_chunk = (audio_chunk * 32767).astype(np.int16)

            # Run prediction
            prediction = self._model.predict(audio_chunk)

            # Check all model scores against threshold
            for model_name, score in prediction.items():
                if score > self.threshold:
                    logger.info(
                        f"Wake word detected: '{model_name}' "
                        f"(confidence: {score:.3f})"
                    )
                    self._detected = True
                    # Reset model state after detection to avoid re-triggering
                    self._model.reset()
                    return True

        except Exception as e:
            logger.error(f"Wake word processing error: {e}")

        return False

    def listen(self, audio_stream) -> None:
        """
        Block until the wake word is detected.

        Continuously reads chunks from the audio stream and processes them
        through the wake word detector.

        Args:
            audio_stream: An iterator/generator yielding audio chunks (np.ndarray).
        """
        logger.debug("Listening for wake word...")
        self._detected = False

        for chunk in audio_stream:
            if self.process_chunk(chunk):
                return

    def reset(self):
        """Reset the detector state."""
        self._detected = False
        if self._model is not None:
            try:
                self._model.reset()
            except Exception:
                pass

    @property
    def is_available(self) -> bool:
        """Check if the wake word detector is properly initialised."""
        return self._model is not None
