# smartSubSync

`smartSubSync` is an mpv subtitle synchronization helper.

When an external subtitle is selected or added in mpv, the Lua script calls a Python helper. The helper samples short `16 kHz` mono audio windows with `ffmpeg`, runs Silero VAD, compares speech activity with SRT timing intervals, and returns the best subtitle delay. The Lua script then applies that value to mpv's `sub-delay`.

## Layout

```text
mpv/
  smartsubsync.lua
  script-opts/
    smartsubsync.conf
smartsubsync/
  alignment.py
  intervals.py
  media.py
  subtitles.py
  sync.py
  timecode.py
  types.py
  vad.py
smartsubsync_cli.py
tests/
videos/
subtitles/
```

`videos/` and `subtitles/` are local sample data directories. They are not required by the mpv script.

## Requirements

- mpv
- Python 3.10+
- ffmpeg
- ffprobe
- torch
- torchaudio
- silero-vad
- numpy

Create the project virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install silero-vad numpy
```

## CLI Usage

```bash
python3 smartsubsync_cli.py "/path/to/video.mkv" "/path/to/subtitle.srt"
```

Machine-readable output for mpv:

```bash
python3 smartsubsync_cli.py --json "/path/to/video.mkv" "/path/to/subtitle.srt"
```

Useful tuning options:

```bash
--window-count 3
--window-duration 30
--search-range 60
--threshold 0.5
```

## mpv Setup

Copy or symlink the Lua script into your mpv scripts directory:

```bash
mkdir -p ~/.config/mpv/scripts
ln -sf /home/shrefsiz/Projects/vad_test/mpv/smartsubsync.lua ~/.config/mpv/scripts/smartsubsync.lua
```

If the Python helper is not next to the repository layout expected by the script, set `helper_path`:

```bash
mkdir -p ~/.config/mpv/script-opts
cp /home/shrefsiz/Projects/vad_test/mpv/script-opts/smartsubsync.conf ~/.config/mpv/script-opts/smartsubsync.conf
```

Then edit:

```text
helper_path=/home/shrefsiz/Projects/vad_test/smartsubsync_cli.py
```

While a video is open in mpv, adding/selecting an external subtitle triggers sync automatically. You can also run it manually with:

```text
Ctrl+s
```

## Development

Run tests:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Run a quick local smoke test:

```bash
python3 smartsubsync_cli.py \
  "videos/Black Sails (2014) - S01E01 - I. (1080p BluRay x265 RCVR).mkv" \
  "subtitles/Black.Sails.S01E01.720p.HDTV.x264-NTb.srt" \
  --window-count 2 \
  --window-duration 30 \
  --search-range 30
```
