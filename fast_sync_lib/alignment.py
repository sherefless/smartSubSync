from __future__ import annotations

from fast_sync_lib.intervals import (
    clip_intervals_to_windows,
    overlap_duration,
    shift_intervals,
    total_duration,
)
from fast_sync_lib.types import AlignmentMetrics, Interval, Window


def compute_metrics(
    vad_intervals: list[Interval],
    subtitle_intervals: list[Interval],
    windows: list[Window],
    offset_seconds: float,
) -> AlignmentMetrics:
    shifted_subtitles = shift_intervals(subtitle_intervals, offset_seconds)
    clipped_subtitles = clip_intervals_to_windows(shifted_subtitles, windows)
    clipped_vad = clip_intervals_to_windows(vad_intervals, windows)
    overlap_total = overlap_duration(clipped_vad, clipped_subtitles)
    vad_total = total_duration(clipped_vad)
    subtitle_total = total_duration(clipped_subtitles)
    union_total = vad_total + subtitle_total - overlap_total

    return AlignmentMetrics(
        offset_seconds=offset_seconds,
        vad_total_seconds=vad_total,
        subtitle_total_seconds=subtitle_total,
        overlap_seconds=overlap_total,
        union_seconds=union_total,
        iou_percent=100.0 * overlap_total / union_total if union_total else 0.0,
        subtitle_coverage_percent=(
            100.0 * overlap_total / subtitle_total if subtitle_total else 0.0
        ),
        vad_coverage_percent=100.0 * overlap_total / vad_total if vad_total else 0.0,
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
    search_range: float,
    coarse_step: float,
    fine_step: float,
    ultra_step: float,
) -> AlignmentMetrics:
    best = compute_metrics(vad_intervals, subtitle_intervals, windows, 0.0)

    for offset in frange(-search_range, search_range, coarse_step):
        metrics = compute_metrics(vad_intervals, subtitle_intervals, windows, offset)
        if metrics.iou_percent > best.iou_percent:
            best = metrics

    coarse_best = best.offset_seconds
    for offset in frange(coarse_best - coarse_step, coarse_best + coarse_step, fine_step):
        metrics = compute_metrics(vad_intervals, subtitle_intervals, windows, offset)
        if metrics.iou_percent > best.iou_percent:
            best = metrics

    fine_best = best.offset_seconds
    for offset in frange(fine_best - fine_step, fine_best + fine_step, ultra_step):
        metrics = compute_metrics(vad_intervals, subtitle_intervals, windows, offset)
        if metrics.iou_percent > best.iou_percent:
            best = metrics

    return best
