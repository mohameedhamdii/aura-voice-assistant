"""
Audio Pipeline module.

Manages microphone input via ALSA/pyaudio, wake word detection, and audio recording.
Handles the ReSpeaker 4-Mic Array HAT with beamforming support.
"""

import io
import struct
import threading
import time
import wave
from pathlib import Path
from typing import Generator, Optional

import numpy as np
from loguru import logger

from vad import VoiceActivityDetector
from wake_word import WakeWordDetector

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    logger.warning("pyaudio not installed. Audio capture will be unavailable.")


class AudioPipeline:
    """
    Complete audio pipeline for the voice assistant.

    Manages microphone input, wake word detection, speech recording,
    and audio playback through the ReSpeaker HAT and I²S speaker.
    """

    def __init__(self, config: dict):
        """
        Initialise the audio pipeline.

        Args:
            config: Dictionary of audio configuration parameters from audio.yaml.
        """
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.chunk_size = config.get("chunk_size", 512)
        self.silence_threshold = config.get("silence_threshold", 500)
        self.silence_duration_s = config.get("silence_duration_s", 1.5)
        self.max_recording_s = config.get("max_recording_s", 15)
        self.min_recording_s = config.get("min_recording_s", 0.5)
        self.noise_gate_enabled = config.get("noise_gate_enabled", True)
        self.noise_gate_threshold = config.get("noise_gate_threshold", 200)
        self.input_device_index = config.get("input_device_index", None)
        self.output_device_index = config.get("output_device_index", None)

        # Audio format
        self._format = pyaudio.paInt16 if HAS_PYAUDIO else None
        self._sample_width = 2  # 16-bit = 2 bytes

        # PyAudio instance
        self._pa = None
        self._input_stream = None
        self._output_stream = None
        self._is_recording = False
        self._is_playing = False
        self._lock = threading.Lock()

        # VAD
        self.vad = VoiceActivityDetector(
            silence_threshold=self.silence_threshold,
            silence_duration_s=self.silence_duration_s,
            min_speech_duration_s=self.min_recording_s,
            sample_rate=self.sample_rate,
            chunk_size=self.chunk_size,
        )

        # Mute state
        self._muted = False

        logger.info(
            f"AudioPipeline initialised: {self.sample_rate} Hz, "
            f"{self.channels} ch, chunk={self.chunk_size}"
        )

    def start(self):
        """Start the audio system and open the input stream."""
        if not HAS_PYAUDIO:
            logger.error("Cannot start audio: pyaudio not available")
            return

        try:
            self._pa = pyaudio.PyAudio()

            # Auto-detect input device if not specified
            if self.input_device_index is None:
                self.input_device_index = self._find_respeaker_device()

            self._input_stream = self._pa.open(
                format=self._format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk_size,
            )

            logger.info("Audio input stream opened successfully")

        except Exception as e:
            logger.error(f"Failed to start audio system: {e}")
            raise

    def stop(self):
        """Stop the audio system and close all streams."""
        if self._input_stream is not None:
            try:
                self._input_stream.stop_stream()
                self._input_stream.close()
            except Exception:
                pass
            self._input_stream = None

        if self._output_stream is not None:
            try:
                self._output_stream.stop_stream()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None

        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

        logger.info("Audio system stopped")

    def _find_respeaker_device(self) -> Optional[int]:
        """
        Auto-detect the ReSpeaker 4-Mic Array HAT.

        Returns:
            Device index for the ReSpeaker, or None to use default.
        """
        if self._pa is None:
            return None

        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            name = info.get("name", "").lower()
            if "respeaker" in name or "seeed" in name:
                logger.info(f"Found ReSpeaker device: index={i}, name={info['name']}")
                return i

        logger.info("ReSpeaker not found, using default input device")
        return None

    def get_stream(self) -> Generator[np.ndarray, None, None]:
        """
        Get a generator that yields audio chunks from the microphone.

        Yields:
            NumPy arrays of int16 audio samples, one chunk at a time.
        """
        if self._input_stream is None:
            logger.error("Audio stream not started. Call start() first.")
            return

        while True:
            if self._muted:
                # Yield silence when muted
                yield np.zeros(self.chunk_size, dtype=np.int16)
                time.sleep(self.chunk_size / self.sample_rate)
                continue

            try:
                raw_data = self._input_stream.read(
                    self.chunk_size,
                    exception_on_overflow=False,
                )
                audio_chunk = np.frombuffer(raw_data, dtype=np.int16)
                yield audio_chunk

            except IOError as e:
                logger.warning(f"Audio input overflow: {e}")
                yield np.zeros(self.chunk_size, dtype=np.int16)
            except Exception as e:
                logger.error(f"Audio read error: {e}")
                break

    def record_until_silence(self) -> Optional[bytes]:
        """
        Record audio until silence is detected or maximum duration is reached.

        Returns:
            WAV-formatted bytes of the recorded audio, or None if no speech detected.
        """
        if self._input_stream is None:
            logger.error("Audio stream not started")
            return None

        self.vad.reset()
        recorded_frames = []
        max_chunks = int(self.max_recording_s * self.sample_rate / self.chunk_size)
        chunk_count = 0

        self._is_recording = True
        logger.debug("Recording started, waiting for speech...")

        try:
            for chunk in self.get_stream():
                if not self._is_recording:
                    break

                chunk_count += 1

                # Apply noise gate if enabled
                if self.noise_gate_enabled:
                    chunk = self.vad.apply_noise_gate(chunk, self.noise_gate_threshold)

                recorded_frames.append(chunk)

                # Check VAD state
                vad_state = self.vad.process_chunk(chunk)

                if vad_state == "end_of_speech":
                    logger.debug(
                        f"End of speech detected after {chunk_count} chunks "
                        f"({chunk_count * self.chunk_size / self.sample_rate:.1f}s)"
                    )
                    break

                if chunk_count >= max_chunks:
                    logger.debug("Maximum recording duration reached")
                    break

        except Exception as e:
            logger.error(f"Recording error: {e}")
        finally:
            self._is_recording = False

        if not recorded_frames:
            return None

        # Convert recorded frames to WAV bytes
        audio_data = np.concatenate(recorded_frames)
        wav_bytes = self._numpy_to_wav(audio_data)

        duration_s = len(audio_data) / self.sample_rate
        logger.info(f"Recorded {duration_s:.1f}s of audio ({len(wav_bytes)} bytes)")

        return wav_bytes

    def stop_recording(self):
        """Stop the current recording."""
        self._is_recording = False

    def play_audio(self, audio_data: bytes, sample_rate: int = None):
        """
        Play audio data through the speaker.

        Args:
            audio_data: Raw PCM audio bytes (int16) or WAV bytes.
            sample_rate: Sample rate of the audio. Uses default if None.
        """
        if not HAS_PYAUDIO or self._pa is None:
            logger.error("Cannot play audio: pyaudio not available")
            return

        if sample_rate is None:
            sample_rate = self.sample_rate

        self._is_playing = True

        try:
            output_stream = self._pa.open(
                format=self._format,
                channels=self.channels,
                rate=sample_rate,
                output=True,
                output_device_index=self.output_device_index,
            )

            # Write audio in chunks
            chunk_bytes = self.chunk_size * self._sample_width
            offset = 0
            while offset < len(audio_data) and self._is_playing:
                end = min(offset + chunk_bytes, len(audio_data))
                output_stream.write(audio_data[offset:end])
                offset = end

            output_stream.stop_stream()
            output_stream.close()

        except Exception as e:
            logger.error(f"Audio playback error: {e}")
        finally:
            self._is_playing = False

    def stop_playback(self):
        """Stop current audio playback (for interruptibility)."""
        self._is_playing = False

    def play_chime(self, chime_type: str):
        """
        Play a notification chime sound.

        Args:
            chime_type: Type of chime ('listening', 'error', 'thinking').
        """
        # Generate simple chime tones programmatically as fallback
        duration_s = 0.2
        t = np.linspace(0, duration_s, int(self.sample_rate * duration_s), False)

        if chime_type == "listening":
            # Rising two-tone beep
            tone1 = np.sin(2 * np.pi * 800 * t[:len(t)//2]) * 16000
            tone2 = np.sin(2 * np.pi * 1200 * t[len(t)//2:]) * 16000
            chime = np.concatenate([tone1, tone2])
        elif chime_type == "error":
            # Descending tone
            tone = np.sin(2 * np.pi * 400 * t) * 16000
            chime = tone
        elif chime_type == "thinking":
            # Soft single tone
            tone = np.sin(2 * np.pi * 600 * t) * 10000
            chime = tone
        else:
            return

        # Apply fade in/out to avoid clicks
        fade_samples = int(0.01 * self.sample_rate)
        if fade_samples > 0 and len(chime) > 2 * fade_samples:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            chime[:fade_samples] *= fade_in
            chime[-fade_samples:] *= fade_out

        audio_bytes = chime.astype(np.int16).tobytes()
        self.play_audio(audio_bytes)

    def set_muted(self, muted: bool):
        """
        Set the mute state of the microphone.

        Args:
            muted: True to mute, False to unmute.
        """
        self._muted = muted
        if muted:
            self._is_recording = False
        logger.info(f"Microphone {'muted' if muted else 'unmuted'}")

    @property
    def is_muted(self) -> bool:
        """Check if the microphone is currently muted."""
        return self._muted

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently being played."""
        return self._is_playing

    def _numpy_to_wav(self, audio_data: np.ndarray) -> bytes:
        """
        Convert a NumPy int16 array to WAV-formatted bytes.

        Args:
            audio_data: NumPy array of int16 audio samples.

        Returns:
            WAV file as bytes.
        """
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self._sample_width)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.astype(np.int16).tobytes())
        return buffer.getvalue()

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
