from __future__ import annotations

from dataclasses import dataclass

from smartsubsync.intervals import (
    clip_intervals_to_windows,
    overlap_duration,
    shift_intervals,
    total_duration,
)
from smartsubsync.types import Interval, Window


@dataclass(frozen=True)
class Metrics:
    offset_seconds: float
    overlap_percent: float
    subtitle_coverage_percent: float
    vad_coverage_percent: float
    overlap_seconds: float


def compute_metrics(
    vad_intervals: list[Interval],
    subtitle_intervals: list[Interval],
    windows: list[Window],
    offset_seconds: float,
) -> Metrics:
    shifted_subtitles = shift_intervals(subtitle_intervals, offset_seconds)
    clipped_subtitles = clip_intervals_to_windows(shifted_subtitles, windows)
    clipped_vad = clip_intervals_to_windows(vad_intervals, windows)
    overlap_total = overlap_duration(clipped_vad, clipped_subtitles)
    vad_total = total_duration(clipped_vad)
    subtitle_total = total_duration(clipped_subtitles)
    union_total = vad_total + subtitle_total - overlap_total

    return Metrics(
        offset_seconds=offset_seconds,
        overlap_percent=100.0 * overlap_total / union_total if union_total else 0.0,
        subtitle_coverage_percent=(
            100.0 * overlap_total / subtitle_total if subtitle_total else 0.0
        ),
        vad_coverage_percent=100.0 * overlap_total / vad_total if vad_total else 0.0,
        overlap_seconds=overlap_total,
    )


def frange(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    current = start
    epsilon = step / 10
    while current <= stop + epsilon:
        values.append(round(current, 6))
        current += step
    return values


def find_best_offset(
    vad_intervals: list[Interval],
    subtitle_intervals: list[Interval],
    windows: list[Window],
    *,
    search_range: float,
    coarse_step: float,
    fine_step: float,
) -> Metrics:
    best = compute_metrics(vad_intervals, subtitle_intervals, windows, 0.0)

    for offset in frange(-search_range, search_range, coarse_step):
        metrics = compute_metrics(vad_intervals, subtitle_intervals, windows, offset)
        if metrics.overlap_percent > best.overlap_percent:
            best = metrics

    coarse_best = best.offset_seconds
    for offset in frange(coarse_best - coarse_step, coarse_best + coarse_step, fine_step):
        metrics = compute_metrics(vad_intervals, subtitle_intervals, windows, offset)
        if metrics.overlap_percent > best.overlap_percent:
            best = metrics

    return best
