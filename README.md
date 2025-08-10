# BPMaster

A command-line Python script to recursively find audio files in a directory, detect their BPM (Beats Per Minute), and adjust their tempo to a target value.

It uses the Essentia library for high-quality BPM detection and the `rubberband-cli` external tool for time-stretching, ensuring audio quality is preserved.

## Features

- Processes `.mp3`, `.wav`, and `.flac` files recursively.
- Detects BPM and confidence score using Essentia's `RhythmExtractor2013`.
- Adjusts audio tempo to a target BPM using `rubberband-cli`.
- Preserves the original directory structure in the output folder.
- Provides an `--analyze-only` mode to inspect BPMs without modifying files.
- Logs all processing errors to an `errors.log` file for easy debugging.
- Displays a `tqdm` progress bar during processing.

## Requirements

- Python 3.9+
- [Essentia](https://essentia.upf.edu/) & [Tqdm](https://github.com/tqdm/tqdm) Python libraries.
- `rubberband-cli` (external command-line tool).

## Installation

It is highly recommended to run this script in a Python virtual environment to avoid conflicts with system-wide packages.

**Step 1: Clone or Download**

First, get the script and its requirements file onto your local machine.
```bash
# If you were using git
# git clone <repository_url>
# cd <repository_directory>

# Or simply make sure bpm_master.py and requirements.txt are in a directory.
```

**Step 2: Install External Dependency (`rubberband-cli`)**

This tool is required for the audio stretching process. Install it using your system's package manager.

On Debian/Ubuntu:
```bash
sudo apt update
sudo apt install rubberband-cli
```
For other Linux distributions (like Fedora, Arch, etc.), use their respective package managers (`dnf`, `pacman`).

**Step 3: Create and Activate a Virtual Environment**

From your project directory (where `bpm_master.py` is located), run the following commands.

```bash
# Create a virtual environment named 'venv'
python3 -m venv venv

# Activate the virtual environment
# On Linux and macOS:
source venv/bin/activate
```
After activation, your shell prompt will likely be prefixed with `(venv)`, indicating that you are now working inside the virtual environment.

**Step 4: Install Python Dependencies**

With the virtual environment active, install the required Python libraries using pip.

```bash
pip install -r requirements.txt
```
This will install `essentia` and `tqdm` inside your virtual environment, keeping your global Python installation clean.

## Usage

The script is run from the command line and accepts several arguments.

```
usage: bpm_master.py [-h] --target-bpm TARGET_BPM [--output-dir OUTPUT_DIR] [--analyze-only] input_folder

Detect and adjust tempo of audio files in a directory.

positional arguments:
  input_folder          Path to the folder containing audio files.

options:
  -h, --help            show this help message and exit
  --target-bpm TARGET_BPM
                        The target BPM for the audio files.
  --output-dir OUTPUT_DIR
                        The directory to save modified files. (default: ./out)
  --analyze-only        If set, only analyze and list BPMs without modifying any files.
```

## Examples

**Example 1: Analyze Only**

To scan all audio files in a directory named `~/Music/samples` and see their detected BPM without changing any files:

```bash
python bpm_master.py ~/Music/samples --target-bpm 120 --analyze-only
```
*(Note: `--target-bpm` is still required but is not used for modification in this mode).*

**Example 2: Adjust Tempo**

To change the tempo of all audio files in `~/Music/loops` to 90 BPM and save the results in a new folder named `~/Music/loops-90bpm`:

```bash
python bpm_master.py ~/Music/loops --target-bpm 90 --output-dir ~/Music/loops-90bpm
```

## Deactivating the Virtual Environment

When you are finished using the script, you can deactivate the virtual environment:
```bash
deactivate
```

## Error Logging

If the script encounters any issues (e.g., a corrupt file, a failure in BPM detection, or an error from `rubberband-cli`), it will log the detailed error to `errors.log` in the same directory where you run the script.
