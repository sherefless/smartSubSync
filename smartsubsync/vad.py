from __future__ import annotations

from typing import Any

from smartsubsync.errors import SmartSubSyncError
from smartsubsync.intervals import merge_intervals
from smartsubsync.media import SAMPLE_RATE
from smartsubsync.types import Interval


def load_silero_model() -> Any:
    try:
        from silero_vad import load_silero_vad
    except ImportError as error:
        raise SmartSubSyncError(
            "silero-vad is not installed. Run the installer again or install dependencies."
        ) from error

    try:
        return load_silero_vad()
    except Exception as error:
        raise SmartSubSyncError(f"Could not load Silero VAD model: {error}") from error


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

    try:
        import torch
        from silero_vad import get_speech_timestamps
    except ImportError as error:
        raise SmartSubSyncError(
            "Silero VAD dependencies are missing. Run the installer again."
        ) from error

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
