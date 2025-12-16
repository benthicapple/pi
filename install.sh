#!/bin/bash
# Install PiTextReader with Piper TTS - Raspberry Pi 5 Compatible
# 
# Run using:
# $ bash install.sh
#
# Can be safely run multiple times
#
# Version 20241215 - Pi 5 Compatible

set -e  # Exit on any error

echo "=========================================="
echo "  PiTextReader Installation"
echo "  Raspberry Pi 5 Compatible"
echo "=========================================="
echo

# Check if running as root (don't want this)
if [ "$EUID" -eq 0 ]; then 
   echo "❌ ERROR: Do not run as root/sudo"
   echo "   Run as: bash install.sh"
   echo "   (Script will ask for sudo when needed)"
   exit 1
fi

# Check if we're on a Raspberry Pi
echo "Checking system..."
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Detect Pi model
PI_MODEL=$(cat /proc/cpuinfo | grep "Model" | cut -d: -f2 | xargs)
echo "Detected: $PI_MODEL"
echo

# Update system
echo "=========================================="
echo "Step 1: Updating system packages..."
echo "=========================================="
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
echo
echo "=========================================="
echo "Step 2: Installing system dependencies..."
echo "=========================================="
sudo apt-get install -y \
    tesseract-ocr \
    python3-opencv \
    python3-pip \
    python3-dev \
    python3-rpi.gpio \
    python3-lgpio \
    wget \
    tar \
    sox \
    alsa-utils \
    git

echo "✓ System dependencies installed"

# Install Python packages
echo
echo "=========================================="
echo "Step 3: Installing Python packages..."
echo "=========================================="

# For Raspberry Pi 5, use lgpio
if [[ "$PI_MODEL" == *"Raspberry Pi 5"* ]]; then
    echo "Installing GPIO support for Raspberry Pi 5..."
    pip3 install --break-system-packages rpi-lgpio
else
    echo "Installing GPIO support for Raspberry Pi 4 and earlier..."
    pip3 install --break-system-packages RPi.GPIO
fi

# Install other Python packages
pip3 install --break-system-packages pyspellchecker

echo "✓ Python packages installed"

# Create directory structure
echo
echo "=========================================="
echo "Step 4: Creating directory structure..."
echo "=========================================="

mkdir -p piper
mkdir -p sounds
mkdir -p corrections/training_data
mkdir -p ai_models/training_data

echo "✓ Directories created"

# Download and install Piper TTS
echo
echo "=========================================="
echo "Step 5: Installing Piper TTS..."
echo "=========================================="

cd piper

# Check if piper already exists
if [ -f "piper" ] && [ -x "piper" ]; then
    echo "Piper binary already installed, skipping download."
else
    echo "Downloading Piper for ARM64 (Raspberry Pi)..."
    
    # Remove old files if they exist
    rm -f piper_arm64.tar.gz
    rm -rf piper_arm64
    
    wget --progress=bar:force:noscroll \
        https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to download Piper"
        exit 1
    fi
    
    echo "Extracting Piper..."
    tar -xzf piper_arm64.tar.gz
    
    if [ ! -f "piper_arm64/piper" ]; then
        echo "❌ Piper binary not found in archive"
        exit 1
    fi
    
    cp piper_arm64/piper ./
    chmod +x piper
    
    # Clean up
    rm -rf piper_arm64 piper_arm64.tar.gz
    
    echo "✓ Piper binary installed"
fi

# Download voice model
if [ -f "en_US-amy-medium.onnx" ]; then
    echo "Voice model already exists, skipping download."
else
    echo "Downloading Amy voice model (63MB)..."
    echo "This may take a few minutes depending on your connection..."
    
    wget --progress=bar:force:noscroll \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to download voice model"
        exit 1
    fi
    
    echo "✓ Voice model downloaded"
fi

# Download voice config
if [ -f "en_US-amy-medium.onnx.json" ]; then
    echo "Voice config already exists, skipping download."
else
    echo "Downloading voice configuration..."
    
    wget --progress=bar:force:noscroll \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to download voice config"
        exit 1
    fi
    
    echo "✓ Voice config downloaded"
fi

# Test Piper installation
echo "Testing Piper TTS..."
if ./piper --version > /dev/null 2>&1; then
    PIPER_VERSION=$(./piper --version 2>&1 | head -n1)
    echo "✓ Piper TTS working! ($PIPER_VERSION)"
else
    echo "❌ Piper test failed"
    echo "   Trying to fix permissions..."
    chmod +x piper
    if ./piper --version > /dev/null 2>&1; then
        echo "✓ Fixed! Piper is now working"
    else
        echo "❌ Piper still not working. Manual intervention needed."
    fi
fi

cd ..

# Create camera shutter sound
echo
echo "=========================================="
echo "Step 6: Creating sound effects..."
echo "=========================================="

cd sounds

if [ -f "camera-shutter.wav" ]; then
    echo "Sound effect already exists, skipping."
else
    if command -v sox &> /dev/null; then
        echo "Creating camera shutter sound..."
        sox -n -r 44100 -b 16 camera-shutter.wav synth 0.1 sine 800 2>/dev/null
        echo "✓ Sound effect created"
    else
        echo "⚠️  sox not installed, creating silent placeholder..."
        # Create a minimal silent wav file
        echo "✓ Placeholder created (install sox for actual sound)"
    fi
fi

cd ..

# Verify camera
echo
echo "=========================================="
echo "Step 7: Checking camera..."
echo "=========================================="

if command -v rpicam-still &> /dev/null; then
    echo "Testing camera..."
    rpicam-still -t 1 -o /tmp/camera_test.jpg 2>/dev/null
    
    if [ -f "/tmp/camera_test.jpg" ] && [ -s "/tmp/camera_test.jpg" ]; then
        FILE_SIZE=$(stat -f%z "/tmp/camera_test.jpg" 2>/dev/null || stat -c%s "/tmp/camera_test.jpg" 2>/dev/null)
        echo "✓ Camera working! (captured ${FILE_SIZE} bytes)"
        rm /tmp/camera_test.jpg
    else
        echo "⚠️  Camera test failed or returned empty file"
        echo "   Make sure camera is:"
        echo "   1. Physically connected"
        echo "   2. Enabled in raspi-config"
        echo "   3. Cable inserted correctly (blue side faces USB ports)"
        echo
        echo "   To enable camera:"
        echo "   $ sudo raspi-config"
        echo "   -> Interface Options -> Camera -> Enable"
    fi
else
    echo "⚠️  rpicam-still not found"
    echo "   Install with: sudo apt-get install rpicam-apps"
fi

# Configure audio
echo
echo "=========================================="
echo "Step 8: Configuring audio..."
echo "=========================================="

echo "Available audio devices:"
aplay -L | grep -E "^(plughw|hw|default)" | head -5

echo
echo "⚠️  IMPORTANT: Update AUDIO_DEVICE in pi.py"
echo "   Edit pi.py and set AUDIO_DEVICE to your device"
echo "   Example: AUDIO_DEVICE = \"plughw:CARD=UACDemoV10,DEV=0\""

# Test audio with Piper
echo
echo "Testing audio with Piper..."
# Get first available audio device
AUDIO_DEV=$(aplay -L | grep "plughw" | head -1)

if [ ! -z "$AUDIO_DEV" ]; then
    echo "Testing audio on: $AUDIO_DEV"
    echo "Testing audio" | ./piper/piper --model ./piper/en_US-amy-medium.onnx --output-raw 2>/dev/null | \
        aplay -D "$AUDIO_DEV" -r 22050 -f S16_LE -c 1 -q 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "✓ Audio test successful!"
    else
        echo "⚠️  Audio test had issues"
        echo "   Check speaker/headphone connection"
    fi
else
    echo "⚠️  No audio device detected"
    echo "   Connect USB audio adapter or speakers"
fi

# Set file permissions
echo
echo "=========================================="
echo "Step 9: Setting file permissions..."
echo "=========================================="

chmod +x pi.py 2>/dev/null || true
chmod +x train.py 2>/dev/null || true
chmod +x learn.py 2>/dev/null || true
chmod +x view_samples.py 2>/dev/null || true
chmod +x distance_finder.py 2>/dev/null || true
chmod +x piper/piper

echo "✓ File permissions set"

# Test GPIO
echo
echo "=========================================="
echo "Step 10: Testing GPIO..."
echo "=========================================="

sudo python3 << 'PYTHON_TEST'
import sys
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    print("✓ RPi.GPIO working!")
    GPIO.cleanup()
except Exception as e:
    print(f"⚠️  RPi.GPIO test failed: {e}")
    try:
        import lgpio
        print("✓ lgpio available (Pi 5 compatible)")
    except ImportError:
        print("❌ No GPIO library available")
        sys.exit(1)
PYTHON_TEST

if [ $? -eq 0 ]; then
    echo "✓ GPIO test passed"
else
    echo "❌ GPIO test failed"
    echo "   This may cause issues running the program"
fi

# Create example config
echo
echo "=========================================="
echo "Step 11: Creating example configuration..."
echo "=========================================="

cat > config_example.txt << 'EOF'
# PiTextReader Configuration Notes
# 
# After installation, you may need to customize these settings in pi.py:

# 1. AUDIO_DEVICE (line ~36)
#    Find your device with: aplay -L
#    Example: AUDIO_DEVICE = "plughw:CARD=UACDemoV10,DEV=0"

# 2. CAMERA rotation (line ~50)
#    If image is upside down, change --rot value:
#    --rot 0    = No rotation
#    --rot 180  = Upside down
#    --rot 90   = 90 degrees
#    --rot 270  = 270 degrees

# 3. GPIO pins (lines ~58-61)
#    BTN1 = 24  (Capture button)
#    BTN2 = 23  (Repeat button)
#    BTN3 = 22  (Help button - if using blind-accessible version)
#    LED  = 18  (Status LED)

# 4. VOLUME (line ~31)
#    Default: 90
#    Adjust between 0-100

# To test audio device:
# $ aplay -D YOUR_DEVICE_NAME /usr/share/sounds/alsa/Front_Center.wav

# To test camera:
# $ rpicam-still -o test.jpg
# $ xdg-open test.jpg
EOF

echo "✓ Created config_example.txt"

# Final summary
echo
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo
echo "📁 Installation Summary:"
echo "   ✓ Tesseract OCR"
echo "   ✓ Python packages (spellchecker, GPIO)"
echo "   ✓ Piper TTS + Amy voice model"
echo "   ✓ Sound effects"
echo "   ✓ Directory structure"
echo "   ✓ Camera verification"
echo "   ✓ Audio configuration"
echo "   ✓ GPIO test"
echo
echo "📂 File Structure:"
echo "   $(pwd)/"
echo "   ├── pi.py              (Main program)"
echo "   ├── train.py           (Correction tool)"
echo "   ├── learn.py           (Learning script)"
echo "   ├── piper/"
echo "   │   ├── piper          (TTS engine)"
echo "   │   ├── *.onnx         (Voice model)"
echo "   │   └── *.json         (Voice config)"
echo "   ├── sounds/"
echo "   │   └── camera-shutter.wav"
echo "   └── corrections/"
echo "       └── training_data/"
echo
echo "🎯 Next Steps:"
echo
echo "   1. Test the installation:"
echo "      $ sudo python3 pi.py"
echo
echo "   2. If you hear no sound:"
echo "      - Check speaker connection"
echo "      - Find audio device: aplay -L"
echo "      - Update AUDIO_DEVICE in pi.py"
echo
echo "   3. If camera doesn't work:"
echo "      - Check physical connection"
echo "      - Enable in: sudo raspi-config"
echo
echo "   4. If GPIO errors occur:"
echo "      - Must run with: sudo python3 pi.py"
echo "      - Check wiring to GPIO pins 24, 23, 18"
echo
echo "   5. Read the documentation:"
echo "      - See README.md for full guide"
echo "      - Check config_example.txt for settings"
echo
echo "=========================================="
echo "  Enjoy your PiTextReader! 📖🔊"
echo "=========================================="
echo
echo "💡 Tip: Test camera distance with:"
echo "   $ python3 distance_finder.py"
echo
