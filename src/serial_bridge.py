"""
Serial Bridge module.

Handles UART serial communication between the Raspberry Pi and the ESP32-C6
Matter bridge. Uses a JSON-based protocol for sending commands and receiving
status responses.

Protocol:
    Pi -> ESP32:  CMD:{"device":"living_room_light","action":"on"}\n
    ESP32 -> Pi:  RSP:{"status":"ok","device":"living_room_light","state":"on"}\n
    ESP32 -> Pi:  HBT:{"devices":[...],"timestamp":...}\n  (heartbeat every 10s)
"""

import json
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from loguru import logger

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False
    logger.warning(
        "pyserial not installed. Serial communication will be unavailable. "
        "Install with: pip install pyserial"
    )


@dataclass
class SerialResponse:
    """Represents a response from the ESP32 bridge."""
    status: str         # 'ok' or 'error'
    device: str         # Device name
    state: str          # Current device state
    error_msg: str = "" # Error message (if status is 'error')


class SerialBridge:
    """
    Serial communication bridge to the ESP32-C6 Matter controller.

    Sends JSON commands over UART and receives responses and heartbeat
    messages from the ESP32.
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baud_rate: int = 115200,
        timeout_s: float = 2.0,
    ):
        """
        Initialise the serial bridge.

        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0' or '/dev/ttyACM0').
            baud_rate: Baud rate for UART communication.
            timeout_s: Read timeout in seconds.
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout_s = timeout_s
        self._serial = None
        self._listener_thread = None
        self._running = False
        self._response_event = threading.Event()
        self._last_response: Optional[SerialResponse] = None
        self._heartbeat_callback: Optional[Callable] = None
        self._device_states: Dict[str, str] = {}
        self._lock = threading.Lock()

    def connect(self) -> bool:
        """
        Open the serial connection to the ESP32.

        Returns:
            True if connection was successful, False otherwise.
        """
        if not HAS_SERIAL:
            logger.error("pyserial not installed")
            return False

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout_s,
                write_timeout=self.timeout_s,
            )

            # Wait for ESP32 to be ready
            time.sleep(1.0)

            # Flush any startup messages
            self._serial.reset_input_buffer()

            # Start listener thread
            self._running = True
            self._listener_thread = threading.Thread(
                target=self._listen_loop,
                daemon=True,
                name="serial-listener",
            )
            self._listener_thread.start()

            logger.info(f"Serial bridge connected on {self.port} at {self.baud_rate} baud")
            return True

        except serial.SerialException as e:
            logger.error(f"Failed to connect to serial port {self.port}: {e}")
            return False

    def disconnect(self):
        """Close the serial connection."""
        self._running = False

        if self._listener_thread is not None:
            self._listener_thread.join(timeout=2.0)
            self._listener_thread = None

        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

        logger.info("Serial bridge disconnected")

    def send_command(self, device: str, action: str, **kwargs) -> Optional[SerialResponse]:
        """
        Send a device command to the ESP32 Matter bridge.

        Args:
            device: Target device name.
            action: Action to perform (on, off, brightness, color).
            **kwargs: Additional parameters (e.g., value for brightness).

        Returns:
            SerialResponse from the ESP32, or None on failure.
        """
        if self._serial is None or not self._serial.is_open:
            logger.error("Serial port not connected")
            return SerialResponse(
                status="error",
                device=device,
                state="unknown",
                error_msg="Serial port not connected",
            )

        # Build command JSON
        cmd_data = {
            "device": device,
            "action": action,
        }
        cmd_data.update(kwargs)

        cmd_line = f"CMD:{json.dumps(cmd_data)}\n"

        try:
            # Clear previous response
            self._response_event.clear()
            self._last_response = None

            # Send command
            with self._lock:
                self._serial.write(cmd_line.encode("utf-8"))
                self._serial.flush()

            logger.debug(f"Sent command: {cmd_line.strip()}")

            # Wait for response with timeout
            if self._response_event.wait(timeout=self.timeout_s):
                return self._last_response
            else:
                logger.warning(f"Timeout waiting for response to command: {cmd_data}")
                return SerialResponse(
                    status="error",
                    device=device,
                    state="unknown",
                    error_msg="Response timeout",
                )

        except serial.SerialException as e:
            logger.error(f"Serial write error: {e}")
            return SerialResponse(
                status="error",
                device=device,
                state="unknown",
                error_msg=str(e),
            )

    def _listen_loop(self):
        """Background thread that listens for messages from the ESP32."""
        logger.debug("Serial listener started")

        while self._running and self._serial is not None:
            try:
                if not self._serial.is_open:
                    break

                line = self._serial.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                if line.startswith("RSP:"):
                    self._handle_response(line[4:])
                elif line.startswith("HBT:"):
                    self._handle_heartbeat(line[4:])
                else:
                    logger.debug(f"Unknown serial message: {line}")

            except serial.SerialException as e:
                if self._running:
                    logger.error(f"Serial read error: {e}")
                break
            except Exception as e:
                logger.error(f"Serial listener error: {e}")

        logger.debug("Serial listener stopped")

    def _handle_response(self, json_str: str):
        """Parse and store a command response."""
        try:
            data = json.loads(json_str)
            self._last_response = SerialResponse(
                status=data.get("status", "unknown"),
                device=data.get("device", "unknown"),
                state=data.get("state", "unknown"),
                error_msg=data.get("error", ""),
            )

            # Update tracked device state
            if self._last_response.status == "ok":
                self._device_states[self._last_response.device] = (
                    self._last_response.state
                )

            self._response_event.set()
            logger.debug(f"Received response: {data}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid response JSON: {json_str} ({e})")

    def _handle_heartbeat(self, json_str: str):
        """Parse a heartbeat message and update device states."""
        try:
            data = json.loads(json_str)
            devices = data.get("devices", [])

            for dev in devices:
                name = dev.get("name", "")
                state = dev.get("state", "unknown")
                if name:
                    self._device_states[name] = state

            if self._heartbeat_callback:
                self._heartbeat_callback(data)

            logger.debug(f"Heartbeat received: {len(devices)} devices")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid heartbeat JSON: {json_str} ({e})")

    def set_heartbeat_callback(self, callback: Callable):
        """
        Set a callback for heartbeat messages.

        Args:
            callback: Function to call with heartbeat data dict.
        """
        self._heartbeat_callback = callback

    def get_device_state(self, device_name: str) -> str:
        """
        Get the last known state of a device.

        Args:
            device_name: Name of the device.

        Returns:
            Last known state string, or 'unknown'.
        """
        return self._device_states.get(device_name, "unknown")

    def get_all_device_states(self) -> Dict[str, str]:
        """Get all tracked device states."""
        return dict(self._device_states)

    @property
    def is_connected(self) -> bool:
        """Check if the serial connection is active."""
        return (
            self._serial is not None
            and self._serial.is_open
            and self._running
        )

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
