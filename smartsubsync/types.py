from __future__ import annotations

from dataclasses import dataclass


Interval = tuple[float, float]


@dataclass(frozen=True)
class Window:
    start: float
    end: float
    center: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class SyncResult:
    offset_seconds: float
    best_overlap_percent: float
    zero_overlap_percent: float
    overlap_improvement_percent: float
    reliable: bool
    retry_used: bool
    sampled_audio_seconds: float
    window_count: int
    elapsed_seconds: float
    timings: dict[str, float]
