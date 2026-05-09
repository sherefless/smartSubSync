#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


TIMESTAMP_RE = re.compile(
    r"(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2}),(?P<milliseconds>\d{3})"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an interactive alignment report for one VAD JSON and one SRT file."
    )
    parser.add_argument(
        "--json-file",
        help="Path to a VAD JSON file. If omitted, you can pick interactively.",
    )
    parser.add_argument(
        "--srt-file",
        help="Path to an SRT subtitle file. If omitted, you can pick interactively.",
    )
    parser.add_argument(
        "--search-range",
        type=float,
        default=180.0,
        help="Search range in seconds for the best subtitle offset. Default: 180.",
    )
    parser.add_argument(
        "--coarse-step",
        type=float,
        default=1.0,
        help="Coarse search step in seconds. Default: 1.0.",
    )
    parser.add_argument(
        "--fine-step",
        type=float,
        default=0.1,
        help="Fine search step in seconds. Default: 0.1.",
    )
    parser.add_argument(
        "--ultra-step",
        type=float,
        default=0.01,
        help="Final refinement step in seconds. Default: 0.01.",
    )
    parser.add_argument(
        "--output-dir",
        default="comparison_reports",
        help="Directory where the HTML report will be written.",
    )
    return parser.parse_args()


def parse_timestamp(value: str) -> float:
    match = TIMESTAMP_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid timestamp: {value}")

    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    milliseconds = int(match.group("milliseconds"))
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def format_timestamp(seconds: float) -> str:
    negative = seconds < 0
    total_milliseconds = round(abs(seconds) * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    prefix = "-" if negative else ""
    return f"{prefix}{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def choose_file(files: list[Path], label: str) -> Path:
    if not files:
        raise FileNotFoundError(f"No files available for {label}")

    print(f"Available {label} files:")
    for index, path in enumerate(files, start=1):
        print(f"{index}. {path.name}")

    selection = input(f"Select {label} file number (1-{len(files)}): ").strip()
    try:
        selected_index = int(selection)
    except ValueError as exc:
        raise ValueError(f"Invalid {label} selection: {selection}") from exc

    if selected_index < 1 or selected_index > len(files):
        raise ValueError(f"{label} selection must be between 1 and {len(files)}")

    return files[selected_index - 1]


def resolve_input_file(provided: str | None, files: list[Path], label: str) -> Path:
    if provided:
        path = Path(provided)
        if not path.exists():
            raise FileNotFoundError(f"{label} file not found: {path}")
        return path
    return choose_file(files, label)


def read_text_with_fallbacks(path: Path) -> str:
    encodings = ("utf-8-sig", "utf-8", "cp1254", "latin-1")
    last_error: UnicodeDecodeError | None = None
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc

    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Could not decode {path} with tried encodings: {encodings}. Last error: {last_error}",
    )


def merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    filtered = sorted((start, end) for start, end in intervals if end > start)
    if not filtered:
        return []

    merged = [filtered[0]]
    for start, end in filtered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def parse_vad_json(path: Path) -> tuple[list[tuple[float, float]], float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    intervals = [
        (parse_timestamp(segment["start"]), parse_timestamp(segment["end"]))
        for segment in payload["speech_segments"]
    ]
    return merge_intervals(intervals), float(payload["duration_sec"])


def parse_srt(path: Path) -> tuple[list[tuple[float, float]], float]:
    content = read_text_with_fallbacks(path)
    intervals: list[tuple[float, float]] = []
    max_end = 0.0

    for line in content.splitlines():
        if "-->" not in line:
            continue
        start_raw, end_raw = [part.strip() for part in line.split("-->", 1)]
        start = parse_timestamp(start_raw)
        end = parse_timestamp(end_raw)
        intervals.append((start, end))
        max_end = max(max_end, end)

    if not intervals:
        raise ValueError(f"No subtitle timing rows found in: {path}")

    return merge_intervals(intervals), max_end


def shift_intervals(
    intervals: list[tuple[float, float]], offset_seconds: float
) -> list[tuple[float, float]]:
    shifted: list[tuple[float, float]] = []
    for start, end in intervals:
        shifted_start = start + offset_seconds
        shifted_end = end + offset_seconds
        if shifted_end <= 0:
            continue
        shifted.append((max(0.0, shifted_start), max(0.0, shifted_end)))
    return shifted


def total_duration(intervals: list[tuple[float, float]]) -> float:
    return sum(end - start for start, end in intervals)


def overlap_duration(
    left: list[tuple[float, float]], right: list[tuple[float, float]]
) -> float:
    total = 0.0
    left_index = 0
    right_index = 0

    while left_index < len(left) and right_index < len(right):
        left_start, left_end = left[left_index]
        right_start, right_end = right[right_index]

        start = max(left_start, right_start)
        end = min(left_end, right_end)
        if end > start:
            total += end - start

        if left_end <= right_end:
            left_index += 1
        else:
            right_index += 1

    return total


def overlap_intervals(
    left: list[tuple[float, float]], right: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    overlaps: list[tuple[float, float]] = []
    left_index = 0
    right_index = 0

    while left_index < len(left) and right_index < len(right):
        left_start, left_end = left[left_index]
        right_start, right_end = right[right_index]

        start = max(left_start, right_start)
        end = min(left_end, right_end)
        if end > start:
            overlaps.append((start, end))

        if left_end <= right_end:
            left_index += 1
        else:
            right_index += 1

    return overlaps


def compute_metrics(
    vad_intervals: list[tuple[float, float]],
    subtitle_intervals: list[tuple[float, float]],
    offset_seconds: float,
) -> dict[str, float]:
    shifted_subtitles = shift_intervals(subtitle_intervals, offset_seconds)
    vad_total = total_duration(vad_intervals)
    subtitle_total = total_duration(shifted_subtitles)
    overlap_total = overlap_duration(vad_intervals, shifted_subtitles)
    union_total = vad_total + subtitle_total - overlap_total

    return {
        "offset_seconds": offset_seconds,
        "vad_total_seconds": vad_total,
        "subtitle_total_seconds": subtitle_total,
        "overlap_seconds": overlap_total,
        "union_seconds": union_total,
        "iou_percent": 100.0 * overlap_total / union_total if union_total else 0.0,
        "subtitle_coverage_percent": (
            100.0 * overlap_total / subtitle_total if subtitle_total else 0.0
        ),
        "vad_coverage_percent": 100.0 * overlap_total / vad_total if vad_total else 0.0,
    }


def frange(start: float, stop: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("Step must be positive")

    values: list[float] = []
    current = start
    epsilon = step / 10
    while current <= stop + epsilon:
        values.append(round(current, 6))
        current += step
    return values


def find_best_offset(
    vad_intervals: list[tuple[float, float]],
    subtitle_intervals: list[tuple[float, float]],
    search_range: float,
    coarse_step: float,
    fine_step: float,
    ultra_step: float,
) -> dict[str, float]:
    best_metrics = compute_metrics(vad_intervals, subtitle_intervals, 0.0)

    for offset in frange(-search_range, search_range, coarse_step):
        metrics = compute_metrics(vad_intervals, subtitle_intervals, offset)
        if metrics["iou_percent"] > best_metrics["iou_percent"]:
            best_metrics = metrics

    coarse_best = best_metrics["offset_seconds"]
    for offset in frange(coarse_best - coarse_step, coarse_best + coarse_step, fine_step):
        metrics = compute_metrics(vad_intervals, subtitle_intervals, offset)
        if metrics["iou_percent"] > best_metrics["iou_percent"]:
            best_metrics = metrics

    fine_best = best_metrics["offset_seconds"]
    for offset in frange(fine_best - fine_step, fine_best + fine_step, ultra_step):
        metrics = compute_metrics(vad_intervals, subtitle_intervals, offset)
        if metrics["iou_percent"] > best_metrics["iou_percent"]:
            best_metrics = metrics

    return best_metrics


def intervals_to_js(intervals: list[tuple[float, float]]) -> str:
    return json.dumps(
        [{"start": round(start, 6), "end": round(end, 6)} for start, end in intervals]
    )


def build_html_report(
    json_path: Path,
    srt_path: Path,
    vad_intervals: list[tuple[float, float]],
    subtitle_intervals: list[tuple[float, float]],
    report_duration: float,
    best_metrics: dict[str, float],
    output_path: Path,
) -> str:
    vad_json = intervals_to_js(vad_intervals)
    subtitle_json = intervals_to_js(subtitle_intervals)
    escaped_json_label = html.escape(json_path.name)
    escaped_srt_label = html.escape(srt_path.name)
    default_slider_min = -max(30.0, abs(best_metrics["offset_seconds"]) + 10.0)
    default_slider_max = max(30.0, abs(best_metrics["offset_seconds"]) + 10.0)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alignment Report</title>
  <style>
    :root {{
      --bg: #f3efe5;
      --panel: #fffaf0;
      --ink: #1f2430;
      --muted: #6b7280;
      --vad: #0f766e;
      --srt: #b45309;
      --overlap: #16a34a;
      --grid: #d6d3d1;
      --accent: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #ede7db 0%, #f8f4eb 100%);
      color: var(--ink);
    }}
    .wrap {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid #e7dcc7;
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 20px 50px rgba(31, 36, 48, 0.08);
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 32px;
      line-height: 1.1;
    }}
    .sub {{
      color: var(--muted);
      margin-bottom: 16px;
    }}
    .files {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 20px;
    }}
    .file-card {{
      background: #fcf8ef;
      border: 1px solid #eadfc7;
      border-radius: 14px;
      padding: 14px;
    }}
    .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }}
    .file-name {{
      font-weight: 600;
      word-break: break-word;
    }}
    .controls {{
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 16px;
      align-items: center;
      margin-bottom: 18px;
    }}
    .slider-box {{
      background: #fcf8ef;
      border: 1px solid #eadfc7;
      border-radius: 14px;
      padding: 16px;
    }}
    .slider-row {{
      display: grid;
      grid-template-columns: 90px 1fr 120px;
      gap: 12px;
      align-items: center;
    }}
    input[type="range"] {{
      width: 100%;
    }}
    button {{
      border: 0;
      background: var(--ink);
      color: white;
      padding: 12px 16px;
      border-radius: 12px;
      cursor: pointer;
      font-weight: 600;
    }}
    button.secondary {{
      background: #d97706;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: #fcf8ef;
      border: 1px solid #eadfc7;
      border-radius: 14px;
      padding: 14px;
    }}
    .metric .value {{
      font-size: 24px;
      font-weight: 700;
      margin-top: 6px;
    }}
    .chart-card {{
      background: #fcf8ef;
      border: 1px solid #eadfc7;
      border-radius: 16px;
      padding: 16px;
      overflow: auto;
    }}
    .legend {{
      display: flex;
      gap: 18px;
      margin-bottom: 12px;
      color: var(--muted);
      flex-wrap: wrap;
    }}
    .legend span::before {{
      content: "";
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
      margin-right: 8px;
      vertical-align: middle;
    }}
    .legend .vad::before {{ background: var(--vad); }}
    .legend .srt::before {{ background: var(--srt); }}
    .legend .overlap::before {{ background: var(--overlap); }}
    .axis-note {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 14px;
    }}
    code {{
      font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
    }}
    @media (max-width: 980px) {{
      .files, .metrics, .controls {{
        grid-template-columns: 1fr;
      }}
      .slider-row {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>VAD / Subtitle Alignment Viewer</h1>
      <div class="sub">
        Positive offset shifts subtitles later in time. Move the slider to see live overlap changes.
      </div>

      <div class="files">
        <div class="file-card">
          <div class="label">VAD JSON</div>
          <div class="file-name">{escaped_json_label}</div>
        </div>
        <div class="file-card">
          <div class="label">Subtitle SRT</div>
          <div class="file-name">{escaped_srt_label}</div>
        </div>
      </div>

      <div class="controls">
        <div class="slider-box">
          <div class="label">Subtitle Offset</div>
          <div class="slider-row">
            <code id="slider-min">{format_timestamp(default_slider_min)}</code>
            <input id="offset-slider" type="range" min="{default_slider_min}" max="{default_slider_max}" step="0.01" value="{best_metrics["offset_seconds"]}">
            <code id="slider-max">{format_timestamp(default_slider_max)}</code>
          </div>
        </div>
        <button id="best-offset-button">Jump To Best Offset</button>
        <button id="zero-offset-button" class="secondary">Reset To 0</button>
      </div>

      <div class="metrics">
        <div class="metric">
          <div class="label">Current Offset</div>
          <div class="value" id="current-offset"></div>
        </div>
        <div class="metric">
          <div class="label">Overall Overlap</div>
          <div class="value" id="iou-percent"></div>
        </div>
        <div class="metric">
          <div class="label">Subtitle Coverage</div>
          <div class="value" id="subtitle-coverage"></div>
        </div>
        <div class="metric">
          <div class="label">VAD Coverage</div>
          <div class="value" id="vad-coverage"></div>
        </div>
        <div class="metric">
          <div class="label">Overlap Duration</div>
          <div class="value" id="overlap-duration"></div>
        </div>
        <div class="metric">
          <div class="label">Best Offset</div>
          <div class="value" id="best-offset">{format_timestamp(best_metrics["offset_seconds"])}</div>
        </div>
      </div>

      <div class="chart-card">
        <div class="legend">
          <span class="vad">VAD speech intervals</span>
          <span class="srt">Shifted subtitle intervals</span>
          <span class="overlap">Intersection</span>
        </div>
        <svg id="timeline" viewBox="0 0 1600 250" width="100%" height="250" aria-label="Alignment timeline"></svg>
        <div class="axis-note">
          Timeline spans from <code>00:00:00,000</code> to <code>{format_timestamp(report_duration)}</code>.
          Report saved to <code>{html.escape(str(output_path))}</code>.
        </div>
      </div>
    </div>
  </div>

  <script>
    const vadIntervals = {vad_json};
    const subtitleIntervals = {subtitle_json};
    const totalDuration = {round(report_duration, 6)};
    const bestOffset = {round(best_metrics["offset_seconds"], 6)};
    const slider = document.getElementById("offset-slider");
    const svg = document.getElementById("timeline");
    const chartWidth = 1500;
    const leftPad = 60;
    const rightPad = 40;
    const usableWidth = chartWidth - leftPad - rightPad;
    const rows = {{
      vad: {{ y: 42, height: 28, color: "#0f766e" }},
      srt: {{ y: 108, height: 28, color: "#b45309" }},
      overlap: {{ y: 174, height: 28, color: "#16a34a" }}
    }};

    function formatTimestamp(seconds) {{
      const negative = seconds < 0;
      const totalMilliseconds = Math.round(Math.abs(seconds) * 1000);
      const hours = Math.floor(totalMilliseconds / 3600000);
      const minutes = Math.floor((totalMilliseconds % 3600000) / 60000);
      const secs = Math.floor((totalMilliseconds % 60000) / 1000);
      const milliseconds = totalMilliseconds % 1000;
      const prefix = negative ? "-" : "";
      return `${{prefix}}${{String(hours).padStart(2, "0")}}:${{String(minutes).padStart(2, "0")}}:${{String(secs).padStart(2, "0")}},${{String(milliseconds).padStart(3, "0")}}`;
    }}

    function totalDurationOf(intervals) {{
      return intervals.reduce((sum, interval) => sum + (interval.end - interval.start), 0);
    }}

    function shiftIntervals(intervals, offset) {{
      return intervals
        .map((interval) => ({{
          start: Math.max(0, interval.start + offset),
          end: Math.max(0, interval.end + offset)
        }}))
        .filter((interval) => interval.end > interval.start);
    }}

    function overlapIntervals(left, right) {{
      const overlaps = [];
      let i = 0;
      let j = 0;

      while (i < left.length && j < right.length) {{
        const start = Math.max(left[i].start, right[j].start);
        const end = Math.min(left[i].end, right[j].end);
        if (end > start) {{
          overlaps.push({{ start, end }});
        }}

        if (left[i].end <= right[j].end) {{
          i += 1;
        }} else {{
          j += 1;
        }}
      }}

      return overlaps;
    }}

    function computeMetrics(offset) {{
      const shifted = shiftIntervals(subtitleIntervals, offset);
      const overlaps = overlapIntervals(vadIntervals, shifted);
      const vadTotal = totalDurationOf(vadIntervals);
      const subtitleTotal = totalDurationOf(shifted);
      const overlapTotal = totalDurationOf(overlaps);
      const unionTotal = vadTotal + subtitleTotal - overlapTotal;
      return {{
        shifted,
        overlaps,
        vadTotal,
        subtitleTotal,
        overlapTotal,
        iouPercent: unionTotal ? (overlapTotal / unionTotal) * 100 : 0,
        subtitleCoveragePercent: subtitleTotal ? (overlapTotal / subtitleTotal) * 100 : 0,
        vadCoveragePercent: vadTotal ? (overlapTotal / vadTotal) * 100 : 0
      }};
    }}

    function xScale(seconds) {{
      return leftPad + (seconds / totalDuration) * usableWidth;
    }}

    function rectFor(interval, row) {{
      const x = xScale(interval.start);
      const width = Math.max(1, xScale(interval.end) - x);
      return `<rect x="${{x.toFixed(2)}}" y="${{row.y}}" width="${{width.toFixed(2)}}" height="${{row.height}}" rx="4" fill="${{row.color}}"></rect>`;
    }}

    function gridSvg() {{
      const marks = 10;
      let parts = "";
      for (let i = 0; i <= marks; i += 1) {{
        const t = (totalDuration / marks) * i;
        const x = xScale(t);
        parts += `<line x1="${{x.toFixed(2)}}" y1="20" x2="${{x.toFixed(2)}}" y2="220" stroke="#d6d3d1" stroke-width="1"></line>`;
        parts += `<text x="${{x.toFixed(2)}}" y="236" text-anchor="middle" fill="#6b7280" font-size="12">${{formatTimestamp(t)}}</text>`;
      }}
      return parts;
    }}

    function rowLabels() {{
      return `
        <text x="12" y="60" fill="#1f2430" font-size="14" font-weight="700">VAD</text>
        <text x="12" y="126" fill="#1f2430" font-size="14" font-weight="700">SRT</text>
        <text x="12" y="192" fill="#1f2430" font-size="14" font-weight="700">Overlap</text>
      `;
    }}

    function render(offset) {{
      const metrics = computeMetrics(offset);

      document.getElementById("current-offset").textContent = formatTimestamp(offset);
      document.getElementById("iou-percent").textContent = `${{metrics.iouPercent.toFixed(2)}}%`;
      document.getElementById("subtitle-coverage").textContent = `${{metrics.subtitleCoveragePercent.toFixed(2)}}%`;
      document.getElementById("vad-coverage").textContent = `${{metrics.vadCoveragePercent.toFixed(2)}}%`;
      document.getElementById("overlap-duration").textContent = formatTimestamp(metrics.overlapTotal);

      const vadRects = vadIntervals.map((interval) => rectFor(interval, rows.vad)).join("");
      const subtitleRects = metrics.shifted.map((interval) => rectFor(interval, rows.srt)).join("");
      const overlapRects = metrics.overlaps.map((interval) => rectFor(interval, rows.overlap)).join("");

      svg.innerHTML = `
        <rect x="0" y="0" width="1600" height="250" rx="14" fill="#fffdf8"></rect>
        ${{gridSvg()}}
        ${{rowLabels()}}
        ${{vadRects}}
        ${{subtitleRects}}
        ${{overlapRects}}
      `;
    }}

    slider.addEventListener("input", () => {{
      render(Number(slider.value));
    }});

    document.getElementById("best-offset-button").addEventListener("click", () => {{
      slider.value = String(bestOffset);
      render(bestOffset);
    }});

    document.getElementById("zero-offset-button").addEventListener("click", () => {{
      slider.value = "0";
      render(0);
    }});

    render(Number(slider.value));
  </script>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    result_files = sorted(Path("results").glob("*.json"))
    subtitle_files = sorted(Path("subtitles").glob("*.srt"))

    json_path = resolve_input_file(args.json_file, result_files, "JSON")
    srt_path = resolve_input_file(args.srt_file, subtitle_files, "SRT")

    vad_intervals, vad_duration = parse_vad_json(json_path)
    subtitle_intervals, subtitle_duration = parse_srt(srt_path)
    report_duration = max(vad_duration, subtitle_duration + args.search_range)

    best_metrics = find_best_offset(
        vad_intervals,
        subtitle_intervals,
        search_range=args.search_range,
        coarse_step=args.coarse_step,
        fine_step=args.fine_step,
        ultra_step=args.ultra_step,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{json_path.stem}__vs__{srt_path.stem}.html"

    html_report = build_html_report(
        json_path=json_path,
        srt_path=srt_path,
        vad_intervals=vad_intervals,
        subtitle_intervals=subtitle_intervals,
        report_duration=report_duration,
        best_metrics=best_metrics,
        output_path=output_path,
    )
    output_path.write_text(html_report, encoding="utf-8")

    zero_metrics = compute_metrics(vad_intervals, subtitle_intervals, 0.0)
    print(f"JSON file: {json_path}")
    print(f"SRT file: {srt_path}")
    print(f"Report: {output_path}")
    print(f"Zero-offset overlap: {zero_metrics['iou_percent']:.2f}%")
    print(
        "Best offset: "
        f"{best_metrics['offset_seconds']:+.2f}s "
        f"({format_timestamp(best_metrics['offset_seconds'])})"
    )
    print(f"Best overlap: {best_metrics['iou_percent']:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
