#!/usr/bin/env python3

"""Decode a video and report per-second RMS/peak plus suspicious silent runs."""

from __future__ import annotations

import argparse
import array
import json
import math
import subprocess
import tempfile
import wave
from pathlib import Path


def db(value: float, full_scale: float = 32768.0) -> float:
    if value <= 0:
        return -120.0
    return 20.0 * math.log10(value / full_scale)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    video = args.video.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"],
        check=True,
    )
    with tempfile.TemporaryDirectory(prefix="audio-second-check-") as temp_name:
        wav_path = Path(temp_name) / "audio.wav"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn",
                "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(wav_path),
            ],
            check=True,
        )
        with wave.open(str(wav_path), "rb") as stream:
            rate = stream.getframerate()
            samples = array.array("h", stream.readframes(stream.getnframes()))

    rows = []
    for second, start in enumerate(range(0, len(samples), rate)):
        chunk = samples[start:start + rate]
        if not chunk:
            continue
        squares = sum(sample * sample for sample in chunk)
        rms = math.sqrt(squares / len(chunk))
        peak = max(abs(sample) for sample in chunk)
        rows.append({
            "second": second,
            "rmsDbfs": round(db(rms), 2),
            "peakDbfs": round(db(peak), 2),
        })

    silent_runs = []
    run_start = None
    for row in rows + [{"second": len(rows), "rmsDbfs": 0.0}]:
        is_silent = float(row["rmsDbfs"]) < -52.0
        if is_silent and run_start is None:
            run_start = int(row["second"])
        elif not is_silent and run_start is not None:
            run_end = int(row["second"])
            if run_end - run_start >= 2:
                silent_runs.append([run_start, run_end])
            run_start = None

    (output / "per-second-rms.txt").write_text(
        "\n".join(f"{row['second']:04d}\t{row['rmsDbfs']:.2f}" for row in rows) + "\n",
        encoding="utf-8",
    )
    (output / "per-second-peak.txt").write_text(
        "\n".join(f"{row['second']:04d}\t{row['peakDbfs']:.2f}" for row in rows) + "\n",
        encoding="utf-8",
    )
    report = {
        "video": str(video),
        "secondsChecked": len(rows),
        "minRmsDbfs": min(row["rmsDbfs"] for row in rows),
        "maxPeakDbfs": max(row["peakDbfs"] for row in rows),
        "silentRunsAtLeast2Seconds": silent_runs,
        "decodePassed": True,
    }
    (output / "audio-check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
