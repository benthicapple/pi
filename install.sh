#!/bin/bash
# Install PiTextReader with Piper TTS - Raspberry Pi 5
# 
# Run using:
# $ bash install.sh

set -e

echo "=========================================="
echo "  PiTextReader Installation - Pi 5"
echo "=========================================="
echo

if [ "$EUID" -eq 0 ]; then 
   echo "❌ ERROR: Do not run as root/sudo"
   echo "   Run as: bash install.sh"
   exit 1
fi

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies
echo
echo "Installing dependencies..."
sudo apt-get install -y \
    tesseract-ocr \
    python3-opencv \
    python3-pip \
    python3-lgpio \
    wget \
    tar \
    sox \
    alsa-utils

# Install Python packages for Pi 5
echo
echo "Installing Python packages..."
pip3 install --break-system-packages rpi-lgpio pyspellchecker

# Create directories
echo
echo "Creating directories..."
mkdir -p piper sounds corrections/training_data ai_models/training_data

# Install Piper TTS
echo
echo "Installing Piper TTS..."
cd piper

if [ ! -f "piper" ]; then
    wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz
    tar -xzf piper_arm64.tar.gz
    PIPER_BIN=$(find . -name "piper" -type f | head -1)
    cp "$PIPER_BIN" ./piper
    chmod +x piper
    rm -rf piper_arm64 piper_arm64.tar.gz
fi

# Download voice model
if [ ! -f "en_US-amy-medium.onnx" ]; then
    echo "Downloading voice model..."
    wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
    wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json
fi

cd ..

# Create sound effect
echo
echo "Creating sound effect..."
cd sounds
if [ ! -f "camera-shutter.wav" ]; then
    sox -n -r 44100 -b 16 camera-shutter.wav synth 0.1 sine 800 2>/dev/null
fi
cd ..

# Create GPIO wrapper for Pi 5
echo
echo "Creating GPIO wrapper..."
cat > gpio_compat.py << 'EOF'
"""GPIO compatibility for Raspberry Pi 5"""
try:
    import lgpio
    import time
    
    class GPIO:
        BCM = "BCM"
        IN = "IN"
        OUT = "OUT"
        PUD_UP = "PUD_UP"
        HIGH = 1
        LOW = 0
        
        _chip = None
        _mode = None
        
        @classmethod
        def setmode(cls, mode):
            cls._mode = mode
            if cls._chip is None:
                cls._chip = lgpio.gpiochip_open(4)  # Pi 5 uses gpiochip4
        
        @classmethod
        def setwarnings(cls, flag):
            pass
        
        @classmethod
        def setup(cls, pin, direction, pull_up_down=None):
            if cls._chip is None:
                cls.setmode(cls.BCM)
            
            if direction == cls.IN:
                lgpio.gpio_claim_input(cls._chip, pin)
                if pull_up_down == cls.PUD_UP:
                    lgpio.gpio_claim_input(cls._chip, pin, lgpio.SET_PULL_UP)
            else:
                lgpio.gpio_claim_output(cls._chip, pin)
        
        @classmethod
        def input(cls, pin):
            return lgpio.gpio_read(cls._chip, pin)
        
        @classmethod
        def output(cls, pin, value):
            lgpio.gpio_write(cls._chip, pin, value)
        
        @classmethod
        def cleanup(cls):
            if cls._chip is not None:
                lgpio.gpiochip_close(cls._chip)
                cls._chip = None
    
except ImportError:
    print("⚠️  lgpio not available, install with: pip3 install rpi-lgpio")
    raise
EOF

# Set permissions
chmod +x pi.py 2>/dev/null || true
chmod +x piper/piper

echo
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "  1. Update pi.py - change GPIO import to:"
echo "     from gpio_compat import GPIO"
echo
echo "  2. Find your audio device:"
echo "     aplay -L"
echo
echo "  3. Update AUDIO_DEVICE in pi.py"
echo
echo "  4. Run with:"
echo "     sudo python3 pi.py"
echo
echo "=========================================="
