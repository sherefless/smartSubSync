from __future__ import annotations

import unittest

from fast_sync_lib.intervals import (
    clip_intervals_to_windows,
    merge_intervals,
    overlap_duration,
    shift_intervals,
)
from fast_sync_lib.types import Window


class IntervalTests(unittest.TestCase):
    def test_merge_intervals(self) -> None:
        merged = merge_intervals([(0.0, 1.0), (0.5, 2.0), (3.0, 4.0)])
        self.assertEqual(merged, [(0.0, 2.0), (3.0, 4.0)])

    def test_shift_intervals(self) -> None:
        shifted = shift_intervals([(1.0, 2.0)], 3.5)
        self.assertEqual(shifted, [(4.5, 5.5)])

    def test_clip_intervals_to_windows(self) -> None:
        windows = [Window(start=10.0, end=20.0, center=15.0)]
        clipped = clip_intervals_to_windows([(5.0, 12.0), (18.0, 25.0)], windows)
        self.assertEqual(clipped, [(10.0, 12.0), (18.0, 20.0)])

    def test_overlap_duration(self) -> None:
        overlap = overlap_duration([(0.0, 2.0), (4.0, 6.0)], [(1.0, 5.0)])
        self.assertEqual(overlap, 2.0)


if __name__ == "__main__":
    unittest.main()
