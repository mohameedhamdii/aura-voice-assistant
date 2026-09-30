# Offline Voice Assistant with On-Device Tiny LLM

> A smart speaker that answers questions and controls local devices with zero internet dependency, running a sub-3B parameter LLM entirely on-device.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Development-yellow)

## Overview

A privacy-first voice assistant that runs entirely offline on a Raspberry Pi 5. It listens for a wake word, transcribes speech locally using Whisper, processes queries with a quantized on-device LLM (1B–3B parameters), generates spoken responses via offline TTS, and controls local smart-home devices over the Matter protocol — all without any cloud connectivity.

### Key Features

- 🎙️ **Wake Word Detection** — Always-on "Hey Assistant" detection with < 5% CPU usage
- 🗣️ **Local Speech-to-Text** — whisper.cpp for fast, private transcription
- 🧠 **On-Device LLM** — Phi-3.5-mini or Qwen2-1.5B running via llama.cpp
- 🔊 **Neural TTS** — Natural-sounding speech output via Piper TTS
- 🏠 **Smart Home Control** — Matter protocol device control via ESP32-C6 bridge
- 💡 **LED Feedback** — WS2812B ring shows listening, thinking, and speaking states
- 🔒 **Complete Privacy** — Zero data leaves the device, ever

## Architecture

```
              ┌──────────────┐
              │  Wake Word   │
              │  Detector    │
              │ (always-on)  │
              └──────┬───────┘
                     │ wake word detected
                     ▼
┌─────────┐  ┌──────────────┐  ┌──────────────┐
│ ReSpeaker│─▶│  whisper.cpp │─▶│    LLM       │
│ 4-Mic   │  │    (ASR)     │  │ (llama.cpp)  │
│ HAT     │  └──────────────┘  └──────┬───────┘
└─────────┘                           │
                          ┌───────────┼───────────┐
                          ▼           ▼           │
                   ┌────────────┐ ┌─────────┐    │
                   │ Intent     │ │ Piper   │    │
                   │ Parser     │ │ TTS     │    │
                   └─────┬──────┘ └────┬────┘    │
                         │             ▼          │
                         │      ┌──────────┐     │
                         │      │ Speaker  │     │
                         │      └──────────┘     │
                         ▼                        │
                  ┌─────────────┐                 │
                  │  ESP32-C6   │                 │
                  │ Matter Ctrl │                 │
                  └──────┬──────┘                 │
                         │ Thread / BLE           │
                         ▼                        │
                  ┌─────────────┐                 │
                  │ Smart Bulb  │                 │
                  │ Smart Plug  │                 │
                  └─────────────┘                 │
```

## Hardware Requirements

| Component | Specific Part | Purpose |
|---|---|---|
| Main compute | Raspberry Pi 5 (8 GB) + Hailo-8L (optional) | Runs Whisper, LLM, TTS |
| Microphone array | ReSpeaker 4-Mic Array HAT | Far-field voice capture |
| Speaker | 3W 4Ω speaker + MAX98357A I²S amp | Audio output |
| LED ring | WS2812B 12-LED ring | Visual feedback |
| Button | Tactile push button | Privacy mute |
| Matter bridge | ESP32-C6 or ESP32-H2 | Smart device control |
| Power supply | 5V / 5A USB-C | Powers the Pi 5 |
| MicroSD card | 128 GB A2 U3 | OS + models |

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/offline-voice-assistant.git
cd offline-voice-assistant

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Download Models

```bash
chmod +x scripts/download_models.sh
./scripts/download_models.sh
```

This downloads:
- **Whisper** base.en model (~150 MB)
- **LLM** Phi-3.5-mini-instruct Q4_K_M (~2.5 GB)
- **Piper TTS** en_US-lessac-medium voice (~65 MB)
- **Wake word** model (~5 MB)

### 3. Configure Audio Hardware

```bash
chmod +x scripts/setup_audio.sh
./scripts/setup_audio.sh
```

### 4. Test Speaker & Microphone

```bash
chmod +x scripts/test_speaker.sh
./scripts/test_speaker.sh
```

### 5. Run the Assistant

```bash
python src/main.py
```

Or with a custom config:

```bash
python src/main.py --config config/assistant.yaml
```

## Configuration

### General Settings (`config/assistant.yaml`)

Configure model paths, hardware settings, and runtime parameters.

### Audio Settings (`config/audio.yaml`)

Adjust microphone sensitivity, silence detection thresholds, and recording limits.

### Device Registry (`config/devices.yaml`)

Register your Matter-compatible smart devices for voice control.

### System Prompt (`config/system_prompt.txt`)

Customize the LLM's personality and behavior.

## ESP32 Matter Bridge

The ESP32-C6 firmware handles communication with Matter-compatible smart devices. See [docs/matter_commissioning.md](docs/matter_commissioning.md) for setup instructions.

### Build Firmware

```bash
cd esp32-matter-bridge
idf.py set-target esp32c6
idf.py build
idf.py flash -p /dev/ttyUSB0
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test modules
pytest tests/test_intent_parser.py -v
pytest tests/test_stt.py -v
```

## Performance

| Stage | Target Latency |
|---|---|
| Wake word detection | < 200 ms |
| Recording (average) | 2–5 s |
| Whisper transcription | 2–3 s |
| LLM inference (Phi-3.5) | 5–10 s |
| TTS synthesis | 1–2 s |
| **Total end-to-end** | **~12–20 s** |

## Project Structure

```
offline-voice-assistant/
├── README.md
├── requirements.txt
├── src/                          # Python source modules
│   ├── main.py                   # Main orchestrator
│   ├── audio_pipeline.py         # Mic input & recording
│   ├── wake_word.py              # Wake word detection
│   ├── vad.py                    # Voice activity detection
│   ├── stt_engine.py             # Whisper STT
│   ├── llm_engine.py             # LLM query engine
│   ├── prompt_manager.py         # Prompt & context management
│   ├── tts_engine.py             # Piper TTS
│   ├── device_controller.py      # Intent parsing & device control
│   ├── serial_bridge.py          # Pi ↔ ESP32 serial comms
│   └── led_controller.py         # WS2812B LED animations
├── config/                       # Configuration files
├── models/                       # Model weights (downloaded)
├── esp32-matter-bridge/          # ESP32-C6 firmware
├── scripts/                      # Setup & utility scripts
├── tests/                        # Unit & integration tests
├── hardware/                     # Wiring diagrams & enclosure
└── docs/                         # Documentation
```

## Documentation

- [Setup Guide](docs/setup_guide.md) — Complete hardware and software setup
- [Matter Commissioning](docs/matter_commissioning.md) — ESP32 Matter bridge setup
- [Model Benchmarks](docs/model_benchmarks.md) — Performance data for different model configurations

## License

MIT License — see [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
