"""
Tests for the LED controller module.

Validates LED state transitions, colour calculations,
and animation behaviour.
"""

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from led_controller import LEDController, COLORS


class TestLEDController:
    """Tests for the LED controller (without real hardware)."""

    def setup_method(self):
        """Create a LED controller instance (no hardware)."""
        self.leds = LEDController(
            num_leds=12,
            gpio_pin=18,
            brightness=50,
        )

    def test_init(self):
        """Controller should initialise without hardware."""
        assert self.leds.num_leds == 12
        assert self.leds.gpio_pin == 18
        assert self.leds.brightness == 50

    def test_valid_states(self):
        """All valid states should be accepted."""
        valid_states = [
            "idle", "listening", "processing", "speaking",
            "command", "error", "muted", "off"
        ]
        for state in valid_states:
            self.leds.set_state(state)
            assert self.leds._target_state == state

    def test_invalid_state(self):
        """Invalid state should not change current state."""
        self.leds.set_state("idle")
        self.leds.set_state("invalid_state")
        assert self.leds._target_state == "idle"

    def test_state_transitions(self):
        """State transitions should update correctly."""
        self.leds.set_state("idle")
        assert self.leds._target_state == "idle"

        self.leds.set_state("listening")
        assert self.leds._target_state == "listening"

        self.leds.set_state("processing")
        assert self.leds._target_state == "processing"

        self.leds.set_state("speaking")
        assert self.leds._target_state == "speaking"

        self.leds.set_state("idle")
        assert self.leds._target_state == "idle"

    def test_dim_color(self):
        """Dimming should reduce RGB values proportionally."""
        color = (100, 200, 50)

        dimmed = LEDController._dim_color(color, 0.5)
        assert dimmed == (50, 100, 25)

        dimmed_zero = LEDController._dim_color(color, 0.0)
        assert dimmed_zero == (0, 0, 0)

        dimmed_full = LEDController._dim_color(color, 1.0)
        assert dimmed_full == (100, 200, 50)

    def test_colors_defined(self):
        """All required colours should be defined."""
        required_colors = [
            "off", "white", "dim_white", "blue",
            "purple", "green", "red", "warm_white"
        ]
        for color_name in required_colors:
            assert color_name in COLORS
            color = COLORS[color_name]
            assert len(color) == 3
            assert all(0 <= c <= 255 for c in color)

    def test_off_color(self):
        """Off colour should be all zeros."""
        assert COLORS["off"] == (0, 0, 0)

    def test_context_manager(self):
        """Context manager should start and stop cleanly."""
        # Without hardware, start/stop should not crash
        with LEDController(num_leds=12) as leds:
            leds.set_state("listening")
            assert leds._target_state == "listening"

    def test_start_stop(self):
        """Start and stop should work without hardware."""
        self.leds.start()
        assert self.leds._running is True

        self.leds.stop()
        assert self.leds._running is False

    def test_current_state_property(self):
        """Current state property should reflect the target state."""
        self.leds._current_state = "processing"
        assert self.leds.current_state == "processing"

    def test_animation_state_mapping(self):
        """Each state should have a corresponding animation method."""
        animation_methods = {
            "idle": "_animate_idle",
            "listening": "_animate_listening",
            "processing": "_animate_processing",
            "speaking": "_animate_speaking",
            "command": "_animate_command",
            "error": "_animate_error",
            "muted": "_animate_muted",
        }
        for state, method_name in animation_methods.items():
            assert hasattr(self.leds, method_name), (
                f"Missing animation method: {method_name}"
            )
