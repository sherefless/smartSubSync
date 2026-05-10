from __future__ import annotations

import unittest

from smartsubsync.timecode import format_timestamp, parse_timestamp


class TimecodeTests(unittest.TestCase):
    def test_parse_timestamp(self) -> None:
        self.assertAlmostEqual(parse_timestamp("00:01:02,345"), 62.345)

    def test_format_timestamp(self) -> None:
        self.assertEqual(format_timestamp(62.345), "00:01:02,345")

    def test_format_negative_timestamp(self) -> None:
        self.assertEqual(format_timestamp(-7.58), "-00:00:07,580")


if __name__ == "__main__":
    unittest.main()
