#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# BPM Master
# Copyright (C) 2025 José Luis Molina Díaz
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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

import sys
import argparse
import logging
from pathlib import Path
import multiprocessing, threading, time
from multiprocessing import Manager

try:
    import essentia
    essentia.log.infoActive = False
    import essentia.standard as es
    import pyrubberband as pyrb
    from rich.console import Console
    from rich.console import Console, Group
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from pydub import AudioSegment

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

def detect_bpm(file_path: str) -> float | None:
    """
    Detects the BPM using the PercivalBpmEstimator algorithm from Essentia,
    applying post-processing heuristics for dance music.
    """
    try:
        # 1. Load the audio file in mono. PercivalBpmEstimator works on raw audio.
        audio = es.MonoLoader(filename=file_path)()

        # 2. Use the PercivalBpmEstimator algorithm.
        # This is another robust estimator recommended in the Essentia documentation.
        bpm = es.PercivalBpmEstimator()(audio)

        # --- Post-processing Heuristics for Dance Music ---

        # 3. Check for octave errors (e.g., 75 BPM instead of 150)
        while bpm < 100:
            bpm *= 2
        
        # 4. Round to the nearest whole number for a cleaner BPM value
        bpm = round(bpm)
        
        return float(bpm)

    except Exception as e:
        logging.error(f"Essentia (PercivalBpmEstimator) failed for {file_path}: {e}")
        return None

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
    file_path, target_bpm, input_path_str, output_path_str, analyze_only, log_file_name, worker_id, status_dict = args
    
    input_path = Path(input_path_str)
    output_path = Path(output_path_str)
    file_name = Path(file_path).name

    try:
        status_dict[worker_id] = f"Detecting BPM for [bold]{file_name}[/bold]"
        detected_bpm = detect_bpm(file_path)

        if detected_bpm is None:
            status_dict[worker_id] = "Idle"
            return (False, file_path, "BPM_DETECTION_FAILED")
        elif analyze_only:
            status_dict[worker_id] = "Idle"
            return (True, file_path, "ANALYZE_ONLY", detected_bpm)
        elif detected_bpm > 0:
            factor = target_bpm / detected_bpm
            relative_path = Path(file_path).relative_to(input_path)
            output_file_path = output_path / relative_path
            output_file_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                status_dict[worker_id] = f"Stretching [bold]{file_name}[/bold]"
                stretch_audio(file_path, str(output_file_path), factor)
                status_dict[worker_id] = "Idle"
                return (True, file_path, "PROCESSED")
            except Exception as e:
                logging.error(f"Failed to stretch audio for {file_path}: {e}")
                status_dict[worker_id] = "Idle"
                return (False, file_path, "STRETCH_FAILED")
        else:
            logging.error(f"Cannot process {file_path} due to invalid detected BPM (0).")
            status_dict[worker_id] = "Idle"
            return (False, file_path, "INVALID_BPM")

    except Exception as e:
        logging.error(f"Unhandled error processing {file_path}: {e}")
        status_dict[worker_id] = "Idle"
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

    console.print(f"Found {len(audio_files)} audio files.")
    
    if not analyze_only:
        output_path.mkdir(parents=True, exist_ok=True)

    processed_count = 0
    modified_count = 0
    failed_count = 0
    log_messages = []

    progress_columns = (
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("eta"),
        TimeRemainingColumn(),
    )
    progress = Progress(*progress_columns, console=console)

    num_cores = multiprocessing.cpu_count()
    
    with Manager() as manager:
        status_dict = manager.dict()
        for i in range(num_cores):
            status_dict[i] = "Idle"

        def get_status_panel() -> Panel:
            status_group = Group(*[Text.from_markup(f"Worker {i+1}: {status_dict[i]}") for i in range(num_cores)])
            return Panel(status_group, title="Worker Status", border_style="blue")

        job_panel = Panel(Group(*[Text.from_markup(msg) for msg in log_messages]), title="Results", border_style="green", expand=True)
        layout = Group(progress, get_status_panel(), job_panel)

        with Live(layout, console=console, screen=False, redirect_stderr=False, vertical_overflow="visible") as live:
            task = progress.add_task("[green]Process [/green]", total=len(audio_files))

            tasks_args = [
                (file, target_bpm, str(input_path), str(output_path), analyze_only, LOG_FILE, i % num_cores, status_dict)
                for i, file in enumerate(audio_files)
            ]

            # --- Threaded updater for the live display ---
            stop_event = threading.Event()
            def updater():
                while not stop_event.is_set():
                    live.update(Group(progress, get_status_panel(), job_panel))
                    time.sleep(0.1)
            
            updater_thread = threading.Thread(target=updater)
            updater_thread.start()
            # -----------------------------------------

            with multiprocessing.Pool(processes=num_cores) as pool:
                for result in pool.imap_unordered(_process_single_file_task, tasks_args):
                    is_success, file_path, status_code, *extra_data = result
                    file_name = Path(file_path).name

                    if is_success:
                        if status_code == "ANALYZE_ONLY":
                            detected_bpm = extra_data[0]
                            log_messages.append(f"[blue] INFO [/blue] {file_name} | BPM: {detected_bpm:.2f}")
                        elif status_code == "PROCESSED":
                            modified_count += 1
                            log_messages.append(f"[green] OK   [/green] Processed {file_name}")
                    else:
                        failed_count += 1
                        if status_code == "BPM_DETECTION_FAILED":
                            log_messages.append(f"[red]  FAIL [/red] Could not detect BPM for: {file_name}")
                        elif status_code == "STRETCH_FAILED":
                            log_messages.append(f"[red]  FAIL [/red] Could not process {file_name} (see {LOG_FILE})")
                        elif status_code == "INVALID_BPM":
                            log_messages.append(f"[red]  FAIL [/red] Invalid BPM (0) for {file_name}")
                        elif status_code == "UNHANDLED_ERROR":
                            log_messages.append(f"[red]  FAIL [/red] Unhandled error for {file_name} (see {LOG_FILE})")
                    
                    processed_count += 1
                    progress.update(task, advance=1)
                    job_panel.renderable = Group(*[Text.from_markup(msg) for msg in log_messages])
            
            # Stop the updater thread
            stop_event.set()
            updater_thread.join()

            # Final cleanup of the status panel
            for i in range(num_cores):
                status_dict[i] = "Idle"
            live.update(Group(progress, get_status_panel(), job_panel))

    # --- Final Summary ---
    summary_messages = []
    summary_messages.append(f"Total files processed: {processed_count}")
    if not analyze_only:
        summary_messages.append(f"Files modified:        {modified_count}")
    summary_messages.append(f"Files failed:          [red]{failed_count}[/red]")
    if failed_count > 0:
        summary_messages.append(f"See '{LOG_FILE}' for details on errors.")

    summary_panel = Panel(
        Group(*[Text.from_markup(msg) for msg in summary_messages]),
        title="[bold green]Processing Complete[/bold green]",
        border_style="green",
        expand=False
    )
    console.print(summary_panel)


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
