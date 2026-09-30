# Whisper Speech-to-Text Models

This directory stores offline GGML/GGUF models for Whisper ASR (`whisper.cpp` / `pywhispercpp`).

## Expected Files

- `ggml-base.en.bin` (~148 MB, default model for Raspberry Pi 5)
- `ggml-small.en.bin` (~488 MB, optional higher accuracy model)

## Downloading

Run the download script from the project root:

```bash
./scripts/download_models.sh
```

Or download manually via curl:

```bash
# Whisper base.en (Recommended for Pi 5 CPU)
curl -L -o models/whisper/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin

# Whisper small.en (Higher accuracy, ~2x higher latency)
curl -L -o models/whisper/ggml-small.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
```

## Performance on Pi 5 (4 Threads)

| Model | Size | RAM Usage | 5s Audio Latency | WER (Clean) |
|---|---|---|---|---|
| `base.en` | 148 MB | ~380 MB | 1.8s - 2.4s | ~94% |
| `small.en` | 488 MB | ~1.1 GB | 5.2s - 7.5s | ~97% |
