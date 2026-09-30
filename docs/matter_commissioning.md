# Matter Device Commissioning Guide

Step-by-step guide for setting up the ESP32-C6 Matter bridge and commissioning smart devices.

---

## Overview

The ESP32-C6 serves as a Matter controller that:
1. Receives commands from the Raspberry Pi over UART (USB-serial)
2. Translates them to Matter cluster commands
3. Sends commands to smart devices over Thread or BLE
4. Reports device states back to the Pi

---

## Prerequisites

### Development Machine (for building ESP32 firmware)

- **ESP-IDF v5.1+** installed ([installation guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/get-started/))
- **ESP-Matter SDK** installed ([GitHub](https://github.com/espressif/esp-matter))
- USB cable for flashing

### Hardware

- ESP32-C6 or ESP32-H2 development board
- Matter-compatible smart bulb (e.g., Eve, Nanoleaf, TP-Link Tapo)
- Matter-compatible smart plug
- USB cable (ESP32 to Pi)

---

## 1. Build & Flash ESP32 Firmware

### 1.1 Set Up Build Environment

```bash
# Source ESP-IDF environment
source $HOME/esp/esp-idf/export.sh

# Set ESP-Matter path
export ESP_MATTER_PATH=$HOME/esp/esp-matter

# Navigate to the firmware directory
cd esp32-matter-bridge
```

### 1.2 Configure & Build

```bash
# Set target to ESP32-C6
idf.py set-target esp32c6

# Configure (optional — defaults are in sdkconfig.defaults)
idf.py menuconfig

# Build
idf.py build
```

### 1.3 Flash to ESP32-C6

```bash
# Flash firmware (replace /dev/ttyUSB0 with your port)
idf.py flash -p /dev/ttyUSB0

# Monitor serial output (for debugging)
idf.py monitor -p /dev/ttyUSB0
```

---

## 2. Commission Smart Devices

### 2.1 Understanding Matter Commissioning

Matter commissioning is the process of adding a new device to your local network "fabric". This involves:

1. **Discovery** — Finding the device via BLE or on-network
2. **PASE** — Establishing a secure session using the device's setup code
3. **Certificate provisioning** — Issuing certificates to the device
4. **Network provisioning** — Giving the device Thread/WiFi credentials
5. **Binding** — Assigning a node ID within the fabric

### 2.2 Prepare Your Smart Device

1. **Factory reset** the smart device (refer to manufacturer instructions)
2. Locate the device's **setup code** (usually on the device or packaging):
   - Manual pairing code (11-digit number)
   - QR code
   - Discriminator value

### 2.3 Commission via ESP32 Serial Console

Connect to the ESP32's serial monitor and use the commissioning commands:

```bash
# On the Pi, connect to ESP32 serial
screen /dev/ttyUSB0 115200

# Or use the Python serial tool
python3 -c "
import serial
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=2)
# Send commissioning command
ser.write(b'CMD:{\"action\":\"commission\",\"setup_code\":\"34970112332\",\"discriminator\":3840}\n')
response = ser.readline()
print(response.decode())
"
```

### 2.4 Alternative: Commission via chip-tool

For initial setup, you can use the CHIP tool on the Pi:

```bash
# Install chip-tool (if available in your setup)
# Commission a device
chip-tool pairing ble-thread <node-id> <setup-code> <discriminator>

# Example: Commission a light bulb as node 1
chip-tool pairing ble-thread 1 34970112332 3840
```

---

## 3. Device Configuration

After commissioning, update `config/devices.yaml` with the correct node IDs:

```yaml
devices:
  - name: "living_room_light"
    display_name: "Living Room Light"
    type: "light"
    matter_node_id: 1          # ← Set to actual node ID
    matter_endpoint: 1
    capabilities:
      - "on_off"
      - "brightness"
      - "color"

  - name: "bedroom_light"
    display_name: "Bedroom Light"
    type: "light"
    matter_node_id: 2          # ← Set to actual node ID
    matter_endpoint: 1
    capabilities:
      - "on_off"
      - "brightness"

  - name: "smart_plug_1"
    display_name: "Smart Plug"
    type: "plug"
    matter_node_id: 3          # ← Set to actual node ID
    matter_endpoint: 1
    capabilities:
      - "on_off"
```

---

## 4. Testing Device Control

### 4.1 Test via Serial Commands

Send test commands directly to the ESP32:

```bash
# Turn on living room light
echo 'CMD:{"device":"living_room_light","action":"on"}' > /dev/ttyUSB0

# Set brightness to 50%
echo 'CMD:{"device":"living_room_light","action":"brightness","value":"50"}' > /dev/ttyUSB0

# Change color to blue
echo 'CMD:{"device":"living_room_light","action":"color","value":"blue"}' > /dev/ttyUSB0

# Turn off smart plug
echo 'CMD:{"device":"smart_plug_1","action":"off"}' > /dev/ttyUSB0
```

### 4.2 Test via Voice

1. Start the voice assistant: `python src/main.py`
2. Say "Hey Assistant"
3. Say "Turn on the living room light"
4. The assistant should respond and the light should turn on

---

## 5. Serial Protocol Reference

### Commands (Pi → ESP32)

```
CMD:{"device":"<name>","action":"<action>","value":"<value>"}\n
```

| Field | Type | Description |
|---|---|---|
| device | string | Device name from registry |
| action | string | `on`, `off`, `brightness`, `color` |
| value | string | Optional: brightness (0-100) or color name |

### Responses (ESP32 → Pi)

```
RSP:{"status":"<ok|error>","device":"<name>","state":"<state>","error":"<msg>"}\n
```

### Heartbeats (ESP32 → Pi, every 10s)

```
HBT:{"devices":[{"name":"<name>","state":"<on|off>","brightness":<0-254>}],"timestamp":<epoch>}\n
```

---

## 6. Troubleshooting

### ESP32 not detected by Pi
- Check USB cable (data cable, not charge-only)
- Try: `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`
- Install USB serial driver if needed: `sudo apt install python3-serial`

### Commissioning fails
- Factory reset the smart device and try again
- Ensure the setup code and discriminator are correct
- Check that Thread/BLE is enabled on the ESP32
- Move the ESP32 closer to the smart device

### Device not responding to commands
- Verify node ID matches in `config/devices.yaml`
- Check the heartbeat messages for device state
- Re-commission the device if it went offline

### Thread network issues
- Ensure only one Thread border router is active on the network
- Check Thread network credentials match
- The ESP32-C6 must remain powered to maintain the Thread network
