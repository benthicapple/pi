#!/usr/bin/python3
"""
learn.py - Learn from corrected training samples
Compatible with pi.py and train.py
Analyzes corrections and creates learned_corrections.json
"""

import json
import os
import sys
import re
from collections import defaultdict
import difflib

# Same paths as pi.py
LEARNING_DIR = "/home/admin/pi/corrections/"
TRAINING_DATA_DIR = os.path.join(LEARNING_DIR, "training_data")
CORRECTIONS_FILE = os.path.join(LEARNING_DIR, "learned_corrections.json")

def load_training_samples():
    """Load all corrected samples"""
    print("Loading training samples...")
    
    if not os.path.exists(TRAINING_DATA_DIR):
        print(f"Error: Training directory not found: {TRAINING_DATA_DIR}")
        print("Collect samples first by running: sudo python3 pi.py")
        return []
    
    samples = []
    for filename in os.listdir(TRAINING_DATA_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(TRAINING_DATA_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    sample = json.load(f)
                    samples.append(sample)
            except Exception as e:
                print(f"Warning: Could not load {filename}: {e}")
    
    print(f"Loaded {len(samples)} samples")
    return samples

def analyze_corrections(samples):
    """Analyze samples to find correction patterns"""
    print("\nAnalyzing corrections...")
    
    # Track word-level changes
    word_changes = defaultdict(lambda: defaultdict(int))
    total_corrections = 0
    
    for sample in samples:
        ocr_text = sample.get('ocr_text', '')
        correct_text = sample.get('corrected_text', '')
        
        # Skip if no correction was made
        if ocr_text == correct_text:
            continue
        
        total_corrections += 1
        print(f"\nAnalyzing: '{ocr_text[:60]}...' -> '{correct_text[:60]}...'")
        
        # Split into words
        ocr_words = ocr_text.split()
        correct_words = correct_text.split()
        
        # Use difflib to align words
        matcher = difflib.SequenceMatcher(None, ocr_words, correct_words)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                # Words that were replaced
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    if i < len(ocr_words) and j < len(correct_words):
                        wrong = ocr_words[i]
                        right = correct_words[j]
                        word_changes[wrong][right] += 1
                        print(f"  Found: '{wrong}' -> '{right}'")
    
    print(f"\nTotal corrections analyzed: {total_corrections}")
    return word_changes

def create_learned_corrections(word_changes, samples):
    """Create learned corrections structure"""
    print("\nCreating learned corrections...")
    
    learned = {
        "word_replacements": {},
        "pattern_fixes": [],
        "context_corrections": {}
    }
    
    # Store word replacements that appear at least 2 times
    print("\nWord replacements:")
    for wrong, rights in word_changes.items():
        most_common_fix = max(rights.items(), key=lambda x: x[1])[0]
        count = rights[most_common_fix]
        
        if count >= 2:
            learned['word_replacements'][wrong] = most_common_fix
            print(f"  '{wrong}' -> '{most_common_fix}' (appeared {count} times)")
    
    # Detect common character patterns
    print("\nPattern fixes:")
    
    # Pattern 1: "qq" at end of prices -> "99"
    if any('qq' in s.get('ocr_text', '') and '99' in s.get('corrected_text', '') for s in samples):
        pattern = {
            'pattern': r'(\d+)\.qq\b',
            'replacement': r'\1.99',
            'description': 'qq at end of price -> 99'
        }
        learned['pattern_fixes'].append(pattern)
        print(f"  {pattern['description']}")
    
    # Pattern 2: "$O" or "$o" -> "$0"
    if any(('$O' in s.get('ocr_text', '') or '$o' in s.get('ocr_text', '')) for s in samples):
        pattern = {
            'pattern': r'\$[Oo]',
            'replacement': '$0',
            'description': '$O or $o -> $0'
        }
        learned['pattern_fixes'].append(pattern)
        print(f"  {pattern['description']}")
    
    # Pattern 3: "l" or "I" between numbers -> "1"
    if any(re.search(r'\d[lI]\d', s.get('ocr_text', '')) and re.search(r'\d1\d', s.get('corrected_text', '')) for s in samples):
        pattern = {
            'pattern': r'(\d)[lI](\d)',
            'replacement': r'\g<1>1\2',
            'description': 'l or I between numbers -> 1'
        }
        learned['pattern_fixes'].append(pattern)
        print(f"  {pattern['description']}")
    
    # Pattern 4: "O" in numbers -> "0"
    if any(re.search(r'\dO\d', s.get('ocr_text', '')) and re.search(r'\d0\d', s.get('corrected_text', '')) for s in samples):
        pattern = {
            'pattern': r'(\d)[Oo](\d)',
            'replacement': r'\g<1>0\2',
            'description': 'O in numbers -> 0'
        }
        learned['pattern_fixes'].append(pattern)
        print(f"  {pattern['description']}")
    
    return learned

def save_corrections(learned):
    """Save learned corrections to file"""
    print(f"\nSaving corrections to: {CORRECTIONS_FILE}")
    
    try:
        os.makedirs(LEARNING_DIR, exist_ok=True)
        
        with open(CORRECTIONS_FILE, 'w') as f:
            json.dump(learned, f, indent=2)
        
        print("✓ Saved successfully!")
        return True
    except Exception as e:
        print(f"✗ Failed to save: {e}")
        return False

def main():
    print("=" * 70)
    print("LEARNING FROM CORRECTIONS")
    print("=" * 70)
    
    # Step 1: Load samples
    samples = load_training_samples()
    
    if len(samples) == 0:
        print("\nNo samples found!")
        print("Steps:")
        print("1. Run: sudo python3 pi.py (with TRAINING_MODE = True)")
        print("2. Capture 5+ images")
        print("3. Run: python3 train.py")
        print("4. Correct the samples")
        print("5. Run: python3 learn.py")
        return
    
    if len(samples) < 5:
        print(f"\n⚠ Warning: Only {len(samples)} samples found")
        print("Recommend collecting at least 5 samples for better learning")
        choice = input("Continue anyway? [y/n] ")
        if choice.lower() != 'y':
            return
    
    # Step 2: Analyze corrections
    word_changes = analyze_corrections(samples)
    
    if not word_changes:
        print("\n⚠ No corrections found!")
        print("All samples have ocr_text == corrected_text")
        print("\nThis means either:")
        print("1. Tesseract was 100% accurate (unlikely)")
        print("2. You haven't corrected the samples yet")
        print("\nRun: python3 train.py to correct samples")
        return
    
    # Step 3: Create learned corrections
    learned = create_learned_corrections(word_changes, samples)
    
    # Step 4: Save
    if save_corrections(learned):
        print("\n" + "=" * 70)
        print("LEARNING COMPLETE!")
        print("=" * 70)
        print(f"Word replacements: {len(learned['word_replacements'])}")
        print(f"Pattern fixes: {len(learned['pattern_fixes'])}")
        print("\nNext steps:")
        print("1. Edit pi.py: Change TRAINING_MODE = False")
        print("2. Run: sudo python3 pi.py")
        print("3. Test with new images - corrections will be applied automatically!")
        print("=" * 70)
    else:
        print("\n✗ Learning failed - check errors above")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)