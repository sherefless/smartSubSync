from __future__ import annotations

from typing import Any

from smartsubsync.intervals import merge_intervals
from smartsubsync.media import SAMPLE_RATE
from smartsubsync.types import Interval


def load_silero_model() -> Any:
    from silero_vad import load_silero_vad

    return load_silero_vad()


def detect_silero_speech(
    audio: list[float],
    *,
    model: Any,
    threshold: float,
    min_speech_ms: float,
    min_silence_ms: float,
) -> list[Interval]:
    if not audio:
        return []

    import torch
    from silero_vad import get_speech_timestamps

    audio_tensor = torch.tensor(audio, dtype=torch.float32)
    segments = get_speech_timestamps(
        audio_tensor,
        model,
        threshold=threshold,
        sampling_rate=SAMPLE_RATE,
        min_speech_duration_ms=int(min_speech_ms),
        min_silence_duration_ms=int(min_silence_ms),
        return_seconds=False,
    )
    return silero_segments_to_intervals(segments)


def silero_segments_to_intervals(segments: list[dict[str, int]]) -> list[Interval]:
    return merge_intervals(
        [(segment["start"] / SAMPLE_RATE, segment["end"] / SAMPLE_RATE) for segment in segments]
    )
