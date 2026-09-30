"""
Main Orchestrator for the Offline Voice Assistant.

Coordinates all modules: audio pipeline, wake word detection, speech-to-text,
LLM query engine, text-to-speech, device controller, and LED feedback.

Usage:
    python src/main.py
    python src/main.py --config config/assistant.yaml
"""

import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path

import yaml
from loguru import logger

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio_pipeline import AudioPipeline
from device_controller import DeviceController
from led_controller import LEDController
from llm_engine import LLMEngine
from stt_engine import STTEngine
from tts_engine import TTSEngine
from wake_word import WakeWordDetector

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


def setup_logging(config: dict):
    """Configure loguru logging based on config."""
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO")
    log_file = log_config.get("file", "logs/assistant.log")
    max_size = log_config.get("max_size_mb", 10)
    backup_count = log_config.get("backup_count", 3)

    # Remove default handler
    logger.remove()

    # Console handler
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # File handler
    log_path = PROJECT_ROOT / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_path),
        level=log_level,
        rotation=f"{max_size} MB",
        retention=backup_count,
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


def load_config(config_path: str) -> dict:
    """
    Load the main configuration file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Configuration dictionary.
    """
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        logger.warning(f"Config file not found at {path}, using defaults")
        return {}

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    logger.info(f"Configuration loaded from {path}")
    return config


def load_audio_config() -> dict:
    """Load the audio-specific configuration."""
    audio_config_path = PROJECT_ROOT / "config" / "audio.yaml"
    if audio_config_path.exists():
        with open(audio_config_path, "r") as f:
            return yaml.safe_load(f)
    return {}


class VoiceAssistant:
    """
    Main voice assistant orchestrator.

    Coordinates the full pipeline: wake word → ASR → LLM → TTS → device control.
    """

    def __init__(self, config: dict):
        """
        Initialise all assistant modules.

        Args:
            config: Main configuration dictionary.
        """
        self.config = config
        self._running = False
        self._mute_thread = None

        # Load sub-configs
        audio_config = load_audio_config()
        models_config = config.get("models", {})
        hardware_config = config.get("hardware", {})

        # --- Initialise modules ---

        # Audio Pipeline
        logger.info("Initialising audio pipeline...")
        self.audio = AudioPipeline(audio_config)

        # Wake Word Detector
        logger.info("Initialising wake word detector...")
        wake_config = models_config.get("wake_word", {})
        wake_model_path = str(PROJECT_ROOT / wake_config.get(
            "path", "models/wake_word/hey_assistant.tflite"
        ))
        self.wake = WakeWordDetector(
            model_path=wake_model_path if Path(wake_model_path).exists() else None,
            model_name=wake_config.get("model_name", "hey_assistant"),
            threshold=wake_config.get("threshold", 0.5),
        )

        # Speech-to-Text Engine
        logger.info("Initialising STT engine...")
        stt_config = models_config.get("whisper", {})
        self.stt = STTEngine(
            model_path=str(PROJECT_ROOT / stt_config.get(
                "path", "models/whisper/ggml-base.en.bin"
            )),
            n_threads=stt_config.get("n_threads", 4),
            language=stt_config.get("language", "en"),
            use_gpu=stt_config.get("use_gpu", False),
        )

        # LLM Query Engine
        logger.info("Initialising LLM engine...")
        llm_config = models_config.get("llm", {})
        self.llm = LLMEngine(
            model_path=str(PROJECT_ROOT / llm_config.get(
                "path", "models/llm/phi-3.5-mini-instruct.Q4_K_M.gguf"
            )),
            system_prompt_path=str(
                PROJECT_ROOT / config.get("system_prompt_path", "config/system_prompt.txt")
            ),
            n_threads=llm_config.get("n_threads", 4),
            n_gpu_layers=llm_config.get("n_gpu_layers", 0),
            temperature=llm_config.get("temperature", 0.3),
            max_tokens=llm_config.get("max_tokens", 100),
            context_window=llm_config.get("context_window", 2048),
            context_turns=llm_config.get("context_turns", 3),
            context_timeout_s=llm_config.get("context_timeout_s", 120),
        )

        # Text-to-Speech Engine
        logger.info("Initialising TTS engine...")
        tts_config = models_config.get("tts", {})
        self.tts = TTSEngine(
            model_path=str(PROJECT_ROOT / tts_config.get(
                "path", "models/piper/en_US-lessac-medium.onnx"
            )),
            voice=tts_config.get("voice", "en_US-lessac-medium"),
            sample_rate=tts_config.get("sample_rate", 22050),
            output_sample_rate=tts_config.get("output_sample_rate", 16000),
        )

        # Device Controller
        logger.info("Initialising device controller...")
        serial_config = hardware_config.get("serial", {})
        self.devices = DeviceController(
            devices_config_path=str(PROJECT_ROOT / "config" / "devices.yaml"),
            serial_port=serial_config.get("port", "/dev/ttyUSB0"),
            baud_rate=serial_config.get("baud_rate", 115200),
            timeout_s=serial_config.get("timeout_s", 2),
        )

        # LED Controller
        logger.info("Initialising LED controller...")
        led_config = hardware_config.get("led", {})
        self.leds = LEDController(
            num_leds=led_config.get("num_leds", 12),
            gpio_pin=led_config.get("gpio_pin", 18),
            brightness=led_config.get("brightness", 50),
            led_type=led_config.get("led_type", "WS2812B"),
        )

        logger.info("All modules initialised")

    def start(self):
        """Start the voice assistant."""
        logger.info("=" * 60)
        logger.info("  Offline Voice Assistant Starting")
        logger.info("=" * 60)

        self._running = True

        # Start hardware
        self.audio.start()
        self.leds.start()

        # Try to connect to ESP32 bridge (non-fatal if unavailable)
        if not self.devices.connect():
            logger.warning(
                "ESP32 Matter bridge not connected. "
                "Device control will be unavailable."
            )

        # Start mute button monitor
        self._start_mute_monitor()

        # Set initial LED state
        self.leds.set_state("idle")

        # Print status
        self._print_status()

        logger.info("Voice assistant is ready. Say 'Hey Assistant' to begin!")
        print("\n🎙️  Voice assistant is ready. Say 'Hey Assistant' to begin!\n")
        print("Press Ctrl+C to stop.\n")

    def _print_status(self):
        """Print the status of all modules."""
        status_lines = [
            f"  Wake word:  {'✅ Ready' if self.wake.is_available else '⚠️  Unavailable (use manual trigger)'}",
            f"  STT:        {'✅ Ready' if self.stt.is_available else '❌ Model not loaded'}",
            f"  LLM:        {'✅ Ready' if self.llm.is_available else '❌ Model not loaded'}",
            f"  TTS:        {'✅ Ready' if self.tts.is_available else '❌ Model not loaded'}",
            f"  Matter:     {'✅ Connected' if self.devices._bridge.is_connected else '⚠️  Not connected'}",
            f"  LEDs:       {'✅ Hardware' if self.leds._strip is not None else 'ℹ️  Simulated'}",
        ]
        logger.info("Module Status:")
        for line in status_lines:
            logger.info(line)

    def run(self):
        """Main processing loop."""
        self.start()

        try:
            while self._running:
                self._process_one_interaction()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()

    def _process_one_interaction(self):
        """Process a single wake word → response cycle."""
        try:
            # Step 1: Wait for wake word
            self.leds.set_state("idle")

            if self.wake.is_available:
                audio_stream = self.audio.get_stream()
                self.wake.listen(audio_stream)
            else:
                # Fallback: wait for keyboard trigger (development mode)
                logger.info("Wake word unavailable. Press Enter to simulate wake word...")
                try:
                    input()
                except EOFError:
                    self._running = False
                    return

            if not self._running:
                return

            # Step 2: Listen for user speech
            logger.info("Wake word detected! Listening...")
            self.leds.set_state("listening")
            self.audio.play_chime("listening")

            recording = self.audio.record_until_silence()

            if recording is None:
                logger.warning("No speech recorded")
                self.leds.set_state("idle")
                return

            # Step 3: Transcribe speech
            logger.info("Transcribing speech...")
            self.leds.set_state("processing")

            user_text = self.stt.transcribe(recording)

            if not user_text or not user_text.strip():
                logger.warning("Transcription returned empty text")
                self.leds.set_state("idle")
                return

            logger.info(f"User said: '{user_text}'")
            print(f"\n👤 User: {user_text}")

            # Step 4: Query LLM
            logger.info("Querying LLM...")
            response_text = self.llm.query(user_text)
            logger.info(f"LLM response: '{response_text}'")

            # Step 5: Parse device commands
            clean_text, device_cmds = self.devices.parse_commands(response_text)

            # Step 6: Execute device commands
            for cmd in device_cmds:
                self.leds.set_state("command")
                result = self.devices.execute(cmd)
                if not result.success:
                    clean_text += f" Sorry, I couldn't control {cmd.device}."
                    logger.warning(
                        f"Device command failed: {cmd.device} -> "
                        f"{cmd.action}: {result.error_msg}"
                    )
                else:
                    logger.info(f"Device command succeeded: {cmd.device} -> {cmd.action}")

            # Step 7: Speak response
            print(f"🤖 Assistant: {clean_text}\n")
            self.leds.set_state("speaking")
            self.tts.speak(clean_text, self.audio)

            # Step 8: Return to idle
            self.leds.set_state("idle")

        except Exception as e:
            logger.error(f"Interaction error: {e}")
            self.leds.set_state("error")
            time.sleep(1.5)
            self.leds.set_state("idle")

    def _start_mute_monitor(self):
        """Start monitoring the mute button GPIO."""
        mute_config = self.config.get("hardware", {}).get("mute_button", {})
        gpio_pin = mute_config.get("gpio_pin", 17)

        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            def mute_callback(channel):
                is_muted = not self.audio.is_muted
                self.audio.set_muted(is_muted)
                if is_muted:
                    self.leds.set_state("muted")
                else:
                    self.leds.set_state("idle")

            GPIO.add_event_detect(
                gpio_pin,
                GPIO.FALLING,
                callback=mute_callback,
                bouncetime=300,
            )

            logger.info(f"Mute button monitor started on GPIO{gpio_pin}")

        except ImportError:
            logger.info("RPi.GPIO not available — mute button disabled")
        except Exception as e:
            logger.warning(f"Failed to set up mute button: {e}")

    def shutdown(self):
        """Gracefully shut down all modules."""
        logger.info("Shutting down voice assistant...")
        self._running = False

        # Stop components
        self.leds.set_state("off")
        self.leds.stop()
        self.audio.stop()
        self.devices.disconnect()

        # Clean up GPIO
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except (ImportError, Exception):
            pass

        logger.info("Voice assistant stopped")
        print("\n👋 Voice assistant stopped. Goodbye!")


def main():
    """Entry point for the voice assistant."""
    parser = argparse.ArgumentParser(
        description="Offline Voice Assistant with On-Device Tiny LLM",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/assistant.yaml",
        help="Path to the main configuration file",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Override log level if debug flag is set
    if args.debug:
        config.setdefault("logging", {})["level"] = "DEBUG"

    # Set up logging
    setup_logging(config)

    # Handle SIGTERM gracefully
    assistant = None

    def signal_handler(sig, frame):
        nonlocal assistant
        if assistant:
            assistant.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)

    # Create and run the assistant
    try:
        assistant = VoiceAssistant(config)
        assistant.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if assistant:
            assistant.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
