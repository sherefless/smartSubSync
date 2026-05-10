# smartSubSync

`smartSubSync` is an automatic subtitle synchronization helper for
[mpv](https://mpv.io/).

When you add or select an external `.srt` subtitle in mpv, the Lua script runs a
small Python helper. The helper samples short `16 kHz` mono audio windows with
`ffmpeg`, detects speech with Silero VAD, compares the detected speech intervals
with subtitle timing intervals, then applies the best `sub-delay` value in mpv.

## Features

- Runs automatically when an external subtitle is added or selected in mpv.
- Uses Silero VAD as the speech detection engine.
- Samples only selected audio windows instead of processing the whole video.
- Keeps user-tunable settings in `smartsubsync.conf`.
- Refuses to apply low-confidence sync results.
- Retries once with a larger sample when confidence is low.

## Requirements

- Python `3.10+`
- mpv
- ffmpeg and ffprobe
- Python packages: `torch`, `torchaudio`, `silero-vad`, `numpy`

## Install On Linux

Install system tools with your package manager. For example:

```bash
sudo apt install mpv ffmpeg python3 python3-venv
```

Create a virtual environment inside the project:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install silero-vad numpy
```

Install the mpv script:

```bash
mkdir -p ~/.config/mpv/scripts ~/.config/mpv/script-opts
ln -sf "$PWD/mpv/smartsubsync.lua" ~/.config/mpv/scripts/smartsubsync.lua
cp mpv/script-opts/smartsubsync.conf ~/.config/mpv/script-opts/smartsubsync.conf
```

Edit `~/.config/mpv/script-opts/smartsubsync.conf` and set these paths:

```text
python=/absolute/path/to/smartSubSync/.venv/bin/python
helper_path=/absolute/path/to/smartSubSync/smartsubsync_cli.py
```

## Install On Windows

Install:

- Python `3.10+`
- mpv
- ffmpeg

Make sure `ffmpeg.exe`, `ffprobe.exe`, and `mpv.exe` are available from your
terminal `PATH`.

Create a virtual environment from PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install silero-vad numpy
```

Create mpv config directories:

```powershell
mkdir $env:APPDATA\mpv\scripts -Force
mkdir $env:APPDATA\mpv\script-opts -Force
copy .\mpv\smartsubsync.lua $env:APPDATA\mpv\scripts\smartsubsync.lua
copy .\mpv\script-opts\smartsubsync.conf $env:APPDATA\mpv\script-opts\smartsubsync.conf
```

Edit `%APPDATA%\mpv\script-opts\smartsubsync.conf` and set these paths:

```text
python=C:\absolute\path\to\smartSubSync\.venv\Scripts\python.exe
helper_path=C:\absolute\path\to\smartSubSync\smartsubsync_cli.py
```

## Usage

Open a video in mpv, then drag an external `.srt` subtitle onto the player.
`smartSubSync` starts automatically and shows progress in mpv's on-screen
display.

You can also run sync manually with:

```text
Ctrl+s
```

If the match is reliable, `smartSubSync` applies `sub-delay` automatically. If
confidence is low after retrying, it leaves the current subtitle delay unchanged
and shows a warning.

## Settings

User settings live here:

```text
Linux:   ~/.config/mpv/script-opts/smartsubsync.conf
Windows: %APPDATA%\mpv\script-opts\smartsubsync.conf
```

Recommended default:

```text
window_count=6
window_duration=60
search_range=120
fine_step=0.02
```

Faster, but less robust for sparse dialogue:

```text
window_count=3
window_duration=30
search_range=60
```

More robust, but slower:

```text
window_count=8
window_duration=90
search_range=180
```

Important options:

- `window_count`: how many subtitle-distributed video windows to sample.
- `window_duration`: duration of each sampled audio window in seconds.
- `search_range`: maximum positive/negative subtitle shift to test in seconds.
- `coarse_step`: first-pass offset search step in seconds.
- `fine_step`: second-pass offset search step in seconds.
- `auto_retry`: retry once with a larger sample if confidence is low.
- `min_overlap_percent`: minimum overlap required before applying the delay.
- `min_improvement_percent`: required improvement over zero-offset alignment.

## CLI

You can test the sync helper without mpv:

```bash
python3 smartsubsync_cli.py "/path/to/video.mkv" "/path/to/subtitle.srt"
```

Print timing breakdown for debugging:

```bash
python3 smartsubsync_cli.py --timings "/path/to/video.mkv" "/path/to/subtitle.srt"
```

Machine-readable output used by mpv:

```bash
python3 smartsubsync_cli.py --json "/path/to/video.mkv" "/path/to/subtitle.srt"
```

## Troubleshooting

If mpv shows `smartSubSync failed`, run the CLI command above directly in a
terminal. Python traceback messages are easier to read there.

Common fixes:

- `No module named numpy`: install dependencies inside the same virtual
  environment configured in `smartsubsync.conf`.
- `ffmpeg not found`: install ffmpeg and ensure it is available from `PATH`.
- Nothing happens when adding subtitles: check that `smartsubsync.lua` is in
  mpv's `scripts` directory.
- Low-confidence warning: try larger `window_count`, `window_duration`, or
  `search_range` values in `smartsubsync.conf`.
- Wrong Python is used: set the absolute `python=` path in `smartsubsync.conf`.

## Development

Run tests:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Validate the Lua script:

```bash
luac -p mpv/smartsubsync.lua
```
