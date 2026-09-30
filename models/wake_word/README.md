# openWakeWord Models

This directory stores openWakeWord TFLite / ONNX model files.

## Wake Word Model

- `hey_assistant.tflite` (~4.8 MB) or openWakeWord default built-in pretrained models (`hey_jarvis`, `alexa`, etc.).

## Downloading / Training

Run the download script to fetch the default models or custom trained model:

```bash
./scripts/download_models.sh
```

Or copy your custom openWakeWord model trained using openWakeWord training notebook:

```bash
cp /path/to/my_wake_word.tflite models/wake_word/hey_assistant.tflite
```

Configure `config/audio.yaml`:
```yaml
wake_word:
  model_path: "models/wake_word/hey_assistant.tflite"
  threshold: 0.5
```
