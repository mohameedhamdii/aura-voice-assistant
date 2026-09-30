# Large Language Models (LLM GGUF)

This directory stores quantized GGUF models for on-device reasoning using `llama.cpp` (`llama-cpp-python`).

## Supported Models

1. **Phi-3.5-mini-instruct (Default Recommended)**
   - Filename: `phi-3.5-mini-instruct.Q4_K_M.gguf`
   - Parameters: 3.8B
   - Quantization: Q4_K_M
   - Size: ~2.39 GB
   - Performance: High quality natural responses and reliable structured command generation.

2. **Qwen2-1.5B-Instruct (Low-Latency Option)**
   - Filename: `qwen2-1_5b-instruct-q4_k_m.gguf`
   - Parameters: 1.5B
   - Quantization: Q4_K_M
   - Size: ~980 MB
   - Performance: Extremely fast (~2.5s response), lower memory footprint.

3. **TinyLlama-1.1B-Chat (Ultra-Lightweight)**
   - Filename: `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`
   - Parameters: 1.1B
   - Quantization: Q4_K_M
   - Size: ~670 MB
   - Performance: Lowest RAM footprint, basic command extraction.

## Downloading

Run the download script:

```bash
./scripts/download_models.sh
```

Or download manually:

```bash
# Phi-3.5-mini-instruct Q4_K_M
curl -L -o models/llm/phi-3.5-mini-instruct.Q4_K_M.gguf \
  https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf

# Qwen2-1.5B-Instruct Q4_K_M
curl -L -o models/llm/qwen2-1_5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2-1.5B-Instruct-GGUF/resolve/main/qwen2-1_5b-instruct-q4_k_m.gguf
```
