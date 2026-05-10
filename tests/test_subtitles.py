from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from smartsubsync.subtitles import parse_srt


class SubtitleTests(unittest.TestCase):
    def test_parse_srt(self) -> None:
        content = """1
00:00:01,000 --> 00:00:02,500
Hello

2
00:00:03,000 --> 00:00:04,000
World
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            srt_path = Path(temp_dir) / "sample.srt"
            srt_path.write_text(content, encoding="utf-8")
            intervals = parse_srt(srt_path)

        self.assertEqual(intervals, [(1.0, 2.5), (3.0, 4.0)])


if __name__ == "__main__":
    unittest.main()
