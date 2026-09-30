"""
Tests for the device controller module (integration tests).

Validates serial command formatting and mock ESP32 communication.
"""

import json
import threading
import time

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from device_controller import DeviceController, DeviceCommand, CommandResult
from serial_bridge import SerialBridge, SerialResponse


class MockSerialPort:
    """Mock serial port that simulates ESP32 responses."""

    def __init__(self):
        self.written_data = []
        self._response_queue = []
        self._read_buffer = b""
        self.is_open = True
        self.timeout = 1.0
        self.write_timeout = 1.0

    def write(self, data: bytes):
        """Capture written data and queue a response."""
        self.written_data.append(data.decode("utf-8"))

        # Parse the command and generate a mock response
        try:
            line = data.decode("utf-8").strip()
            if line.startswith("CMD:"):
                cmd_data = json.loads(line[4:])
                response = {
                    "status": "ok",
                    "device": cmd_data.get("device", "unknown"),
                    "state": cmd_data.get("action", "unknown"),
                }
                self._read_buffer += f"RSP:{json.dumps(response)}\n".encode("utf-8")
        except Exception:
            pass

    def readline(self) -> bytes:
        """Read a line from the mock buffer."""
        if not self._read_buffer:
            time.sleep(0.1)
            return b""

        if b"\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split(b"\n", 1)
            return line + b"\n"

        data = self._read_buffer
        self._read_buffer = b""
        return data

    def flush(self):
        pass

    def close(self):
        self.is_open = False

    def reset_input_buffer(self):
        self._read_buffer = b""


class TestDeviceControllerIntegration:
    """Integration tests for device controller with mock serial."""

    def test_serial_command_format(self):
        """Verify the JSON command format sent over serial."""
        mock_port = MockSerialPort()

        # Manually test command formatting
        cmd_data = {"device": "living_room_light", "action": "on"}
        cmd_line = f"CMD:{json.dumps(cmd_data)}\n"
        mock_port.write(cmd_line.encode("utf-8"))

        assert len(mock_port.written_data) == 1
        sent = mock_port.written_data[0]
        assert sent.startswith("CMD:")
        assert '"device": "living_room_light"' in sent or '"device":"living_room_light"' in sent

    def test_serial_response_parsing(self):
        """Verify response parsing from mock ESP32."""
        bridge = SerialBridge(port="/dev/null")

        # Simulate response handling
        json_str = '{"status":"ok","device":"living_room_light","state":"on"}'
        bridge._handle_response(json_str)

        assert bridge._last_response is not None
        assert bridge._last_response.status == "ok"
        assert bridge._last_response.device == "living_room_light"
        assert bridge._last_response.state == "on"

    def test_heartbeat_parsing(self):
        """Verify heartbeat message parsing."""
        bridge = SerialBridge(port="/dev/null")

        heartbeat_data = {
            "devices": [
                {"name": "living_room_light", "state": "on"},
                {"name": "smart_plug_1", "state": "off"},
            ],
            "timestamp": 1234567890,
        }

        bridge._handle_heartbeat(json.dumps(heartbeat_data))

        assert bridge.get_device_state("living_room_light") == "on"
        assert bridge.get_device_state("smart_plug_1") == "off"
        assert bridge.get_device_state("unknown_device") == "unknown"

    def test_heartbeat_callback(self):
        """Verify heartbeat callback is invoked."""
        bridge = SerialBridge(port="/dev/null")
        callback_data = []

        bridge.set_heartbeat_callback(lambda data: callback_data.append(data))

        heartbeat = '{"devices":[{"name":"test","state":"on"}]}'
        bridge._handle_heartbeat(heartbeat)

        assert len(callback_data) == 1
        assert "devices" in callback_data[0]

    def test_invalid_response_json(self):
        """Invalid JSON should be handled gracefully."""
        bridge = SerialBridge(port="/dev/null")
        bridge._handle_response("not valid json")
        assert bridge._last_response is None

    def test_command_result_success(self):
        """CommandResult should correctly represent success."""
        result = CommandResult(
            success=True,
            device="living_room_light",
            action="on",
            state="on",
        )
        assert result.success is True
        assert result.error_msg == ""

    def test_command_result_failure(self):
        """CommandResult should correctly represent failure."""
        result = CommandResult(
            success=False,
            device="living_room_light",
            action="on",
            error_msg="Device not reachable",
        )
        assert result.success is False
        assert "not reachable" in result.error_msg

    def test_execute_without_connection(self):
        """Executing without connection should return failure."""
        controller = DeviceController(
            devices_config_path=os.path.join(
                os.path.dirname(__file__), "..", "config", "devices.yaml"
            ),
            serial_port="/dev/null",
        )

        cmd = DeviceCommand(device="living_room_light", action="on")
        result = controller.execute(cmd)

        assert result.success is False

    def test_get_device_states(self):
        """Should track device states from heartbeats."""
        bridge = SerialBridge(port="/dev/null")

        # Simulate heartbeat
        bridge._device_states = {
            "living_room_light": "on",
            "bedroom_light": "off",
        }

        states = bridge.get_all_device_states()
        assert len(states) == 2
        assert states["living_room_light"] == "on"

    def test_connection_state(self):
        """Bridge should report disconnected when not connected."""
        bridge = SerialBridge(port="/dev/null")
        assert bridge.is_connected is False
