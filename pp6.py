#!/usr/bin/python3
#
# PiTextReader - Smart Tesseract with Correction Learning + Repeat + Spellcheck
# Tesseract does OCR, AI learns to fix its mistakes
# Added: Repeat button (GPIO 23) and spellcheck
#
import RPi.GPIO as GPIO
import os, sys
import logging
import subprocess
import threading
import time
import re
import json
from collections import defaultdict
import difflib

# Try to import spellchecker
try:
    from spellchecker import SpellChecker
    SPELLCHECK_AVAILABLE = True
except ImportError:
    SPELLCHECK_AVAILABLE = False
    print("Spellchecker not installed. Install with: pip3 install --break-system-packages pyspellchecker")

##### USER VARIABLES
DEBUG   = 1
SPEED   = 1.0
VOLUME  = 90

# === TRAINING MODE SWITCHES ===
TRAINING_MODE = True       # True = Collect Tesseract mistakes
LEARNING_ENABLED = True     # True = Apply learned corrections
USE_SPELLCHECK = True       # True = Apply spellcheck to results

# PIPER SETTINGS
PIPER_DIR   = "/home/admin/pi/piper/"
PIPER_PATH  = PIPER_DIR + "piper"
MODEL_PATH  = PIPER_DIR + "en_US-amy-medium.onnx"

# USB AUDIO DEVICE
AUDIO_DEVICE = "plughw:CARD=UACDemoV10,DEV=0"

# OTHER SETTINGS
SOUNDS  = "/home/admin/pi/sounds/"
CAMERA  = "rpicam-still -cfx 128:128 --awb auto --rot 180 -t 500 -o /tmp/image.jpg"

# CORRECTION LEARNING PATHS
LEARNING_DIR = "/home/admin/pi/corrections/"
TRAINING_DATA_DIR = os.path.join(LEARNING_DIR, "training_data")
CORRECTIONS_FILE = os.path.join(LEARNING_DIR, "learned_corrections.json")

# GPIO BUTTONS
BTN1    = 24    # Main capture button
BTN2    = 23    # Repeat button (NEW!)
LED     = 18    # LED indicator

### GLOBALS
current_tts = None
last_text_read = ""  # Store last text for repeat
spell = None
learned_corrections = {
    "word_replacements": {},      # "qq" -> "99"
    "pattern_fixes": [],          # regex patterns
    "context_corrections": {}     # "after $" context
}

############ SPELLCHECK FUNCTIONS ################

def initialize_spellcheck():
    """Initialize spellchecker"""
    global spell
    
    if not SPELLCHECK_AVAILABLE:
        logger.warning("Spellchecker not available")
        return False
    
    try:
        logger.info("Initializing spellchecker...")
        spell = SpellChecker()
        
        # Add common OCR-friendly words that might be flagged
        spell.word_frequency.load_words(['ocr', 'tesseract', 'qr', 'barcode'])
        
        logger.info("Spellchecker initialized")
        return True
    except Exception as e:
        logger.error(f"Spellcheck init failed: {e}")
        return False

def apply_spellcheck(text):
    """Apply spellcheck to text, being careful with numbers and special terms"""
    
    if not USE_SPELLCHECK or spell is None:
        return text
    
    try:
        original = text
        words = text.split()
        corrected_words = []
        
        for word in words:
            # Skip if it's a number, price, or has special chars
            if re.match(r'^[\d\$\.\,\%\@\#]+$', word):
                corrected_words.append(word)
                continue
            
            # Skip short words (likely abbreviations)
            if len(word) <= 2:
                corrected_words.append(word)
                continue
            
            # Remove punctuation for checking
            clean_word = re.sub(r'[^\w]', '', word)
            
            if not clean_word:
                corrected_words.append(word)
                continue
            
            # Check if misspelled
            if clean_word.lower() in spell:
                # Word is correct
                corrected_words.append(word)
            else:
                # Get correction
                correction = spell.correction(clean_word)
                
                if correction and correction != clean_word.lower():
                    # Apply correction, preserving original case and punctuation
                    if clean_word.isupper():
                        fixed = correction.upper()
                    elif clean_word[0].isupper():
                        fixed = correction.capitalize()
                    else:
                        fixed = correction
                    
                    # Restore punctuation
                    fixed_word = word.replace(clean_word, fixed)
                    corrected_words.append(fixed_word)
                    logger.info(f"Spellcheck: '{word}' -> '{fixed_word}'")
                else:
                    # No good correction, keep original
                    corrected_words.append(word)
        
        result = ' '.join(corrected_words)
        
        if result != original:
            logger.info(f"Spellcheck applied: '{original}' -> '{result}'")
        
        return result
        
    except Exception as e:
        logger.error(f"Spellcheck error: {e}")
        return text

############ CORRECTION LEARNING ################

def load_learned_corrections():
    """Load previously learned corrections"""
    global learned_corrections
    
    try:
        if os.path.exists(CORRECTIONS_FILE):
            with open(CORRECTIONS_FILE, 'r') as f:
                learned_corrections = json.load(f)
            logger.info(f"Loaded {len(learned_corrections['word_replacements'])} learned corrections")
        else:
            logger.info("No learned corrections yet")
    except Exception as e:
        logger.error(f"Failed to load corrections: {e}")

def save_learned_corrections():
    """Save learned corrections"""
    try:
        os.makedirs(LEARNING_DIR, exist_ok=True)
        with open(CORRECTIONS_FILE, 'w') as f:
            json.dump(learned_corrections, f, indent=2)
        logger.info("Saved learned corrections")
    except Exception as e:
        logger.error(f"Failed to save corrections: {e}")

def learn_from_corrections():
    """Analyze all training samples to learn common mistakes"""
    global learned_corrections
    
    logger.info("=" * 60)
    logger.info("LEARNING FROM CORRECTIONS")
    logger.info("=" * 60)
    
    try:
        if not os.path.exists(TRAINING_DATA_DIR):
            logger.error("No training data found")
            return False
        
        samples = []
        for filename in os.listdir(TRAINING_DATA_DIR):
            if filename.endswith('.json'):
                with open(os.path.join(TRAINING_DATA_DIR, filename), 'r') as f:
                    samples.append(json.load(f))
        
        if len(samples) < 5:
            logger.error(f"Need at least 5 samples, have {len(samples)}")
            speak(f"Need more samples. Have {len(samples)}, need 5")
            return False
        
        logger.info(f"Analyzing {len(samples)} samples...")
        speak(f"Learning from {len(samples)} samples")
        
        # Track word-level changes
        word_changes = defaultdict(lambda: defaultdict(int))
        
        for sample in samples:
            ocr_text = sample['ocr_text']
            correct_text = sample['corrected_text']
            
            if ocr_text == correct_text:
                continue
            
            logger.info(f"Learning from: '{ocr_text}' -> '{correct_text}'")
            
            # Word-level analysis
            ocr_words = ocr_text.split()
            correct_words = correct_text.split()
            
            # Use difflib to align words
            matcher = difflib.SequenceMatcher(None, ocr_words, correct_words)
            
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'replace':
                    for i, j in zip(range(i1, i2), range(j1, j2)):
                        if i < len(ocr_words) and j < len(correct_words):
                            wrong = ocr_words[i]
                            right = correct_words[j]
                            word_changes[wrong][right] += 1
                            logger.info(f"  Learned: '{wrong}' -> '{right}'")
        
        # Store corrections that appear multiple times
        for wrong, rights in word_changes.items():
            most_common_fix = max(rights.items(), key=lambda x: x[1])[0]
            if rights[most_common_fix] >= 2:
                learned_corrections['word_replacements'][wrong] = most_common_fix
        
        # Learn common character patterns
        char_patterns = []
        
        if any('qq' in s['ocr_text'] and '99' in s['corrected_text'] for s in samples):
            char_patterns.append({
                'pattern': r'(\d+)\.qq\b',
                'replacement': r'\1.99',
                'description': 'qq at end of price -> 99'
            })
        
        if any('$O' in s['ocr_text'] or '$o' in s['ocr_text'] for s in samples):
            char_patterns.append({
                'pattern': r'\$[Oo]',
                'replacement': '$0',
                'description': '$O or $o -> $0'
            })
        
        if any(re.search(r'\dl', s['ocr_text']) and re.search(r'\d1', s['corrected_text']) for s in samples):
            char_patterns.append({
                'pattern': r'(\d)[lI](\d)',
                'replacement': r'\g<1>1\2',
                'description': 'l or I between numbers -> 1'
            })
        
        learned_corrections['pattern_fixes'] = char_patterns
        
        save_learned_corrections()
        
        logger.info("=" * 60)
        logger.info("LEARNING COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Word replacements: {len(learned_corrections['word_replacements'])}")
        logger.info(f"Pattern fixes: {len(learned_corrections['pattern_fixes'])}")
        
        for wrong, right in learned_corrections['word_replacements'].items():
            logger.info(f"  '{wrong}' -> '{right}'")
        
        for pattern in learned_corrections['pattern_fixes']:
            logger.info(f"  Pattern: {pattern['description']}")
        
        speak("Learning complete")
        return True
        
    except Exception as e:
        logger.error(f"Learning failed: {e}")
        logger.exception("Full error:")
        return False

def apply_learned_corrections(text):
    """Apply learned corrections to Tesseract output"""
    
    if not LEARNING_ENABLED:
        return text
    
    original = text
    
    # Apply word replacements
    for wrong, right in learned_corrections['word_replacements'].items():
        text = re.sub(r'\b' + re.escape(wrong) + r'\b', right, text)
    
    # Apply pattern fixes
    for pattern_fix in learned_corrections['pattern_fixes']:
        text = re.sub(pattern_fix['pattern'], pattern_fix['replacement'], text)
    
    if text != original:
        logger.info(f"Applied corrections: '{original}' -> '{text}'")
    
    return text

def save_training_sample(image_path, ocr_text):
    """Save training sample"""
    try:
        timestamp = int(time.time())
        sample_id = f"sample_{timestamp}"
        
        os.makedirs(TRAINING_DATA_DIR, exist_ok=True)
        
        image_dest = os.path.join(TRAINING_DATA_DIR, f"{sample_id}.jpg")
        subprocess.run(["cp", image_path, image_dest], check=True)
        
        metadata = {
            "id": sample_id,
            "timestamp": timestamp,
            "ocr_text": ocr_text,
            "corrected_text": ocr_text,
            "image_path": image_dest
        }
        
        metadata_path = os.path.join(TRAINING_DATA_DIR, f"{sample_id}.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Saved training sample: {sample_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save sample: {e}")
        return False

############ THREAD CLASS ################
class RaspberryThread(threading.Thread):
    def __init__(self, function):
        self.running = False
        self.function = function
        super(RaspberryThread, self).__init__()

    def start(self):
        self.running = True
        super(RaspberryThread, self).start()

    def run(self):
        while self.running:
            self.function()

    def stop(self):
        self.running = False

###########################################
# HARDWARE FUNCTIONS
###########################################

def led(val):
    logger.info('led('+str(val)+')')
    if val:
        GPIO.output(LED, GPIO.HIGH)
    else:
        GPIO.output(LED, GPIO.LOW)

def sound(val):
    logger.info('sound()')
    cmd = f"/usr/bin/aplay -D {AUDIO_DEVICE} -q {val}"
    os.system(cmd)

def speak(val, store_for_repeat=False):
    """Speak text using Piper TTS"""
    global last_text_read
    
    logger.info(f'speak(): {val[:50]}')
    
    # Only store if explicitly told to (from OCR results)
    if store_for_repeat:
        last_text_read = val
        logger.info(f"Stored for repeat: {val[:50]}")
    
    try:
        piper_proc = subprocess.Popen(
            [PIPER_PATH, "--model", MODEL_PATH, "--output-raw"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        aplay_proc = subprocess.Popen(
            ["aplay", "-D", AUDIO_DEVICE, "-f", "S16_LE", "-r", "22050", "-c", "1"],
            stdin=piper_proc.stdout,
            stderr=subprocess.PIPE
        )

        piper_proc.stdout.close()
        piper_proc.stdin.write((val + "\n").encode("utf-8"))
        piper_proc.stdin.close()

        aplay_proc.wait()
        piper_proc.wait()

    except Exception as e:
        logger.error(f"Error in speak: {e}")

def volume(val):
    logger.info('volume('+str(val)+')')
    cmd = f"sudo amixer -q sset PCM,0 {int(val)}%"
    os.system(cmd)

def cleanText():
    """Clean and process OCR text with all corrections"""
    logger.info('cleanText()')
    try:
        with open('/tmp/text.txt', 'r') as f:
            text = f.read()

        logger.info(f"Original Tesseract output: {text[:200]}")
        
        # Basic cleanup
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\$\s+', '$', text)
        
        # Step 1: Apply learned corrections
        text = apply_learned_corrections(text)
        logger.info(f"After learned corrections: {text[:200]}")
        
        # Step 2: Apply spellcheck
        text = apply_spellcheck(text)
        logger.info(f"After spellcheck: {text[:200]}")
        
        # Step 3: Standard cleanup (from your original code)
        text = re.sub(r'\$[Oo]', '$0', text)
        text = re.sub(r'\$[lI]', '$1', text)
        text = re.sub(r'(\d)[Oo](\d)', r'\1 0 \2', text)
        text = re.sub(r'(\d)[lI](\d)', r'\1 1 \2', text)
        text = re.sub(r'[Oo](\d)', r'0\1', text)
        text = re.sub(r'(\d)[Oo]', r'\1 0', text)
        text = re.sub(r'(\d)\s*:\s*(\d)', r'\1:\2', text)
        text = re.sub(r'(\d)\s*/\s*(\d)', r'\1/\2', text)
        text = re.sub(r'\$(\d+\.?\d*)', r'\1 dollars ', text)
        
        text = text.replace('%', ' percent ')
        text = text.replace('&', ' and ')
        text = text.replace('@', ' at ')
        text = text.replace('#', ' number ')
        text = text.replace('+', ' plus ')
        text = text.replace('=', ' equals ')
        text = text.replace('*', ' times ')
        text = text.replace('°', ' degrees ')
        
        text = re.sub(r'\s+', ' ', text).strip()
        
        logger.info(f"Final cleaned text: {text[:200]}")
        
        with open('/tmp/text.txt', 'w') as f:
            f.write(text)

    except Exception as e:
        logger.error(f"Error in cleanText: {e}")

def playTTS():
    """Play text-to-speech of the processed text"""
    logger.info('playTTS()')
    global current_tts, last_text_read
    
    try:
        with open('/tmp/text.txt', 'r') as f:
            text_content = f.read().strip()

        if not text_content:
            speak("No text detected")
            return

        # Store this text for repeat button BEFORE speaking it
        last_text_read = text_content
        logger.info(f"Stored for repeat: {text_content[:100]}")

        piper_cmd = [PIPER_PATH, '--model', MODEL_PATH, '--output-raw']
        aplay_cmd = ["aplay", "-D", AUDIO_DEVICE, "-f", "S16_LE", "-r", "22050", "-c", "1"]

        current_tts = subprocess.Popen(aplay_cmd, stdin=subprocess.PIPE)
        piper_proc = subprocess.Popen(piper_cmd, stdin=subprocess.PIPE, 
                                      stdout=current_tts.stdin, stderr=subprocess.PIPE)

        piper_proc.stdin.write((text_content + "\n").encode("utf-8"))
        piper_proc.stdin.close()

        piper_proc.wait()
        current_tts.stdin.close()
        current_tts.wait()

    except Exception as e:
        logger.error(f"Error in playTTS: {e}")

def stopTTS():
    """Stop current TTS playback"""
    global current_tts
    if GPIO.input(BTN1) == GPIO.LOW:
        logger.info('stopTTS()')
        if current_tts and current_tts.poll() is None:
            current_tts.kill()
        time.sleep(0.5)

def repeatLastText():
    """Repeat the last text that was read (NEW!)"""
    global last_text_read
    
    logger.info('repeatLastText()')
    
    if not last_text_read:
        speak("No text to repeat")
        return
    
    logger.info(f"Repeating: {last_text_read[:50]}")
    speak(last_text_read)

def getData():
    """Capture image and perform OCR"""
    logger.info('getData()')
    led(0)
    
    sound(SOUNDS + "camera-shutter.wav")
    os.system(CAMERA)
    
    speak("taking picture. hold still for 5 seconds")
    
    # Use Tesseract
    os.system("/usr/bin/tesseract /tmp/image.jpg /tmp/text")
    
    # Save training sample if in training mode
    if TRAINING_MODE:
        try:
            with open('/tmp/text.txt', 'r') as f:
                ocr_text = f.read()
            save_training_sample('/tmp/image.jpg', ocr_text)
            speak("Training sample saved")
        except:
            pass
    
    # Clean text (applies learned corrections + spellcheck)
    cleanText()
    playTTS()

###########################################
# MAIN
###########################################
try:
    global rt
    
    # Setup Logging
    logger = logging.getLogger()
    handler = logging.FileHandler('debug.log')
    
    if DEBUG:
        logger.setLevel(logging.INFO)
        handler.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.ERROR)
        handler.setLevel(logging.ERROR)
    
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logger.addHandler(console)
    
    logger.info('=' * 60)
    logger.info('PiTextReader - Smart Tesseract + Repeat + Spellcheck')
    logger.info('=' * 60)
    logger.info(f'TRAINING_MODE: {TRAINING_MODE}')
    logger.info(f'LEARNING_ENABLED: {LEARNING_ENABLED}')
    logger.info(f'USE_SPELLCHECK: {USE_SPELLCHECK}')
    logger.info('=' * 60)
    
    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(BTN1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN2, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Repeat button
    GPIO.setup(LED, GPIO.OUT)
    
    # Thread
    rt = RaspberryThread(function=stopTTS)
    current_tts = None
    last_text_read = ""
    
    volume(VOLUME)
    
    # Load learned corrections
    os.makedirs(LEARNING_DIR, exist_ok=True)
    load_learned_corrections()
    
    # Initialize spellcheck
    if USE_SPELLCHECK:
        if initialize_spellcheck():
            logger.info("Spellcheck ready")
        else:
            logger.warning("Spellcheck disabled")
            USE_SPELLCHECK = False
    
    # Status announcement
    num_corrections = len(learned_corrections['word_replacements'])
    status_parts = []
    
    if num_corrections > 0:
        status_parts.append(f"{num_corrections} learned corrections")
    
    if USE_SPELLCHECK:
        status_parts.append("spellcheck enabled")
    
    if status_parts:
        speak(f"Ready with {' and '.join(status_parts)}")
    else:
        speak("Ready")
    
    led(1)
    
    logger.info("Buttons:")
    logger.info("  GPIO 24 (BTN1) = Capture image")
    logger.info("  GPIO 23 (BTN2) = Repeat last text")
    
    # Main loop
    while True:
        # Button 1: Capture and read
        if GPIO.input(BTN1) == GPIO.LOW:
            getData()
            rt.stop()
            rt = RaspberryThread(function=stopTTS)
            led(1)
            time.sleep(0.5)
            
            if TRAINING_MODE:
                speak("Sample saved. Ready for next")
            else:
                speak("OK, ready")
        
        # Button 2: Repeat last text (NEW!)
        elif GPIO.input(BTN2) == GPIO.LOW:
            repeatLastText()
            time.sleep(0.5)  # Debounce
        
        time.sleep(0.2)

except KeyboardInterrupt:
    logger.info("exiting")

GPIO.cleanup()
sys.exit(0)