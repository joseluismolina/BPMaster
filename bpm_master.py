#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BPM Master - Audio Tempo Adjustment Script
==========================================

This script recursively finds audio files in a given directory, detects their
BPM (Beats Per Minute), and adjusts their tempo to a target BPM using an
external tool.

**Installation:**

1.  **Python Dependencies:**
    Install the required Python libraries using pip. It is recommended to do
    this within a virtual environment.

    ```bash
    pip install -r requirements.txt
    ```
    (This will install `essentia` and `tqdm`)

2.  **External Tool (rubberband-cli):**
    This script relies on `rubberband-cli` for audio time-stretching.
    You must install it using your system's package manager.

    On Debian/Ubuntu:
    ```bash
    sudo apt update
    sudo apt install rubberband-cli
    ```

    On other Linux distributions, use the appropriate package manager (e.g., `yum`, `pacman`).

**Usage:**

```bash
python bpm_master.py /path/to/your/audio --target-bpm 120
```

**Examples:**

# Analyze all audio files in '~/Music/samples' without changing them:
python bpm_master.py ~/Music/samples --target-bpm 120 --analyze-only

# Change tempo of all audio in '~/Music/loops' to 90 BPM and save them in '~/Music/loops_processed':
python bpm_master.py ~/Music/loops --target-bpm 90 --output-dir ~/Music/loops_processed
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path

try:
    from tqdm import tqdm
    import essentia.standard as es
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

    Args:
        file_path: Absolute path to the audio file.

    Returns:
        A tuple containing (bpm, confidence). Returns (None, None) on failure.
    """
    try:
        loader = es.MonoLoader(filename=file_path)
        audio = loader()
        
        # RhythmExtractor2013 with the 'multifeature' method
        rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
        bpm, _, confidence, _, _ = rhythm_extractor(audio)

        if bpm is None or bpm == 0:
            logging.error(f"BPM detection failed for {file_path}. Result was 0 or None.")
            return None, None
            
        return bpm, confidence
    except Exception as e:
        logging.error(f"Essentia failed to process {file_path}: {e}")
        return None, None

def stretch_audio(input_file: str, output_file: str, factor: float):
    """
    Stretches audio tempo using rubberband-cli.

    Args:
        input_file: Path to the source audio file.
        output_file: Path to save the modified audio file.
        factor: The tempo stretch factor (e.g., 1.1 for +10%).

    Raises:
        subprocess.CalledProcessError: If rubberband-cli returns a non-zero exit code.
    """
    command = [
        'rubberband',
        '--tempo', str(factor),
        '--quiet', # Prevents rubberband from printing its own progress
        input_file,
        output_file
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def process_folder(folder: str, target_bpm: float, out_dir: str, analyze_only: bool):
    """
    Main function to process a folder of audio files.

    Args:
        folder: The root folder to search for audio files.
        target_bpm: The desired target BPM.
        out_dir: The directory to save modified files.
        analyze_only: If True, only analyze and print BPMs.
    """
    print(f"Searching for audio files in: {folder}")
    
    # Find all audio files recursively
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
    
    # Create output directory if it doesn't exist and we are modifying files
    if not analyze_only:
        output_path.mkdir(parents=True, exist_ok=True)

    # Statistics counters
    processed_count = 0
    modified_count = 0
    failed_count = 0

    # Progress bar
    progress_bar = tqdm(audio_files, desc="Processing files", unit="file")

    for file_path in progress_bar:
        processed_count += 1
        
        # Update progress bar description
        progress_bar.set_postfix_str(Path(file_path).name)

        detected_bpm, confidence = detect_bpm(file_path)

        if detected_bpm is None:
            print(f"-> Failed to detect BPM for: {Path(file_path).name}")
            failed_count += 1
            continue

        if analyze_only:
            print(f"  - File: {Path(file_path).name} | Detected BPM: {detected_bpm:.2f} (Confidence: {confidence:.2f})")
            continue

        # --- Tempo Modification Logic ---
        if detected_bpm > 0:
            factor = target_bpm / detected_bpm
            
            # Create the same sub-directory structure in the output folder
            relative_path = Path(file_path).relative_to(input_path)
            output_file_path = output_path / relative_path
            output_file_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                stretch_audio(file_path, str(output_file_path), factor)
                modified_count += 1
            except subprocess.CalledProcessError as e:
                logging.error(f"rubberband-cli failed for {file_path}: {e.stderr}")
                print(f"-> Failed to stretch audio for: {Path(file_path).name} (see {LOG_FILE})")
                failed_count += 1
            except Exception as e:
                logging.error(f"An unexpected error occurred during stretching of {file_path}: {e}")
                print(f"-> An unexpected error occurred for: {Path(file_path).name} (see {LOG_FILE})")
                failed_count += 1
        else:
            failed_count += 1
            logging.error(f"Cannot process {file_path} due to invalid detected BPM (0).")
            print(f"-> Failed to process: {Path(file_path).name} (BPM was 0)")


    # --- Final Summary ---
    print("" + "="*30)
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
        help="The directory to save modified files.(default: ./out)"
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

    # Basic validation
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
