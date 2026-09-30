#!/usr/bin/env bash
# ============================================================================
# test_speaker.sh — Test audio input and output hardware
# ============================================================================
#
# Runs a series of tests:
#   1. Lists ALSA audio devices
#   2. Plays a test tone through the speaker
#   3. Records a short audio clip from the microphone
#   4. Plays back the recorded clip
#
# Usage:
#   chmod +x scripts/test_speaker.sh
#   ./scripts/test_speaker.sh
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Audio Hardware Test${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ============================================================================
# Test 1: List audio devices
# ============================================================================
echo -e "${YELLOW}Test 1: Listing audio playback devices...${NC}"
aplay -l 2>/dev/null || echo -e "${RED}  No playback devices found${NC}"
echo ""

echo -e "${YELLOW}Test 2: Listing audio capture devices...${NC}"
arecord -l 2>/dev/null || echo -e "${RED}  No capture devices found${NC}"
echo ""

# ============================================================================
# Test 2: Generate and play test tone
# ============================================================================
echo -e "${YELLOW}Test 3: Playing test tone (440 Hz, 2 seconds)...${NC}"

# Generate a 440 Hz sine wave test tone using Python
python3 -c "
import numpy as np
import wave
import struct
import sys

sample_rate = 16000
duration = 2.0
frequency = 440.0
amplitude = 16000

t = np.linspace(0, duration, int(sample_rate * duration), False)
tone = (np.sin(2 * np.pi * frequency * t) * amplitude).astype(np.int16)

with wave.open('/tmp/test_tone.wav', 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    f.writeframes(tone.tobytes())

print('  Test tone generated: /tmp/test_tone.wav')
"

aplay -q /tmp/test_tone.wav 2>/dev/null && \
    echo -e "${GREEN}  ✓ Speaker test passed — did you hear a tone?${NC}" || \
    echo -e "${RED}  ✗ Speaker test failed — check speaker connection${NC}"
echo ""

# ============================================================================
# Test 3: Record from microphone
# ============================================================================
echo -e "${YELLOW}Test 4: Recording from microphone (3 seconds)...${NC}"
echo "  Speak into the microphone now!"

RECORD_FILE="/tmp/test_recording.wav"
arecord -f S16_LE -r 16000 -c 1 -d 3 "$RECORD_FILE" 2>/dev/null && \
    echo -e "${GREEN}  ✓ Recording saved to $RECORD_FILE${NC}" || \
    echo -e "${RED}  ✗ Recording failed — check microphone connection${NC}"
echo ""

# ============================================================================
# Test 4: Play back recording
# ============================================================================
if [ -f "$RECORD_FILE" ]; then
    echo -e "${YELLOW}Test 5: Playing back recording...${NC}"
    aplay -q "$RECORD_FILE" 2>/dev/null && \
        echo -e "${GREEN}  ✓ Playback complete — did you hear your voice?${NC}" || \
        echo -e "${RED}  ✗ Playback failed${NC}"
else
    echo -e "${YELLOW}Test 5: Skipped (no recording available)${NC}"
fi
echo ""

# ============================================================================
# Test 5: Check ALSA mixer levels
# ============================================================================
echo -e "${YELLOW}Test 6: Current ALSA mixer levels...${NC}"
amixer 2>/dev/null | grep -E "(Simple mixer|Mono:|Playback|Capture)" | head -20 || \
    echo -e "${YELLOW}  Could not read mixer levels${NC}"
echo ""

# ============================================================================
# Summary
# ============================================================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Audio test complete${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "If all tests passed, your audio hardware is ready."
echo "If any tests failed, check:"
echo "  1. ReSpeaker HAT is properly seated on the GPIO header"
echo "  2. Speaker is connected to the MAX98357A amplifier"
echo "  3. Run 'sudo ./scripts/setup_audio.sh' first"
echo ""

# Cleanup
rm -f /tmp/test_tone.wav /tmp/test_recording.wav 2>/dev/null || true
