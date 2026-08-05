#!/usr/bin/env python3

"""Generate deterministic teaching-focus cues from structured question data."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "questions.json"
DEFAULT_OUTPUT = ROOT / "data" / "focus-cues.auto.json"

STOP_ANCHORS = {
    "本题", "计算", "结果", "每分钟", "题干", "给出", "正确", "答案",
    "这个", "该项", "其中", "需要", "最后", "第一步", "第二步", "第三步",
}
TERM_ENDINGS = (
    "通气量", "血流量", "输出量", "排血量", "容量", "频率", "比值",
    "参考值", "计算值", "单位", "数据", "指标", "浓度", "压力", "剂量",
    "症状", "体征", "诊断", "治疗", "检查", "病因", "机制",
)


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value))


def caption_index(question: dict[str, Any], section: str, occurrence: int = 0) -> int:
    matches = [
        index for index, item in enumerate(question["segments"])
        if str(item[0]) == section
    ]
    if occurrence >= len(matches):
        raise ValueError(f"Missing narration section {section!r} occurrence {occurrence}")
    return matches[occurrence]


def longest_shared_phrase(source: str, spoken: str, maximum: int = 12) -> str:
    source = compact_text(source)
    spoken = compact_text(spoken)
    best = ""
    for length in range(min(maximum, len(source)), 1, -1):
        for start in range(0, len(source) - length + 1):
            candidate = source[start:start + length].strip("，。；：、（）()0123456789./")
            if len(candidate) < 2 or candidate in STOP_ANCHORS:
                continue
            if candidate in spoken:
                return candidate
    return best


def anchor_for(phrase: str, spoken: str, *fallbacks: str) -> str:
    candidates = (phrase, *fallbacks)
    for candidate in candidates:
        if candidate and compact_text(candidate) in compact_text(spoken):
            return compact_text(candidate)
    for candidate in candidates:
        shared = longest_shared_phrase(candidate, spoken)
        if shared:
            return shared
    raise ValueError(f"Cannot align focus phrase {phrase!r} to narration {spoken!r}")


def trim_term(value: str) -> str:
    value = re.sub(r"^(?:本题中|本题|每分钟|先|再|按|把|将|由)", "", value)
    value = re.sub(r"(?:进行|计算|得到|作为)$", "", value)
    return value[-16:]


def terms(text: str) -> list[str]:
    chunks = re.findall(r"[\u3400-\u9fff/]{2,18}", text)
    found: list[str] = []
    for chunk in chunks:
        for ending in TERM_ENDINGS:
            cursor = 0
            while True:
                end = chunk.find(ending, cursor)
                if end < 0:
                    break
                end += len(ending)
                start = max(0, end - 12)
                candidate = trim_term(chunk[start:end])
                if 2 <= len(candidate) <= 16 and candidate not in found:
                    found.append(candidate)
                cursor = end
    return found


def phrase_after(text: str, connector: str) -> str:
    if connector not in text:
        return ""
    tail = text.split(connector, 1)[1]
    candidates = terms(tail)
    return candidates[0] if candidates else ""


def choose_knowledge_phrase(title: str, text: str) -> str:
    if "减去" in text or "扣除" in text:
        chosen = phrase_after(text, "减去") or phrase_after(text, "扣除")
        if chosen:
            return chosen
    if "按" in text:
        chosen = phrase_after(text, "按")
        if chosen:
            return chosen
    if "等于" in text:
        chosen = phrase_after(text, "等于")
        if chosen:
            return chosen
    candidates = terms(text)
    if candidates:
        title_shared = [item for item in candidates if item in title or title in item]
        return (title_shared or candidates)[0]
    return text[: min(8, len(text))].rstrip("，。；")


def choose_reminder_phrases(text: str) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    patterns = (
        (r"分清([\u3400-\u9fff]{2,8})(?:的层级)?", lambda m: "分清" + m.group(1).removesuffix("的层级")),
        (r"单位统一", lambda _m: "单位统一"),
        (r"以([\u3400-\u9fff]{2,10})为准", lambda m: "以" + m.group(1) + "为准"),
        (r"不要([^，。]{2,10})", lambda m: "不要" + m.group(1)),
        (r"必须([^，。]{2,10})", lambda m: "必须" + m.group(1)),
    )
    for pattern, formatter in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        phrase = formatter(match)
        if phrase in text and all(existing[0] != phrase for existing in selected):
            mode = "circle" if len(phrase) <= 4 else "highlight" if len(selected) == 2 else "underline"
            selected.append((phrase, mode))
        if len(selected) == 3:
            break
    if not selected:
        fallback = next((item for item in terms(text) if len(item) <= 12), text[:8])
        selected.append((fallback, "underline"))
    return selected


def choose_analysis_phrase(note: str) -> str:
    patterns = (
        r"近似参考值", r"低于(?:本题)?计算值", r"高于(?:本题)?计算值",
        r"不符合", r"不能直接套用", r"不能", r"错误", r"偏差", r"误加", r"误减",
    )
    for pattern in patterns:
        match = re.search(pattern, note)
        if match:
            phrase = match.group(0).replace("本题", "")
            if phrase in note:
                return phrase
            return match.group(0)
    candidates = terms(note)
    return (candidates or [note[:8]])[0]


def choose_answer_phrase(question: dict[str, Any]) -> str:
    reason = str(question["answerReason"])
    value = re.escape(str(question["options"][question["answer"]]))
    patterns = (
        rf"[\u3400-\u9fff/]*?(?:比值|结果)(?:为|等于){value}",
        rf"[\u3400-\u9fff/]+(?:为|等于){value}",
        rf"{value}",
    )
    for pattern in patterns:
        matches = re.findall(pattern, reason)
        if matches:
            phrase = matches[-1]
            if len(phrase) <= 16:
                return phrase
            return phrase[-16:]
    raise ValueError("Cannot identify answer focus phrase")


def mode_for(phrase: str, index: int = 0) -> str:
    if any(token in phrase for token in ("不", "低于", "高于", "为准")):
        return "highlight"
    if len(phrase) <= 5 and index % 2:
        return "circle"
    return "underline"


def build_focus(question: dict[str, Any], midroll_label: str) -> dict[str, list[dict[str, Any]]]:
    segments = question["segments"]
    read_index = caption_index(question, "读题")
    read_spoken = str(segments[read_index][1])
    stem = []
    for row, phrase in enumerate(question["marks"]):
        stem.append({
            "phrase": phrase,
            "caption": read_index,
            "anchor": anchor_for(phrase, read_spoken),
            "row": row,
            "mode": mode_for(phrase, row),
        })

    knowledge_indices = [
        index for index, item in enumerate(segments) if str(item[0]) == "知识点"
    ]
    knowledge = []
    for row, (title, text) in enumerate(question["knowledge"]):
        caption = knowledge_indices[min(row, len(knowledge_indices) - 1)]
        spoken = str(segments[caption][1])
        phrase = choose_knowledge_phrase(str(title), str(text))
        knowledge.append({
            "phrase": phrase,
            "caption": caption,
            "anchor": anchor_for(phrase, spoken, str(text)),
            "row": row,
            "mode": mode_for(phrase, row + 1),
        })

    reminder_index = caption_index(question, "品牌提醒")
    reminder_spoken = str(segments[reminder_index][1])
    reminder_text = reminder_spoken.removeprefix(f"{midroll_label}：")
    reminder = [
        {
            "phrase": phrase,
            "caption": reminder_index,
            "anchor": anchor_for(phrase, reminder_spoken),
            "mode": mode,
        }
        for phrase, mode in choose_reminder_phrases(reminder_text)
    ]

    analysis_indices = [
        index for index, item in enumerate(segments) if str(item[0]) == "逐项解析"
    ]
    analysis = []
    for row, note in question["optionNotes"]:
        if str(row) == str(question["answer"]):
            continue
        matching = [
            index for index in analysis_indices
            if re.search(rf"(?:^|[。；，]){re.escape(str(row))}项", str(segments[index][1]))
            or f"{row}项" in str(segments[index][1])
        ]
        caption = matching[0] if matching else analysis_indices[-1]
        spoken = str(segments[caption][1])
        phrase = choose_analysis_phrase(str(note))
        try:
            anchor = anchor_for(phrase, spoken, str(note))
        except ValueError:
            anchor = longest_shared_phrase(str(note), spoken) or longest_shared_phrase(
                "误加进去了常见原因", spoken
            )
            if not anchor:
                anchor = spoken[-8:].rstrip("。")
        analysis.append({
            "phrase": phrase,
            "caption": caption,
            "anchor": anchor,
            "row": str(row),
            "mode": mode_for(phrase, len(analysis)),
        })

    answer_index = caption_index(question, "公布答案")
    answer_spoken = str(segments[answer_index][1])
    answer_phrase = choose_answer_phrase(question)
    normalized_answer = answer_phrase.replace("/", "")
    answer = [{
        "phrase": answer_phrase,
        "caption": answer_index,
        "anchor": anchor_for(normalized_answer, answer_spoken, str(question["options"][question["answer"]])),
        "row": str(question["answer"]),
        "mode": "highlight",
    }]

    takeaway_index = caption_index(question, "考点口诀")
    takeaway_spoken = str(segments[takeaway_index][1])
    takeaway = [
        {
            "phrase": str(line),
            "caption": takeaway_index,
            "anchor": anchor_for(str(line), takeaway_spoken),
            "row": row,
            "mode": "circle" if row == len(question["takeawayLines"]) - 1 else "underline",
        }
        for row, line in enumerate(question["takeawayLines"])
    ]
    return {
        "stem": stem,
        "knowledge": knowledge,
        "reminder": reminder,
        "analysis": analysis,
        "answer": answer,
        "takeaway": takeaway,
    }


def generate(payload: dict[str, Any]) -> dict[str, Any]:
    presentation = payload.get("presentation", {})
    label = str(presentation.get("midrollLabel") or "易哈佛教研提醒")
    return {
        "schemaVersion": 1,
        "generator": "deterministic-medical-focus-v1",
        "questions": {
            str(question["number"]): build_focus(question, label)
            for question in payload["questions"]
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"Refusing to overwrite: {output}")
    payload = json.loads(args.data.resolve().read_text(encoding="utf-8"))
    result = generate(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated automatic focus cues: {output}")


if __name__ == "__main__":
    main()
