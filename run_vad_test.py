#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import torch
from silero_vad import get_speech_timestamps, load_silero_vad


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Silero VAD on a WAV file or WAV files in a directory."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default="testSamples",
        help="A mono 16 kHz PCM WAV file or a directory containing WAV files.",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="How many speech segments to include in the preview.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Speech threshold passed to Silero VAD.",
    )
    parser.add_argument(
        "--pick",
        type=int,
        default=None,
        help="Pick a file by its 1-based index when the input path is a directory.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all WAV files in the directory without prompting.",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Directory where per-audio JSON output files will be written.",
    )
    return parser.parse_args()


def load_wav_tensor(path: Path) -> tuple[torch.Tensor, int, float]:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        duration_sec = frame_count / sample_rate

        if channels != 1:
            raise ValueError(f"Expected mono WAV, got {channels} channels")
        if sample_width != 2:
            raise ValueError(f"Expected 16-bit PCM WAV, got {sample_width * 8}-bit")
        if sample_rate != 16000:
            raise ValueError(f"Expected 16 kHz WAV, got {sample_rate} Hz")

        audio_bytes = bytearray(wav_file.readframes(frame_count))

    audio_tensor = torch.frombuffer(audio_bytes, dtype=torch.int16).to(torch.float32)
    audio_tensor = audio_tensor / 32768.0
    return audio_tensor, sample_rate, duration_sec


def format_timestamp(seconds: float) -> str:
    total_milliseconds = round(seconds * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def format_timestamp_from_samples(sample_index: int, sample_rate: int) -> str:
    return format_timestamp(sample_index / sample_rate)


def summarize_segments(
    segments: list[dict[str, int]], sample_rate: int
) -> tuple[float, float]:
    total_speech_sec = sum(
        (segment["end"] - segment["start"]) / sample_rate for segment in segments
    )
    total_silence_sec = 0.0

    for index in range(1, len(segments)):
        total_silence_sec += (
            segments[index]["start"] - segments[index - 1]["end"]
        ) / sample_rate

    return total_speech_sec, total_silence_sec


def resolve_wav_files(input_path: Path, pick: int | None, process_all: bool) -> list[Path]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    if input_path.is_file():
        if input_path.suffix.lower() != ".wav":
            raise ValueError(f"Expected a .wav file, got: {input_path.name}")
        return [input_path]

    wav_files = sorted(input_path.glob("*.wav"))
    if not wav_files:
        raise FileNotFoundError(f"No .wav files found in: {input_path}")

    if process_all:
        return wav_files

    if pick is not None:
        if pick < 1 or pick > len(wav_files):
            raise ValueError(f"--pick must be between 1 and {len(wav_files)}")
        return [wav_files[pick - 1]]

    print("Available test files:")
    for index, wav_file in enumerate(wav_files, start=1):
        print(f"{index}. {wav_file.name}")

    selection = input(
        f"Select a file number (1-{len(wav_files)}) or type 'all': "
    ).strip()

    if selection.lower() == "all":
        return wav_files

    try:
        chosen_index = int(selection)
    except ValueError as exc:
        raise ValueError("Invalid selection. Enter a file number or 'all'.") from exc

    if chosen_index < 1 or chosen_index > len(wav_files):
        raise ValueError(f"Selection must be between 1 and {len(wav_files)}")

    return [wav_files[chosen_index - 1]]


def write_result_json(
    output_dir: Path,
    wav_path: Path,
    sample_rate: int,
    duration_sec: float,
    speech_segments: list[dict[str, int]],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{wav_path.stem}.json"
    formatted_segments = [
        {
            "sample_start": segment["start"],
            "sample_end": segment["end"],
            "start": format_timestamp_from_samples(segment["start"], sample_rate),
            "end": format_timestamp_from_samples(segment["end"], sample_rate),
        }
        for segment in speech_segments
    ]
    payload = {
        "file": wav_path.name,
        "sample_rate": sample_rate,
        "duration_sec": round(duration_sec, 2),
        "speech_segment_count": len(speech_segments),
        "speech_segments": formatted_segments,
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)
    wav_files = resolve_wav_files(input_path, pick=args.pick, process_all=args.all)

    started_at = time.perf_counter()
    model = load_silero_vad()
    processed_files: list[dict[str, object]] = []
    total_audio_sec = 0.0
    total_speech_sec_all = 0.0

    for wav_path in wav_files:
        audio_tensor, sample_rate, duration_sec = load_wav_tensor(wav_path)
        speech_segments = get_speech_timestamps(
            audio_tensor,
            model,
            threshold=args.threshold,
            sampling_rate=sample_rate,
            return_seconds=False,
        )

        file_speech_sec, total_silence_sec = summarize_segments(
            speech_segments, sample_rate
        )
        output_path = write_result_json(
            output_dir,
            wav_path,
            sample_rate,
            duration_sec,
            speech_segments,
        )
        processed_files.append(
            {
                "file": wav_path.name,
                "result_file": str(output_path),
                "duration_sec": round(duration_sec, 2),
                "speech_segment_count": len(speech_segments),
                "speech_total_sec": round(file_speech_sec, 2),
            }
        )
        total_audio_sec += duration_sec
        total_speech_sec_all += file_speech_sec

    elapsed_sec = time.perf_counter() - started_at
    print(f"Processed files: {len(processed_files)}")
    print(f"Total audio duration: {format_timestamp(total_audio_sec)}")
    print(f"Total speech duration: {format_timestamp(total_speech_sec_all)}")
    print(f"Total processing time: {format_timestamp(elapsed_sec)}")
    for item in processed_files:
        print(
            f"- {item['file']} -> {item['result_file']} "
            f"({item['speech_segment_count']} segments, "
            f"speech {format_timestamp(item['speech_total_sec'])})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
