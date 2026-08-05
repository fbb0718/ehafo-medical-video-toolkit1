#!/usr/bin/env python3

"""Generate resumable cloned narration for medical exam question videos."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import mlx.core as mx
from mlx_audio.audio_io import write as audio_write
from mlx_audio.tts.utils import load_model
from mlx_audio.utils import load_audio


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "questions.json"
DEFAULT_OUTPUT = ROOT / "assets" / "voice" / "reviewed"


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def generate_segment(
    model: Any,
    reference_audio: Any,
    reference_text: str,
    text: str,
    output_path: Path,
    seed: int,
) -> None:
    mx.random.seed(seed)
    results = list(
        model.generate(
            text=text,
            ref_audio=reference_audio,
            ref_text=reference_text,
            lang_code="chinese",
            temperature=0.68,
            top_k=30,
            top_p=0.9,
            repetition_penalty=1.5,
            max_tokens=1800,
            verbose=False,
        )
    )
    if not results:
        raise RuntimeError(f"Model produced no audio for: {text}")
    raw = output_path.with_suffix(".raw.wav")
    audio = mx.concatenate([result.audio for result in results], axis=0)
    audio_write(str(raw), audio, results[0].sample_rate, format="wav")
    run(
        "ffmpeg", "-y", "-v", "error", "-i", str(raw),
        "-af",
        "silenceremove=start_periods=1:start_duration=0:start_threshold=-44dB:"
        "start_silence=0.08,areverse,"
        "silenceremove=start_periods=1:start_duration=0:start_threshold=-44dB:"
        "start_silence=0.24,areverse,afade=t=in:st=0:d=0.04,apad=pad_dur=0.30",
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(output_path),
    )
    raw.unlink(missing_ok=True)


def make_silence(path: Path, seconds: float) -> None:
    if path.exists():
        return
    run(
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        "anullsrc=r=48000:cl=mono", "-t", f"{seconds:.3f}",
        "-c:a", "pcm_s16le", str(path),
    )


def fit_outro(path: Path, target: float = 4.35) -> None:
    source_duration = duration(path)
    if source_duration <= target:
        return
    ratio = source_duration / target
    fitted = path.with_suffix(".fitted.wav")
    run(
        "ffmpeg", "-y", "-v", "error", "-i", str(path),
        "-af", f"atempo={ratio:.8f},atrim=duration={target:.3f}",
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(fitted),
    )
    fitted.replace(path)


def assemble_question(
    question: dict[str, Any],
    output_root: Path,
    profile: dict[str, Any] | None = None,
    shared_outro: dict[str, Any] | None = None,
) -> Path:
    number = int(question["number"])
    question_dir = output_root / f"q{number:02d}"
    segment_dir = question_dir / "segments"
    concat_path = question_dir / "concat.txt"
    concat_lines: list[str] = []
    captions: list[dict[str, Any]] = []
    segment_manifest: list[dict[str, Any]] = []
    cursor = 0.0
    shared_outro_path = (
        (ROOT / str(shared_outro["audio"])).resolve() if shared_outro else None
    )

    for index, (section, text, pause) in enumerate(question["segments"]):
        segment_path = (
            shared_outro_path
            if section == "关注片尾" and shared_outro_path is not None
            else segment_dir / f"segment-{index:02d}.wav"
        )
        if segment_path is None:
            raise RuntimeError("共享片尾路径未配置")
        speech_duration = duration(segment_path)
        captions.append({
            "index": index,
            "section": section,
            "text": text,
            "start": round(cursor, 3),
            "end": round(cursor + speech_duration, 3),
        })
        concat_lines.append(f"file '{segment_path}'")
        silence_path = output_root / f"silence-{float(pause):.2f}.wav"
        make_silence(silence_path, float(pause))
        concat_lines.append(f"file '{silence_path}'")
        segment_manifest.append({
            "index": index,
            "section": section,
            "text": text,
            "pauseAfter": pause,
            "audio": str(segment_path.relative_to(ROOT)),
            "speechDuration": round(speech_duration, 3),
        })
        cursor += speech_duration + float(pause)

    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix=f"question-q{number:02d}-") as tmp_name:
        raw_path = Path(tmp_name) / "raw.wav"
        run(
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", str(concat_path), "-c:a", "pcm_s16le", str(raw_path),
        )
        final_path = question_dir / f"question-q{number:02d}-voice.wav"
        run(
            "ffmpeg", "-y", "-v", "error", "-i", str(raw_path),
            "-af", "loudnorm=I=-16:LRA=8:TP=-1.5",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(final_path),
        )

    payload = {
        "number": number,
        "model": "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16",
        "voice": (profile or {}).get("nameZh", "本地克隆老师音色"),
        "audio": str(final_path.relative_to(ROOT)),
        "duration": round(duration(final_path), 3),
        "captions": captions,
        "segments": segment_manifest,
    }
    (question_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return final_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--questions", default="1-1")
    parser.add_argument("--overwrite-segments", action="store_true")
    parser.add_argument(
        "--overwrite-shared-outro",
        action="store_true",
        help="Explicitly regenerate the exam-level shared outro audio.",
    )
    parser.add_argument(
        "--force-segments",
        default="",
        help="Comma-separated question:segment pairs to regenerate, for example 7:7",
    )
    args = parser.parse_args()

    start, end = (int(value) for value in args.questions.split("-", 1))
    data = json.loads(args.data.resolve().read_text(encoding="utf-8"))
    questions = [q for q in data["questions"] if start <= int(q["number"]) <= end]
    forced = {
        tuple(int(part) for part in item.split(":", 1))
        for item in args.force_segments.split(",") if item.strip()
    }
    profile = json.loads((ROOT / data["voiceProfile"]).read_text(encoding="utf-8"))
    shared_outro = data.get("sharedOutro")
    output_root = args.output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    shared_path: Path | None = None
    shared_text: str | None = None
    if shared_outro:
        shared_path = (ROOT / str(shared_outro["audio"])).resolve()
        shared_path.relative_to(ROOT)
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_text = str(shared_outro["text"])
        for question in questions:
            outro_segments = [
                str(text)
                for section, text, _pause in question["segments"]
                if section == "关注片尾"
            ]
            if outro_segments != [shared_text]:
                raise ValueError(
                    f"q{int(question['number']):02d} 片尾文案与共享片尾不一致"
                )
    needs_shared_outro = bool(
        shared_outro
        and shared_path
        and (args.overwrite_shared_outro or not shared_path.exists())
    )
    needs_question_audio = args.overwrite_segments or any(
        (
            not (output_root / f"q{int(question['number']):02d}" / "segments" / f"segment-{index:02d}.wav").exists()
            or (int(question["number"]), index) in forced
        )
        for question in questions
        for index, (section, _text, _pause) in enumerate(question["segments"])
        if not (shared_outro and section == "关注片尾")
    )
    model = None
    reference_audio = None
    if needs_shared_outro or needs_question_audio:
        print(f"Loading clone model for {profile['nameZh']}: {profile['model']}", flush=True)
        model = load_model(profile["model"])
        reference_audio = load_audio(
            str(ROOT / profile["referenceAudio"]), sample_rate=model.sample_rate
        )
    else:
        print("All narration assets already exist; clone model not loaded.", flush=True)

    if shared_outro:
        if needs_shared_outro:
            print(f"Generating shared outro: {shared_outro['id']}", flush=True)
            if model is None or reference_audio is None or shared_path is None or shared_text is None:
                raise RuntimeError("共享片尾生成环境未初始化")
            generate_segment(
                model,
                reference_audio,
                profile["referenceText"],
                shared_text,
                shared_path,
                seed=731013,
            )
            fit_outro(shared_path)
        else:
            print(f"Reusing shared outro: {shared_path.relative_to(ROOT)}", flush=True)

    total = sum(
        sum(1 for section, _text, _pause in question["segments"] if not (shared_outro and section == "关注片尾"))
        for question in questions
    )
    done = 0
    for question in questions:
        number = int(question["number"])
        segment_dir = output_root / f"q{number:02d}" / "segments"
        segment_dir.mkdir(parents=True, exist_ok=True)
        for index, (_section, text, _pause) in enumerate(question["segments"]):
            if shared_outro and _section == "关注片尾":
                if (number, index) in forced:
                    raise ValueError(
                        "共享片尾不能按题号强制重建，请使用 --overwrite-shared-outro"
                    )
                print(f"q{number:02d} s{index:02d}: shared outro", flush=True)
                continue
            done += 1
            output_path = segment_dir / f"segment-{index:02d}.wav"
            if output_path.exists() and not args.overwrite_segments and (number, index) not in forced:
                print(f"[{done:03d}/{total:03d}] q{number:02d} s{index:02d} reuse", flush=True)
                continue
            print(f"[{done:03d}/{total:03d}] q{number:02d} s{index:02d}: {text}", flush=True)
            if model is None or reference_audio is None:
                raise RuntimeError("题目配音生成环境未初始化")
            generate_segment(
                model,
                reference_audio,
                profile["referenceText"],
                text,
                output_path,
                seed=731000 + number * 100 + index,
            )
            if _section == "关注片尾":
                fit_outro(output_path)
        final_path = assemble_question(question, output_root, profile, shared_outro)
        print(f"Assembled q{number:02d}: {duration(final_path):.3f}s", flush=True)


if __name__ == "__main__":
    main()
