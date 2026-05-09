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

    def as_dict(self) -> dict[str, float]:
        return {
            "start": self.start,
            "end": self.end,
            "center": self.center,
        }


@dataclass(frozen=True)
class AlignmentMetrics:
    offset_seconds: float
    vad_total_seconds: float
    subtitle_total_seconds: float
    overlap_seconds: float
    union_seconds: float
    iou_percent: float
    subtitle_coverage_percent: float
    vad_coverage_percent: float
