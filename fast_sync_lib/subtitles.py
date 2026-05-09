from __future__ import annotations

from pathlib import Path

from fast_sync_lib.intervals import merge_intervals
from fast_sync_lib.timecode import parse_timestamp
from fast_sync_lib.types import Interval


def read_text_with_fallbacks(path: Path) -> str:
    encodings = ("utf-8-sig", "utf-8", "cp1254", "latin-1")
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode subtitle file: {path}")


def parse_srt(path: Path) -> list[Interval]:
    content = read_text_with_fallbacks(path)
    intervals: list[Interval] = []

    for line in content.splitlines():
        if "-->" not in line:
            continue
        start_raw, end_raw = [part.strip() for part in line.split("-->", 1)]
        intervals.append((parse_timestamp(start_raw), parse_timestamp(end_raw)))

    if not intervals:
        raise ValueError(f"No subtitle intervals found in: {path}")

    return merge_intervals(intervals)
