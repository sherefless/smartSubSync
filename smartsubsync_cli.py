#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartsubsync.sync import estimate_subtitle_sync
from smartsubsync.timecode import format_timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate subtitle delay for mpv.")
    parser.add_argument("video_file", help="Path to the currently playing video.")
    parser.add_argument("subtitle_file", help="Path to the external SRT subtitle.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--window-count", type=int, default=3)
    parser.add_argument("--window-duration", type=float, default=30.0)
    parser.add_argument("--search-range", type=float, default=60.0)
    parser.add_argument("--coarse-step", type=float, default=0.5)
    parser.add_argument("--fine-step", type=float, default=0.05)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--min-speech-ms", type=float, default=120.0)
    parser.add_argument("--min-silence-ms", type=float, default=180.0)
    parser.add_argument("--profile", action="store_true", help="Print timing breakdown.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
    )

    if args.json:
        print(
            json.dumps(
                {
                    "offset_seconds": round(result.offset_seconds, 3),
                    "best_overlap_percent": round(result.best_overlap_percent, 2),
                    "zero_overlap_percent": round(result.zero_overlap_percent, 2),
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
    print(f"Sampled audio: {format_timestamp(result.sampled_audio_seconds)}")
    print(f"Elapsed: {format_timestamp(result.elapsed_seconds)}")
    if args.profile:
        print("Timing breakdown:")
        for key, value in result.timings.items():
            print(f"  {key}: {format_timestamp(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
