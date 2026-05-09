# smartSubSync

`smartSubSync` is a small CLI tool that estimates subtitle offset for a video file by:

- extracting short `16 kHz` mono audio windows with `ffmpeg`
- running `silero-vad` on those sampled windows
- comparing VAD speech activity against subtitle timing intervals
- reporting the best estimated subtitle shift

The current implementation is intentionally CLI-only. It prints sync metrics to stdout and does not generate HTML reports.

## Requirements

- Python `>=3.14`
- `ffmpeg`
- `ffprobe`

Python dependencies:

- `torch`
- `torchaudio`
- `silero-vad`

## Installation

Create a virtual environment and install the dependencies you need for the CLI:

```bash
python -m venv venv
venv/bin/python -m pip install torch torchaudio silero-vad
```

Make sure `ffmpeg` and `ffprobe` are available on your system `PATH`.

## Usage

Basic usage:

```bash
venv/bin/python fast_sync.py "/path/to/video.mkv" "/path/to/subtitles.srt"
```

Example:

```bash
venv/bin/python fast_sync.py \
  "videos/Black Sails (2014) - S01E01 - I. (1080p BluRay x265 RCVR).mkv" \
  "subtitles/Black.Sails.S01E01.720p.HDTV.x264-NTb.srt"
```

Useful options:

```bash
--window-count 6
--window-duration 90
--search-range 180
--coarse-step 0.5
--fine-step 0.1
--ultra-step 0.02
--threshold 0.5
```

## Output

The CLI prints:

- input video path
- input subtitle path
- number of sampled windows
- total sampled audio duration
- overlap at zero offset
- best detected offset
- best overlap score
- total elapsed time

Example output:

```text
Video: videos/example.mkv
Subtitle: subtitles/example.srt
Sample windows: 6
Sampled audio total: 00:09:00,000
Zero-offset overlap: 31.20%
Best offset: +7.42s (00:00:07,420)
Best overlap: 58.14%
Elapsed: 00:00:03,114
```

## Project Layout

```text
fast_sync.py
fast_sync_lib/
  cli.py
  alignment.py
  intervals.py
  media.py
  subtitles.py
  timecode.py
  types.py
tests/
```

## Development

Run the stdlib test suite:

```bash
venv/bin/python -m unittest discover -s tests -p "test_*.py"
```

Syntax check:

```bash
venv/bin/python -m py_compile fast_sync.py fast_sync_lib/*.py tests/*.py
```
