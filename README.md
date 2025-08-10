# BPM Master (Cross-Platform)

A command-line Python script to recursively find audio files in a directory, detect their BPM (Beats Per Minute), and adjust their tempo to a target value.

Thanks to the `pyrubberband` library, this tool is fully cross-platform (Windows, macOS, Linux) and all dependencies are installed easily with pip.

## Features

- Processes `.mp3`, `.wav`, and `.flac` files recursively.
- Fully cross-platform (Windows, macOS, Linux).
- All dependencies managed by pip; no external software needed.
- Detects BPM and confidence score using Essentia.
- Adjusts audio tempo using the high-quality Rubberband library via `pyrubberband`.
- Preserves the original directory structure in the output folder.
- Provides an `--analyze-only` mode to inspect BPMs without modifying files.
- Logs all processing errors to an `errors.log` file.

## Requirements

- Python 3.9+
- Pip and a virtual environment.

## Installation

Running this script in a Python virtual environment is the recommended way to avoid conflicts with system-wide packages.

**Step 1: Create and Activate a Virtual Environment**

From your project directory, run the following commands.

```bash
# Create a virtual environment named 'venv'
python3 -m venv venv

# Activate the virtual environment

# On Linux and macOS:
source venv/bin/activate

# On Windows (using Command Prompt):
.\venv\Scripts\activate.bat

# On Windows (using PowerShell):
.\venv\Scripts\Activate.ps1
```
After activation, your shell prompt will likely be prefixed with `(venv)`.

**Step 2: Install Dependencies**

With the virtual environment active, install all required Python libraries from the `requirements.txt` file.

```bash
pip install -r requirements.txt
```
This will install `essentia`, `rich`, and `pyrubberband`.

## Usage

See the help message for all options:
```bash
python bpm_master.py --help
```

### Examples

**1. Adjusting Tempo**

To change the tempo of all audio files in `~/Music/loops` to 140 BPM:

```bash
python bpm_master.py ~/Music/loops --target-bpm 140 --output-dir ~/Music/loops-140bpm
```

**2. Analyzing Only**

To scan all audio files in `~/Music/samples` and see their detected BPM without changing any files:

```bash
python bpm_master.py ~/Music/samples --target-bpm 120 --analyze-only
```
