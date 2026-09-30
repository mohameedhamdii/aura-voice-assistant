# Hardware Architecture & Assembly Guide

This document describes the complete hardware design, Bill of Materials (BOM), 40-pin GPIO allocation, schematic connections, and assembly instructions for the **Offline Voice Assistant**.

---

## 1. Hardware Bill of Materials (BOM)

| Component | Part / Model Number | Qty | Interface | Voltage / Power | Purpose |
|---|---|---|---|---|---|
| **Host Single-Board Computer** | Raspberry Pi 5 (8 GB RAM) | 1 | 40-pin GPIO, USB-C | 5.1V / 5.0A (27W USB-PD) | Whisper ASR, llama.cpp LLM, Piper TTS |
| **Active Cooler** | Official Raspberry Pi 5 Active Cooler | 1 | 4-pin JST PWM Fan | 5V | Prevents thermal throttling during LLM inference |
| **MicroSD Card** | SanDisk Extreme Pro 128 GB A2 U3 V30 | 1 | MicroSD UHS-I | 3.3V | OS, GGUF models, ONNX models |
| **Far-Field Mic Array** | Seeed Studio ReSpeaker 4-Mic Array HAT | 1 | I2C + 4-channel TDM | 5V / 3.3V | 360° voice capture, beamforming, acoustic echo cancel |
| **I²S DAC Amplifier** | Adafruit MAX98357A Class-D Amp | 1 | I²S (BCLK, LRCLK, DIN) | 5V / 3.2W output | Low-noise digital audio playback |
| **Speaker Driver** | Dayton Audio DMA45-4 (4 Ω, 3 W RMS) | 1 | Analog Terminal | Up to 5W peak | Clear voice reproduction (120 Hz - 20 kHz) |
| **Visual LED Feedback** | WS2812B 12-Pixel RGB Ring (50 mm OD) | 1 | 1-Wire Digital (GPIO18 PWM) | 5V (60 mA per LED peak) | System status indicators (listening, thinking, speaking) |
| **Level Shifter / Diode** | 1N4001 Diode or 74AHCT125 | 1 | Inline power / signal | 5V / 3.3V | Drops WS2812 VCC to 4.3V for reliable 3.3V logic high |
| **Privacy Mute Button** | 12 mm Momentary Tactile Push Button | 1 | GPIO input (GPIO17) | 3.3V with internal pull-up | Hardware microphone mute / privacy switch |
| **Matter / Thread Bridge** | ESP32-C6-DevKitC-1 (or ESP32-H2) | 1 | UART (115,200 baud) + USB | 5V / 150 mA | Matter controller over Thread/BLE (802.15.4) |
| **Power Supply** | Official Raspberry Pi 27W USB-C PSU | 1 | USB-C PD | 5.1V @ 5.0A | Stable high-current rail for Pi 5 + peripherals |
| **Enclosure** | 3D Printed Cylindrical Speaker Housing | 1 | — | PLA / PETG | Structural housing, acoustic chamber, light ring mount |

---

## 2. Raspberry Pi 5 40-Pin GPIO Pinout Allocation

The Raspberry Pi 5 header provides connections for the ReSpeaker HAT, MAX98357A I²S DAC, WS2812B LED Ring, Mute Button, and ESP32-C6 UART.

```
                    Raspberry Pi 5 GPIO Header (J8)
                    ──────────────────────────────
         +3.3V Power (Pin 1)  ●  ●  (Pin 2)   +5V Power (To MAX98357A & LED)
       SDA1 / I2C0 (Pin 3)  ●  ●  (Pin 4)   +5V Power (To ESP32-C6 5V)
       SCL1 / I2C0 (Pin 5)  ●  ●  (Pin 6)   Ground (System Common GND)
            GPIO 4 (Pin 7)  ●  ●  (Pin 8)   GPIO 14 / UART0 TXD (To ESP32 RXD)
            Ground (Pin 9)  ●  ●  (Pin 10)  GPIO 15 / UART0 RXD (To ESP32 TXD)
      MUTE_BTN (GPIO17, Pin 11)  ●  ●  (Pin 12)  GPIO 18 / PWM0 (To WS2812B Data)
           GPIO 27 (Pin 13)  ●  ●  (Pin 14)  Ground
           GPIO 22 (Pin 15)  ●  ●  (Pin 16)  GPIO 23
         +3.3V Power (Pin 17)  ●  ●  (Pin 18)  GPIO 24
           GPIO 10 (Pin 19)  ●  ●  (Pin 20)  Ground
            GPIO 9 (Pin 21)  ●  ●  (Pin 22)  GPIO 25
           GPIO 11 (Pin 23)  ●  ●  (Pin 24)  GPIO 8
            Ground (Pin 25)  ●  ●  (Pin 26)  GPIO 7
           I2C_EEPROM (Pin 27)  ●  ●  (Pin 28)  I2C_EEPROM
           GPIO 5  (Pin 29)  ●  ●  (Pin 30)  Ground
           GPIO 6  (Pin 31)  ●  ●  (Pin 32)  GPIO 12
           GPIO 13 (Pin 33)  ●  ●  (Pin 34)  Ground
    I2S_BCLK (GPIO 19, Pin 35)  ●  ●  (Pin 36)  GPIO 16
           GPIO 26 (Pin 37)  ●  ●  (Pin 38)  I2S_DIN (GPIO 20, Pin 38)
            Ground (Pin 39)  ●  ●  (Pin 40)  I2S_LRCLK (GPIO 21, Pin 40)
```

---

## 3. Subsystem Wiring Tables

### 3.1 MAX98357A I²S DAC Amplifier → Raspberry Pi 5

| MAX98357A Pin | Pi 5 Physical Pin | Pi 5 BCM Signal | Description |
|---|---|---|---|
| **VIN** | Pin 2 or Pin 4 | `+5V Power` | Power rail (5V delivers 3.2W into 4Ω) |
| **GND** | Pin 6 or Pin 14 | `GND` | Ground return |
| **BCLK** | Pin 35 | `GPIO 19 (PCM_CLK)` | Bit clock |
| **LRC (LRCLK)**| Pin 40 | `GPIO 21 (PCM_FS)` | Left/Right Word Clock (Frame Sync) |
| **DIN** | Pin 38 | `GPIO 20 (PCM_DOUT)`| Serial Data Out from Pi to DAC |
| **SD_MODE** | Pull-up to VIN with 100kΩ | — | Left channel mono audio mix |
| **GAIN** | Connect to GND | — | Default 9 dB gain (prevents clipping) |
| **SPK+ / SPK-**| Speaker +/- | — | Connect to 4 Ω 3 W speaker driver |

### 3.2 WS2812B 12-LED Ring → Raspberry Pi 5

| WS2812B Pin | Connection | Note |
|---|---|---|
| **5V (Power)** | Pi 5 Pin 2 (+5V) via 1N4001 Diode | Drops 5.1V to ~4.4V so 3.3V logic is recognized |
| **GND** | Pi 5 Pin 14 (GND) | Common ground |
| **DI (Data In)**| Pi 5 Pin 12 (`GPIO 18 / PWM0`) | Driven by `rpi_ws281x` hardware PWM |
| **Capacitor** | 470 µF / 16V across 5V and GND | Absorbs inrush current transients |

### 3.3 ESP32-C6 Matter Bridge → Raspberry Pi 5

| ESP32-C6 Pin | Pi 5 Physical Pin | Signal | Description |
|---|---|---|---|
| **5V (VBUS/VIN)**| Pi 5 Pin 4 | `+5V Power` | Powers ESP32 development board |
| **GND** | Pi 5 Pin 9 | `GND` | Shared serial signal ground reference |
| **RX (GPIO 16)**| Pi 5 Pin 8 | `GPIO 14 (UART0 TX)` | Pi transmits commands to ESP32 |
| **TX (GPIO 17)**| Pi 5 Pin 10 | `GPIO 15 (UART0 RX)` | ESP32 transmits telemetry/status to Pi |

*(Alternative: Connect ESP32-C6 via USB-C data cable to any Pi 5 USB 3.0 port. The bridge communicates over `/dev/ttyUSB0` or `/dev/ttyACM0` automatically).*

### 3.4 Hardware Mute Button

| Button Pin | Connection | Description |
|---|---|---|
| **Pin A** | Pi 5 Pin 11 (`GPIO 17`) | Sense line configured with internal pull-up |
| **Pin B** | Pi 5 Pin 9 (`GND`) | Ground closure |
| **Debounce**| 100 nF ceramic capacitor across Pins A & B | Eliminates mechanical contact bounce |

---

## 4. Power Budget & Grounding Architecture

### Power Consumption Budget (5.1 V Rail)

```
Raspberry Pi 5 (Active Cooler + Quad A76 @ 2.4 GHz):   2.35 A peak (12.0 W)
ReSpeaker 4-Mic Array HAT:                            0.12 A (0.6 W)
MAX98357A I2S DAC + 3W Speaker:                       0.65 A peak (3.3 W)
WS2812B 12-LED Ring (Full white @ 50% brightness):    0.36 A (1.8 W)
ESP32-C6 Thread / BLE Radio:                          0.15 A peak (0.8 W)
-------------------------------------------------------------------------
Total Worst-Case Concurrent Consumption:              3.63 A (18.5 W)
PSU Headroom (Official 27W 5.1V / 5.0A):             1.37 A reserve (27% margin)
```

### Critical Grounding & Audio Noise Immunity
1. **Star Ground Topology:** Connect the audio amplifier GND directly to a Pi 5 Ground pin separate from the LED and ESP32 return lines to prevent LED PWM switching noise from leaking into speaker playback.
2. **Bulk Capacitance:** Place a 470 µF electrolytic capacitor and a 0.1 µF ceramic capacitor in parallel across the MAX98357A power pins.
3. **Ferrite Bead:** Install a clip-on ferrite bead on the USB-C power lead to attenuate high-frequency switching hash.
