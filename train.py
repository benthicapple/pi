#!/usr/bin/python3
"""Interactive tool to correct training samples"""

import json
import os
import sys

TRAINING_DIR = "/home/admin/pi/ai_models/training_data/"

def load_samples():
    """Load all training samples"""
    samples = []
    for filename in os.listdir(TRAINING_DIR):
        if filename.endswith('.json'):
            path = os.path.join(TRAINING_DIR, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                data['json_path'] = path
                samples.append(data)
    return sorted(samples, key=lambda x: x['timestamp'])

def save_sample(sample):
    """Save corrected sample back to JSON file"""
    with open(sample['json_path'], 'w') as f:
        json.dump({
            'id': sample['id'],
            'timestamp': sample['timestamp'],
            'ocr_text': sample['ocr_text'],
            'corrected_text': sample['corrected_text'],
            'image_path': sample['image_path']
        }, f, indent=2)

def main():
    """Main correction workflow"""
    
    # Check if directory exists
    if not os.path.exists(TRAINING_DIR):
        print(f"Error: Training directory not found: {TRAINING_DIR}")
        print("Make sure you've collected training samples first!")
        return
    
    # Load samples
    samples = load_samples()
    
    if not samples:
        print("No training samples found!")
        print(f"Directory checked: {TRAINING_DIR}")
        print("\nCollect samples first by running:")
        print("  sudo python3 pitextreader.py")
        print("  (with TRAINING_MODE = True)")
        return
    
    print("=" * 60)
    print("TRAINING SAMPLE CORRECTION TOOL")
    print("=" * 60)
    print(f"Found {len(samples)} samples\n")
    print("Instructions:")
    print("  - Press [Enter] to keep the AI's result")
    print("  - Type the correct text to fix errors")
    print("  - Type 's' to skip")
    print("  - Type 'q' to quit")
    print("=" * 60)
    
    corrected_count = 0
    
    for i, sample in enumerate(samples, 1):
        print(f"\n{'=' * 60}")
        print(f"Sample {i}/{len(samples)}")
        print(f"{'=' * 60}")
        print(f"ID: {sample['id']}")
        print(f"Image: {sample['image_path']}")
        print("-" * 60)
        print(f"AI detected:")
        print(f"  {sample['ocr_text']}")
        print("-" * 60)
        
        current_correction = sample.get('corrected_text', sample['ocr_text'])
        
        # Show if already corrected
        if current_correction != sample['ocr_text']:
            print(f"Current correction:")
            print(f"  {current_correction}")
            print("-" * 60)
            print("(This sample was already corrected)")
        
        print("\nWhat should this say?")
        print("  [Enter] = Keep current text")
        print("  [Type text] = Enter correct text")
        print("  [s] = Skip to next")
        print("  [q] = Quit")
        
        choice = input("\n> ").strip()
        
        if choice.lower() == 'q':
            print("\n" + "=" * 60)
            print(f"Exiting... Corrected {corrected_count} samples")
            print("=" * 60)
            break
            
        elif choice.lower() == 's':
            print("⊳ Skipped")
            continue
            
        elif choice == '':
            # Keep current
            sample['corrected_text'] = current_correction
            save_sample(sample)
            print("✓ Kept current text")
            
        else:
            # User entered correction
            sample['corrected_text'] = choice
            save_sample(sample)
            print(f"✓ Saved correction: {choice}")
            corrected_count += 1
    
    print("\n" + "=" * 60)
    print("CORRECTION COMPLETE!")
    print("=" * 60)
    print(f"Corrected: {corrected_count} samples")
    print(f"Total samples: {len(samples)}")
    print("\nNext steps:")
    print("1. Run 'python3 view_samples.py' to review")
    print("2. Edit pitextreader.py: FINE_TUNE_MODEL = True")
    print("3. Run 'sudo python3 pitextreader.py' to train")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)