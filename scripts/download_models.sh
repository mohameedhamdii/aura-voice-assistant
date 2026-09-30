#!/usr/bin/env bash
# ============================================================================
# download_models.sh — Download all required AI models for the voice assistant
# ============================================================================
#
# Downloads:
#   1. Whisper base.en model (GGML format, ~150 MB)
#   2. Phi-3.5-mini-instruct LLM (GGUF Q4_K_M, ~2.5 GB)
#   3. Piper TTS voice model (en_US-lessac-medium, ~65 MB)
#   4. openWakeWord model (~5 MB)
#
# Usage:
#   chmod +x scripts/download_models.sh
#   ./scripts/download_models.sh
#
# Requirements: curl or wget
# ============================================================================

set -euo pipefail

# Colours for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Offline Voice Assistant — Model Downloader${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check for download tool
if command -v curl &> /dev/null; then
    DOWNLOAD="curl -L -o"
    DOWNLOAD_PROGRESS="curl -L --progress-bar -o"
elif command -v wget &> /dev/null; then
    DOWNLOAD="wget -O"
    DOWNLOAD_PROGRESS="wget --show-progress -O"
else
    echo -e "${RED}Error: Neither curl nor wget found. Please install one.${NC}"
    exit 1
fi

# Create model directories
echo -e "${YELLOW}Creating model directories...${NC}"
mkdir -p "$PROJECT_ROOT/models/whisper"
mkdir -p "$PROJECT_ROOT/models/llm"
mkdir -p "$PROJECT_ROOT/models/piper"
mkdir -p "$PROJECT_ROOT/models/wake_word"

# ============================================================================
# 1. Whisper base.en model
# ============================================================================
WHISPER_MODEL="$PROJECT_ROOT/models/whisper/ggml-base.en.bin"
WHISPER_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"

if [ -f "$WHISPER_MODEL" ]; then
    echo -e "${GREEN}✓ Whisper base.en model already exists${NC}"
else
    echo -e "${YELLOW}Downloading Whisper base.en model (~150 MB)...${NC}"
    $DOWNLOAD_PROGRESS "$WHISPER_MODEL" "$WHISPER_URL"
    echo -e "${GREEN}✓ Whisper model downloaded${NC}"
fi

# ============================================================================
# 2. Phi-3.5-mini-instruct LLM (Q4_K_M GGUF)
# ============================================================================
LLM_MODEL="$PROJECT_ROOT/models/llm/phi-3.5-mini-instruct.Q4_K_M.gguf"
LLM_URL="https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf"

if [ -f "$LLM_MODEL" ]; then
    echo -e "${GREEN}✓ Phi-3.5-mini LLM model already exists${NC}"
else
    echo -e "${YELLOW}Downloading Phi-3.5-mini-instruct Q4_K_M (~2.5 GB)...${NC}"
    echo -e "${YELLOW}  This may take several minutes depending on your connection.${NC}"
    $DOWNLOAD_PROGRESS "$LLM_MODEL" "$LLM_URL"
    echo -e "${GREEN}✓ LLM model downloaded${NC}"
fi

# ============================================================================
# 3. Piper TTS voice model (en_US-lessac-medium)
# ============================================================================
PIPER_MODEL="$PROJECT_ROOT/models/piper/en_US-lessac-medium.onnx"
PIPER_CONFIG="$PROJECT_ROOT/models/piper/en_US-lessac-medium.onnx.json"
PIPER_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"

if [ -f "$PIPER_MODEL" ] && [ -f "$PIPER_CONFIG" ]; then
    echo -e "${GREEN}✓ Piper TTS model already exists${NC}"
else
    echo -e "${YELLOW}Downloading Piper TTS voice model (~65 MB)...${NC}"
    $DOWNLOAD_PROGRESS "$PIPER_MODEL" "$PIPER_BASE_URL/en_US-lessac-medium.onnx"
    $DOWNLOAD_PROGRESS "$PIPER_CONFIG" "$PIPER_BASE_URL/en_US-lessac-medium.onnx.json"
    echo -e "${GREEN}✓ Piper TTS model downloaded${NC}"
fi

# ============================================================================
# 4. openWakeWord model
# ============================================================================
WAKE_MODEL="$PROJECT_ROOT/models/wake_word/hey_assistant.tflite"
WAKE_URL="https://huggingface.co/davidscripka/openwakeword/resolve/main/hey_jarvis_v0.1.tflite"

if [ -f "$WAKE_MODEL" ]; then
    echo -e "${GREEN}✓ Wake word model already exists${NC}"
else
    echo -e "${YELLOW}Downloading wake word model (~5 MB)...${NC}"
    echo -e "${YELLOW}  Note: Using 'hey_jarvis' as base. Rename to train custom wake word.${NC}"
    $DOWNLOAD_PROGRESS "$WAKE_MODEL" "$WAKE_URL"
    echo -e "${GREEN}✓ Wake word model downloaded${NC}"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  All models downloaded successfully!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "Model locations:"
echo "  Whisper:    $WHISPER_MODEL"
echo "  LLM:        $LLM_MODEL"
echo "  Piper TTS:  $PIPER_MODEL"
echo "  Wake word:  $WAKE_MODEL"
echo ""

# Check total disk usage
TOTAL_SIZE=$(du -sh "$PROJECT_ROOT/models" 2>/dev/null | cut -f1)
echo -e "Total model size: ${YELLOW}${TOTAL_SIZE}${NC}"
echo ""
echo -e "${GREEN}Ready to run: python src/main.py${NC}"
