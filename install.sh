#!/bin/bash
# Install PiTextReader with Piper TTS
# 
# Run using:
# $ bash install.sh
#
# Can be safely run multiple times
#
# version 20241215

echo "=================================="
echo "PiTextReader Installation"
echo "=================================="
echo

# Update system
echo "Updating system packages..."
sudo apt-get update

# Install required packages
echo "Installing dependencies..."
sudo apt-get install -y tesseract-ocr python3-opencv python3-pip wget tar

# Install Python packages
echo "Installing Python packages..."
pip3 install --break-system-packages pyspellchecker RPi.GPIO

# Create directory structure
echo "Creating directories..."
mkdir -p piper
mkdir -p sounds
mkdir -p corrections/training_data

# Download and install Piper TTS
echo "=================================="
echo "Installing Piper TTS..."
echo "=================================="

cd piper

# Check if piper already exists
if [ -f "piper" ] && [ -x "piper" ]; then
    echo "Piper binary already installed."
else
    echo "Downloading Piper for ARM64..."
    wget -q --show-progress https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz
    
    echo "Extracting Piper..."
    tar -xzf piper_arm64.tar.gz
    cp piper_arm64/piper ./
    
    # Make executable
    chmod +x piper
    
    # Clean up
    rm -rf piper_arm64 piper_arm64.tar.gz
    
    echo "✓ Piper binary installed"
fi

# Download voice model
if [ -f "en_US-amy-medium.onnx" ]; then
    echo "Voice model already downloaded."
else
    echo "Downloading Amy voice model (63MB, may take a few minutes)..."
    wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
    echo "✓ Voice model downloaded"
fi

# Download voice config
if [ -f "en_US-amy-medium.onnx.json" ]; then
    echo "Voice config already downloaded."
else
    echo "Downloading voice config..."
    wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json
    echo "✓ Voice config downloaded"
fi

# Test Piper installation
echo "Testing Piper TTS..."
if ./piper --version > /dev/null 2>&1; then
    echo "✓ Piper TTS working!"
else
    echo "✗ Piper TTS test failed"
    echo "  Try running: chmod +x piper"
fi

cd ..

# Download camera shutter sound
echo "=================================="
echo "Installing sound effects..."
echo "=================================="

cd sounds

if [ -f "camera-shutter.wav" ]; then
    echo "Sound effect already exists."
else
    # Check if sox is installed
    if command -v sox &> /dev/null; then
        echo "Creating camera shutter sound..."
        sox -n -r 44100 -b 16 camera-shutter.wav synth 0.1 sine 800
        echo "✓ Sound effect created"
    else
        echo "Installing sox..."
        sudo apt-get install -y sox
        echo "Creating camera shutter sound..."
        sox -n -r 44100 -b 16 camera-shutter.wav synth 0.1 sine 800
        echo "✓ Sound effect created"
    fi
fi

cd ..

# Verify Camera is configured
echo "=================================="
echo "Checking camera..."
echo "=================================="

if command -v rpicam-still &> /dev/null; then
    rpicam-still -t 1 -o /tmp/camera_test.jpg 2>/dev/null
    if [ -f "/tmp/camera_test.jpg" ]; then
        echo "✓ Camera detected and working!"
        rm /tmp/camera_test.jpg
    else
        echo "✗ Camera not detected!"
        echo "  Make sure camera is connected and enabled"
        echo "  Run: sudo raspi-config > Interface Options > Camera > Enable"
    fi
else
    echo "✗ rpicam-still not found!"
    echo "  This is normal on older Pi OS versions"
    echo "  Camera commands will be updated during first run"
fi

# Set correct permissions
echo "=================================="
echo "Setting permissions..."
echo "=================================="

chmod +x pi.py 2>/dev/null
chmod +x train.py 2>/dev/null
chmod +x learn.py 2>/dev/null
chmod +x piper/piper

echo "✓ Permissions set"

# Install crontab if cronfile exists
if [ -f "cronfile" ]; then
    echo "Installing crontab entry..."
    crontab cronfile
    echo "✓ Crontab entry installed"
fi

# Final summary
echo
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo
echo "What was installed:"
echo "  ✓ Tesseract OCR"
echo "  ✓ Python packages (spellchecker, GPIO)"
echo "  ✓ Piper TTS + Amy voice"
echo "  ✓ Sound effects"
echo "  ✓ Camera verification"
echo
echo "File structure:"
echo "  $(pwd)/"
echo "    ├── pi.py"
echo "    ├── train.py"
echo "    ├── learn.py"
echo "    ├── piper/"
echo "    │   ├── piper"
echo "    │   ├── en_US-amy-medium.onnx"
echo "    │   └── en_US-amy-medium.onnx.json"
echo "    └── sounds/"
echo "        └── camera-shutter.wav"
echo
echo "Next steps:"
echo "  1. Test the installation:"
echo "     $ sudo python3 pi.py"
echo
echo "  2. If you get audio errors:"
echo "     $ aplay -L"
echo "     (Check your audio device name)"
echo
echo "  3. For help:"
echo "     See README.md"
echo
echo "=================================="
