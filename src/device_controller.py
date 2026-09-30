"""
Device Controller module.

Parses device commands from LLM output and sends them to smart devices
via the ESP32-C6 Matter bridge. Includes both regex-based and rule-based
fallback intent parsing.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from loguru import logger

from serial_bridge import SerialBridge, SerialResponse


@dataclass
class DeviceCommand:
    """Represents a parsed device control command."""
    device: str
    action: str
    value: Optional[str] = None  # For brightness(0-100) or color(name)


@dataclass
class CommandResult:
    """Result of executing a device command."""
    success: bool
    device: str
    action: str
    state: str = ""
    error_msg: str = ""


class DeviceController:
    """
    Device controller that parses commands and communicates with Matter devices.

    Supports both structured command extraction from LLM output and
    rule-based fallback parsing for natural language commands.
    """

    def __init__(
        self,
        devices_config_path: str = "config/devices.yaml",
        serial_port: str = "/dev/ttyUSB0",
        baud_rate: int = 115200,
        timeout_s: float = 2.0,
    ):
        """
        Initialise the device controller.

        Args:
            devices_config_path: Path to the devices YAML config file.
            serial_port: Serial port for ESP32 communication.
            baud_rate: Serial baud rate.
            timeout_s: Serial command timeout.
        """
        self.devices: Dict[str, dict] = {}
        self.device_aliases: Dict[str, str] = {}
        self._bridge = SerialBridge(
            port=serial_port,
            baud_rate=baud_rate,
            timeout_s=timeout_s,
        )

        # Load device registry
        self._load_devices(devices_config_path)

        # Rule-based fallback keywords
        self._action_keywords = {
            "on": ["turn on", "switch on", "enable", "activate", "power on", "lights on"],
            "off": ["turn off", "switch off", "disable", "deactivate", "power off", "lights off"],
            "brightness": ["dim", "brighten", "brightness", "set brightness", "dim to", "brighten to"],
            "color": ["set color", "change color", "make it", "set to", "change to"],
        }

        # Color keyword mappings
        self._color_keywords = {
            "red": "red",
            "blue": "blue",
            "green": "green",
            "white": "white",
            "warm": "warm",
            "cool": "cool",
            "purple": "purple",
            "orange": "orange",
            "yellow": "yellow",
        }

    def _load_devices(self, config_path: str):
        """Load the device registry from the YAML config."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Device config not found at {config_path}")
            return

        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)

            for device in config.get("devices", []):
                name = device["name"]
                self.devices[name] = device

                # Register aliases for fuzzy matching
                for alias in device.get("aliases", []):
                    self.device_aliases[alias.lower()] = name

                # Also register the name itself and display name
                self.device_aliases[name.lower()] = name
                self.device_aliases[name.replace("_", " ").lower()] = name
                display_name = device.get("display_name", "")
                if display_name:
                    self.device_aliases[display_name.lower()] = name

            logger.info(f"Loaded {len(self.devices)} devices from config")

        except Exception as e:
            logger.error(f"Failed to load device config: {e}")

    def connect(self) -> bool:
        """
        Connect to the ESP32 Matter bridge.

        Returns:
            True if connection was successful.
        """
        return self._bridge.connect()

    def disconnect(self):
        """Disconnect from the ESP32 Matter bridge."""
        self._bridge.disconnect()

    def parse_commands(self, response_text: str) -> Tuple[str, List[DeviceCommand]]:
        """
        Parse device commands from LLM response text.

        First attempts regex extraction of [DEVICE_CMD: ...] tags.
        Falls back to rule-based keyword matching if no structured
        commands are found.

        Args:
            response_text: Raw LLM response text.

        Returns:
            Tuple of (clean_text_for_tts, list_of_device_commands).
        """
        commands = []

        # Step 1: Extract structured commands via regex
        pattern = r'\[DEVICE_CMD:\s*([^\]]+)\]'
        matches = re.findall(pattern, response_text)

        for match in matches:
            cmd = self._parse_structured_command(match)
            if cmd:
                commands.append(cmd)

        # Remove command tags from text
        clean_text = re.sub(pattern, '', response_text).strip()
        clean_text = re.sub(r'\n+', ' ', clean_text).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)

        # Step 2: If no structured commands found, try rule-based fallback
        if not commands:
            fallback_cmds = self._parse_natural_language(response_text)
            commands.extend(fallback_cmds)

        if commands:
            logger.info(f"Parsed {len(commands)} device command(s)")
            for cmd in commands:
                logger.debug(f"  Command: {cmd}")

        return clean_text, commands

    def _parse_structured_command(self, cmd_string: str) -> Optional[DeviceCommand]:
        """
        Parse a structured [DEVICE_CMD: ...] string.

        Args:
            cmd_string: Raw command parameters, e.g., 'action=on, device=living_room_light'.

        Returns:
            DeviceCommand or None.
        """
        try:
            params = {}
            for part in cmd_string.split(","):
                part = part.strip()
                if "=" in part:
                    key, value = part.split("=", 1)
                    params[key.strip().lower()] = value.strip()

            action = params.get("action", "")
            device = params.get("device", "")

            if not action or not device:
                return None

            # Validate device exists
            if device not in self.devices:
                resolved = self._resolve_device_name(device)
                if resolved:
                    device = resolved
                else:
                    logger.warning(f"Unknown device: {device}")
                    return None

            # Validate action against device capabilities
            if not self._validate_action(device, action):
                logger.warning(
                    f"Action '{action}' not supported by device '{device}'"
                )
                return None

            # Extract value for parameterised actions
            value = None
            if "(" in action:
                action_name, value = self._extract_action_value(action)
                action = action_name

            return DeviceCommand(device=device, action=action, value=value)

        except Exception as e:
            logger.error(f"Failed to parse command '{cmd_string}': {e}")
            return None

    def _parse_natural_language(self, text: str) -> List[DeviceCommand]:
        """
        Rule-based fallback parser for natural language device commands.

        Args:
            text: Text to parse for device commands.

        Returns:
            List of extracted DeviceCommands.
        """
        commands = []
        text_lower = text.lower()

        # Detect action
        detected_action = None
        detected_value = None

        for action, keywords in self._action_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    detected_action = action

                    # Extract brightness value
                    if action == "brightness":
                        brightness_match = re.search(
                            r'(?:to|at)?\s*(\d{1,3})\s*(?:percent|%)?',
                            text_lower[text_lower.index(keyword):]
                        )
                        if brightness_match:
                            detected_value = brightness_match.group(1)
                        elif "dim" in keyword:
                            detected_value = "30"
                        elif "brighten" in keyword:
                            detected_value = "100"

                    # Extract color
                    elif action == "color":
                        for color_name in self._color_keywords:
                            if color_name in text_lower:
                                detected_value = self._color_keywords[color_name]
                                break
                    break

            if detected_action:
                break

        if not detected_action:
            return commands

        # Detect device
        detected_device = None
        for alias, device_name in self.device_aliases.items():
            if alias in text_lower:
                detected_device = device_name
                break

        # Try fuzzy matching if no exact match
        if not detected_device:
            detected_device = self._fuzzy_match_device(text_lower)

        if detected_device:
            # Map compound actions to simple ones
            if detected_action == "brightness":
                action = f"brightness"
            elif detected_action == "color":
                action = f"color"
            else:
                action = detected_action

            commands.append(DeviceCommand(
                device=detected_device,
                action=action,
                value=detected_value,
            ))

        return commands

    def _resolve_device_name(self, name: str) -> Optional[str]:
        """Resolve a device name using aliases and fuzzy matching."""
        name_lower = name.lower().replace("_", " ")

        # Check aliases
        if name_lower in self.device_aliases:
            return self.device_aliases[name_lower]

        # Fuzzy match
        return self._fuzzy_match_device(name_lower)

    def _fuzzy_match_device(self, text: str) -> Optional[str]:
        """
        Fuzzy match text against known device names and aliases.

        Args:
            text: Text to search for device names.

        Returns:
            Best matching device name, or None if no match found.
        """
        best_match = None
        best_score = 0.6  # Minimum matching threshold

        for alias, device_name in self.device_aliases.items():
            # Check if alias appears as a substring
            if alias in text:
                return device_name

            # Fuzzy string matching
            score = SequenceMatcher(None, alias, text).ratio()
            if score > best_score:
                best_score = score
                best_match = device_name

        return best_match

    def _validate_action(self, device_name: str, action: str) -> bool:
        """Check if an action is valid for a given device."""
        device = self.devices.get(device_name)
        if not device:
            return False

        capabilities = device.get("capabilities", [])

        # Strip parameterised value for validation
        base_action = action.split("(")[0] if "(" in action else action

        if base_action in ("on", "off"):
            return "on_off" in capabilities
        elif base_action in ("brightness", "dim", "brighten"):
            return "brightness" in capabilities
        elif base_action == "color":
            return "color" in capabilities

        return False

    def _extract_action_value(self, action: str) -> Tuple[str, str]:
        """Extract action name and value from parameterised action string."""
        match = re.match(r'(\w+)\(([^)]+)\)', action)
        if match:
            return match.group(1), match.group(2)
        return action, ""

    def execute(self, command: DeviceCommand) -> CommandResult:
        """
        Execute a device command via the Matter bridge.

        Args:
            command: DeviceCommand to execute.

        Returns:
            CommandResult indicating success or failure.
        """
        if not self._bridge.is_connected:
            logger.warning("Serial bridge not connected, attempting reconnect...")
            if not self._bridge.connect():
                return CommandResult(
                    success=False,
                    device=command.device,
                    action=command.action,
                    error_msg="ESP32 bridge not connected",
                )

        try:
            # Build command kwargs
            kwargs = {}
            if command.value:
                kwargs["value"] = command.value

            # Send via serial bridge
            response = self._bridge.send_command(
                device=command.device,
                action=command.action,
                **kwargs,
            )

            if response is None:
                return CommandResult(
                    success=False,
                    device=command.device,
                    action=command.action,
                    error_msg="No response from bridge",
                )

            if response.status == "ok":
                logger.info(
                    f"Device command executed: {command.device} -> "
                    f"{command.action} (state: {response.state})"
                )
                return CommandResult(
                    success=True,
                    device=command.device,
                    action=command.action,
                    state=response.state,
                )
            else:
                return CommandResult(
                    success=False,
                    device=command.device,
                    action=command.action,
                    error_msg=response.error_msg,
                )

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return CommandResult(
                success=False,
                device=command.device,
                action=command.action,
                error_msg=str(e),
            )

    def get_device_status(self, device_name: str) -> str:
        """Get the current status of a device."""
        return self._bridge.get_device_state(device_name)

    def get_all_statuses(self) -> Dict[str, str]:
        """Get all device statuses."""
        return self._bridge.get_all_device_states()

    def get_registered_devices(self) -> List[dict]:
        """Get the list of registered devices."""
        return list(self.devices.values())

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
