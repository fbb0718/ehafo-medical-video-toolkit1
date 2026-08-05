#!/usr/bin/env python3

"""Build and render a medical question-video project from one JSON config."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def resolve(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT)
    return path


def run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def select_voice(config: dict[str, Any], voice: str | None = None) -> dict[str, Any]:
    selected = voice or str(config.get("voice") or "")
    profiles = config.get("voiceProfiles")
    outros = config.get("sharedOutros")
    if not selected:
        raise ValueError("项目配置缺少 voice")
    if not isinstance(profiles, dict) or selected not in profiles:
        raise ValueError(f"未知音色：{selected}；可用音色：{', '.join(sorted(profiles or {}))}")
    if not isinstance(outros, dict) or selected not in outros:
        raise ValueError(f"音色 {selected} 缺少固定片尾配置")

    resolved = copy.deepcopy(config)
    resolved["voice"] = selected
    resolved["voiceProfile"] = str(profiles[selected])
    resolved["sharedOutro"] = copy.deepcopy(outros[selected])
    if str(resolved["sharedOutro"].get("voice")) != selected:
        raise ValueError(f"音色 {selected} 与固定片尾配置不匹配")
    roots = resolved.get("paths", {}).get("reviewedAudioRoots", {})
    if roots:
        if selected not in roots:
            raise ValueError(f"音色 {selected} 缺少配音输出目录")
        resolved["paths"]["reviewedAudioRoot"] = str(roots[selected])
    return resolved


def validate_voice_resources(config: dict[str, Any]) -> dict[str, Any]:
    selected = str(config["voice"])
    profile_path = resolve(str(config["voiceProfile"]))
    if not profile_path.is_file():
        raise ValueError(f"音色 {selected} 缺少配置：{profile_path.relative_to(ROOT)}")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if str(profile.get("voiceKey")) != selected:
        raise ValueError(f"音色 {selected} 与 profile.json 的 voiceKey 不匹配")
    reference_path = resolve(str(profile.get("referenceAudio", "")))
    if not reference_path.is_file():
        raise ValueError(f"音色 {selected} 缺少参考音频：{reference_path.relative_to(ROOT)}")
    outro = config["sharedOutro"]
    outro_path = resolve(str(outro.get("audio", "")))
    if not outro_path.is_file():
        raise ValueError(f"音色 {selected} 缺少固定片尾：{outro_path.relative_to(ROOT)}")
    return profile


def load_config(path: Path, voice: str | None = None) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = ("projectId", "presentation", "paths", "questions", "variant")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError("项目配置缺少字段：" + "、".join(missing))
    presentation = config["presentation"]
    required_presentation = (
        "brandName",
        "courseName",
        "midrollLabel",
        "outroTitle",
        "outroText",
        "disclaimer",
    )
    missing = [key for key in required_presentation if not presentation.get(key)]
    if missing:
        raise ValueError("展示配置缺少字段：" + "、".join(missing))
    return select_voice(config, voice)


def prepare_runtime_data(config: dict[str, Any]) -> Path:
    paths = config["paths"]
    source = resolve(paths["questionScripts"])
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["presentation"] = config["presentation"]
    if config.get("voiceProfile"):
        payload["voiceProfile"] = config["voiceProfile"]
    if config.get("sharedOutro"):
        payload["sharedOutro"] = config["sharedOutro"]
    runtime = ROOT / "data" / ".runtime-questions.json"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return runtime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "project.json")
    parser.add_argument("--voice", choices=("yhn", "mcy"), help="选择克隆音色")
    parser.add_argument(
        "--background", choices=("white", "green"),
        help="选择白色或绿色背景；未指定时读取 config/project.json",
    )
    parser.add_argument("--skip-voice", action="store_true")
    parser.add_argument(
        "--overwrite-shared-outro",
        action="store_true",
        help="Explicitly rebuild the exam-level shared outro audio.",
    )
    parser.add_argument("--skip-check", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument(
        "--quality", choices=("draft", "standard", "high"), default="high"
    )
    args = parser.parse_args()

    config = load_config(args.config.resolve(), args.voice)
    validate_voice_resources(config)
    runtime_data = prepare_runtime_data(config)
    paths = config["paths"]
    questions = str(config["questions"])
    variant = str(config["variant"])
    prefix = str(config.get("filePrefix") or config["projectId"])
    background = args.background or str(config.get("background") or "white")
    if background not in {"white", "green"}:
        raise ValueError(f"未知背景：{background}；可用背景：white、green")
    voice_dir = resolve(paths["reviewedAudioRoot"])
    focus_data = resolve(paths["focusCues"])
    generated_dir = resolve(paths["generatedRoot"])
    checks_dir = resolve(paths.get("checkRoot", "checks"))
    checks_dir.mkdir(parents=True, exist_ok=True)

    python = sys.executable
    if not args.skip_voice:
        voice_command = [
            python,
            "scripts/synthesize_question_audio.py",
            "--data",
            str(runtime_data),
            "--output-dir",
            str(voice_dir),
            "--questions",
            questions,
        ]
        if args.overwrite_shared_outro:
            voice_command.append("--overwrite-shared-outro")
        run(voice_command)

    run([
        python,
        "scripts/build_question_compositions.py",
        "--data",
        str(runtime_data),
        "--focus-data",
        str(focus_data),
        "--voice-dir",
        str(voice_dir),
        "--output-dir",
        str(generated_dir),
        "--questions",
        questions,
        "--variant",
        variant,
        "--file-prefix",
        prefix,
        "--background",
        background,
        "--overwrite",
    ])

    if not args.skip_check:
        run([
            python,
            "scripts/check_question_focus.py",
            "--data",
            str(runtime_data),
            "--focus-data",
            str(focus_data),
            "--voice-dir",
            str(voice_dir),
            "--generated-dir",
            str(generated_dir),
            "--questions",
            questions,
            "--variant",
            variant,
            "--file-prefix",
            prefix,
            "--background",
            background,
            "--output",
            str(checks_dir / "focus-check.json"),
        ])

    if not args.skip_render:
        run([
            python,
            "scripts/render_question_videos.py",
            "--source-dir",
            str(generated_dir),
            "--questions",
            questions,
            "--variant",
            variant,
            "--file-prefix",
            prefix,
            "--background",
            background,
            "--quality",
            args.quality,
            "--suffix",
            "final",
        ])


if __name__ == "__main__":
    main()
