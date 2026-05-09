from __future__ import annotations

import argparse
import time
from pathlib import Path

from silero_vad import load_silero_vad

from fast_sync_lib.alignment import compute_metrics, find_best_offset
from fast_sync_lib.media import (
    collect_vad_intervals,
    choose_window_centers,
    probe_duration,
)
from fast_sync_lib.subtitles import parse_srt
from fast_sync_lib.timecode import format_timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fast subtitle sync estimation from a video file and an SRT subtitle."
    )
    parser.add_argument("video_file", help="Path to the source video file.")
    parser.add_argument("srt_file", help="Path to the subtitle .srt file.")
    parser.add_argument(
        "--window-count",
        type=int,
        default=6,
        help="How many short windows to sample from the video. Default: 6.",
    )
    parser.add_argument(
        "--window-duration",
        type=float,
        default=90.0,
        help="Duration in seconds for each sampled window. Default: 90.",
    )
    parser.add_argument(
        "--search-range",
        type=float,
        default=180.0,
        help="Search range in seconds for subtitle offset. Default: 180.",
    )
    parser.add_argument(
        "--coarse-step",
        type=float,
        default=0.5,
        help="Coarse search step in seconds. Default: 0.5.",
    )
    parser.add_argument(
        "--fine-step",
        type=float,
        default=0.1,
        help="Fine search step in seconds. Default: 0.1.",
    )
    parser.add_argument(
        "--ultra-step",
        type=float,
        default=0.02,
        help="Final search refinement step in seconds. Default: 0.02.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Silero VAD threshold. Default: 0.5.",
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> int:
    video_path = Path(args.video_file)
    srt_path = Path(args.srt_file)

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    started_at = time.perf_counter()
    subtitle_intervals = parse_srt(srt_path)
    video_duration = probe_duration(video_path)
    centers = choose_window_centers(
        subtitle_intervals,
        video_duration=video_duration,
        window_count=args.window_count,
        window_duration=args.window_duration,
    )

    model = load_silero_vad()
    vad_intervals, windows = collect_vad_intervals(
        video_path=video_path,
        model=model,
        centers=centers,
        window_duration=args.window_duration,
        threshold=args.threshold,
    )
    if not vad_intervals:
        raise RuntimeError("No speech intervals detected in sampled windows.")

    best_metrics = find_best_offset(
        vad_intervals=vad_intervals,
        subtitle_intervals=subtitle_intervals,
        windows=windows,
        search_range=args.search_range,
        coarse_step=args.coarse_step,
        fine_step=args.fine_step,
        ultra_step=args.ultra_step,
    )
    zero_metrics = compute_metrics(vad_intervals, subtitle_intervals, windows, 0.0)

    elapsed = time.perf_counter() - started_at
    sampled_total = sum(window.duration for window in windows)
    print(f"Video: {video_path}")
    print(f"Subtitle: {srt_path}")
    print(f"Sample windows: {len(windows)}")
    print(f"Sampled audio total: {format_timestamp(sampled_total)}")
    print(f"Zero-offset overlap: {zero_metrics.iou_percent:.2f}%")
    print(
        "Best offset: "
        f"{best_metrics.offset_seconds:+.2f}s "
        f"({format_timestamp(best_metrics.offset_seconds)})"
    )
    print(f"Best overlap: {best_metrics.iou_percent:.2f}%")
    print(f"Elapsed: {format_timestamp(elapsed)}")
    return 0
