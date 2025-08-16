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
    This will install `essentia`, `pyrubberband`, `pydub`, and `rich`.

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
import multiprocessing

try:
    import essentia
    import essentia.standard as es
    import pyrubberband as pyrb
    from rich.console import Console
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn
    from pydub import AudioSegment

    # Deactivate Essentia's INFO logs to avoid spamming the console
    essentia.log.info_active = False

except ImportError as e:
    print(f"Error: A required library is not installed. {e}", file=sys.stderr)
    print("Please install dependencies by running: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


# --- Constants ---
SUPPORTED_EXTENSIONS = ['.mp3', '.wav', '.flac']
LOG_FILE = 'errors.log'

# --- Rich Console ---
console = Console()

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
    Stretches audio tempo using pyrubberband and uses pydub for I/O.
    """
    # Essentia is still used for loading the audio
    audio, sr_float, _, _, _, _ = es.AudioLoader(filename=input_file)()
    sr = int(sr_float)

    # Pyrubberband for stretching
    stretched_audio = pyrb.time_stretch(audio, sr, factor)

    # Convert numpy array to pydub AudioSegment
    # The audio data needs to be in 16-bit integer format for pydub
    if stretched_audio.ndim == 1:
        channels = 1
    else:
        channels = stretched_audio.shape[1]

    samples = (stretched_audio * 32767).astype("int16")
    
    audio_segment = AudioSegment(
        samples.tobytes(),
        frame_rate=sr,
        sample_width=samples.dtype.itemsize,
        channels=channels
    )

    # Export with pydub
    output_format = Path(output_file).suffix[1:].lower()
    audio_segment.export(output_file, format=output_format)


def _process_single_file_task(args):
    file_path, target_bpm, input_path_str, output_path_str, analyze_only, log_file_name = args
    
    input_path = Path(input_path_str)
    output_path = Path(output_path_str)

    try:
        detected_bpm, confidence = detect_bpm(file_path)

        if detected_bpm is None:
            return (False, file_path, "BPM_DETECTION_FAILED")
        elif analyze_only:
            return (True, file_path, "ANALYZE_ONLY", detected_bpm, confidence)
        elif detected_bpm > 0:
            factor = target_bpm / detected_bpm
            relative_path = Path(file_path).relative_to(input_path)
            output_file_path = output_path / relative_path
            output_file_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                stretch_audio(file_path, str(output_file_path), factor)
                return (True, file_path, "PROCESSED")
            except Exception as e:
                logging.error(f"Failed to stretch audio for {file_path}: {e}")
                return (False, file_path, "STRETCH_FAILED")
        else:
            logging.error(f"Cannot process {file_path} due to invalid detected BPM (0).")
            return (False, file_path, "INVALID_BPM")

    except Exception as e:
        logging.error(f"Unhandled error processing {file_path}: {e}")
        return (False, file_path, "UNHANDLED_ERROR")

def process_folder(folder: str, target_bpm: float, out_dir: str, analyze_only: bool):
    """
    Main function to process a folder of audio files with a Rich progress bar.
    """
    console.print(f"Searching for audio files in: [cyan]{folder}[/cyan]")
    
    input_path = Path(folder).expanduser()
    output_path = Path(out_dir).expanduser()
    
    audio_files = [
        str(p) for p in input_path.rglob('*') 
        if p.suffix.lower() in SUPPORTED_EXTENSIONS and p.is_file()
    ]

    if not audio_files:
        console.print("[yellow]No audio files found. Exiting.[/yellow]")
        return

    console.print(f"Found {len(audio_files)} audio files. Processing...")
    
    if not analyze_only:
        output_path.mkdir(parents=True, exist_ok=True)

    processed_count = 0
    modified_count = 0
    failed_count = 0

    progress_columns = (
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("eta"),
        TimeRemainingColumn(),
    )

    num_cores = multiprocessing.cpu_count()
    console.print(f"Using {num_cores} CPU cores for parallel processing.")

    with Progress(*progress_columns, console=console) as progress:
        task = progress.add_task("[green]Processing...", total=len(audio_files))

        # Prepare arguments for each task
        tasks_args = [
            (file_path, target_bpm, str(input_path), str(output_path), analyze_only, LOG_FILE)
            for file_path in audio_files
        ]

        with multiprocessing.Pool(processes=num_cores) as pool:
            for result in pool.imap_unordered(_process_single_file_task, tasks_args):
                is_success, file_path, status_code, *extra_data = result
                file_name = Path(file_path).name

                if is_success:
                    if status_code == "ANALYZE_ONLY":
                        detected_bpm, confidence = extra_data
                        console.print(f"[blue] -> INFO [/blue] {file_name} | BPM: {detected_bpm:.2f} (Confidence: {confidence:.2f})")
                    elif status_code == "PROCESSED":
                        modified_count += 1
                        console.print(f"[green] -> OK   [/green] Processed {file_name}")
                else:
                    failed_count += 1
                    if status_code == "BPM_DETECTION_FAILED":
                        console.print(f"[red] -> FAIL [/red] Could not detect BPM for: {file_name}")
                    elif status_code == "STRETCH_FAILED":
                        console.print(f"[red] -> FAIL [/red] Could not process {file_name} (see {LOG_FILE})")
                    elif status_code == "INVALID_BPM":
                        console.print(f"[red] -> FAIL [/red] Invalid BPM (0) for {file_name}")
                    elif status_code == "UNHANDLED_ERROR":
                        console.print(f"[red] -> FAIL [/red] Unhandled error for {file_name} (see {LOG_FILE})")
                
                processed_count += 1
                progress.update(task, advance=1, description=f"[green]Processing [bold]{file_name}[/bold]")

    # --- Final Summary ---
    console.print("\n" + "="*30)
    console.print("[bold green]Processing Complete[/bold green]")
    console.print("="*30)
    console.print(f"Total files processed: {processed_count}")
    if not analyze_only:
        console.print(f"Files modified:        {modified_count}")
    console.print(f"Files failed:          [red]{failed_count}[/red]")
    if failed_count > 0:
        console.print(f"See '{LOG_FILE}' for details on errors.")
    console.print("="*30)


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
        console.print(f"[bold red]Error: Input folder not found at '{input_folder_path}'[/bold red]")
        sys.exit(1)
    
    if args.target_bpm <= 0:
        console.print("[bold red]Error: Target BPM must be a positive number.[/bold red]")
        sys.exit(1)

    process_folder(
        folder=str(input_folder_path),
        target_bpm=args.target_bpm,
        out_dir=args.output_dir,
        analyze_only=args.analyze_only
    )

if __name__ == "__main__":
    main()
