from __future__ import annotations

import re


TIMESTAMP_RE = re.compile(
    r"(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2}),(?P<milliseconds>\d{3})"
)


def parse_timestamp(value: str) -> float:
    match = TIMESTAMP_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid timestamp: {value}")

    return (
        int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + int(match.group("seconds"))
        + int(match.group("milliseconds")) / 1000
    )


def format_timestamp(seconds: float) -> str:
    negative = seconds < 0
    total_milliseconds = round(abs(seconds) * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    prefix = "-" if negative else ""
    return f"{prefix}{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"
