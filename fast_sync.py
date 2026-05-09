#!/usr/bin/env python3

from __future__ import annotations

from fast_sync_lib.cli import parse_args, run


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
