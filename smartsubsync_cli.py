#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Callable

from smartsubsync.sync import (
    DEFAULT_COARSE_STEP,
    DEFAULT_FINE_STEP,
    DEFAULT_MIN_IMPROVEMENT_PERCENT,
    DEFAULT_MIN_OVERLAP_PERCENT,
    DEFAULT_MIN_SILENCE_MS,
    DEFAULT_MIN_SPEECH_MS,
    DEFAULT_SEARCH_RANGE,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW_COUNT,
    DEFAULT_WINDOW_DURATION,
    estimate_subtitle_sync,
)
from smartsubsync.timecode import format_timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate subtitle delay for mpv.")
    parser.add_argument("video_file", help="Path to the currently playing video.")
    parser.add_argument("subtitle_file", help="Path to the external SRT subtitle.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--window-count", type=int, default=DEFAULT_WINDOW_COUNT)
    parser.add_argument("--window-duration", type=float, default=DEFAULT_WINDOW_DURATION)
    parser.add_argument("--search-range", type=float, default=DEFAULT_SEARCH_RANGE)
    parser.add_argument("--coarse-step", type=float, default=DEFAULT_COARSE_STEP)
    parser.add_argument("--fine-step", type=float, default=DEFAULT_FINE_STEP)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--min-speech-ms", type=float, default=DEFAULT_MIN_SPEECH_MS)
    parser.add_argument("--min-silence-ms", type=float, default=DEFAULT_MIN_SILENCE_MS)
    parser.add_argument("--min-overlap-percent", type=float, default=DEFAULT_MIN_OVERLAP_PERCENT)
    parser.add_argument(
        "--min-improvement-percent",
        type=float,
        default=DEFAULT_MIN_IMPROVEMENT_PERCENT,
    )
    parser.add_argument("--no-auto-retry", action="store_true")
    parser.add_argument("--timings", action="store_true", help="Print timing breakdown.")
    parser.add_argument(
        "--progress-file",
        help="Write progress updates as JSON for mpv's on-screen display.",
    )
    return parser.parse_args()


def make_progress_callback(path: Path | None) -> Callable[[float, str], None] | None:
    if path is None:
        return None

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f"{path.name}.tmp"

    def write_progress(percent: float, message: str) -> None:
        payload = {
            "percent": max(0, min(100, round(percent))),
            "message": message,
        }
        tmp_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp_path, path)

    return write_progress


def main() -> int:
    args = parse_args()
    progress_callback = make_progress_callback(
        Path(args.progress_file) if args.progress_file else None
    )
    result = estimate_subtitle_sync(
        Path(args.video_file),
        Path(args.subtitle_file),
        window_count=args.window_count,
        window_duration=args.window_duration,
        search_range=args.search_range,
        coarse_step=args.coarse_step,
        fine_step=args.fine_step,
        threshold=args.threshold,
        min_speech_ms=args.min_speech_ms,
        min_silence_ms=args.min_silence_ms,
        min_overlap_percent=args.min_overlap_percent,
        min_improvement_percent=args.min_improvement_percent,
        auto_retry=not args.no_auto_retry,
        progress_callback=progress_callback,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "offset_seconds": round(result.offset_seconds, 3),
                    "best_overlap_percent": round(result.best_overlap_percent, 2),
                    "zero_overlap_percent": round(result.zero_overlap_percent, 2),
                    "overlap_improvement_percent": round(
                        result.overlap_improvement_percent, 2
                    ),
                    "reliable": result.reliable,
                    "retry_used": result.retry_used,
                    "sampled_audio_seconds": round(result.sampled_audio_seconds, 3),
                    "window_count": result.window_count,
                    "elapsed_seconds": round(result.elapsed_seconds, 3),
                    "timings": {
                        key: round(value, 3) for key, value in result.timings.items()
                    },
                },
                separators=(",", ":"),
            )
        )
        return 0

    print(f"Best offset: {result.offset_seconds:+.3f}s")
    print(f"Best overlap: {result.best_overlap_percent:.2f}%")
    print(f"Zero-offset overlap: {result.zero_overlap_percent:.2f}%")
    print(f"Overlap improvement: {result.overlap_improvement_percent:.2f}%")
    print(f"Reliable: {'yes' if result.reliable else 'no'}")
    print(f"Retry used: {'yes' if result.retry_used else 'no'}")
    print(f"Sampled audio: {format_timestamp(result.sampled_audio_seconds)}")
    print(f"Elapsed: {format_timestamp(result.elapsed_seconds)}")
    if args.timings:
        print("Timing breakdown:")
        for key, value in result.timings.items():
            print(f"  {key}: {format_timestamp(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
