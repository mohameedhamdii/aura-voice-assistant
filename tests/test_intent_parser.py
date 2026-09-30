"""
Tests for the intent parser and device controller module.

Validates device command extraction from LLM output for 15 test cases,
covering structured commands, natural language fallback, and edge cases.
"""

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from device_controller import DeviceController, DeviceCommand


# Path to the devices config relative to test file
DEVICES_CONFIG = os.path.join(
    os.path.dirname(__file__), "..", "config", "devices.yaml"
)


class TestIntentParser:
    """Tests for device command extraction — 15 test cases."""

    def setup_method(self):
        """Create a device controller with the real device config."""
        self.controller = DeviceController(
            devices_config_path=DEVICES_CONFIG,
            serial_port="/dev/null",  # Won't actually connect
        )

    # --- Structured command parsing (regex-based) ---

    def test_01_simple_on_command(self):
        """Parse a basic 'turn on' structured command."""
        response = (
            "Turning on the living room light. "
            "[DEVICE_CMD: action=on, device=living_room_light]"
        )
        clean_text, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].device == "living_room_light"
        assert commands[0].action == "on"
        assert "[DEVICE_CMD" not in clean_text

    def test_02_simple_off_command(self):
        """Parse a basic 'turn off' structured command."""
        response = (
            "Turning off the bedroom light. "
            "[DEVICE_CMD: action=off, device=bedroom_light]"
        )
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].device == "bedroom_light"
        assert commands[0].action == "off"

    def test_03_brightness_command(self):
        """Parse a brightness control command."""
        response = (
            "Setting living room light to 50% brightness. "
            "[DEVICE_CMD: action=brightness, device=living_room_light, value=50]"
        )
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].device == "living_room_light"
        assert commands[0].action == "brightness"

    def test_04_color_command(self):
        """Parse a colour change command."""
        response = (
            "Changing living room light to blue. "
            "[DEVICE_CMD: action=color, device=living_room_light, value=blue]"
        )
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].action == "color"

    def test_05_multiple_commands(self):
        """Parse multiple device commands in one response."""
        response = (
            "Turning on both lights. "
            "[DEVICE_CMD: action=on, device=living_room_light] "
            "[DEVICE_CMD: action=on, device=bedroom_light]"
        )
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 2

    def test_06_plug_command(self):
        """Parse a smart plug command."""
        response = (
            "Turning off the smart plug. "
            "[DEVICE_CMD: action=off, device=smart_plug_1]"
        )
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].device == "smart_plug_1"

    def test_07_no_command_in_response(self):
        """Response without device commands should return empty list."""
        response = "The capital of France is Paris."
        clean_text, commands = self.controller.parse_commands(response)

        assert len(commands) == 0
        assert "Paris" in clean_text

    # --- Natural language fallback parsing ---

    def test_08_natural_turn_on(self):
        """Natural language 'turn on' should be parsed by fallback."""
        response = "Sure, I'll turn on the living room light for you."
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].device == "living_room_light"
        assert commands[0].action == "on"

    def test_09_natural_turn_off(self):
        """Natural language 'turn off' should be parsed by fallback."""
        response = "I'll turn off the bedroom light right away."
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].device == "bedroom_light"
        assert commands[0].action == "off"

    def test_10_natural_switch_on(self):
        """Alias 'switch on' should be understood."""
        response = "I'll switch on the plug for you."
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].action == "on"

    def test_11_natural_dim(self):
        """Natural language 'dim' should map to brightness action."""
        response = "I'll dim the living room light."
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].action == "brightness"
        assert commands[0].value == "30"  # dim defaults to 30

    # --- Edge cases ---

    def test_12_unknown_device(self):
        """Unknown device in structured command should be rejected."""
        response = "[DEVICE_CMD: action=on, device=nonexistent_device]"
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 0

    def test_13_invalid_action_for_device(self):
        """Color command on a device without color capability should be rejected."""
        response = "[DEVICE_CMD: action=color, device=smart_plug_1]"
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 0  # smart_plug_1 only has on_off

    def test_14_clean_text_formatting(self):
        """Clean text should have no extra whitespace or newlines."""
        response = (
            "Done.\n\n"
            "[DEVICE_CMD: action=on, device=living_room_light]\n\n"
            "The light is now on."
        )
        clean_text, commands = self.controller.parse_commands(response)

        assert "\n" not in clean_text
        assert "  " not in clean_text
        assert len(commands) == 1

    def test_15_device_alias_matching(self):
        """Device aliases should resolve to the correct device name."""
        # "bedroom" is an alias for "bedroom_light"
        response = "I'll turn on the bedroom light."
        _, commands = self.controller.parse_commands(response)

        assert len(commands) == 1
        assert commands[0].device == "bedroom_light"


class TestDeviceCommand:
    """Tests for the DeviceCommand dataclass."""

    def test_creation(self):
        """Basic dataclass creation."""
        cmd = DeviceCommand(device="living_room_light", action="on")
        assert cmd.device == "living_room_light"
        assert cmd.action == "on"
        assert cmd.value is None

    def test_creation_with_value(self):
        """Creation with optional value."""
        cmd = DeviceCommand(device="living_room_light", action="brightness", value="75")
        assert cmd.value == "75"


class TestDeviceRegistry:
    """Tests for the device registry loading."""

    def test_load_devices(self):
        """Should load all devices from config."""
        controller = DeviceController(
            devices_config_path=DEVICES_CONFIG,
            serial_port="/dev/null",
        )

        assert len(controller.devices) == 3
        assert "living_room_light" in controller.devices
        assert "bedroom_light" in controller.devices
        assert "smart_plug_1" in controller.devices

    def test_device_capabilities(self):
        """Devices should have correct capabilities."""
        controller = DeviceController(
            devices_config_path=DEVICES_CONFIG,
            serial_port="/dev/null",
        )

        living_room = controller.devices["living_room_light"]
        assert "on_off" in living_room["capabilities"]
        assert "brightness" in living_room["capabilities"]
        assert "color" in living_room["capabilities"]

        plug = controller.devices["smart_plug_1"]
        assert "on_off" in plug["capabilities"]
        assert "brightness" not in plug["capabilities"]

    def test_device_aliases(self):
        """Device aliases should be registered."""
        controller = DeviceController(
            devices_config_path=DEVICES_CONFIG,
            serial_port="/dev/null",
        )

        assert "bedroom" in controller.device_aliases
        assert controller.device_aliases["bedroom"] == "bedroom_light"
        assert "plug" in controller.device_aliases
        assert controller.device_aliases["plug"] == "smart_plug_1"
