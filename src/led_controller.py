"""
LED Ring Controller module.

Drives the WS2812B 12-LED ring to provide visual state feedback
for the voice assistant. Runs animations in a dedicated thread
to avoid blocking the main pipeline.

LED States:
    - idle:       All LEDs off or dim white breathe
    - listening:  Spinning blue dot
    - processing: Pulsing purple
    - speaking:   Gentle green breathe
    - command:    Quick green flash
    - error:      Red blink × 3
    - muted:      Solid red (single LED)
"""

import colorsys
import math
import threading
import time
from typing import Tuple

from loguru import logger

try:
    import board
    import neopixel
    HAS_NEOPIXEL = True
except ImportError:
    HAS_NEOPIXEL = False

try:
    from rpi_ws281x import PixelStrip, Color as WS2812Color
    HAS_WS281X = True
except ImportError:
    HAS_WS281X = False


# Colour definitions (R, G, B)
COLORS = {
    "off": (0, 0, 0),
    "white": (255, 255, 255),
    "dim_white": (20, 20, 20),
    "blue": (0, 80, 255),
    "purple": (130, 0, 200),
    "green": (0, 200, 50),
    "red": (255, 0, 0),
    "warm_white": (255, 200, 100),
}

# Animation frame rate
ANIMATION_FPS = 30


class LEDController:
    """
    WS2812B LED ring controller with state-based animations.

    Runs animations in a background thread, exposing a simple
    `set_state(state)` API for the main orchestrator.
    """

    def __init__(
        self,
        num_leds: int = 12,
        gpio_pin: int = 18,
        brightness: int = 50,
        led_type: str = "WS2812B",
    ):
        """
        Initialise the LED controller.

        Args:
            num_leds: Number of LEDs in the ring.
            gpio_pin: GPIO pin for the LED data line (must support PWM).
            brightness: Default brightness (0-255).
            led_type: LED type identifier.
        """
        self.num_leds = num_leds
        self.gpio_pin = gpio_pin
        self.brightness = brightness
        self.led_type = led_type

        self._strip = None
        self._current_state = "off"
        self._target_state = "off"
        self._animation_thread = None
        self._running = False
        self._lock = threading.Lock()

        # Try to initialise hardware
        self._init_hardware()

    def _init_hardware(self):
        """Initialise the LED hardware."""
        if HAS_WS281X:
            try:
                self._strip = PixelStrip(
                    self.num_leds,
                    self.gpio_pin,
                    800000,          # LED frequency (Hz)
                    10,              # DMA channel
                    False,           # Invert signal
                    self.brightness,
                    0,               # Channel
                )
                self._strip.begin()
                logger.info(
                    f"LED strip initialised: {self.num_leds} LEDs on GPIO{self.gpio_pin}"
                )
            except Exception as e:
                logger.warning(f"Failed to initialise WS2812 strip: {e}")
                self._strip = None
        elif HAS_NEOPIXEL:
            try:
                pin = getattr(board, f"D{self.gpio_pin}")
                self._strip = neopixel.NeoPixel(
                    pin,
                    self.num_leds,
                    brightness=self.brightness / 255.0,
                    auto_write=False,
                )
                logger.info(
                    f"NeoPixel strip initialised: {self.num_leds} LEDs on D{self.gpio_pin}"
                )
            except Exception as e:
                logger.warning(f"Failed to initialise NeoPixel strip: {e}")
                self._strip = None
        else:
            logger.info(
                "No LED library available (rpi_ws281x or neopixel). "
                "LED animations will be simulated in logs."
            )

    def start(self):
        """Start the animation thread."""
        if self._running:
            return

        self._running = True
        self._animation_thread = threading.Thread(
            target=self._animation_loop,
            daemon=True,
            name="led-animation",
        )
        self._animation_thread.start()
        logger.debug("LED animation thread started")

    def stop(self):
        """Stop the animation thread and turn off LEDs."""
        self._running = False
        if self._animation_thread is not None:
            self._animation_thread.join(timeout=2.0)
            self._animation_thread = None

        self._set_all_leds(COLORS["off"])
        logger.debug("LED animation thread stopped")

    def set_state(self, state: str):
        """
        Set the LED animation state.

        Args:
            state: One of 'idle', 'listening', 'processing', 'speaking',
                   'command', 'error', 'muted', 'off'.
        """
        valid_states = {
            "idle", "listening", "processing", "speaking",
            "command", "error", "muted", "off"
        }

        if state not in valid_states:
            logger.warning(f"Unknown LED state: '{state}'")
            return

        with self._lock:
            self._target_state = state

        logger.debug(f"LED state -> {state}")

    def _animation_loop(self):
        """Main animation loop running in a background thread."""
        frame = 0
        frame_time = 1.0 / ANIMATION_FPS

        while self._running:
            with self._lock:
                state = self._target_state
                self._current_state = state

            try:
                if state == "idle":
                    self._animate_idle(frame)
                elif state == "listening":
                    self._animate_listening(frame)
                elif state == "processing":
                    self._animate_processing(frame)
                elif state == "speaking":
                    self._animate_speaking(frame)
                elif state == "command":
                    self._animate_command(frame)
                elif state == "error":
                    self._animate_error(frame)
                elif state == "muted":
                    self._animate_muted()
                elif state == "off":
                    self._set_all_leds(COLORS["off"])
            except Exception as e:
                logger.error(f"LED animation error: {e}")

            frame += 1
            time.sleep(frame_time)

    def _animate_idle(self, frame: int):
        """Idle: dim white breathe effect."""
        # Breathing effect using sine wave
        breath = (math.sin(frame * 0.05) + 1) / 2  # 0.0 to 1.0
        brightness = int(5 + breath * 15)  # 5 to 20
        color = (brightness, brightness, brightness)
        self._set_all_leds(color)

    def _animate_listening(self, frame: int):
        """Listening: spinning blue dot."""
        self._set_all_leds(COLORS["off"])

        # Spinning dot with trail
        position = (frame // 2) % self.num_leds
        blue = COLORS["blue"]

        # Main dot
        self._set_led(position, blue)
        # Trail (dimmer)
        trail1 = (position - 1) % self.num_leds
        trail2 = (position - 2) % self.num_leds
        self._set_led(trail1, self._dim_color(blue, 0.4))
        self._set_led(trail2, self._dim_color(blue, 0.15))

        self._show()

    def _animate_processing(self, frame: int):
        """Processing: pulsing purple."""
        pulse = (math.sin(frame * 0.1) + 1) / 2  # 0.0 to 1.0
        base = COLORS["purple"]
        brightness = 0.2 + pulse * 0.8  # 0.2 to 1.0
        color = self._dim_color(base, brightness)
        self._set_all_leds(color)

    def _animate_speaking(self, frame: int):
        """Speaking: gentle green breathe."""
        breath = (math.sin(frame * 0.08) + 1) / 2
        base = COLORS["green"]
        brightness = 0.3 + breath * 0.7
        color = self._dim_color(base, brightness)
        self._set_all_leds(color)

    def _animate_command(self, frame: int):
        """Command sent: quick green flash (then return to speaking)."""
        # Flash for ~0.5 seconds (15 frames at 30fps)
        flash_phase = frame % 30

        if flash_phase < 5:
            self._set_all_leds(COLORS["green"])
        elif flash_phase < 10:
            self._set_all_leds(COLORS["off"])
        elif flash_phase < 15:
            self._set_all_leds(COLORS["green"])
        else:
            # Return to idle-like state after flash
            self._set_all_leds(self._dim_color(COLORS["green"], 0.3))

    def _animate_error(self, frame: int):
        """Error: red blink × 3."""
        # 3 blinks over ~1.5 seconds (45 frames at 30fps)
        blink_phase = frame % 45

        if blink_phase < 5:
            self._set_all_leds(COLORS["red"])
        elif blink_phase < 10:
            self._set_all_leds(COLORS["off"])
        elif blink_phase < 15:
            self._set_all_leds(COLORS["red"])
        elif blink_phase < 20:
            self._set_all_leds(COLORS["off"])
        elif blink_phase < 25:
            self._set_all_leds(COLORS["red"])
        else:
            self._set_all_leds(COLORS["off"])

    def _animate_muted(self):
        """Muted: solid red on first LED only."""
        self._set_all_leds(COLORS["off"])
        self._set_led(0, COLORS["red"])
        self._show()

    def _set_all_leds(self, color: Tuple[int, int, int]):
        """Set all LEDs to the same colour and update the strip."""
        if self._strip is None:
            return

        if HAS_WS281X and isinstance(self._strip, PixelStrip):
            ws_color = WS2812Color(color[0], color[1], color[2])
            for i in range(self.num_leds):
                self._strip.setPixelColor(i, ws_color)
            self._strip.show()
        elif HAS_NEOPIXEL:
            self._strip.fill(color)
            self._strip.show()

    def _set_led(self, index: int, color: Tuple[int, int, int]):
        """Set a single LED to a colour (does NOT call show)."""
        if self._strip is None or index < 0 or index >= self.num_leds:
            return

        if HAS_WS281X and isinstance(self._strip, PixelStrip):
            self._strip.setPixelColor(index, WS2812Color(color[0], color[1], color[2]))
        elif HAS_NEOPIXEL:
            self._strip[index] = color

    def _show(self):
        """Push pixel data to the LED strip."""
        if self._strip is None:
            return

        try:
            self._strip.show()
        except Exception:
            pass

    @staticmethod
    def _dim_color(
        color: Tuple[int, int, int], factor: float
    ) -> Tuple[int, int, int]:
        """
        Dim a colour by a factor.

        Args:
            color: RGB tuple.
            factor: Brightness factor (0.0 to 1.0).

        Returns:
            Dimmed RGB tuple.
        """
        return (
            int(color[0] * factor),
            int(color[1] * factor),
            int(color[2] * factor),
        )

    @property
    def current_state(self) -> str:
        """Get the current LED state."""
        return self._current_state

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
