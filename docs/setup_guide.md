# Setup Guide — Offline Voice Assistant

Complete guide for setting up the hardware and software from scratch.

---

## Prerequisites

### Hardware Checklist

- [ ] Raspberry Pi 5 (8 GB RAM)
- [ ] 128 GB microSD card (A2 U3 class recommended)
- [ ] 5V / 5A USB-C power supply
- [ ] ReSpeaker 4-Mic Array HAT
- [ ] 3W 4Ω speaker + MAX98357A I²S amplifier breakout
- [ ] WS2812B 12-LED ring
- [ ] Tactile push button (for mute)
- [ ] ESP32-C6 or ESP32-H2 development board
- [ ] USB cable for ESP32 ↔ Pi connection
- [ ] Matter-compatible smart bulb (for testing)
- [ ] Matter-compatible smart plug (for testing)
- [ ] Jumper wires, breadboard (for prototyping)
- [ ] 3D-printed enclosure (optional)

### Software Checklist

- [ ] Raspberry Pi OS 64-bit (Bookworm) — headless
- [ ] Python 3.11+
- [ ] Git
- [ ] ESP-IDF 5.x (for ESP32 firmware, on development machine)

---

## 1. Raspberry Pi Setup

### 1.1 Flash Raspberry Pi OS

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Select **Raspberry Pi OS Lite (64-bit)** — Bookworm
3. Click the gear icon to configure:
   - Set hostname: `voice-assistant`
   - Enable SSH
   - Set username/password
   - Configure WiFi (for initial setup only)
4. Flash to the microSD card
5. Insert card and boot the Pi

### 1.2 Initial System Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    git build-essential cmake \
    portaudio19-dev libasound2-dev \
    i2c-tools python3-smbus \
    libopenblas-dev libatlas-base-dev

# Enable I²C and SPI
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
```

### 1.3 Clone the Project

```bash
cd ~
git clone https://github.com/yourusername/offline-voice-assistant.git
cd offline-voice-assistant

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2. Hardware Assembly

### 2.1 Wiring Diagram

```
Raspberry Pi 5 GPIO Header
─────────────────────────
Pin 1  (3.3V)    → WS2812B VCC (if using 3.3V logic level)
Pin 2  (5V)      → WS2812B VCC (recommended for brightness)
Pin 6  (GND)     → WS2812B GND, Button GND, MAX98357A GND
Pin 11 (GPIO17)  → Mute button (other leg to GND)
Pin 12 (GPIO18)  → WS2812B Data In (DIN)
Pin 35 (GPIO19)  → MAX98357A BCLK (I²S bit clock)
Pin 38 (GPIO20)  → MAX98357A DIN (I²S data)
Pin 40 (GPIO21)  → MAX98357A LRC (I²S word select)

ReSpeaker 4-Mic Array HAT
─────────────────────────
Mounts directly on GPIO header (40-pin)
No additional wiring needed.

ESP32-C6
─────────────────────────
USB connection to Pi (appears as /dev/ttyUSB0 or /dev/ttyACM0)
```

### 2.2 ReSpeaker HAT

1. **Power off** the Raspberry Pi
2. Carefully align the ReSpeaker HAT with the 40-pin GPIO header
3. Press down firmly but gently until fully seated
4. The HAT should sit flat with no pins visible

### 2.3 Speaker + Amplifier

Connect the MAX98357A I²S amplifier:

| MAX98357A Pin | Pi GPIO | Description |
|---|---|---|
| VIN | 5V (Pin 2) | Power |
| GND | GND (Pin 6) | Ground |
| BCLK | GPIO19 (Pin 35) | Bit clock |
| DIN | GPIO20 (Pin 38) | Data |
| LRC | GPIO21 (Pin 40) | Word select |

Solder the speaker wires to the MAX98357A output pads (+ and −).

### 2.4 LED Ring

| WS2812B Pin | Pi GPIO | Description |
|---|---|---|
| VCC | 5V (Pin 2) | Power (5V for full brightness) |
| GND | GND (Pin 6) | Ground |
| DIN | GPIO18 (Pin 12) | Data input |

> **Note:** GPIO18 uses PWM channel 0. If using the ReSpeaker HAT, check for GPIO conflicts and use GPIO10 (SPI0 MOSI) as an alternative.

### 2.5 Mute Button

| Button Pin | Pi GPIO | Description |
|---|---|---|
| Leg 1 | GPIO17 (Pin 11) | Input with internal pull-up |
| Leg 2 | GND (Pin 6) | Ground |

---

## 3. Audio Setup

```bash
# Run the audio setup script (as root)
sudo ./scripts/setup_audio.sh

# Reboot for changes to take effect
sudo reboot

# After reboot, test audio
./scripts/test_speaker.sh
```

---

## 4. Download AI Models

```bash
# Download all required models (~3 GB total)
./scripts/download_models.sh
```

This downloads:
- **Whisper** base.en GGML model (~150 MB)
- **Phi-3.5-mini-instruct** Q4_K_M GGUF (~2.5 GB)
- **Piper TTS** en_US-lessac-medium voice (~65 MB)
- **openWakeWord** hey_assistant model (~5 MB)

---

## 5. ESP32 Matter Bridge

See [Matter Commissioning Guide](matter_commissioning.md) for detailed instructions.

Quick summary:
1. Install ESP-IDF 5.x on your development machine
2. Flash the `esp32-matter-bridge` firmware to the ESP32-C6
3. Connect ESP32-C6 to Pi via USB
4. Commission your Matter devices

---

## 6. Running the Assistant

```bash
# Activate virtual environment
source venv/bin/activate

# Run the assistant
python src/main.py

# Run with debug logging
python src/main.py --debug

# Run with custom config
python src/main.py --config config/assistant.yaml
```

---

## 7. Running as a Service (systemd)

To start the assistant automatically on boot:

```bash
sudo nano /etc/systemd/system/voice-assistant.service
```

```ini
[Unit]
Description=Offline Voice Assistant
After=multi-user.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/offline-voice-assistant
ExecStart=/home/pi/offline-voice-assistant/venv/bin/python src/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable voice-assistant
sudo systemctl start voice-assistant

# Check status
sudo systemctl status voice-assistant

# View logs
journalctl -u voice-assistant -f
```

---

## 8. Troubleshooting

### No audio output
- Check `aplay -l` to verify the speaker is detected
- Run `alsamixer` and ensure volumes are not muted
- Verify I²S overlay is in `/boot/firmware/config.txt`

### Microphone not working
- Check `arecord -l` to verify the ReSpeaker is detected
- Ensure the HAT is fully seated on the GPIO header
- Run `sudo i2cdetect -y 1` to check I²C communication

### Wake word not detecting
- Lower the threshold in `config/audio.yaml`
- Check microphone volume with `alsamixer`
- Test recording with `arecord -f S16_LE -r 16000 -c 1 -d 3 test.wav`

### LLM too slow
- Switch to a smaller model (Qwen2-1.5B or TinyLlama-1.1B)
- Reduce `max_tokens` in config
- Consider adding a Hailo-8L accelerator

### ESP32 not responding
- Check USB connection: `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`
- Monitor ESP32 output: `screen /dev/ttyUSB0 115200`
- Re-flash the firmware if needed
