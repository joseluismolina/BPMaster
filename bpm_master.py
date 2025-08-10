#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
BPM Master - Cross-Platform Audio Tempo Adjustment Script
==========================================================

This script recursively finds audio files in a given directory, detects their
BPM (Beats Per Minute), and adjusts their tempo to a target BPM.

It is fully cross-platform (Windows, macOS, Linux) and handles all processing
using Python libraries.

**Installation:**

This project uses a virtual environment to manage dependencies.

1.  **Create and activate a virtual environment:**
    ```bash
    # Create the environment
    python3 -m venv venv

    # Activate it (on Linux/macOS)
    source venv/bin/activate
    # On Windows (Command Prompt)
    # .\venv\Scripts\activate.bat
    ```

2.  **Install all dependencies via pip:**
    ```bash
    pip install -r requirements.txt
    ```
    This will install `essentia`, `tqdm`, and `pyrubberband`.

**Usage:**

```bash
python bpm_master.py /path/to/your/audio --target-bpm 120
```
"""

import os
import sys
import argparse
import logging
from pathlib import Path

try:
    from tqdm import tqdm
    import essentia
    import essentia.standard as es
    import pyrubberband as pyrb

    # Deactivate Essentia's INFO logs to avoid spamming the console
    essentia.log.info_active = False

except ImportError as e:
    print(f"Error: A required library is not installed. {e}", file=sys.stderr)
    print("Please install dependencies by running: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


# --- Constants ---
SUPPORTED_EXTENSIONS = ['.mp3', '.wav', '.flac']
LOG_FILE = 'errors.log'

# --- Logger Configuration ---
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOG_FILE,
    filemode='w'
)

def detect_bpm(file_path: str) -> tuple[float | None, float | None]:
    """
    Detects the BPM and confidence of an audio file using Essentia.
    """
    try:
        loader = es.MonoLoader(filename=file_path)
        audio = loader()
        rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
        bpm, _, confidence, _, _ = rhythm_extractor(audio)

        if bpm is None or bpm == 0:
            logging.error(f"BPM detection failed for {file_path}. Result was 0 or None.")
            return None, None
            
        return bpm, confidence
    except Exception as e:
        logging.error(f"Essentia failed to detect BPM in {file_path}: {e}")
        return None, None

def stretch_audio(input_file: str, output_file: str, factor: float):
    """
    Stretches audio tempo using pyrubberband and Essentia for I/O.

    Args:
        input_file: Path to the source audio file.
        output_file: Path to save the modified audio file.
        factor: The tempo stretch factor (e.g., 1.1 for +10%).
    
    Raises:
        Exception: If audio loading, processing, or writing fails.
    """
    # Use Essentia to load audio to a numpy array and get sample rate
    audio, sr_float, _, _, _, _ = es.AudioLoader(filename=input_file)()
    
    # The sample rate must be an integer for pyrubberband and AudioWriter
    sr = int(sr_float)
    
    # Use pyrubberband to time-stretch the audio data
    # Note: pyrubberband expects mono or stereo, Essentia's AudioLoader provides stereo if available
    stretched_audio = pyrb.time_stretch(audio, sr, factor)
    
    # Use Essentia to write the stretched numpy array back to a file
    output_format = Path(output_file).suffix[1:].lower()
    es.AudioWriter(filename=output_file, format=output_format, sampleRate=sr)(stretched_audio)


def process_folder(folder: str, target_bpm: float, out_dir: str, analyze_only: bool):
    """
    Main function to process a folder of audio files.
    """
    print(f"Searching for audio files in: {folder}")
    
    input_path = Path(folder).expanduser()
    output_path = Path(out_dir).expanduser()
    
    audio_files = [
        str(p) for p in input_path.rglob('*') 
        if p.suffix.lower() in SUPPORTED_EXTENSIONS and p.is_file()
    ]

    if not audio_files:
        print("No audio files found. Exiting.")
        return

    print(f"Found {len(audio_files)} audio files. Processing...")
    
    if not analyze_only:
        output_path.mkdir(parents=True, exist_ok=True)

    processed_count = 0
    modified_count = 0
    failed_count = 0

    progress_bar = tqdm(audio_files, desc="Processing files", unit="file")

    for file_path in progress_bar:
        processed_count += 1
        progress_bar.set_postfix_str(Path(file_path).name)

        detected_bpm, confidence = detect_bpm(file_path)

        if detected_bpm is None:
            print(f"-> Failed to detect BPM for: {Path(file_path).name}")
            failed_count += 1
            continue

        if analyze_only:
            print(f"  - File: {Path(file_path).name} | Detected BPM: {detected_bpm:.2f} (Confidence: {confidence:.2f})")
            continue

        if detected_bpm > 0:
            factor = target_bpm / detected_bpm
            
            relative_path = Path(file_path).relative_to(input_path)
            output_file_path = output_path / relative_path
            output_file_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                stretch_audio(file_path, str(output_file_path), factor)
                modified_count += 1
            except Exception as e:
                logging.error(f"Failed to stretch audio for {file_path}: {e}")
                print(f"-> Failed to stretch audio for: {Path(file_path).name} (see {LOG_FILE})")
                failed_count += 1
        else:
            failed_count += 1
            logging.error(f"Cannot process {file_path} due to invalid detected BPM (0).")
            print(f"-> Failed to process: {Path(file_path).name} (BPM was 0)")


    # --- Final Summary ---
    print("\n" + "="*30)
    print("Processing Complete")
    print("="*30)
    print(f"Total files processed: {processed_count}")
    if not analyze_only:
        print(f"Files modified:        {modified_count}")
    print(f"Files failed:          {failed_count}")
    if failed_count > 0:
        print(f"See '{LOG_FILE}' for details on errors.")
    print("="*30)


def main():
    """Main entry point and argument parsing."""
    parser = argparse.ArgumentParser(
        description="Detect and adjust tempo of audio files in a directory.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_folder",
        help="Path to the folder containing audio files."
    )
    parser.add_argument(
        "--target-bpm",
        type=float,
        required=True,
        help="The target BPM for the audio files."
    )
    parser.add_argument(
        "--output-dir",
        default="./out",
        help="The directory to save modified files.\n(default: ./out)"
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="If set, only analyze and list BPMs without modifying any files."
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    input_folder_path = Path(args.input_folder).expanduser()
    if not input_folder_path.is_dir():
        print(f"Error: Input folder not found at '{input_folder_path}'", file=sys.stderr)
        sys.exit(1)
    
    if args.target_bpm <= 0:
        print(f"Error: Target BPM must be a positive number.", file=sys.stderr)
        sys.exit(1)

    process_folder(
        folder=str(input_folder_path),
        target_bpm=args.target_bpm,
        out_dir=args.output_dir,
        analyze_only=args.analyze_only
    )

if __name__ == "__main__":
    main()