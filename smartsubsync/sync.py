from __future__ import annotations

import time
from pathlib import Path

from smartsubsync.alignment import compute_metrics, find_best_offset
from smartsubsync.intervals import merge_intervals
from smartsubsync.media import SAMPLE_RATE, extract_audio_window, probe_duration
from smartsubsync.subtitles import parse_srt
from smartsubsync.types import Interval, SyncResult, Window
from smartsubsync.vad import detect_silero_speech, load_silero_model


DEFAULT_WINDOW_COUNT = 6
DEFAULT_WINDOW_DURATION = 60.0
DEFAULT_SEARCH_RANGE = 120.0
DEFAULT_COARSE_STEP = 0.5
DEFAULT_FINE_STEP = 0.02
DEFAULT_THRESHOLD = 0.5
DEFAULT_MIN_SPEECH_MS = 120.0
DEFAULT_MIN_SILENCE_MS = 180.0
DEFAULT_MIN_OVERLAP_PERCENT = 45.0
DEFAULT_MIN_IMPROVEMENT_PERCENT = 8.0

RETRY_WINDOW_COUNT = 8
RETRY_WINDOW_DURATION = 90.0
RETRY_SEARCH_RANGE = 180.0


def choose_window_centers(
    subtitle_intervals: list[Interval],
    *,
    video_duration: float,
    window_count: int,
    window_duration: float,
) -> list[float]:
    if window_count < 1:
        raise ValueError("window_count must be at least 1")

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
        centers.append(min(max(center, usable_start), usable_end))

    deduped: list[float] = []
    min_spacing = max(10.0, window_duration * 0.35)
    for center in sorted(centers):
        if not deduped or center - deduped[-1] >= min_spacing:
            deduped.append(center)

    return deduped or [min(max(video_duration / 2, usable_start), usable_end)]


def collect_speech_intervals(
    video_path: Path,
    centers: list[float],
    *,
    model,
    window_duration: float,
    threshold: float,
    min_speech_ms: float,
    min_silence_ms: float,
    timings: dict[str, float] | None = None,
) -> tuple[list[Interval], list[Window]]:
    speech_intervals: list[Interval] = []
    windows: list[Window] = []

    for center in centers:
        start_sec = max(0.0, center - window_duration / 2)
        audio_started_at = time.perf_counter()
        audio = extract_audio_window(video_path, start_sec, window_duration)
        if timings is not None:
            timings["extract_audio"] = timings.get("extract_audio", 0.0) + (
                time.perf_counter() - audio_started_at
            )
        real_duration = len(audio) / SAMPLE_RATE
        windows.append(Window(start=start_sec, end=start_sec + real_duration, center=center))

        vad_started_at = time.perf_counter()
        local_intervals = detect_silero_speech(
            audio,
            model=model,
            threshold=threshold,
            min_speech_ms=min_speech_ms,
            min_silence_ms=min_silence_ms,
        )
        if timings is not None:
            timings["vad"] = timings.get("vad", 0.0) + (
                time.perf_counter() - vad_started_at
            )
        speech_intervals.extend(
            (start_sec + start, start_sec + end) for start, end in local_intervals
        )

    return merge_intervals(speech_intervals), windows


def is_reliable_match(
    *,
    best_overlap_percent: float,
    zero_overlap_percent: float,
    min_overlap_percent: float,
    min_improvement_percent: float,
) -> bool:
    return (
        best_overlap_percent >= min_overlap_percent
        and best_overlap_percent - zero_overlap_percent >= min_improvement_percent
    )


def estimate_subtitle_sync_once(
    video_path: Path,
    subtitle_path: Path,
    *,
    window_count: int,
    window_duration: float,
    search_range: float,
    coarse_step: float,
    fine_step: float,
    threshold: float,
    min_speech_ms: float,
    min_silence_ms: float,
    min_overlap_percent: float,
    min_improvement_percent: float,
    retry_used: bool = False,
) -> SyncResult:
    started_at = time.perf_counter()
    timings: dict[str, float] = {}

    parse_started_at = time.perf_counter()
    subtitle_intervals = parse_srt(subtitle_path)
    timings["parse_srt"] = time.perf_counter() - parse_started_at

    probe_started_at = time.perf_counter()
    video_duration = probe_duration(video_path)
    timings["probe_duration"] = time.perf_counter() - probe_started_at

    centers_started_at = time.perf_counter()
    centers = choose_window_centers(
        subtitle_intervals,
        video_duration=video_duration,
        window_count=window_count,
        window_duration=window_duration,
    )
    timings["choose_windows"] = time.perf_counter() - centers_started_at

    model_started_at = time.perf_counter()
    model = load_silero_model()
    timings["load_model"] = time.perf_counter() - model_started_at

    vad_intervals, windows = collect_speech_intervals(
        video_path,
        centers,
        model=model,
        window_duration=window_duration,
        threshold=threshold,
        min_speech_ms=min_speech_ms,
        min_silence_ms=min_silence_ms,
        timings=timings,
    )
    if not vad_intervals:
        raise RuntimeError("No speech intervals detected in sampled windows.")

    search_started_at = time.perf_counter()
    best = find_best_offset(
        vad_intervals,
        subtitle_intervals,
        windows,
        search_range=search_range,
        coarse_step=coarse_step,
        fine_step=fine_step,
    )
    timings["search_offset"] = time.perf_counter() - search_started_at

    zero_started_at = time.perf_counter()
    zero = compute_metrics(vad_intervals, subtitle_intervals, windows, 0.0)
    timings["zero_metrics"] = time.perf_counter() - zero_started_at
    elapsed = time.perf_counter() - started_at
    timings["total"] = elapsed
    improvement = best.overlap_percent - zero.overlap_percent

    return SyncResult(
        offset_seconds=best.offset_seconds,
        best_overlap_percent=best.overlap_percent,
        zero_overlap_percent=zero.overlap_percent,
        overlap_improvement_percent=improvement,
        reliable=is_reliable_match(
            best_overlap_percent=best.overlap_percent,
            zero_overlap_percent=zero.overlap_percent,
            min_overlap_percent=min_overlap_percent,
            min_improvement_percent=min_improvement_percent,
        ),
        retry_used=retry_used,
        sampled_audio_seconds=sum(window.duration for window in windows),
        window_count=len(windows),
        elapsed_seconds=elapsed,
        timings=timings,
    )


def estimate_subtitle_sync(
    video_path: Path,
    subtitle_path: Path,
    *,
    window_count: int = DEFAULT_WINDOW_COUNT,
    window_duration: float = DEFAULT_WINDOW_DURATION,
    search_range: float = DEFAULT_SEARCH_RANGE,
    coarse_step: float = DEFAULT_COARSE_STEP,
    fine_step: float = DEFAULT_FINE_STEP,
    threshold: float = DEFAULT_THRESHOLD,
    min_speech_ms: float = DEFAULT_MIN_SPEECH_MS,
    min_silence_ms: float = DEFAULT_MIN_SILENCE_MS,
    min_overlap_percent: float = DEFAULT_MIN_OVERLAP_PERCENT,
    min_improvement_percent: float = DEFAULT_MIN_IMPROVEMENT_PERCENT,
    auto_retry: bool = True,
) -> SyncResult:
    started_at = time.perf_counter()
    result = estimate_subtitle_sync_once(
        video_path,
        subtitle_path,
        window_count=window_count,
        window_duration=window_duration,
        search_range=search_range,
        coarse_step=coarse_step,
        fine_step=fine_step,
        threshold=threshold,
        min_speech_ms=min_speech_ms,
        min_silence_ms=min_silence_ms,
        min_overlap_percent=min_overlap_percent,
        min_improvement_percent=min_improvement_percent,
    )

    should_retry = (
        auto_retry
        and not result.reliable
        and (
            window_count < RETRY_WINDOW_COUNT
            or window_duration < RETRY_WINDOW_DURATION
            or search_range < RETRY_SEARCH_RANGE
        )
    )
    if not should_retry:
        result.timings["wall_total"] = time.perf_counter() - started_at
        return result

    retry_result = estimate_subtitle_sync_once(
        video_path,
        subtitle_path,
        window_count=max(window_count, RETRY_WINDOW_COUNT),
        window_duration=max(window_duration, RETRY_WINDOW_DURATION),
        search_range=max(search_range, RETRY_SEARCH_RANGE),
        coarse_step=coarse_step,
        fine_step=fine_step,
        threshold=threshold,
        min_speech_ms=min_speech_ms,
        min_silence_ms=min_silence_ms,
        min_overlap_percent=min_overlap_percent,
        min_improvement_percent=min_improvement_percent,
        retry_used=True,
    )
    retry_result.timings["first_attempt_total"] = result.elapsed_seconds
    retry_result.timings["wall_total"] = time.perf_counter() - started_at
    return retry_result
