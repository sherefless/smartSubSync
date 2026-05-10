from __future__ import annotations

import array
import subprocess
from pathlib import Path


SAMPLE_RATE = 16000


def run_command(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def probe_duration(video_path: Path) -> float:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
    )
    return float(result.stdout.decode("utf-8").strip())


def extract_audio_window(video_path: Path, start_sec: float, duration_sec: float) -> list[float]:
    result = run_command(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{duration_sec:.3f}",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-",
        ]
    )
    samples = array.array("h")
    samples.frombytes(result.stdout)
    return [sample / 32768.0 for sample in samples]
