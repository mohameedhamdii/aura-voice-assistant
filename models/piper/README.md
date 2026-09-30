# Piper Text-to-Speech Models

This directory stores offline ONNX neural voices for Piper TTS (`piper-tts`).

## Expected Files

- `en_US-lessac-medium.onnx` (~63 MB)
- `en_US-lessac-medium.onnx.json` (~5 KB, phoneme mapping & synthesis config)

## Downloading

Run the download script:

```bash
./scripts/download_models.sh
```

Or download manually via curl:

```bash
curl -L -o models/piper/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx

curl -L -o models/piper/en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

## Voice Characteristics

- Voice: Lessac (clean, professional American English female voice)
- Sample Rate: 22,050 Hz (automatically resampled to 16,000 Hz if required by ALSA)
- Real-Time Factor (RTF) on Pi 5: ~0.18 (synthesizes 5s of speech in ~0.9s)
