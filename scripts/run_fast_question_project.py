#!/usr/bin/env python3

"""Run automatic focus generation, fast rendering, and final media QA."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from auto_focus_cues import generate
from build_question_compositions import validate_focus
from run_question_project import (
    load_config,
    prepare_runtime_data,
    resolve,
    validate_voice_resources,
)


ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def media_probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,size:stream=codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def validate_media(path: Path, expected_duration: float) -> dict[str, Any]:
    probe = media_probe(path)
    streams = probe["streams"]
    video = next((item for item in streams if item.get("width")), None)
    audio = next((item for item in streams if item.get("sample_rate")), None)
    if not video or video.get("codec_name") != "h264":
        raise ValueError("Fast output must contain H.264 video")
    if (int(video["width"]), int(video["height"])) != (1080, 1920):
        raise ValueError("Fast output must be 1080x1920")
    if not audio or audio.get("codec_name") != "aac" or int(audio["sample_rate"]) != 48000:
        raise ValueError("Fast output must contain 48 kHz AAC audio")
    duration = float(probe["format"]["duration"])
    if abs(duration - expected_duration) > 0.15:
        raise ValueError(
            f"Fast output duration mismatch: {duration:.3f}s vs {expected_duration:.3f}s"
        )
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        check=True,
    )
    return probe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "project.json")
    parser.add_argument("--voice", choices=("yhn", "mcy"), help="选择已有审核配音的音色")
    parser.add_argument(
        "--background", choices=("white", "green"),
        help="选择白色或绿色背景；未指定时读取 config/project.json",
    )
    parser.add_argument("--variant", default="fast-auto-v1")
    parser.add_argument("--questions", default="")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    config = load_config(args.config.resolve(), args.voice)
    validate_voice_resources(config)
    runtime_path = prepare_runtime_data(config)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    paths = config["paths"]
    questions_range = args.questions or str(config["questions"])
    start, end = (int(value) for value in questions_range.split("-", 1))
    prefix = str(config.get("filePrefix") or config["projectId"])
    background = args.background or str(config.get("background") or "white")
    if background not in {"white", "green"}:
        raise ValueError(f"未知背景：{background}；可用背景：white、green")
    voice_dir = resolve(paths["reviewedAudioRoot"])
    work_dir = resolve(paths.get("fastGeneratedRoot", "generated/fast"))
    checks_dir = resolve(paths.get("checkRoot", "checks")) / f"fast-{background}-{args.variant}"
    focus_path = work_dir / f"focus-cues-{args.variant}.json"
    focus_payload = generate(runtime)
    focus_path.parent.mkdir(parents=True, exist_ok=True)
    focus_path.write_text(
        json.dumps(focus_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    questions = {
        int(question["number"]): question for question in runtime["questions"]
    }
    label = str(runtime.get("presentation", {}).get("midrollLabel") or "易哈佛教研提醒")
    expected_duration: dict[int, float] = {}
    for number in range(start, end + 1):
        manifest = json.loads(
            (voice_dir / f"q{number:02d}" / "manifest.json").read_text(encoding="utf-8")
        )
        validate_focus(
            questions[number], manifest["captions"],
            focus_payload["questions"][str(number)], label,
        )
        expected_duration[number] = round(float(manifest["duration"]) + 0.35, 3)

    render_command = [
        sys.executable, "scripts/render_fast_question_video.py",
        "--data", str(runtime_path),
        "--focus-data", str(focus_path),
        "--voice-dir", str(voice_dir),
        "--work-dir", str(work_dir),
        "--output-dir", str(ROOT / "renders"),
        "--questions", questions_range,
        "--variant", args.variant,
        "--file-prefix", prefix,
        "--background", background,
        "--fps", str(args.fps),
    ]
    if args.overwrite:
        render_command.append("--overwrite")
    run(render_command)

    outputs: dict[str, Any] = {}
    for number in range(start, end + 1):
        output = ROOT / "renders" / f"{prefix}-q{number:02d}-{background}-{args.variant}-final.mp4"
        qa_dir = checks_dir / f"q{number:02d}" / "audio"
        qa_dir.mkdir(parents=True, exist_ok=True)
        run([
            sys.executable, "scripts/check_video_audio_by_second.py",
            str(output), str(qa_dir),
        ])
        probe = validate_media(output, expected_duration[number])
        audio_check = json.loads((qa_dir / "audio-check.json").read_text(encoding="utf-8"))
        if not audio_check["decodePassed"] or audio_check["silentRunsAtLeast2Seconds"]:
            raise ValueError(f"q{number:02d} failed final audio QA")
        outputs[f"q{number:02d}"] = {
            "video": str(output.relative_to(ROOT)),
            "probe": probe,
            "audioCheck": audio_check,
        }

    elapsed = time.perf_counter() - started
    report = {
        "schemaVersion": 1,
        "pipeline": "ehafo-fast-medical-video-hq-aligned-v5.3",
        "scope": "structured content + reviewed audio -> final MP4",
        "questions": questions_range,
        "variant": args.variant,
        "background": background,
        "focus": str(focus_path.relative_to(ROOT)),
        "outputs": outputs,
        "elapsedSeconds": round(elapsed, 3),
        "underFiveMinutes": elapsed < 300,
    }
    report_path = checks_dir / "pipeline-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"FAST_PIPELINE_SECONDS={elapsed:.3f}")
    print(f"UNDER_FIVE_MINUTES={str(elapsed < 300).lower()}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
