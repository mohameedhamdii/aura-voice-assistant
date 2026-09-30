#!/usr/bin/env bash
# ============================================================================
# setup_audio.sh — Configure audio hardware on Raspberry Pi 5
# ============================================================================
#
# Sets up:
#   1. ReSpeaker 4-Mic Array HAT drivers
#   2. ALSA configuration for I²S speaker output
#   3. Audio routing and volume levels
#
# Usage:
#   chmod +x scripts/setup_audio.sh
#   sudo ./scripts/setup_audio.sh
#
# Must be run as root (sudo) on Raspberry Pi OS Bookworm 64-bit
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Audio Hardware Setup — Raspberry Pi 5${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (sudo).${NC}"
    echo "Usage: sudo ./scripts/setup_audio.sh"
    exit 1
fi

# Check if on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}Warning: Not running on a Raspberry Pi.${NC}"
    echo "This script is designed for Raspberry Pi OS. Proceeding anyway..."
    echo ""
fi

# ============================================================================
# 1. Update system packages
# ============================================================================
echo -e "${YELLOW}Step 1: Updating system packages...${NC}"
apt-get update -qq
apt-get install -y -qq \
    portaudio19-dev \
    python3-pyaudio \
    alsa-utils \
    libasound2-dev \
    i2c-tools \
    python3-smbus
echo -e "${GREEN}✓ System packages installed${NC}"

# ============================================================================
# 2. Enable I²C and SPI interfaces
# ============================================================================
echo -e "${YELLOW}Step 2: Enabling I²C and SPI interfaces...${NC}"

# Enable I²C
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt
    echo -e "${GREEN}  ✓ I²C enabled${NC}"
else
    echo -e "${GREEN}  ✓ I²C already enabled${NC}"
fi

# Enable SPI
if ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtparam=spi=on" >> /boot/firmware/config.txt
    echo -e "${GREEN}  ✓ SPI enabled${NC}"
else
    echo -e "${GREEN}  ✓ SPI already enabled${NC}"
fi

# ============================================================================
# 3. Install ReSpeaker drivers
# ============================================================================
echo -e "${YELLOW}Step 3: Setting up ReSpeaker 4-Mic Array HAT...${NC}"

# Install seeed-voicecard driver if not present
if [ ! -d "/opt/seeed-voicecard" ]; then
    echo "  Cloning seeed-voicecard driver..."
    cd /opt
    git clone --depth 1 https://github.com/HinTak/seeed-voicecard.git
    cd seeed-voicecard
    ./install.sh
    echo -e "${GREEN}  ✓ ReSpeaker driver installed${NC}"
else
    echo -e "${GREEN}  ✓ ReSpeaker driver already installed${NC}"
fi

# ============================================================================
# 4. Configure I²S audio output (MAX98357A)
# ============================================================================
echo -e "${YELLOW}Step 4: Configuring I²S audio output...${NC}"

# Add HiFiBerry DAC overlay for I²S output (compatible with MAX98357A)
if ! grep -q "dtoverlay=hifiberry-dac" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtoverlay=hifiberry-dac" >> /boot/firmware/config.txt
    echo -e "${GREEN}  ✓ I²S DAC overlay added${NC}"
else
    echo -e "${GREEN}  ✓ I²S DAC overlay already configured${NC}"
fi

# ============================================================================
# 5. Create ALSA configuration
# ============================================================================
echo -e "${YELLOW}Step 5: Creating ALSA configuration...${NC}"

cat > /etc/asound.conf << 'EOF'
# ALSA configuration for Offline Voice Assistant
# ReSpeaker 4-Mic Array (input) + I²S DAC speaker (output)

# Default PCM device — use the ReSpeaker for capture, I²S for playback
pcm.!default {
    type asym
    capture.pcm "mic"
    playback.pcm "speaker"
}

# ReSpeaker 4-Mic Array (input)
pcm.mic {
    type plug
    slave {
        pcm "hw:seeed4micvoicec"
        rate 16000
        channels 1
    }
}

# I²S Speaker output (MAX98357A)
pcm.speaker {
    type plug
    slave {
        pcm "hw:sndrpihifiberry"
        rate 16000
        channels 1
    }
}

# Default control device
ctl.!default {
    type hw
    card 0
}
EOF

echo -e "${GREEN}✓ ALSA configuration written to /etc/asound.conf${NC}"

# ============================================================================
# 6. Set audio levels
# ============================================================================
echo -e "${YELLOW}Step 6: Setting audio levels...${NC}"

# Set capture volume to 80%
amixer -c seeed4micvoicec sset 'Capture' 80% 2>/dev/null || \
    echo -e "${YELLOW}  Note: Could not set capture volume (ReSpeaker not connected?)${NC}"

# Set playback volume to 90%
amixer sset 'Master' 90% 2>/dev/null || \
    amixer sset 'PCM' 90% 2>/dev/null || \
    echo -e "${YELLOW}  Note: Could not set playback volume${NC}"

echo -e "${GREEN}✓ Audio levels configured${NC}"

# ============================================================================
# 7. Add user to audio group
# ============================================================================
echo -e "${YELLOW}Step 7: Configuring user permissions...${NC}"
REAL_USER="${SUDO_USER:-pi}"
usermod -aG audio "$REAL_USER" 2>/dev/null || true
usermod -aG i2c "$REAL_USER" 2>/dev/null || true
usermod -aG gpio "$REAL_USER" 2>/dev/null || true
usermod -aG spi "$REAL_USER" 2>/dev/null || true
echo -e "${GREEN}✓ User '$REAL_USER' added to audio, i2c, gpio, spi groups${NC}"

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  Audio setup complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: A reboot is required for changes to take effect.${NC}"
echo ""
echo "After reboot, test with:"
echo "  ./scripts/test_speaker.sh"
echo ""
read -p "Reboot now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    reboot
fi
