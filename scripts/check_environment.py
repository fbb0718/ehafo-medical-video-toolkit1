#!/usr/bin/env python3

"""Validate the portable toolkit runtime and all required local resources."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from run_question_project import load_config, select_voice, validate_voice_resources


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FILES = (
    "config/project.json",
    "data/questions.json",
    "scripts/auto_focus_cues.py",
    "scripts/render_fast_question_video.py",
    "scripts/run_fast_question_project.py",
    "scripts/check_video_audio_by_second.py",
    "assets/brand/ehafo-leaf.png",
    "assets/voice/profiles/yhn/profile.json",
    "assets/voice/profiles/yhn/reference.wav",
    "assets/voice/profiles/mcy/profile.json",
    "assets/voice/profiles/mcy/reference.wav",
    "assets/voice/shared/clinical-assistant-follow-v1/manifest.json",
    "assets/voice/shared/clinical-assistant-follow-v1/yhn固定片尾.wav",
    "assets/voice/shared/clinical-assistant-follow-v1/mcy固定片尾.wav",
)
FONT_FILES = (
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_json(relative: str) -> Any:
    path = ROOT / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"无法读取 JSON：{relative}（{error}）")


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        fail(f"缺少命令：{name}")
    return path


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def check_fast_runtime(preinstall: bool) -> None:
    if platform.system() != "Darwin":
        fail("高质量对齐快速渲染器当前仅支持 macOS")
    if sys.version_info < (3, 11):
        fail(f"Python 版本过低：{platform.python_version()}，需要 3.11 或更高")
    for font_path in FONT_FILES:
        if not font_path.is_file():
            fail(f"缺少 macOS 系统字体：{font_path}")

    ffmpeg = require_command("ffmpeg")
    require_command("ffprobe")
    encoders = command_output([ffmpeg, "-hide_banner", "-encoders"])
    if "libx264" not in encoders:
        fail("FFmpeg 不包含 libx264 编码器")
    if " aac " not in encoders and " aac\n" not in encoders:
        fail("FFmpeg 不包含 AAC 编码器")

    if not preinstall:
        try:
            import PIL
        except ImportError as error:
            fail("缺少 Pillow，请先运行‘首次安装快速版.command’")
        if PIL.__version__ != "12.2.0":
            fail(f"Pillow 版本必须为 12.2.0，当前为 {PIL.__version__}")


def check_resources() -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            fail(f"工具包缺少必要文件：{relative}")

    raw_config = load_json("config/project.json")
    config = load_config(ROOT / "config" / "project.json")
    questions = load_json("data/questions.json")
    load_json("assets/voice/shared/clinical-assistant-follow-v1/manifest.json")

    profile_ids: set[str] = set()
    for voice in ("yhn", "mcy"):
        selected = select_voice(raw_config, voice)
        profile = validate_voice_resources(selected)
        profile_id = str(profile.get("id") or "")
        if not profile_id:
            fail(f"音色 {voice} 的 profile.json 缺少 id")
        if profile_id in profile_ids:
            fail(f"音色 {voice} 与另一音色使用了相同的 profile id")
        profile_ids.add(profile_id)

    paths = config.get("paths", {})
    reviewed_root = ROOT / str(paths.get("reviewedAudioRoot", "assets/voice/reviewed-smooth"))
    for question in questions.get("questions", []):
        number = int(question["number"])
        manifest_path = reviewed_root / f"q{number:02d}" / "manifest.json"
        if not manifest_path.is_file():
            fail(f"第 {number} 题缺少审核音频 manifest：{manifest_path.relative_to(ROOT)}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        audio_path = ROOT / str(manifest["audio"])
        if not audio_path.is_file():
            fail(f"第 {number} 题缺少审核音频：{audio_path.relative_to(ROOT)}")
        for segment in manifest.get("segments", []):
            segment_audio = ROOT / str(segment["audio"])
            if not segment_audio.is_file():
                fail(f"第 {number} 题缺少分段音频：{segment_audio.relative_to(ROOT)}")

def check_high_quality_runtime() -> None:
    node = require_command("node")
    require_command("npm")
    version = command_output([node, "--version"]).strip().lstrip("v")
    major = int(version.split(".", 1)[0])
    if major < 22:
        fail(f"Node.js 版本过低：{version}，高质量模式需要 22 或更高")


def check_voice_runtime() -> None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        fail("本地克隆配音仅支持 Apple Silicon Mac")
    if not ((3, 11) <= sys.version_info[:2] <= (3, 12)):
        fail(f"本地克隆配音需要 Python 3.11 或 3.12，当前为 {platform.python_version()}")
    try:
        import mlx  # noqa: F401
        import mlx_audio  # noqa: F401
    except ImportError:
        fail("缺少本地克隆配音依赖，请运行‘首次安装.command’")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preinstall", action="store_true")
    parser.add_argument("--include-high-quality", action="store_true")
    parser.add_argument("--include-voice", action="store_true")
    args = parser.parse_args()

    try:
        check_resources()
        check_fast_runtime(args.preinstall)
        if args.include_high_quality:
            check_high_quality_runtime()
        if args.include_voice:
            check_voice_runtime()
    except (RuntimeError, subprocess.CalledProcessError, ValueError) as error:
        print(f"环境检查失败：{error}", file=sys.stderr)
        print("ENVIRONMENT_OK=false")
        raise SystemExit(1)

    print(f"macOS={platform.mac_ver()[0]}")
    print(f"architecture={platform.machine()}")
    print(f"python={platform.python_version()}")
    print("配置、字体、品牌资源、审核音频、yhn/mcy 音色和固定片尾：完整")
    print("ENVIRONMENT_OK=true")


if __name__ == "__main__":
    main()
