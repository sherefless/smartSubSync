from __future__ import annotations

import unittest

from fast_sync_lib.alignment import compute_metrics, find_best_offset
from fast_sync_lib.types import Window


class AlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows = [Window(start=0.0, end=30.0, center=15.0)]
        self.vad = [(10.0, 12.0), (20.0, 22.0)]
        self.subtitles = [(8.0, 10.0), (18.0, 20.0)]

    def test_compute_metrics(self) -> None:
        metrics = compute_metrics(self.vad, self.subtitles, self.windows, 2.0)
        self.assertGreater(metrics.iou_percent, 99.0)

    def test_find_best_offset(self) -> None:
        best = find_best_offset(
            vad_intervals=self.vad,
            subtitle_intervals=self.subtitles,
            windows=self.windows,
            search_range=5.0,
            coarse_step=1.0,
            fine_step=0.1,
            ultra_step=0.01,
        )
        self.assertAlmostEqual(best.offset_seconds, 2.0, places=1)


if __name__ == "__main__":
    unittest.main()
