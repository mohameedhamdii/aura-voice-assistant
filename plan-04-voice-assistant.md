# Plan 04 — Offline Voice Assistant with On-Device Tiny LLM

> **One-liner:** A smart speaker that answers questions and controls local devices with zero internet dependency, running a sub-3B parameter LLM entirely on-device.

---

## 1. Project Overview

### 1.1 Goal
Build an offline, privacy-first voice assistant that listens for a wake word, transcribes speech locally using Whisper, processes the query with a quantized on-device LLM (1B–3B parameters), generates a spoken response via offline TTS, and can control local smart-home devices over the Matter protocol — all without any cloud connectivity.

### 1.2 Domain
Voice & Edge AI

### 1.3 Portfolio Value
Sub-1B models fit true microcontroller-class devices, while 1B–3B models hit the sweet spot for boards like the Pi 5. Choosing the right model tier for the hardware is exactly the judgment call interviewers probe. This project demonstrates ASR, NLU, TTS, and IoT control all running at the edge.

---

## 2. Hardware Bill of Materials

| Component | Specific Part / Model | Qty | Purpose |
|---|---|---|---|
| Main compute | Raspberry Pi 5 (8 GB) + Hailo-8L (optional) | 1 | Runs Whisper, LLM, TTS |
| Microphone array | ReSpeaker 4-Mic Array HAT | 1 | Far-field voice capture with beamforming |
| Speaker | 3 W 4 Ω full-range speaker + MAX98357A I²S amp | 1 | Audio output |
| LED ring | WS2812B 12-LED ring | 1 | Visual feedback (listening, thinking, speaking) |
| Button | Tactile push button (mute mic) | 1 | Privacy mute |
| Matter bridge | ESP32-C6 or ESP32-H2 (Thread/BLE) | 1 | Controls Matter-compatible smart devices |
| Smart devices (demo) | Smart LED bulb (Matter-compatible) + smart plug | 2 | Demo targets for voice control |
| Power supply | 5 V / 5 A USB-C | 1 | Powers the Pi 5 |
| Enclosure | 3D-printed cylindrical speaker housing | 1 | Smart-speaker form factor |
| MicroSD card | 128 GB A2 U3 | 1 | OS + models (LLM + Whisper + TTS) |

### 2.1 Hardware Assembly Notes
- Mount the ReSpeaker HAT on top of the Pi 5 GPIO header.
- Place the speaker at the bottom of the cylindrical enclosure with the sound port facing down/out.
- LED ring sits on top, visible through a frosted acrylic diffuser.
- ESP32-C6 communicates with Pi 5 over UART or USB-serial for Matter commands.

---

## 3. Software Stack & Dependencies

| Layer | Technology | Notes |
|---|---|---|
| OS | Raspberry Pi OS 64-bit (Bookworm) | Headless, no desktop |
| Wake word | openWakeWord or Porcupine (Picovoice) | Detects "Hey Assistant" or custom wake word |
| Speech-to-text | whisper.cpp (base or small model) | Local ASR, ~74M or ~244M params |
| LLM | llama.cpp | Runs quantized GGUF model on CPU + optional Hailo offload |
| LLM model | Phi-3.5-mini-instruct (3.8B, Q4_K_M) or Qwen2-1.5B (Q4) | Choose based on RAM/speed tradeoff |
| Text-to-speech | Piper TTS | Offline neural TTS, VITS-based |
| Smart home protocol | Matter (via ESP32-C6) | Controls lights, plugs, etc. |
| Matter SDK | connectedhomeip (CHIP) on ESP32 | Device commissioning & control |
| Audio I/O | ALSA + pyaudio | Mic input and speaker output |
| Intent parser | Rule-based + LLM hybrid | Extracts device commands from LLM output |
| Programming language | Python 3.11 + C++ (whisper.cpp, llama.cpp) | — |

---

## 4. System Architecture

```
                         ┌──────────────┐
                         │  Wake Word   │
                         │  Detector    │
                         │ (always-on)  │
                         └──────┬───────┘
                                │ "wake word detected"
                                ▼
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│  ReSpeaker  │────────▶│  whisper.cpp │────────▶│    LLM       │
│  4-Mic HAT  │  audio  │    (ASR)     │  text   │ (llama.cpp)  │
│  (capture)  │  stream │  base/small  │  query  │ Phi-3.5 /    │
└─────────────┘         └──────────────┘         │ Qwen2-1.5B   │
                                                  └──────┬───────┘
                                                         │ response text
                                          ┌──────────────┼──────────────┐
                                          ▼              ▼              │
                                   ┌────────────┐ ┌───────────┐        │
                                   │ Intent     │ │ Piper TTS │        │
                                   │ Parser     │ │ (speak    │        │
                                   │ (device    │ │  response)│        │
                                   │  commands) │ └─────┬─────┘        │
                                   └─────┬──────┘       │              │
                                         │              ▼              │
                                         │       ┌────────────┐        │
                                         │       │  Speaker   │        │
                                         │       │  (I²S out) │        │
                                         │       └────────────┘        │
                                         ▼                             │
                                  ┌─────────────┐                      │
                                  │  ESP32-C6   │                      │
                                  │  (Matter    │                      │
                                  │   bridge)   │                      │
                                  └──────┬──────┘                      │
                                         │ Thread / BLE                │
                                         ▼                             │
                                  ┌─────────────┐                      │
                                  │ Smart Bulb  │                      │
                                  │ Smart Plug  │                      │
                                  └─────────────┘                      │
```

---

## 5. Detailed Module Breakdown

### 5.1 Module A — Audio Pipeline (`audio_pipeline.py`)

**Responsibility:** Manage microphone input, wake word detection, and audio recording.

**Implementation details:**
1. **Continuous listening loop:**
   - Open the ReSpeaker 4-mic array via ALSA (`pyaudio`) at 16 kHz, 16-bit mono.
   - Feed 512-sample chunks into the wake word detector.
   - The ReSpeaker HAT supports on-board beamforming — configure via I²C to output a single focused channel.
2. **Wake word detection:**
   - Use openWakeWord with a custom "Hey Assistant" model.
   - The detector runs continuously with minimal CPU usage (< 5% of one core).
   - On detection: play a short "listening" chime, set LED ring to blue breathing animation.
3. **Speech recording:**
   - After wake word, record audio until one of:
     - 1.5 seconds of silence detected (energy-based VAD — voice activity detection).
     - Maximum recording duration (15 seconds) reached.
   - Apply a simple noise gate (discard samples below threshold).
   - Save the recording as a 16 kHz WAV buffer in memory.
4. **Mute button:** If the mute button GPIO is LOW, stop all mic processing and set LED to red.

**Configuration (`config/audio.yaml`):**
```yaml
sample_rate: 16000
channels: 1
chunk_size: 512
silence_threshold: 500        # energy threshold
silence_duration_s: 1.5
max_recording_s: 15
wake_word_model: "hey_assistant"
```

**Files to create:**
- `src/audio_pipeline.py`
- `src/wake_word.py`
- `src/vad.py` (voice activity detection)

---

### 5.2 Module B — Speech-to-Text (`stt_engine.py`)

**Responsibility:** Transcribe recorded speech to text using whisper.cpp.

**Implementation details:**
1. Use the `pywhispercpp` Python bindings for whisper.cpp.
2. **Model selection:**
   - `whisper-base.en` (~74M params, ~150 MB, ~3 s inference for 5 s audio on Pi 5).
   - `whisper-small.en` (~244M params, ~500 MB, ~8 s inference) — better accuracy, use if latency is acceptable.
3. **Inference flow:**
   - Load model once at startup, keep in memory.
   - Receive WAV buffer from audio pipeline.
   - Run transcription with language forced to English, no timestamps.
   - Return the transcribed text string.
4. **Optimisations:**
   - Use the quantized INT8 GGML model for reduced memory usage.
   - Set `n_threads` to 4 (all Pi 5 cores).
   - Disable translation mode (transcribe only).

**Files to create:**
- `src/stt_engine.py`

---

### 5.3 Module C — LLM Query Engine (`llm_engine.py`)

**Responsibility:** Process the transcribed text query and generate a helpful response.

**Implementation details:**
1. Use `llama-cpp-python` bindings for llama.cpp.
2. **Model options (choose one based on performance testing):**
   - **Phi-3.5-mini-instruct (3.8B, Q4_K_M GGUF):** ~2.5 GB, high quality, ~10–15 s first-token on Pi 5.
   - **Qwen2-1.5B-Instruct (Q4_K_M GGUF):** ~1 GB, faster (~5 s first-token), lower quality.
   - **TinyLlama-1.1B (Q4_K_M GGUF):** ~700 MB, fastest, basic quality.
3. **System prompt:**
```
You are a helpful, concise voice assistant running on a local device with no internet access. 
Answer questions briefly (1-3 sentences). 
If the user asks to control a smart device, respond with BOTH:
1. A natural confirmation (e.g., "Turning on the living room light.")
2. A structured command on a new line: [DEVICE_CMD: action=on, device=living_room_light]
Available devices: living_room_light, bedroom_light, smart_plug_1
Available actions: on, off, brightness(0-100), color(red/blue/green/white/warm)
```
4. **Inference settings:**
   - `temperature`: 0.3 (slightly creative but mostly deterministic).
   - `max_tokens`: 100 (keep responses short for voice).
   - `n_threads`: 4.
   - `n_gpu_layers`: 0 (CPU only) or offload to Hailo if supported.
5. **Conversation context:**
   - Maintain a sliding window of the last 3 exchanges (user + assistant) for context.
   - Clear context after 2 minutes of inactivity.
6. **Response parsing:**
   - Extract `[DEVICE_CMD: ...]` tags from the LLM response.
   - Pass device commands to the intent parser.
   - Pass the natural-language part to TTS.

**Files to create:**
- `src/llm_engine.py`
- `src/prompt_manager.py`
- `config/system_prompt.txt`

---

### 5.4 Module D — Intent Parser & Device Controller (`device_controller.py`)

**Responsibility:** Parse device commands from LLM output and send them to smart devices via the Matter bridge.

**Implementation details:**
1. **Intent parsing:**
   - Regex-based extraction of `[DEVICE_CMD: action=X, device=Y]` from LLM output.
   - Validate `action` against allowed actions and `device` against registered devices.
   - If the LLM fails to generate a structured command but the user clearly asked for device control, use a rule-based fallback parser:
     - Keywords: "turn on", "turn off", "dim", "brighten", "set color" → map to actions.
     - Device name fuzzy matching.
2. **Matter bridge communication (Pi → ESP32-C6):**
   - Serial protocol over UART (115200 baud):
     ```
     CMD:{"device":"living_room_light","action":"on"}\n
     RSP:{"status":"ok","device":"living_room_light","state":"on"}\n
     ```
   - The ESP32-C6 receives the JSON command, maps it to the appropriate Matter cluster command (On/Off, Level Control, Color Control), and sends it to the target device over Thread or BLE.
3. **Device registry (`config/devices.yaml`):**
```yaml
devices:
  - name: "living_room_light"
    type: "light"
    matter_node_id: 1
    matter_endpoint: 1
    capabilities: ["on_off", "brightness", "color"]
  - name: "bedroom_light"
    type: "light"
    matter_node_id: 2
    matter_endpoint: 1
    capabilities: ["on_off", "brightness"]
  - name: "smart_plug_1"
    type: "plug"
    matter_node_id: 3
    matter_endpoint: 1
    capabilities: ["on_off"]
```
4. **Feedback loop:** After executing a command, the ESP32 sends back a confirmation. The assistant speaks: "Done. The living room light is now on."

**Files to create:**
- `src/device_controller.py`
- `src/serial_bridge.py`
- `config/devices.yaml`
- `esp32-matter-bridge/` (separate firmware project, see Module G)

---

### 5.5 Module E — Text-to-Speech (`tts_engine.py`)

**Responsibility:** Convert the LLM's text response into spoken audio.

**Implementation details:**
1. Use Piper TTS with the `en_US-lessac-medium` voice model (~65 MB, good quality).
2. **Inference pipeline:**
   - Strip any `[DEVICE_CMD: ...]` tags from the text before speaking.
   - Feed cleaned text to Piper, receive raw PCM audio (22050 Hz, 16-bit mono).
   - Resample to 16000 Hz if needed (to match ALSA output config).
3. **Audio playback:**
   - Stream PCM to the speaker via ALSA (pyaudio or `aplay`).
   - While speaking, set LED ring to green pulse animation.
   - After speaking, return to idle (LED off or dim white).
4. **Interruptibility:** If the wake word is detected while speaking, stop TTS playback immediately and start listening.

**Files to create:**
- `src/tts_engine.py`
- `models/piper/en_US-lessac-medium.onnx`
- `models/piper/en_US-lessac-medium.onnx.json`

---

### 5.6 Module F — LED Ring Controller (`led_controller.py`)

**Responsibility:** Drive the WS2812B LED ring to provide visual state feedback.

**Implementation details:**
1. Use the `rpi_ws281x` Python library.
2. **LED animations mapped to assistant state:**

| State | Animation | Colour |
|---|---|---|
| Idle | All LEDs off or dim white breathe | White |
| Wake word detected / Listening | Spinning blue dot | Blue |
| Processing (ASR + LLM) | Pulsing purple | Purple |
| Speaking (TTS) | Gentle green breathe | Green |
| Device command sent | Quick green flash | Green |
| Error | Red blink × 3 | Red |
| Muted | Solid red (single LED) | Red |

3. Run LED updates in a dedicated thread to avoid blocking the main pipeline.
4. Expose a `set_state(state: str)` API called by the main orchestrator.

**Files to create:**
- `src/led_controller.py`

---

### 5.7 Module G — ESP32 Matter Bridge Firmware (`esp32-matter-bridge/`)

**Responsibility:** Receive commands from the Pi over serial, send Matter commands to smart devices.

**Implementation details:**
1. **Platform:** ESP-IDF 5.x + ESP-Matter SDK (connectedhomeip).
2. **Device commissioning:**
   - On first boot, the ESP32-C6 starts a Matter commissioning flow.
   - Commission smart devices (bulb, plug) into the local Matter fabric using the ESP32 as a controller.
   - Store fabric credentials and device node IDs in NVS (non-volatile storage).
3. **Serial command handler:**
   - Listen on UART0 for JSON commands from the Pi.
   - Parse JSON, map to Matter cluster commands:
     - `on_off` → On/Off cluster, command On/Off.
     - `brightness` → Level Control cluster, MoveToLevel.
     - `color` → Color Control cluster, MoveToHueAndSaturation.
   - Send Matter command to target device.
   - Send JSON response back over UART with success/failure status.
4. **Heartbeat:** Send a status message to the Pi every 10 s listing connected devices and their states.

**Files to create:**
- `esp32-matter-bridge/main/main.c`
- `esp32-matter-bridge/main/serial_handler.c`
- `esp32-matter-bridge/main/matter_controller.c`
- `esp32-matter-bridge/main/device_registry.c`
- `esp32-matter-bridge/CMakeLists.txt`
- `esp32-matter-bridge/sdkconfig.defaults`

---

## 6. Directory Structure

```
offline-voice-assistant/
├── README.md
├── requirements.txt
├── src/
│   ├── main.py                        # Main orchestrator
│   ├── audio_pipeline.py
│   ├── wake_word.py
│   ├── vad.py
│   ├── stt_engine.py
│   ├── llm_engine.py
│   ├── prompt_manager.py
│   ├── tts_engine.py
│   ├── device_controller.py
│   ├── serial_bridge.py
│   └── led_controller.py
├── config/
│   ├── audio.yaml
│   ├── devices.yaml
│   ├── system_prompt.txt
│   └── assistant.yaml                 # General config (model paths, etc.)
├── models/
│   ├── whisper/
│   │   └── ggml-base.en.bin
│   ├── llm/
│   │   └── phi-3.5-mini-instruct.Q4_K_M.gguf
│   ├── piper/
│   │   ├── en_US-lessac-medium.onnx
│   │   └── en_US-lessac-medium.onnx.json
│   └── wake_word/
│       └── hey_assistant.tflite
├── esp32-matter-bridge/
│   ├── CMakeLists.txt
│   ├── sdkconfig.defaults
│   └── main/
│       ├── main.c
│       ├── serial_handler.h / .c
│       ├── matter_controller.h / .c
│       └── device_registry.h / .c
├── scripts/
│   ├── download_models.sh
│   ├── setup_audio.sh
│   └── test_speaker.sh
├── tests/
│   ├── test_audio_pipeline.py
│   ├── test_stt.py
│   ├── test_llm.py
│   ├── test_intent_parser.py
│   ├── test_device_controller.py
│   └── test_led_controller.py
├── hardware/
│   ├── wiring_diagram.pdf
│   └── enclosure_stl/
│       └── speaker_housing.stl
└── docs/
    ├── setup_guide.md
    ├── matter_commissioning.md
    └── model_benchmarks.md
```

---

## 7. Main Orchestrator (`main.py`) — Pseudocode

```python
def main():
    # Initialise all modules
    audio = AudioPipeline(config["audio"])
    wake = WakeWordDetector(config["wake_word"])
    stt = STTEngine(model_path="models/whisper/ggml-base.en.bin")
    llm = LLMEngine(model_path="models/llm/phi-3.5-mini-instruct.Q4_K_M.gguf")
    tts = TTSEngine(model_path="models/piper/en_US-lessac-medium.onnx")
    devices = DeviceController(config["devices"], serial_port="/dev/ttyUSB0")
    leds = LEDController(num_leds=12)
    
    leds.set_state("idle")
    
    while True:
        # Step 1: Wait for wake word
        audio_stream = audio.get_stream()
        wake.listen(audio_stream)  # blocks until wake word detected
        
        # Step 2: Listen for user speech
        leds.set_state("listening")
        audio.play_chime("listening")
        recording = audio.record_until_silence()
        
        # Step 3: Transcribe
        leds.set_state("processing")
        user_text = stt.transcribe(recording)
        if not user_text.strip():
            leds.set_state("idle")
            continue
        
        # Step 4: Query LLM
        response_text = llm.query(user_text)
        
        # Step 5: Parse device commands
        clean_text, device_cmds = devices.parse_commands(response_text)
        
        # Step 6: Execute device commands
        for cmd in device_cmds:
            result = devices.execute(cmd)
            if not result.success:
                clean_text += f" Sorry, I couldn't control {cmd.device}."
        
        # Step 7: Speak response
        leds.set_state("speaking")
        tts.speak(clean_text)
        
        # Step 8: Return to idle
        leds.set_state("idle")
```

---

## 8. Performance Targets & Benchmarks

| Stage | Target Latency | Notes |
|---|---|---|
| Wake word detection | < 200 ms | Continuous, low-CPU |
| Recording (average utterance) | 2–5 s | Depends on user speech length |
| Whisper transcription (base.en) | 2–3 s | For a 5 s utterance on Pi 5 |
| LLM inference (Phi-3.5, Q4) | 5–10 s | First token ~3 s, generation ~20 tok/s |
| LLM inference (Qwen2-1.5B, Q4) | 2–5 s | Faster but lower quality |
| TTS synthesis | 1–2 s | For 1–3 sentence response |
| **Total end-to-end** | **~12–20 s** | From end of speech to start of response |

*To reduce perceived latency:*
- Start TTS as soon as the first sentence of LLM output is complete (streaming).
- Play a "thinking" sound during processing.

---

## 9. Testing Strategy

| Test | Type | What it validates |
|---|---|---|
| `test_audio_pipeline.py` | Unit | Mic capture, VAD silence detection, recording correct duration |
| `test_stt.py` | Unit | 10 pre-recorded WAV files transcribed correctly (> 90% WER) |
| `test_llm.py` | Unit | 10 sample queries produce sensible responses |
| `test_intent_parser.py` | Unit | Device command extraction correct for 15 test cases |
| `test_device_controller.py` | Integration | Serial commands sent correctly; mock ESP32 responds |
| `test_led_controller.py` | Unit | LED state transitions correct |
| End-to-end voice test | System | Speak 10 varied commands, verify correct responses and device actions |

---

## 10. Stretch Goals

- **Multi-room audio:** Multiple Pi units synchronised, with the nearest one responding.
- **Custom wake word training:** Use openWakeWord to train a personalised wake word.
- **Streaming LLM response:** Start TTS before LLM finishes generating (sentence-level streaming).
- **Music playback:** "Play relaxing music" → play local MP3 files.
- **Timer/alarm support:** "Set a timer for 5 minutes" → local countdown with alarm sound.
- **Whisper fine-tuning:** Fine-tune Whisper on accented speech or domain-specific vocabulary.

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LLM too slow on Pi 5 CPU | High latency, poor UX | Use smaller model (Qwen2-1.5B); add Hailo-8L for offloading |
| Whisper misunderstands commands | Wrong device actions | Add confirmation step: "Did you say 'turn off bedroom light'?" |
| Matter commissioning complexity | Can't control devices | Use pre-commissioned demo setup; provide step-by-step guide |
| RAM pressure (Whisper + LLM in memory) | OOM or swapping | Unload Whisper during LLM inference; use mmap for models |
| Wake word false positives | Annoying triggers | Tune detection threshold; add confirmation chime before recording |

---

## 12. Estimated Timeline

| Phase | Duration | Deliverable |
|---|---|---|
| Hardware assembly (Pi + mic + speaker + LEDs) | 2 days | Audio I/O working |
| Wake word + audio pipeline | 2 days | "Hey Assistant" triggers recording |
| Whisper ASR integration | 2 days | Speech transcribed to text |
| LLM integration + prompt engineering | 3 days | Queries answered correctly |
| TTS integration | 1 day | Spoken responses |
| Device control (intent parser + serial bridge) | 3 days | Matter devices controlled |
| ESP32 Matter bridge firmware | 4 days | ESP32 commissions and controls Matter devices |
| LED animations + UX polish | 1 day | Visual feedback working |
| End-to-end testing + documentation | 2 days | Reliable demo |
| **Total** | **~20 days** | — |
