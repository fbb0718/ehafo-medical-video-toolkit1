#!/usr/bin/env python3

"""Create a portable, non-overwriting fast medical-video toolkit bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
DEFAULT_NAME = f"ehafo-fast-medical-video-toolkit-hq-aligned-v5.3-{datetime.now().strftime('%Y%m%d')}"

FILES = (
    "README.md",
    "PORTABLE_SETUP.md",
    "FAST_WORKFLOW.md",
    "DESIGN.md",
    "requirements-fast.txt",
    "requirements-voice-apple-silicon.txt",
    "requirements.txt",
    "package.json",
    "package-lock.json",
    "hyperframes.json",
    "首次安装.command",
    "首次安装快速版.command",
    "生成视频.command",
    "生成快速视频.command",
    "环境检查.command",
    "config/project.json",
    "data/README.md",
    "data/questions.json",
    "data/focus-cues.json",
    "scripts/auto_focus_cues.py",
    "scripts/build_question_compositions.py",
    "scripts/check_question_focus.py",
    "scripts/check_environment.py",
    "scripts/check_video_audio_by_second.py",
    "scripts/package_fast_toolkit.py",
    "scripts/render_fast_question_video.py",
    "scripts/render_question_videos.py",
    "scripts/run_fast_question_project.py",
    "scripts/run_question_project.py",
    "scripts/synthesize_question_audio.py",
    "tests/test_fast_transitions.py",
    "tests/test_background_themes.py",
    "tests/test_voice_profiles.py",
    "assets/brand/ehafo-leaf.png",
    "assets/voice/profiles/yhn/profile.json",
    "assets/voice/profiles/yhn/reference.wav",
    "assets/voice/profiles/mcy/profile.json",
    "assets/voice/profiles/mcy/reference.wav",
    "assets/voice/shared/clinical-assistant-follow-v1/manifest.json",
    "assets/voice/shared/clinical-assistant-follow-v1/yhn固定片尾.wav",
    "assets/voice/shared/clinical-assistant-follow-v1/mcy固定片尾.wav",
    "assets/voice/reviewed-smooth/q05/manifest.json",
    "assets/voice/reviewed-smooth/q05/question-q05-voice.wav",
) + tuple(
    f"assets/voice/reviewed-smooth/q05/segments/segment-{index:02d}.wav"
    for index in range(13)
)

EXAMPLE_FILES = {
    "examples/q05/clinical-assistant-q05-white-yhn-fast-hq-aligned-v5-final.mp4":
        "examples/q05/clinical-assistant-q05-white-yhn-fast-hq-aligned-v5-final.mp4",
    "examples/q05/pipeline-report.json":
        "examples/q05/pipeline-report.json",
    "examples/q05/contact-sheet.png":
        "examples/q05/contact-sheet.png",
    "examples/q05/c-item-transition-check.mp4":
        "examples/q05/c-item-transition-check.mp4",
    "examples/q05/c-transition.png":
        "examples/q05/c-transition.png",
    "renders/clinical-assistant-q05-green-green-theme-v5.3.1-check-final.mp4":
        "examples/q05/clinical-assistant-q05-green-yhn-v5.3-final.mp4",
    "checks/fast-green-green-theme-v5.3.1-check/pipeline-report.json":
        "examples/q05/green-pipeline-report.json",
    "checks/fast-green-green-theme-v5.3.1-check/frames/contact-sheet.png":
        "examples/q05/green-contact-sheet.png",
    "checks/green-theme-v5.3-hq-preview.png":
        "examples/q05/green-hyperframes-hq-preview.png",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy(source_relative: str, destination: Path, destination_relative: str | None = None) -> None:
    source = ROOT / source_relative
    if not source.exists():
        raise FileNotFoundError(f"Bundle source is missing: {source}")
    target = destination / (destination_relative or source_relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def make_example_report_portable(destination: Path) -> None:
    report_videos = {
        "pipeline-report.json": "examples/q05/clinical-assistant-q05-white-yhn-fast-hq-aligned-v5-final.mp4",
        "green-pipeline-report.json": "examples/q05/clinical-assistant-q05-green-yhn-v5.3-final.mp4",
    }
    for report_name, video_path in report_videos.items():
        report_path = destination / "examples" / "q05" / report_name
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for output in report.get("outputs", {}).values():
            output["video"] = video_path
            audio_check = output.get("audioCheck", {})
            if audio_check.get("video"):
                audio_check["video"] = video_path
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WORKSPACE / "exports" / DEFAULT_NAME)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing bundle: {output}")
    output.mkdir(parents=True)

    for relative in FILES:
        copy(relative, output)
    for source, target in EXAMPLE_FILES.items():
        copy(source, output, target)
    make_example_report_portable(output)

    bundle = {
        "schemaVersion": 3,
        "packageVersion": "5.3",
        "bundleType": "ehafo-fast-medical-question-video-toolkit",
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fastPipeline": "scripts/run_fast_question_project.py",
        "highQualityPipeline": "scripts/run_question_project.py",
        "automaticFocus": "scripts/auto_focus_cues.py",
        "sampleQuestion": 5,
        "renderer": "pillow-ffmpeg-fast-hq-aligned-v5.3.1",
        "availableBackgrounds": ["white", "green"],
        "defaultBackground": "white",
        "sampleMeasuredSeconds": 33.590,
        "greenSampleMeasuredSeconds": 108.682,
        "underFiveMinutes": True,
        "containsSampleAudio": True,
        "containsSampleVideo": True,
        "containsModelWeights": False,
        "availableVoices": ["yhn", "mcy"],
        "defaultVoice": "yhn",
        "containsBothCloneReferences": True,
        "containsBothReviewedFixedOutros": True,
        "portablePlatform": "macOS 13+ (Apple Silicon or Intel for fast mode)",
        "voiceGenerationPlatform": "Apple Silicon only",
        "environmentCheck": "scripts/check_environment.py",
        "transitionRegressionTest": "tests/test_fast_transitions.py",
    }
    (output / "BUNDLE.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.name == "MANIFEST.sha256":
            continue
        lines.append(f"{sha256(path)}  {path.relative_to(output)}")
    (output / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created fast toolkit bundle: {output}")
    print(f"Files: {len(lines)}")


if __name__ == "__main__":
    main()
