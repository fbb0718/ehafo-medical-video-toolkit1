#!/usr/bin/env python3

"""Validate targeted teaching marks and narration-synced cue times."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from build_question_compositions import cue_time, validate_focus


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "questions.json"
DEFAULT_FOCUS = ROOT / "data" / "focus-cues.json"
DEFAULT_VOICE = ROOT / "assets" / "voice" / "reviewed"
TAKEAWAY_MAX_UNITS_PER_SECOND = 3.8
TAKEAWAY_MIN_INTERNAL_PAUSES = 4


def spoken_units(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def internal_pause_count(audio_path: Path, speech_duration: float) -> int:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", str(audio_path), "-af",
            "silencedetect=noise=-38dB:d=0.15", "-f", "null", "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    pauses = re.findall(
        r"silence_end: ([0-9.]+) \| silence_duration: ([0-9.]+)",
        result.stderr,
    )
    return sum(
        1 for end, pause_duration in pauses
        if float(pause_duration) >= 0.15
        and float(end) - float(pause_duration) > 0.2
        and float(end) < speech_duration - 0.2
    )


def validate_takeaway_pacing(
    question: dict[str, object], manifest: dict[str, object]
) -> dict[str, float | int]:
    segments = [
        item for item in manifest["segments"]
        if item["section"] == "考点口诀"
    ]
    if len(segments) != 1:
        raise ValueError("narration manifest must contain exactly one 考点口诀 segment")

    speech_duration = float(segments[0]["speechDuration"])
    units = sum(spoken_units(str(line)) for line in question["takeawayLines"])
    units_per_second = units / speech_duration
    audio_path = (ROOT / str(segments[0]["audio"])).resolve()
    audio_path.relative_to(ROOT)
    pauses = internal_pause_count(audio_path, speech_duration)
    if units_per_second > TAKEAWAY_MAX_UNITS_PER_SECOND:
        raise ValueError(
            "考点口诀语速过快："
            f"{units_per_second:.2f} 字符/秒，"
            f"上限 {TAKEAWAY_MAX_UNITS_PER_SECOND:.2f} 字符/秒"
        )
    if pauses < TAKEAWAY_MIN_INTERNAL_PAUSES:
        raise ValueError(
            f"考点口诀停顿不足：检测到 {pauses} 处，"
            f"至少需要 {TAKEAWAY_MIN_INTERNAL_PAUSES} 处"
        )
    return {
        "takeawaySpeechDuration": round(speech_duration, 3),
        "takeawayUnits": units,
        "takeawayUnitsPerSecond": round(units_per_second, 3),
        "takeawayMaxUnitsPerSecond": TAKEAWAY_MAX_UNITS_PER_SECOND,
        "takeawayInternalPauses": pauses,
        "takeawayMinInternalPauses": TAKEAWAY_MIN_INTERNAL_PAUSES,
    }


class PanelTextParser(HTMLParser):
    def __init__(self, target_id: str) -> None:
        super().__init__()
        self.target_id = target_id
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if self.depth:
            self.depth += 1
        elif attributes.get("id") == self.target_id:
            self.depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self.depth:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.parts.append(data)

    @property
    def text(self) -> str:
        return "".join(self.parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="1-1")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--focus-data", type=Path, default=DEFAULT_FOCUS)
    parser.add_argument("--voice-dir", type=Path, default=DEFAULT_VOICE)
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--file-prefix", default="question")
    parser.add_argument("--background", choices=("white", "green"), default="white")
    args = parser.parse_args()

    start, end = (int(value) for value in args.questions.split("-", 1))
    data = json.loads(args.data.resolve().read_text(encoding="utf-8"))
    questions = {
        int(question["number"]): question
        for question in data["questions"]
    }
    focus_questions = json.loads(
        args.focus_data.resolve().read_text(encoding="utf-8")
    )["questions"]
    report: dict[str, object] = {"passed": True, "questions": {}}

    for number in range(start, end + 1):
        question = questions[number]
        focus = focus_questions[str(number)]
        manifest = json.loads(
            (args.voice_dir.resolve() / f"q{number:02d}" / "manifest.json").read_text(encoding="utf-8")
        )
        captions = manifest["captions"]
        pacing = validate_takeaway_pacing(question, manifest)
        presentation = data.get("presentation", {})
        label = str(presentation.get("midrollLabel") or "易哈佛教研提醒")
        validate_focus(question, captions, focus, label)
        answer = str(question["answer"])
        early_answers = [item for item in focus["analysis"] if str(item["row"]) == answer]
        if early_answers:
            raise ValueError(f"q{number:02d} marks the correct answer before reveal")

        html_path = args.generated_dir.resolve() / f"{args.file_prefix}-q{number:02d}-{args.background}-{args.variant}.html"
        source = html_path.read_text(encoding="utf-8")
        reminder = str(question["segments"][6][1]).removeprefix(f"{label}：")
        parser = PanelTextParser("teach-brand")
        parser.feed(source)
        if reminder not in parser.text:
            raise ValueError(f"q{number:02d} reminder copy is missing from the course panel")

        cues: list[dict[str, object]] = []
        for section in ("knowledge", "reminder", "analysis"):
            for item in focus[section]:
                at = cue_time(captions, item)
                caption = captions[int(item["caption"])]
                cues.append({
                    "section": section,
                    "row": item.get("row"),
                    "phrase": item["phrase"],
                    "anchor": item["anchor"],
                    "caption": item["caption"],
                    "markerAt": at,
                    "captionStart": round(0.2 + float(caption["start"]), 3),
                    "captionEnd": round(0.2 + float(caption["end"]), 3),
                })
        report["questions"][f"q{number:02d}"] = {
            "passed": True,
            "reminderVisible": True,
            "correctAnswerProtected": True,
            **pacing,
            "cues": cues,
        }

    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Validated q{start:02d}-q{end:02d}: {args.output.resolve()}")


if __name__ == "__main__":
    main()
