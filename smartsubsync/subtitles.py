from __future__ import annotations

from pathlib import Path

from smartsubsync.errors import SmartSubSyncError
from smartsubsync.intervals import merge_intervals
from smartsubsync.timecode import parse_timestamp
from smartsubsync.types import Interval


def read_text_with_fallbacks(path: Path) -> str:
    if not path.exists():
        raise SmartSubSyncError(f"Subtitle file not found: {path}")

    encodings = ("utf-8-sig", "utf-8", "cp1254", "latin-1")
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise SmartSubSyncError(f"Could not decode subtitle file: {path}")


def parse_srt(path: Path) -> list[Interval]:
    content = read_text_with_fallbacks(path)
    intervals: list[Interval] = []

    for line in content.splitlines():
        if "-->" not in line:
            continue
        start_raw, end_raw = [part.strip() for part in line.split("-->", 1)]
        try:
            intervals.append((parse_timestamp(start_raw), parse_timestamp(end_raw)))
        except ValueError as error:
            raise SmartSubSyncError(f"Invalid subtitle timing line: {line}") from error

    if not intervals:
        raise SmartSubSyncError(f"No subtitle intervals found in: {path}")

    return merge_intervals(intervals)
