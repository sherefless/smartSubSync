from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import torch
from silero_vad import get_speech_timestamps

from fast_sync_lib.intervals import merge_intervals
from fast_sync_lib.types import Interval, Window


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


def extract_audio_window(
    video_path: Path, start_sec: float, duration_sec: float
) -> torch.Tensor:
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
    audio_bytes = bytearray(result.stdout)
    if not audio_bytes:
        return torch.empty(0, dtype=torch.float32)

    audio = torch.frombuffer(audio_bytes, dtype=torch.int16).to(torch.float32)
    return audio / 32768.0


def choose_window_centers(
    subtitle_intervals: list[Interval],
    video_duration: float,
    window_count: int,
    window_duration: float,
) -> list[float]:
    if window_count < 1:
        raise ValueError("--window-count must be at least 1")

    subtitle_midpoints = [(start + end) / 2 for start, end in subtitle_intervals]
    usable_start = window_duration / 2
    usable_end = max(usable_start, video_duration - window_duration / 2)

    centers: list[float] = []
    for index in range(window_count):
        quantile = (index + 1) / (window_count + 1)
        midpoint_index = min(
            len(subtitle_midpoints) - 1,
            max(0, round(quantile * (len(subtitle_midpoints) - 1))),
        )
        center = subtitle_midpoints[midpoint_index]
        center = min(max(center, usable_start), usable_end)
        centers.append(center)

    deduped: list[float] = []
    min_spacing = max(10.0, window_duration * 0.35)
    for center in sorted(centers):
        if not deduped or center - deduped[-1] >= min_spacing:
            deduped.append(center)

    if not deduped:
        deduped = [min(max(video_duration / 2, usable_start), usable_end)]

    return deduped


def collect_vad_intervals(
    video_path: Path,
    model: Any,
    centers: list[float],
    window_duration: float,
    threshold: float,
) -> tuple[list[Interval], list[Window]]:
    intervals: list[Interval] = []
    windows: list[Window] = []

    for center in centers:
        start_sec = max(0.0, center - window_duration / 2)
        audio = extract_audio_window(video_path, start_sec, window_duration)
        window = Window(
            start=start_sec,
            end=start_sec + len(audio) / SAMPLE_RATE,
            center=center,
        )
        windows.append(window)

        if len(audio) == 0:
            continue

        speech_segments = get_speech_timestamps(
            audio,
            model,
            threshold=threshold,
            sampling_rate=SAMPLE_RATE,
            return_seconds=False,
        )
        for segment in speech_segments:
            intervals.append(
                (
                    start_sec + segment["start"] / SAMPLE_RATE,
                    start_sec + segment["end"] / SAMPLE_RATE,
                )
            )

    return merge_intervals(intervals), windows
