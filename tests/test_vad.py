from __future__ import annotations

import unittest

from smartsubsync.media import SAMPLE_RATE
from smartsubsync.vad import silero_segments_to_intervals


class SileroVadTests(unittest.TestCase):
    def test_silero_segments_to_intervals(self) -> None:
        segments = [
            {"start": 1600, "end": 3840},
            {"start": 8000, "end": 11520},
        ]

        self.assertEqual(
            silero_segments_to_intervals(segments),
            [(1600 / SAMPLE_RATE, 3840 / SAMPLE_RATE), (8000 / SAMPLE_RATE, 11520 / SAMPLE_RATE)],
        )


if __name__ == "__main__":
    unittest.main()
