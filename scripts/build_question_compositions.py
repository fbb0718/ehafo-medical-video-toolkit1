#!/usr/bin/env python3

"""Build white or green formal HyperFrames medical question compositions."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "questions.json"
FOCUS_DATA = ROOT / "data" / "focus-cues.json"
VOICE_ROOT = ROOT / "assets" / "voice" / "reviewed"
OUTPUT_ROOT = ROOT / "generated" / "compositions"


def marker_mode(index: int, phrase: str) -> str:
    modes = ["underline", "highlight", "circle", "underline"]
    mode = modes[index % len(modes)]
    # Circles are reserved for short, single-line keywords. A circle around a
    # wrapping inline box collapses into the narrow artifact seen in q02.
    return "underline" if mode == "circle" and len(phrase) > 4 else mode


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def mark_stem(text: str, phrases: list[str], prefix: str, complete: bool = False) -> str:
    rendered = esc(text)
    for index, phrase in enumerate(phrases):
        escaped = esc(phrase)
        mode = marker_mode(index, phrase)
        replacement = (
            f'<span id="{prefix}-mark-{index}" class="mark-wrap mark-{mode}{" mark-complete" if complete else ""}">'
            f'<span class="mark-text">{escaped}</span>'
            '<span class="mark-stroke"></span></span>'
        )
        rendered = rendered.replace(escaped, replacement, 1)
    return rendered


def marked(text: str, marker_id: str, mode: str = "underline") -> str:
    if mode == "circle" and len(text) > 8:
        mode = "underline"
    return (
        f'<span class="teach-mark teach-{mode}" id="{marker_id}">'
        f'<span class="teach-mark-text">{esc(text)}</span>'
        '<span class="teach-stroke"></span></span>'
    )


def marked_phrase(text: str, phrase: str, marker_id: str, mode: str = "highlight") -> str:
    if not phrase or phrase not in text:
        return esc(text)
    before, after = text.split(phrase, 1)
    return esc(before) + marked(phrase, marker_id, mode) + esc(after)


def marked_phrases(text: str, focuses: list[dict[str, Any]]) -> str:
    """Render only explicitly selected focus phrases, preserving surrounding copy."""
    if not focuses:
        return esc(text)
    positioned: list[tuple[int, int, dict[str, Any]]] = []
    for focus in focuses:
        phrase = str(focus["phrase"])
        start = text.find(phrase)
        if start < 0:
            raise ValueError(f"Focus phrase {phrase!r} is not present in {text!r}")
        positioned.append((start, start + len(phrase), focus))
    positioned.sort(key=lambda item: item[0])
    parts: list[str] = []
    cursor = 0
    for start, end, focus in positioned:
        if start < cursor:
            raise ValueError(f"Overlapping focus phrases in {text!r}")
        parts.append(esc(text[cursor:start]))
        parts.append(marked(
            text[start:end],
            str(focus["markerId"]),
            str(focus.get("mode", "underline")),
        ))
        cursor = end
    parts.append(esc(text[cursor:]))
    return "".join(parts)


def panel(panel_id: str, eyebrow: str, body: str, visible: bool = False) -> str:
    state = " teaching-visible" if visible else ""
    return (
        f'<section class="teaching-panel{state}" id="{panel_id}" '
        'data-layout-allow-overlap data-layout-allow-occlusion data-layout-allow-overflow>'
        f'<div class="teaching-eyebrow">{esc(eyebrow)}</div>{body}</section>'
    )


def wm() -> str:
    return '<div class="watermarks" data-layout-ignore><span>易哈佛</span><span>易哈佛</span><span>易哈佛</span></div>'


def theme_css(background: str) -> str:
    if background == "white":
        return ""
    if background != "green":
        raise ValueError(f"Unsupported background: {background}")
    return '''
    /* Green theme changes colors only; v5.2 geometry and typography stay intact. */
    html,body,#root,.scene { background:#003A46; }
    body { color:#F7FAFA; }
    .watermarks { color:#B8D637;opacity:.12; }
    .watermarks span { display:none; }
    .watermarks span:first-child {
      left:auto;right:24px;top:auto;bottom:278px;
      min-height:42px;padding-left:48px;
      display:flex;align-items:center;
      background:url("assets/brand/ehafo-leaf.png") left center/38px 38px no-repeat;
      font-size:36px;transform:rotate(-7deg);
    }
    .top-brand { color:#F7FAFA; }
    .eyebrow,.teaching-eyebrow { border-color:#F4D04F;color:#F4D04F;background:transparent; }
    .cover-number,.read-head,.question-head { color:#F4D04F; }
    .cover h1,.read-stem,.question-stem,.teaching-panel h3,.brand-message p,.analysis-row p,.answer-reason,.memory-line { color:#F7FAFA; }
    .cover-topic,.read-note { color:#D5E2E3; }
    .read-label { color:#003A46;background:#F4D04F; }
    .read-board,.question-board,.teaching-frame,.teaching-panel { border-color:#6F898D;background:#00343D; }
    .option-row,.read-options .option-row { border-color:#6F898D;background:rgba(255,255,255,.045);color:#F7FAFA; }
    .option-row b,.knowledge-row b,.knowledge-row strong,.analysis-row b { color:#F4D04F; }
    .teaching-frame { border-top-color:#F4D04F; }
    .knowledge-row,.brand-message { border-color:#6F898D;background:rgba(255,255,255,.045); }
    .knowledge-row p { color:#F7FAFA; }
    .analysis-row,.memory-row { border-color:#6F898D; }
    .course-disclaimer { color:#AFC5C8; }
    .caption { color:#F7FAFA;text-shadow:0 2px 0 #003A46,2px 0 0 #003A46,-2px 0 0 #003A46,0 -2px 0 #003A46; }
    .outro,.outro p { color:#F7FAFA;background:#003A46; }
'''


def time_of(captions: list[dict[str, Any]], index: int) -> float:
    return round(0.2 + float(captions[index]["start"]), 3)


def cue_time(captions: list[dict[str, Any]], cue: dict[str, Any]) -> float:
    """Place a marker near the spoken anchor inside its real narration window."""
    if cue.get("atSeconds") is not None:
        return round(float(cue["atSeconds"]), 3)
    if "at" in cue:
        return round(float(cue["at"]), 3)
    caption = captions[int(cue["caption"])]
    spoken = str(caption["text"])
    anchor = str(cue["anchor"])
    position = spoken.find(anchor)
    if position < 0:
        raise ValueError(f"Spoken anchor {anchor!r} is not present in {spoken!r}")
    speech_duration = float(caption["end"]) - float(caption["start"])
    usable = max(0.1, speech_duration - 0.65)
    denominator = max(1, len(spoken) - len(anchor))
    progress = min(1.0, position / denominator)
    return round(0.2 + float(caption["start"]) + 0.28 + progress * usable, 3)


def cue_duration(cue: dict[str, Any], fallback: float) -> float:
    return round(float(cue.get("duration", fallback)), 3)


def validate_focus(
    question: dict[str, Any], captions: list[dict[str, Any]], focus: dict[str, Any],
    midroll_label: str,
) -> None:
    number = int(question["number"])
    option_notes = {key: note for key, note in question["optionNotes"]}
    reminder_text = str(question["segments"][6][1]).removeprefix(f"{midroll_label}：")
    sources = {
        "stem": lambda _item: str(question["stem"]),
        "knowledge": lambda item: str(question["knowledge"][int(item["row"])][1]),
        "reminder": lambda _item: reminder_text,
        "analysis": lambda item: str(option_notes[str(item["row"])]),
        "answer": lambda _item: str(question["answerReason"]),
        "takeaway": lambda item: str(question["takeawayLines"][int(item["row"])]),
    }
    expected_counts = {
        "stem": len(question["marks"]),
        "answer": 1,
        "takeaway": len(question["takeawayLines"]),
    }
    for section, resolver in sources.items():
        entries = focus.get(section, [])
        if not entries:
            raise ValueError(f"q{number:02d} has no {section} focus entries")
        if section in expected_counts and len(entries) != expected_counts[section]:
            raise ValueError(
                f"q{number:02d} expected {expected_counts[section]} {section} entries, "
                f"got {len(entries)}"
            )
        for item in entries:
            phrase = str(item["phrase"])
            source = resolver(item)
            if phrase not in source:
                raise ValueError(f"q{number:02d} {section} phrase {phrase!r} is missing")
            if len(phrase) > 16:
                raise ValueError(f"q{number:02d} {section} phrase is too long: {phrase!r}")
            if (
                section not in {"stem", "answer", "takeaway"}
                and len(phrase) > 4
                and len(phrase) / len(source) > 0.55
            ):
                raise ValueError(f"q{number:02d} {section} focus covers too much copy: {phrase!r}")
            marker_at = cue_time(captions, item)
            caption = captions[int(item["caption"])]
            window_start = 0.2 + float(caption["start"])
            window_end = 0.2 + float(caption["end"])
            if not window_start <= marker_at <= window_end:
                raise ValueError(f"q{number:02d} {section} cue falls outside narration")
            duration = cue_duration(item, 0.58)
            if not 0.18 <= duration <= 4.5:
                raise ValueError(f"q{number:02d} {section} cue duration is invalid: {duration}")
            if marker_at + duration > window_end + 0.15:
                raise ValueError(f"q{number:02d} {section} cue finishes outside narration")


def build(
    question: dict[str, Any], audio: dict[str, Any], focus: dict[str, Any],
    course: dict[str, Any] | None = None, background: str = "white",
) -> str:
    number = int(question["number"])
    course = course or {}
    presentation = course.get("presentation", course)
    display_number = str(question.get("displayNumber") or f"{number:02d}")
    brand = str(presentation.get("brandName") or "易哈佛")
    course_name = str(presentation.get("courseName") or "医学考试易错题讲解")
    midroll_label = str(presentation.get("midrollLabel") or f"{brand}教研提醒")
    outro_title = str(presentation.get("outroTitle") or f"关注{brand}")
    outro_text = str(presentation.get("outroText") or "理解考点，比只记答案更重要")
    disclaimer = str(
        presentation.get("disclaimer")
        or "医学考试题目解析 · 仅供备考学习，不作为诊疗或用药建议"
    )
    module_short = course_name.removesuffix("讲解")
    captions = audio["captions"]
    validate_focus(question, captions, focus, midroll_label)
    knowledge_focus = [dict(item, markerId=f"tk-k{index}") for index, item in enumerate(focus["knowledge"])]
    reminder_focus = [dict(item, markerId=f"tk-r{index}") for index, item in enumerate(focus["reminder"])]
    analysis_focus = [dict(item, markerId=f"tk-a{index}") for index, item in enumerate(focus["analysis"])]
    stem_focus = focus.get("stem", [])
    answer_focus_cues = focus.get("answer", [])
    takeaway_focus = focus.get("takeaway", [])
    outro_at = time_of(captions, 13)
    duration = round(max(float(audio["duration"]) + 0.35, outro_at + 4.5), 3)
    read_at = time_of(captions, 1)
    lesson_at = time_of(captions, 2)
    knowledge_at = time_of(captions, 3)
    brand_at = time_of(captions, 6)
    analysis_at = time_of(captions, 7)
    answer_at = time_of(captions, 10)
    takeaway_at = time_of(captions, 12)

    read_options = "".join(
        f'<div class="option-row"><b>{key}</b><span>{esc(value)}</span></div>'
        for key, value in question["options"].items()
    )
    lesson_options = "".join(
        f'<div class="option-row" id="option-{key}"><b>{key}</b><span>{esc(value)}</span></div>'
        for key, value in question["options"].items()
    )
    knowledge_rows = "".join(
        '<div class="knowledge-row">'
        f'<b>0{index + 1}</b><p><strong>{esc(title)}</strong>'
        f'{marked_phrases(text, [item for item in knowledge_focus if int(item["row"]) == index])}</p></div>'
        for index, (title, text) in enumerate(question["knowledge"])
    )
    analysis_rows = "".join(
        f'<div class="analysis-row" id="analysis-row-{esc(key)}">'
        f'<b>{esc(key)}</b><p>{marked_phrases(note, [item for item in analysis_focus if str(item["row"]) == key])}</p></div>'
        for key, note in question["optionNotes"]
    )
    takeaway = "".join(
        f'<div class="memory-row">{marked(line, f"tk-t{index}", "circle" if index == 3 else "underline")}</div>'
        for index, line in enumerate(question["takeawayLines"])
    )
    caption_html = "".join(
        f'<div class="caption{" long" if len(item["text"]) > 27 else ""}" id="caption-{index}">{esc(item["text"])}</div>'
        for index, item in enumerate(captions[:-1])
    )
    caption_json = json.dumps(captions[:-1], ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    audio_src = audio["audio"]
    read_stem = mark_stem(question["stem"], question["marks"], "read")
    lesson_stem = mark_stem(question["stem"], question["marks"], "compact", True)

    knowledge_panel = panel(
        "teach-knowledge", "知识点拆解",
        f'<h3>{esc(question["topic"])}</h3><div class="knowledge-list">{knowledge_rows}</div>',
        True,
    )
    reminder_text = str(question["segments"][6][1]).removeprefix(f"{midroll_label}：")
    brand_panel = panel(
        "teach-brand", midroll_label,
        '<div class="brand-message"><span class="large-leaf"></span>'
        f'<p>{marked_phrases(reminder_text, reminder_focus)}</p></div>',
    )
    analysis_panel = panel(
        "teach-analysis", "逐项辨析 · 暂不标答案",
        f'<div class="analysis-list">{analysis_rows}</div>',
    )
    answer_focus = str(answer_focus_cues[0]["phrase"])
    answer_panel = panel(
        "teach-answer", "答案揭晓",
        f'<div class="answer-line"><span>{esc(question["answer"])}</span><h3>{esc(question["options"][question["answer"]])}</h3></div>'
        f'<p class="answer-reason">{marked_phrase(question["answerReason"], answer_focus, "tk-answer", "highlight")}</p>',
    )
    takeaway_panel = panel(
        "teach-takeaway", "考点收口",
        f'<h3>考点口诀</h3><div class="memory-line">{takeaway}</div>',
    )

    composition_id = f"ehafo-question-q{number:02d}-{background}-v1"
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=1080, height=1920" />
  <title>{esc(course_name)} {esc(display_number)}</title>
  <script src="node_modules/gsap/dist/gsap.min.js"></script>
  <style>
    @font-face {{ font-family:"PingFang SC"; src:local("PingFang SC"); }}
    @font-face {{ font-family:"Songti SC"; src:local("Songti SC"); }}
    * {{ box-sizing:border-box; }}
    html,body {{ width:1080px;height:1920px;margin:0;overflow:hidden;background:#F4F6F8; }}
    body {{ color:#15202B;font-family:"PingFang SC",sans-serif;letter-spacing:0; }}
    #root {{ position:relative;width:1080px;height:1920px;overflow:hidden;background:#F4F6F8; }}
    .scene {{ position:absolute;inset:0;width:100%;height:100%;overflow:hidden;background:#F4F6F8; }}
    #read,#lesson,#outro {{ opacity:0; }}
    .watermarks {{ position:absolute;inset:0;color:#1769E0;opacity:.045;font-size:88px;font-weight:900; }}
    .watermarks span {{ position:absolute;transform:rotate(-18deg);white-space:nowrap; }}
    .watermarks span:nth-child(1) {{ left:92px;top:390px; }} .watermarks span:nth-child(2) {{ right:115px;top:910px; }} .watermarks span:nth-child(3) {{ left:150px;bottom:350px; }}
    h1,h2,h3,p {{ margin:0;letter-spacing:0; }}
    .cover-inner {{ position:relative;z-index:2;width:100%;height:100%;padding:120px 182px 370px 72px;display:flex;flex-direction:column;justify-content:center;gap:30px; }}
    .eyebrow,.teaching-eyebrow {{ width:max-content;padding:9px 15px;border:2px solid #1769E0;color:#1769E0;background:#F4F6F8;font-size:28px;font-weight:850; }}
    .cover-number {{ color:#1769E0;font-size:180px;line-height:.9;font-weight:900;font-variant-numeric:tabular-nums; }}
    .cover h1 {{ max-width:820px;font-size:82px;line-height:1.22;font-weight:900; }}
    .cover-topic {{ max-width:820px;font-family:"Songti SC",serif;color:#536273;font-size:46px;line-height:1.42;font-weight:700; }}
    .read-inner {{ position:relative;z-index:2;width:100%;height:100%;padding:300px 182px 330px 72px;display:flex;flex-direction:column;gap:22px; }}
    .read-label {{ width:max-content;padding:9px 15px;color:#FFFFFF;background:#1769E0;font-size:29px;font-weight:850; }}
    .read-board {{ flex:1;min-height:0;padding:28px 26px;border:2px solid #DCE3EA;background:#FFFFFF;transform-origin:top left; }}
    .read-head {{ margin-bottom:18px;color:#1769E0;font-size:30px;font-weight:850; }}
    .read-stem {{ font-size:52px;line-height:1.43;font-weight:850; }}
    .read-options {{ margin-top:24px;display:grid;gap:10px; }}
    .option-row {{ min-height:70px;padding:9px 15px;display:grid;grid-template-columns:50px 1fr;align-items:center;gap:8px;border:2px solid #DCE3EA;background:#F4F6F8;font-size:36px;line-height:1.3; }}
    .option-row b {{ color:#1769E0;font-size:39px; }}
    .read-options .option-row {{ min-height:78px;font-size:41px;background:#FFFFFF; }}
    .read-note {{ color:#536273;font-size:28px;line-height:1.45; }}
    .mark-wrap,.teach-mark {{ position:relative;display:inline;z-index:1;-webkit-box-decoration-break:clone;box-decoration-break:clone; }}
    .mark-text,.teach-mark-text {{ position:relative;z-index:2; }}
    .mark-stroke,.teach-stroke {{ position:absolute;z-index:1;pointer-events:none; }}
    .mark-underline,.teach-underline {{ background-image:linear-gradient(#B42318,#B42318);background-repeat:no-repeat;background-position:0 100%;background-size:0% 6px; }}
    .mark-highlight,.teach-highlight {{ background-image:linear-gradient(rgba(180,35,24,.20),rgba(180,35,24,.20));background-repeat:no-repeat;background-position:0 76%;background-size:0% 72%; }}
    .mark-circle .mark-stroke,.mark-double .mark-stroke,.teach-circle .teach-stroke {{ left:-8px;right:-8px;top:-4px;bottom:-4px;border:4px solid #B42318;border-radius:48% 52% 46% 54%;transform:scale(0) rotate(-2deg); }}
    .mark-circle,.mark-double,.teach-circle {{ display:inline-block;white-space:nowrap; }}
    .mark-complete.mark-underline {{ background-size:100% 6px; }} .mark-complete.mark-highlight {{ background-size:100% 72%; }}
    .mark-complete.mark-circle .mark-stroke,.mark-complete.mark-double .mark-stroke {{ transform:scale(1) rotate(-2deg); }}
    .lesson-inner {{ position:relative;z-index:2;width:100%;height:100%;padding:300px 182px 310px 72px;display:flex;flex-direction:column;gap:17px; }}
    .question-board {{ flex:0 0 auto;padding:18px 20px 20px;border:2px solid #DCE3EA;background:#FFFFFF; }}
    .question-head {{ margin-bottom:11px;color:#1769E0;font-size:27px;font-weight:850; }}
    .question-stem {{ font-size:38px;line-height:1.38;font-weight:850; }}
    .option-list {{ margin-top:12px;display:grid;gap:6px; }}
    .option-list .option-row {{ min-height:54px;padding:6px 12px;font-size:31px;grid-template-columns:42px 1fr; }}
    .option-list .option-row b {{ font-size:33px; }}
    .teaching-frame {{ position:relative;flex:1 1 auto;min-height:0;overflow:hidden;border-top:3px solid #1769E0;background:#FFFFFF; }}
    .teaching-panel {{ position:absolute;inset:0;width:100%;height:100%;padding:24px;opacity:0;background:#FFFFFF;display:flex;flex-direction:column;gap:15px; }}
    .teaching-panel.teaching-visible {{ opacity:1; }}
    .teaching-panel h3 {{ font-size:43px;line-height:1.28;font-weight:900; }}
    .knowledge-list {{ display:grid;gap:10px; }}
    .knowledge-row {{ padding:11px 12px;display:grid;grid-template-columns:48px 1fr;gap:10px;align-items:start;background:#F4F6F8; }}
    .knowledge-row b {{ color:#1769E0;font-size:30px; }} .knowledge-row p {{ font-size:32px;line-height:1.38;font-weight:600; }} .knowledge-row strong {{ display:block;margin-bottom:3px;color:#1769E0;font-size:31px; }}
    .analysis-list {{ display:grid;gap:6px; }}
    .analysis-row {{ padding:7px 10px;display:grid;grid-template-columns:38px 1fr;gap:7px;align-items:start;border-bottom:2px solid #DCE3EA;transform-origin:left center; }}
    .analysis-row b {{ color:#1769E0;font-size:30px; }} .analysis-row p {{ font-size:29px;line-height:1.32;font-weight:600; }}
    .brand-message {{ margin:auto 0;padding:30px 26px;display:grid;grid-template-columns:88px 1fr;gap:20px;align-items:center;background:#F4F6F8;border:2px solid #DCE3EA; }}
    .large-leaf,.brand-leaf {{ background:url("assets/brand/ehafo-leaf.png") center/contain no-repeat; }}
    .large-leaf {{ width:82px;height:82px; }} .brand-message p {{ font-size:38px;line-height:1.52;font-weight:750; }}
    .answer-line {{ display:flex;align-items:center;gap:22px; }} .answer-line>span {{ width:108px;height:108px;display:grid;place-items:center;color:#FFFFFF;background:#18864B;font-size:72px;font-weight:900; }}
    .answer-line h3 {{ color:#18864B;font-size:49px; }} .answer-reason {{ padding-top:22px;border-top:3px solid #18864B;font-size:38px;line-height:1.48;font-weight:650; }}
    .memory-line {{ display:grid;gap:10px;font-family:"Songti SC",serif;font-size:49px;line-height:1.32;font-weight:850; }}
    .memory-row {{ padding:5px 0;border-bottom:2px solid #DCE3EA; }}
    .caption-rail {{ position:absolute;z-index:70;left:72px;right:182px;bottom:145px;height:170px;display:grid;place-items:center; }}
    .caption {{ position:absolute;width:100%;opacity:0;color:#15202B;text-align:center;font-size:50px;line-height:1.36;font-weight:850;text-shadow:0 2px 0 #FFFFFF,2px 0 0 #FFFFFF,-2px 0 0 #FFFFFF,0 -2px 0 #FFFFFF; }}
    .caption.long {{ font-size:42px; }}
    .top-brand {{ position:absolute;z-index:80;top:220px;left:72px;display:flex;align-items:center;gap:14px;color:#536273;font-size:38px;font-weight:850; }}
    .brand-leaf {{ width:54px;height:54px;flex:0 0 54px; }}
    .course-disclaimer {{ position:absolute;z-index:80;left:72px;right:182px;bottom:45px;color:#536273;text-align:center;font-size:24px;font-weight:650; }}
    .outro {{ z-index:100;display:flex;align-items:center;justify-content:center;background:#FFFFFF; }}
    .outro-inner {{ width:100%;height:100%;padding:220px 182px 260px 72px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:34px;text-align:center; }}
    .outro-logo {{ width:150px;height:150px;background:url("assets/brand/ehafo-leaf.png") center/contain no-repeat; }}
    .outro h2 {{ max-width:760px;font-size:72px;line-height:1.28;font-weight:900; }} .outro p {{ color:#536273;font-size:42px;font-weight:750; }}
    .follow-button {{ width:150px;height:150px;display:grid;place-items:center;border-radius:50%;color:#FFFFFF;background:#1769E0;font-size:104px;line-height:1;font-weight:500;box-shadow:0 18px 40px rgba(23,105,224,.25); }}
    .follow-check {{ position:absolute;opacity:0;color:#18864B;font-size:105px;font-weight:900; }}
    {theme_css(background)}
  </style>
</head>
<body>
<div id="root" data-composition-id="{composition_id}" data-start="0" data-duration="{duration:.3f}" data-width="1080" data-height="1920">
  <audio class="clip" id="narration" src="{esc(audio_src)}" data-start="0.2" data-duration="{float(audio['duration']):.3f}" data-track-index="0" data-volume="1"></audio>
  <section class="scene cover" id="cover" data-layout-allow-overflow data-layout-allow-overlap data-layout-allow-occlusion>{wm()}<div class="cover-inner"><div class="eyebrow">{esc(module_short)}</div><div class="cover-number">{esc(display_number)}</div><h1>{esc(question['coverHook'])}</h1><p class="cover-topic">{esc(question['topic'])}</p></div></section>
  <section class="scene" id="read" data-layout-allow-overflow data-layout-allow-overlap data-layout-allow-occlusion>{wm()}<div class="read-inner"><div class="read-label">跟老师一起读题</div><div class="read-board"><div class="read-head">{esc(display_number)} · {esc(question['type'])}</div><h2 class="read-stem">{read_stem}</h2><div class="read-options">{read_options}</div></div><p class="read-note">先定位题干条件和问法，暂不判断答案。</p></div></section>
  <section class="scene" id="lesson" data-layout-allow-overflow data-layout-allow-overlap data-layout-allow-occlusion>{wm()}<div class="lesson-inner"><div class="question-board"><div class="question-head">{esc(display_number)} · {esc(question['type'])}</div><h2 class="question-stem">{lesson_stem}</h2><div class="option-list">{lesson_options}</div></div><div class="teaching-frame">{knowledge_panel}{brand_panel}{analysis_panel}{answer_panel}{takeaway_panel}</div></div></section>
  <div class="top-brand" data-layout-allow-occlusion><span class="brand-leaf"></span><span>{esc(brand)} · {esc(course_name)}</span></div>
  <div class="course-disclaimer" data-layout-allow-occlusion>{esc(disclaimer)}</div>
  <div class="caption-rail">{caption_html}</div>
  <section class="scene outro" id="outro" data-layout-allow-overlap data-layout-allow-occlusion><div class="outro-inner"><div class="outro-logo"></div><h2>{esc(outro_title)}</h2><p>{esc(outro_text)}</p><div class="follow-button"><span class="follow-plus">＋</span><span class="follow-check">✓</span></div></div></section>
</div>
<script>
  window.__timelines=window.__timelines||{{}};
  const CAPTIONS={caption_json};
  const tl=gsap.timeline({{paused:true}});
  tl.from("#cover .eyebrow",{{x:-36,duration:.52,ease:"expo.out"}},.2);
  tl.from("#cover .cover-number",{{scale:.82,duration:.7,ease:"back.out(1.2)"}},.32);
  tl.from("#cover h1",{{y:38,duration:.62,ease:"power3.out"}},.46);
  tl.from("#cover .cover-topic",{{x:30,duration:.48,ease:"sine.out"}},.7);
  function pushScene(next,previous,at){{tl.fromTo(next,{{x:72,opacity:0}},{{x:0,opacity:1,duration:.48,ease:"power3.inOut",immediateRender:false}},at);tl.to(previous,{{x:-72,opacity:0,duration:.48,ease:"power3.inOut"}},at);}}
  pushScene("#read","#cover",{read_at - .55:.3f});
  tl.from("#read .read-label",{{x:-28,opacity:0,duration:.28,ease:"expo.out"}},{read_at - .48:.3f});
  tl.from("#read .read-stem",{{y:28,opacity:0,duration:.30,ease:"power3.out"}},{read_at - .32:.3f});
  tl.from("#read .option-row",{{x:22,opacity:0,duration:.24,stagger:.035,ease:"sine.out"}},{read_at - .20:.3f});
  tl.from("#read .read-note",{{opacity:0,duration:.28,ease:"power1.out"}},{read_at - .12:.3f});
  function drawMark(selector,at,duration=.58){{const el=document.querySelector(selector);if(!el)return;if(el.classList.contains("mark-circle")||el.classList.contains("mark-double")||el.classList.contains("teach-circle")){{tl.fromTo(`${{selector}} .mark-stroke,${{selector}} .teach-stroke`,{{scale:0}},{{scale:1,duration,ease:"back.out(1.3)"}},at);}}else{{const size=el.classList.contains("mark-highlight")||el.classList.contains("teach-highlight")?"100% 72%":"100% 6px";tl.fromTo(selector,{{backgroundSize:"0% 0%"}},{{backgroundSize:size,duration,ease:"power2.out"}},at);}}}}
  {''.join(f'drawMark("#read-mark-{i}",{cue_time(captions, stem_focus[i]):.3f},{cue_duration(stem_focus[i], .55):.3f});' for i in range(len(question['marks'])))}
  pushScene("#lesson","#read",{lesson_at:.3f});
  tl.from("#lesson .question-head",{{x:-24,opacity:0,duration:.38,ease:"expo.out"}},{lesson_at + .18:.3f});
  tl.from("#lesson .question-stem",{{y:20,opacity:0,duration:.45,ease:"power3.out"}},{lesson_at + .26:.3f});
  tl.from("#lesson .option-row",{{x:20,opacity:0,duration:.28,stagger:.045,ease:"sine.out"}},{lesson_at + .38:.3f});
  tl.from("#teach-knowledge .teaching-eyebrow",{{x:-20,opacity:0,duration:.34,ease:"expo.out"}},{knowledge_at:.3f});
  tl.from("#teach-knowledge h3",{{y:20,opacity:0,duration:.42,ease:"power3.out"}},{knowledge_at + .08:.3f});
  tl.from("#teach-knowledge .knowledge-row",{{x:22,opacity:0,duration:.34,stagger:.09,ease:"sine.out"}},{knowledge_at + .2:.3f});
  {''.join(f'drawMark("#{item["markerId"]}",{cue_time(captions, item):.3f},{cue_duration(item, .62):.3f});' for item in knowledge_focus)}
  function switchTeaching(next,previous,at){{tl.fromTo(next,{{x:56,opacity:0}},{{x:0,opacity:1,duration:.42,ease:"power3.inOut",immediateRender:false}},at);tl.to(previous,{{x:-56,opacity:0,duration:.42,ease:"power3.inOut"}},at);}}
  switchTeaching("#teach-brand","#teach-knowledge",{brand_at:.3f});
  tl.from("#teach-brand .large-leaf",{{scale:.72,opacity:0,duration:.5,ease:"back.out(1.25)"}},{brand_at + .16:.3f});
  tl.from("#teach-brand p",{{y:22,opacity:0,duration:.5,ease:"power3.out"}},{brand_at + .24:.3f});
  {''.join(f'drawMark("#{item["markerId"]}",{cue_time(captions, item):.3f},{cue_duration(item, .58):.3f});' for item in reminder_focus)}
  switchTeaching("#teach-analysis","#teach-brand",{analysis_at:.3f});
  tl.from("#teach-analysis .analysis-row",{{x:22,opacity:0,duration:.3,stagger:.055,ease:"sine.out"}},{analysis_at + .18:.3f});
  {''.join(f'tl.fromTo("#analysis-row-{item["row"]} b",{{scale:1}},{{scale:1.18,duration:.22,repeat:1,yoyo:true,ease:"power2.inOut"}},{max(analysis_at + .18, cue_time(captions, item) - .12):.3f});drawMark("#{item["markerId"]}",{cue_time(captions, item):.3f},{cue_duration(item, .52):.3f});' for item in analysis_focus)}
  switchTeaching("#teach-answer","#teach-analysis",{answer_at:.3f});
  tl.from("#teach-answer .answer-line>span",{{scale:.68,opacity:0,duration:.54,ease:"back.out(1.3)"}},{answer_at + .12:.3f});
  tl.from("#teach-answer h3",{{x:28,opacity:0,duration:.46,ease:"power3.out"}},{answer_at + .22:.3f});
  tl.from("#teach-answer .answer-reason",{{y:20,opacity:0,duration:.5,ease:"sine.out"}},{answer_at + .38:.3f});
  tl.to("#option-{esc(question['answer'])}",{{backgroundColor:"#18864B",color:"#FFFFFF",borderColor:"#18864B",duration:.35,ease:"power2.out"}},{answer_at + .18:.3f});
  tl.to("#option-{esc(question['answer'])} b",{{color:"#FFFFFF",duration:.2,ease:"power1.out"}},{answer_at + .18:.3f});
  drawMark("#tk-answer",{cue_time(captions, answer_focus_cues[0]):.3f},{cue_duration(answer_focus_cues[0], .7):.3f});
  switchTeaching("#teach-takeaway","#teach-answer",{takeaway_at:.3f});
  tl.from("#teach-takeaway h3",{{y:18,opacity:0,duration:.42,ease:"power3.out"}},{takeaway_at + .1:.3f});
  tl.from("#teach-takeaway .memory-row",{{x:28,opacity:0,duration:.4,stagger:.12,ease:"sine.out"}},{takeaway_at + .22:.3f});
  {''.join(f'drawMark("#tk-t{i}",{cue_time(captions, takeaway_focus[i]):.3f},{cue_duration(takeaway_focus[i], .55):.3f});' for i in range(4))}
  CAPTIONS.forEach((caption,index)=>{{const s=`#caption-${{index}}`;const start=.2+caption.start;const end=.2+caption.end;tl.set(s,{{opacity:1}},start);tl.fromTo(s,{{y:9}},{{y:0,duration:.16,ease:"power2.out"}},start);tl.set(s,{{opacity:0}},end);}});
  tl.fromTo("#outro",{{scale:.94,opacity:0}},{{scale:1,opacity:1,duration:.52,ease:"power3.inOut",immediateRender:false}},{outro_at:.3f});
  tl.from("#outro .outro-logo",{{scale:.7,opacity:0,duration:.58,ease:"back.out(1.3)"}},{outro_at + .18:.3f});
  tl.from("#outro h2",{{y:28,opacity:0,duration:.5,ease:"power3.out"}},{outro_at + .3:.3f});
  tl.from("#outro p",{{x:24,opacity:0,duration:.46,ease:"sine.out"}},{outro_at + .46:.3f});
  tl.from("#outro .follow-button",{{scale:.4,opacity:0,duration:.52,ease:"back.out(1.5)"}},{outro_at + .72:.3f});
  tl.to("#outro .follow-button",{{scale:.88,duration:.16,ease:"power2.in"}},{outro_at + 2.05:.3f});
  tl.set("#outro .follow-plus",{{opacity:0}},{outro_at + 2.22:.3f});
  tl.set("#outro .follow-check",{{opacity:1}},{outro_at + 2.22:.3f});
  tl.to("#outro .follow-button",{{scale:1,backgroundColor:"#EAF6EF",duration:.34,ease:"back.out(1.4)"}},{outro_at + 2.22:.3f});
  window.__timelines["{composition_id}"]=tl;
</script>
</body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="1-1")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--voice-dir", type=Path, default=VOICE_ROOT)
    parser.add_argument("--focus-data", type=Path, default=FOCUS_DATA)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--variant", default="v1")
    parser.add_argument("--file-prefix", default="question")
    parser.add_argument("--background", choices=("white", "green"), default="white")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    start, end = (int(value) for value in args.questions.split("-", 1))
    payload = json.loads(args.data.resolve().read_text(encoding="utf-8"))
    focus_payload = json.loads(args.focus_data.resolve().read_text(encoding="utf-8"))["questions"]
    output_root = args.output_dir.resolve()
    voice_root = args.voice_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    for question in payload["questions"]:
        number = int(question["number"])
        if not start <= number <= end:
            continue
        manifest_path = voice_root / f"q{number:02d}" / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing narration manifest: {manifest_path}")
        audio = json.loads(manifest_path.read_text(encoding="utf-8"))
        output_path = output_root / f"{args.file_prefix}-q{number:02d}-{args.background}-{args.variant}.html"
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(f"Refusing to overwrite: {output_path}")
        focus = focus_payload.get(str(number))
        if focus is None:
            raise KeyError(f"Missing focus configuration for q{number:02d}")
        output_path.write_text(
            build(question, audio, focus, payload, args.background), encoding="utf-8"
        )
        try:
            label = output_path.relative_to(ROOT)
        except ValueError:
            label = output_path
        print(f"Built {label}")


if __name__ == "__main__":
    main()
