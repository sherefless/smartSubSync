from __future__ import annotations

from smartsubsync.types import Interval, Window


def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    cleaned = sorted((start, end) for start, end in intervals if end > start)
    if not cleaned:
        return []

    merged = [cleaned[0]]
    for start, end in cleaned[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def shift_intervals(intervals: list[Interval], offset_seconds: float) -> list[Interval]:
    return [
        (start + offset_seconds, end + offset_seconds)
        for start, end in intervals
        if end + offset_seconds > 0
    ]


def total_duration(intervals: list[Interval]) -> float:
    return sum(end - start for start, end in intervals)


def clip_intervals_to_windows(
    intervals: list[Interval], windows: list[Window]
) -> list[Interval]:
    clipped: list[Interval] = []
    interval_index = 0

    for window in windows:
        while (
            interval_index < len(intervals)
            and intervals[interval_index][1] <= window.start
        ):
            interval_index += 1

        scan_index = interval_index
        while scan_index < len(intervals) and intervals[scan_index][0] < window.end:
            start, end = intervals[scan_index]
            clipped_start = max(start, window.start)
            clipped_end = min(end, window.end)
            if clipped_end > clipped_start:
                clipped.append((clipped_start, clipped_end))
            scan_index += 1

    return merge_intervals(clipped)


def overlap_duration(left: list[Interval], right: list[Interval]) -> float:
    total = 0.0
    left_index = 0
    right_index = 0

    while left_index < len(left) and right_index < len(right):
        start = max(left[left_index][0], right[right_index][0])
        end = min(left[left_index][1], right[right_index][1])
        if end > start:
            total += end - start

        if left[left_index][1] <= right[right_index][1]:
            left_index += 1
        else:
            right_index += 1

    return total
