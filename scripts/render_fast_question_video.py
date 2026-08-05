#!/usr/bin/env python3

"""Render medical question videos quickly from cached stills and FFmpeg transitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from build_question_compositions import cue_time


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / ".runtime-questions.json"
DEFAULT_FOCUS = ROOT / "data" / "focus-cues.auto.json"
DEFAULT_VOICE = ROOT / "assets" / "voice" / "reviewed-smooth"
DEFAULT_WORK = ROOT / "generated" / "fast"
DEFAULT_OUTPUT = ROOT / "renders"
WIDTH = 1080
HEIGHT = 1920
SANS_FONT = Path("/System/Library/Fonts/PingFang.ttc")
SERIF_FONT = Path("/System/Library/Fonts/Supplemental/Songti.ttc")

BG = "#F4F6F8"
PAPER = "#FFFFFF"
INK = "#15202B"
MUTED = "#536273"
LINE = "#DCE3EA"
BLUE = "#1769E0"
GREEN = "#18864B"
RED = "#B42318"
HIGHLIGHT = "#F0D3D1"  # rgba(180, 35, 24, 0.20) composited over white
WATERMARK = "#EAEFF7"
BRAND_INK = MUTED
LABEL_INK = PAPER
SELECTED_INK = PAPER
CAPTION_STROKE = PAPER
BACKGROUND_NAME = "white"
RENDERER_VERSION = "pillow-ffmpeg-fast-hq-aligned-v5.3.1"

SANS_FACE = {"regular": 2, "medium": 5, "semibold": 8}
SERIF_FACE = {"regular": 6, "bold": 1, "black": 0}


@dataclass
class Clip:
    image: Path
    hold: float
    transition: str = "fade"
    transition_duration: float = 0.28


def set_theme(background: str) -> None:
    global BG, PAPER, INK, MUTED, LINE, BLUE, HIGHLIGHT, WATERMARK
    global BRAND_INK, LABEL_INK, SELECTED_INK, CAPTION_STROKE, BACKGROUND_NAME
    if background == "white":
        BG, PAPER, INK, MUTED = "#F4F6F8", "#FFFFFF", "#15202B", "#536273"
        LINE, BLUE = "#DCE3EA", "#1769E0"
        HIGHLIGHT, WATERMARK = "#F0D3D1", "#EAEFF7"
        BRAND_INK, LABEL_INK, SELECTED_INK, CAPTION_STROKE = MUTED, PAPER, PAPER, PAPER
    elif background == "green":
        BG, PAPER, INK, MUTED = "#003A46", "#00343D", "#F7FAFA", "#D5E2E3"
        LINE, BLUE = "#6F898D", "#F4D04F"
        HIGHLIGHT = "#243136"  # rgba(180,35,24,.20) over #00343D
        WATERMARK = "#B8D637"
        BRAND_INK, LABEL_INK, SELECTED_INK, CAPTION_STROKE = INK, BG, INK, BG
    else:
        raise ValueError(f"Unsupported background: {background}")
    BACKGROUND_NAME = background


def scene_group(segment_index: int) -> str:
    if segment_index == 0:
        return "cover"
    if segment_index == 1:
        return "read"
    if 2 <= segment_index <= 5:
        return "knowledge"
    if segment_index == 6:
        return "reminder"
    if 7 <= segment_index <= 9:
        return "analysis"
    if 10 <= segment_index <= 11:
        return "answer"
    if segment_index == 12:
        return "takeaway"
    return "outro"


def transition_for_state(segment_index: int, state_index: int) -> tuple[str, float]:
    if state_index > 0:
        return "fade", 0.20
    if segment_index == 13:
        return "fade", 0.52
    if segment_index > 0 and scene_group(segment_index) != scene_group(segment_index - 1):
        return "slideleft", 0.30
    return "fade", 0.16


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def font(
    size: int,
    serif: bool = False,
    weight: str = "regular",
) -> ImageFont.FreeTypeFont:
    path = SERIF_FONT if serif else SANS_FONT
    faces = SERIF_FACE if serif else SANS_FACE
    return ImageFont.truetype(str(path), size=size, index=faces[weight])


def text_width(text: str, selected_font: ImageFont.FreeTypeFont) -> float:
    return float(selected_font.getlength(text))


def layout_lines(
    text: str, selected_font: ImageFont.FreeTypeFont, max_width: float
) -> list[tuple[int, int, str]]:
    lines: list[tuple[int, int, str]] = []
    start = 0
    cursor = 0
    current = ""
    for character in text:
        if character == "\n":
            lines.append((start, cursor, current))
            cursor += 1
            start = cursor
            current = ""
            continue
        candidate = current + character
        if current and text_width(candidate, selected_font) > max_width:
            lines.append((start, cursor, current))
            start = cursor
            current = character
        else:
            current = candidate
        cursor += 1
    lines.append((start, cursor, current))
    return lines


def fit_font_size(
    text: str,
    max_width: int,
    max_height: int,
    initial: int,
    minimum: int,
    weight: str = "regular",
) -> int:
    for size in range(initial, minimum - 1, -2):
        selected_font = font(size, weight=weight)
        lines = layout_lines(text, selected_font, max_width)
        line_height = int(size * 1.42)
        if len(lines) * line_height <= max_height:
            return size
    return minimum


def draw_marker(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    mode: str,
) -> None:
    x0, y0, x1, y1 = box
    if mode == "highlight":
        draw.rounded_rectangle(
            (x0 - 4, y0 + (y1 - y0) * 0.28, x1 + 4, y1 + 2),
            radius=3,
            fill=HIGHLIGHT,
        )
    elif mode == "circle" and x1 - x0 < 320:
        draw.ellipse((x0 - 8, y0 - 4, x1 + 8, y1 + 5), outline=RED, width=4)
    else:
        draw.line((x0, y1 + 2, x1, y1 + 2), fill=RED, width=6)


def draw_marked_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    selected_font: ImageFont.FreeTypeFont,
    fill: str | None = None,
    marks: list[dict[str, Any]] | None = None,
    line_ratio: float = 1.42,
    stroke_width: int = 0,
) -> int:
    x, y = xy
    fill = fill or INK
    lines = layout_lines(text, selected_font, max_width)
    line_height = int(selected_font.size * line_ratio)
    marks = marks or []
    spans: list[tuple[int, int, str]] = []
    for item in marks:
        phrase = str(item["phrase"])
        start = text.find(phrase)
        if start >= 0:
            spans.append((start, start + len(phrase), str(item.get("mode", "underline"))))
    for line_index, (start, end, line) in enumerate(lines):
        line_y = y + line_index * line_height
        for mark_start, mark_end, mode in spans:
            left = max(start, mark_start)
            right = min(end, mark_end)
            if left >= right:
                continue
            prefix = text[start:left]
            marked = text[left:right]
            marker_x0 = x + text_width(prefix, selected_font)
            marker_x1 = marker_x0 + text_width(marked, selected_font)
            bbox = draw.textbbox((marker_x0, line_y), marked, font=selected_font)
            draw_marker(draw, (marker_x0, bbox[1], marker_x1, bbox[3]), mode)
        draw.text(
            (x, line_y), line, font=selected_font, fill=fill,
            stroke_width=stroke_width, stroke_fill=fill,
        )
    return y + len(lines) * line_height


def draw_brand_chrome(image: Image.Image, presentation: dict[str, Any]) -> None:
    draw = ImageDraw.Draw(image)
    brand = str(presentation.get("brandName") or "易哈佛")
    course = str(presentation.get("courseName") or "医学考试易错题讲解")
    leaf = ROOT / "assets" / "brand" / "ehafo-leaf.png"
    if leaf.exists():
        icon = Image.open(leaf).convert("RGBA")
        icon.thumbnail((54, 54), Image.Resampling.LANCZOS)
        image.alpha_composite(icon, (72, 220))
    draw.text(
        (140, 219), f"{brand} · {course}",
        font=font(38, weight="semibold"), fill=BRAND_INK,
    )
    if BACKGROUND_NAME == "green":
        watermark_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        watermark_draw = ImageDraw.Draw(watermark_layer)
        watermark_font = font(36, weight="semibold")
        text_width_px = int(text_width(brand, watermark_font))
        mark_width = 38 + 10 + text_width_px
        mark_x, mark_y = WIDTH - 24 - mark_width, HEIGHT - 278 - 42
        if leaf.exists():
            mark_icon = Image.open(leaf).convert("RGBA")
            mark_icon.thumbnail((38, 38), Image.Resampling.LANCZOS)
            watermark_layer.alpha_composite(mark_icon, (mark_x, mark_y + 2))
        watermark_draw.text(
            (mark_x + 48, mark_y), brand, font=watermark_font, fill=WATERMARK
        )
        watermark_layer.putalpha(watermark_layer.getchannel("A").point(lambda a: int(a * .12)))
        image.alpha_composite(watermark_layer)
    else:
        watermark_font = font(88, weight="semibold")
        for x, y in ((92, 390), (610, 910), (150, 1470)):
            draw.text((x, y), brand, font=watermark_font, fill=WATERMARK)
    disclaimer = str(
        presentation.get("disclaimer")
        or "医学考试题目解析 · 仅供备考学习，不作为诊疗或用药建议"
    )
    disclaimer_font = font(24, weight="medium")
    disclaimer_width = text_width(disclaimer, disclaimer_font)
    draw.text((72 + (826 - disclaimer_width) / 2, 1837), disclaimer, font=disclaimer_font, fill=MUTED)


def draw_label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    filled: bool = False,
) -> int:
    x, y = xy
    selected_font = font(28, weight="semibold")
    width = int(text_width(text, selected_font)) + 30
    height = 54
    draw.rectangle(
        (x, y, x + width, y + height),
        fill=BLUE if filled else BG,
        outline=BLUE,
        width=2,
    )
    draw.text((x + 15, y + 7), text, font=selected_font, fill=LABEL_INK if filled else BLUE)
    return y + height


def draw_option_rows(
    draw: ImageDraw.ImageDraw,
    options: dict[str, Any],
    box: tuple[int, int, int, int],
    answer: str | None = None,
    row_height: int = 54,
    gap: int = 6,
    text_size: int = 31,
    key_size: int = 33,
    white_rows: bool = False,
) -> None:
    x0, y0, x1, _y1 = box
    for index, (key, value) in enumerate(options.items()):
        y = y0 + index * (row_height + gap)
        selected = answer == key
        fill = GREEN if selected else PAPER if white_rows else BG
        text_fill = SELECTED_INK if selected else INK
        draw.rectangle((x0, y, x1, y + row_height), fill=fill, outline=GREEN if selected else LINE, width=2)
        text_y = y + max(4, (row_height - text_size) // 2 - 3)
        draw.text((x0 + 13, text_y), key, font=font(key_size, weight="semibold"), fill=SELECTED_INK if selected else BLUE)
        draw.text((x0 + 64, text_y), str(value), font=font(text_size), fill=text_fill)


def draw_question_board(
    image: Image.Image,
    question: dict[str, Any],
    stem_marks: list[dict[str, Any]],
    reveal_answer: bool = False,
    expanded: bool = False,
) -> int:
    draw = ImageDraw.Draw(image)
    x0, x1 = 72, 898
    y0 = 374 if expanded else 300
    stem = str(question["stem"])
    stem_size = 52 if expanded else 38
    stem_font = font(stem_size, weight="semibold")
    stem_max_width = 774 if expanded else 786
    stem_lines = layout_lines(stem, stem_font, stem_max_width)
    stem_height = len(stem_lines) * int(stem_size * (1.43 if expanded else 1.38))
    stem_y = y0 + (76 if expanded else 61)
    options_y = stem_y + stem_height + (24 if expanded else 12)
    row_height = 78 if expanded else 54
    gap = 10 if expanded else 6
    options_height = len(question["options"]) * row_height + (len(question["options"]) - 1) * gap
    content_bottom = options_y + options_height + (28 if expanded else 52)
    y1 = 1502 if expanded else content_bottom
    draw.rectangle((x0, y0, x1, y1), fill=PAPER, outline=LINE, width=2)
    draw.text(
        (x0 + (26 if expanded else 20), y0 + (26 if expanded else 18)),
        f"{question.get('displayNumber', question['number'])} · {question['type']}",
        font=font(30 if expanded else 27, weight="semibold"), fill=BLUE,
    )
    draw_marked_text(
        draw, stem, (x0 + (26 if expanded else 20), stem_y), stem_max_width,
        stem_font, marks=stem_marks, line_ratio=1.43 if expanded else 1.38,
    )
    draw_option_rows(
        draw, question["options"],
        (x0 + (26 if expanded else 20), options_y, x1 - (26 if expanded else 20), y1 - 20),
        str(question["answer"]) if reveal_answer else None,
        row_height=row_height,
        gap=gap,
        text_size=41 if expanded else 31,
        key_size=39 if expanded else 33,
        white_rows=expanded,
    )
    return y1


def draw_panel_shell(
    image: Image.Image,
    eyebrow: str,
    title: str = "",
    top: int = 880,
) -> tuple[ImageDraw.ImageDraw, int]:
    draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = 72, top, 898, 1610
    draw.rectangle((x0, y0, x1, y1), fill=PAPER)
    draw.line((x0, y0, x1, y0), fill=BLUE, width=3)
    cursor = draw_label(draw, (x0 + 24, y0 + 24), eyebrow) + 15
    if title:
        draw.text((x0 + 24, cursor), title, font=font(43, weight="semibold"), fill=INK)
        cursor += 70
    return draw, cursor


def active_marks(focus: dict[str, Any], section: str, applied: set[str]) -> list[dict[str, Any]]:
    return [
        item for index, item in enumerate(focus.get(section, []))
        if f"{section}:{index}" in applied
    ]


def draw_knowledge(
    image: Image.Image, question: dict[str, Any], focus: dict[str, Any], applied: set[str], top: int
) -> None:
    draw, cursor = draw_panel_shell(image, "知识点拆解", str(question["topic"]), top)
    marks = active_marks(focus, "knowledge", applied)
    for row, (title, text) in enumerate(question["knowledge"]):
        row_height = 130
        draw.rectangle((96, cursor, 874, cursor + row_height), fill=BG)
        draw.text((108, cursor + 12), f"0{row + 1}", font=font(30, weight="semibold"), fill=BLUE)
        draw.text((166, cursor + 9), str(title), font=font(31, weight="semibold"), fill=BLUE)
        row_marks = [item for item in marks if int(item.get("row", -1)) == row]
        draw_marked_text(
            draw, str(text), (166, cursor + 48), 684,
            font(30, weight="medium"), marks=row_marks, line_ratio=1.38,
        )
        cursor += row_height + 10


def draw_reminder(
    image: Image.Image, question: dict[str, Any], focus: dict[str, Any], applied: set[str], label: str, top: int
) -> None:
    draw, cursor = draw_panel_shell(image, label, top=top)
    text = str(question["segments"][6][1]).removeprefix(f"{label}：")
    card_top = cursor + 30
    draw.rectangle((96, card_top, 874, card_top + 390), fill=BG, outline=LINE, width=2)
    leaf = ROOT / "assets" / "brand" / "ehafo-leaf.png"
    if leaf.exists():
        icon = Image.open(leaf).convert("RGBA")
        icon.thumbnail((82, 82), Image.Resampling.LANCZOS)
        image.alpha_composite(icon, (120, card_top + 145))
    draw_marked_text(
        draw, text, (224, card_top + 58), 620, font(38, weight="medium"),
        marks=active_marks(focus, "reminder", applied), line_ratio=1.52,
    )


def draw_analysis(
    image: Image.Image, question: dict[str, Any], focus: dict[str, Any], applied: set[str], top: int
) -> None:
    draw, cursor = draw_panel_shell(image, "逐项辨析 · 暂不标答案", top=top)
    marks = active_marks(focus, "analysis", applied)
    for key, note in question["optionNotes"]:
        row_height = 102
        draw.line((96, cursor + row_height - 4, 874, cursor + row_height - 4), fill=LINE, width=2)
        draw.text((106, cursor + 10), str(key), font=font(30, weight="semibold"), fill=BLUE)
        row_marks = [item for item in marks if str(item.get("row")) == str(key)]
        draw_marked_text(
            draw, str(note), (151, cursor + 8), 704,
            font(28, weight="medium"), marks=row_marks, line_ratio=1.32,
        )
        cursor += row_height


def draw_answer(
    image: Image.Image, question: dict[str, Any], focus: dict[str, Any], applied: set[str], top: int
) -> None:
    draw, cursor = draw_panel_shell(image, "答案揭晓", top=top)
    answer = str(question["answer"])
    draw.rectangle((96, cursor + 4, 204, cursor + 112), fill=GREEN)
    draw.text((125, cursor + 10), answer, font=font(72, weight="semibold"), fill=SELECTED_INK)
    draw.text((226, cursor + 28), str(question["options"][answer]), font=font(49, weight="semibold"), fill=GREEN)
    draw.line((96, cursor + 142, 874, cursor + 142), fill=GREEN, width=3)
    draw_marked_text(
        draw, str(question["answerReason"]), (96, cursor + 166), 778,
        font(36, weight="medium"), marks=active_marks(focus, "answer", applied), line_ratio=1.48,
    )


def draw_takeaway(
    image: Image.Image, question: dict[str, Any], focus: dict[str, Any], applied: set[str], top: int
) -> None:
    draw, cursor = draw_panel_shell(image, "考点收口", "考点口诀", top)
    marks = active_marks(focus, "takeaway", applied)
    for row, line in enumerate(question["takeawayLines"]):
        row_marks = [item for item in marks if int(item.get("row", -1)) == row]
        draw_marked_text(
            draw, str(line), (100, cursor), 770,
            font(49, serif=True, weight="black"), marks=row_marks, line_ratio=1.32,
        )
        draw.line((96, cursor + 66, 874, cursor + 66), fill=LINE, width=2)
        cursor += 80


def draw_caption(image: Image.Image, text: str) -> None:
    draw = ImageDraw.Draw(image)
    x0, x1 = 72, 898
    initial = 50 if len(text) <= 27 else 42
    size = fit_font_size(text, x1 - x0, 170, initial, 36, weight="semibold")
    selected_font = font(size, weight="semibold")
    lines = layout_lines(text, selected_font, x1 - x0)
    line_height = int(size * 1.36)
    total_height = len(lines) * line_height
    y = 1605 + max(0, (170 - total_height) // 2)
    for _start, _end, line in lines:
        width = text_width(line, selected_font)
        draw.text(
            (x0 + (x1 - x0 - width) / 2, y), line, font=selected_font, fill=INK,
            stroke_width=2, stroke_fill=CAPTION_STROKE,
        )
        y += line_height


def render_scene(
    question: dict[str, Any],
    focus: dict[str, Any],
    presentation: dict[str, Any],
    segment_index: int,
    caption_text: str,
    applied: set[str],
) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    brand = str(presentation.get("brandName") or "易哈佛")
    if segment_index == 0:
        draw_brand_chrome(image, presentation)
        module = str(presentation.get("courseName") or "医学考试易错题讲解").removesuffix("讲解")
        draw_label(draw, (72, 530), module)
        draw.text(
            (72, 614), str(question.get("displayNumber") or question["number"]),
            font=font(180, weight="semibold"), fill=BLUE,
        )
        draw_marked_text(
            draw, str(question["coverHook"]), (72, 824), 800,
            font(82, weight="semibold"), line_ratio=1.22,
        )
        draw_marked_text(
            draw, str(question["topic"]), (72, 1055), 826,
            font(46, serif=True, weight="bold"), fill=MUTED, line_ratio=1.42,
        )
        draw_caption(image, caption_text)
        return image
    if segment_index == 13:
        leaf = ROOT / "assets" / "brand" / "ehafo-leaf.png"
        if leaf.exists():
            icon = Image.open(leaf).convert("RGBA")
            icon.thumbnail((150, 150), Image.Resampling.LANCZOS)
            image.alpha_composite(icon, (465, 590))
        title = str(presentation.get("outroTitle") or f"关注{brand}")
        subtitle = str(presentation.get("outroText") or "理解考点，比只记答案更重要")
        title_font = font(72, weight="semibold")
        title_width = text_width(title, title_font)
        draw.text(((WIDTH - title_width) / 2, 790), title, font=title_font, fill=INK)
        subtitle_font = font(42, weight="medium")
        subtitle_width = text_width(subtitle, subtitle_font)
        draw.text(((WIDTH - subtitle_width) / 2, 905), subtitle, font=subtitle_font, fill=MUTED)
        draw.ellipse((465, 1015, 615, 1165), fill="#EAF6EF")
        draw.line((500, 1090, 532, 1122), fill=GREEN, width=12)
        draw.line((532, 1122, 584, 1057), fill=GREEN, width=12)
        return image

    draw_brand_chrome(image, presentation)
    stem_marks = active_marks(focus, "stem", applied)
    if segment_index == 1:
        draw_label(draw, (72, 300), "跟老师一起读题", filled=True)
        draw_question_board(image, question, stem_marks, expanded=True)
        draw.text(
            (72, 1532), "先定位题干条件和问法，暂不判断答案。",
            font=font(28), fill=MUTED,
        )
        draw_caption(image, caption_text)
        return image

    reveal_answer = segment_index >= 10
    board_bottom = draw_question_board(image, question, stem_marks, reveal_answer)
    panel_top = board_bottom + 17
    label = str(presentation.get("midrollLabel") or f"{brand}教研提醒")
    if 2 <= segment_index <= 5:
        draw_knowledge(image, question, focus, applied, panel_top)
    elif segment_index == 6:
        draw_reminder(image, question, focus, applied, label, panel_top)
    elif 7 <= segment_index <= 9:
        draw_analysis(image, question, focus, applied, panel_top)
    elif 10 <= segment_index <= 11:
        draw_answer(image, question, focus, applied, panel_top)
    elif segment_index == 12:
        draw_takeaway(image, question, focus, applied, panel_top)
    draw_caption(image, caption_text)
    return image


def image_key(segment_index: int, caption_text: str, applied: set[str]) -> str:
    payload = json.dumps(
        {
            "renderer": RENDERER_VERSION,
            "background": BACKGROUND_NAME,
            "segment": segment_index,
            "caption": caption_text,
            "applied": sorted(applied),
        },
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_clips(
    question: dict[str, Any],
    manifest: dict[str, Any],
    focus: dict[str, Any],
    presentation: dict[str, Any],
    frame_dir: Path,
) -> tuple[list[Clip], float, int]:
    captions = manifest["captions"]
    target_duration = round(float(manifest["duration"]) + 0.35, 3)
    events: list[tuple[float, str]] = []
    for section, items in focus.items():
        for index, item in enumerate(items):
            events.append((cue_time(captions, item), f"{section}:{index}"))
    events.sort()
    frame_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Clip] = []
    applied: set[str] = set()
    generated = 0
    for segment_index, caption in enumerate(captions):
        segment_start = 0.0 if segment_index == 0 else 0.2 + float(caption["start"])
        segment_end = (
            0.2 + float(captions[segment_index + 1]["start"])
            if segment_index + 1 < len(captions)
            else target_duration
        )
        segment_events = [item for item in events if segment_start <= item[0] < segment_end]
        cursor = segment_start
        states: list[tuple[float, set[str]]] = []
        states.append((cursor, set(applied)))
        for at, event_key in segment_events:
            if at - cursor < 0.08:
                applied.add(event_key)
                states[-1] = (states[-1][0], set(applied))
                continue
            applied.add(event_key)
            states.append((at, set(applied)))
            cursor = at
        for state_index, (at, state_applied) in enumerate(states):
            next_at = states[state_index + 1][0] if state_index + 1 < len(states) else segment_end
            hold = max(0.08, next_at - at)
            key = image_key(segment_index, str(caption["text"]), state_applied)
            path = frame_dir / f"frame-{key}.png"
            if not path.exists():
                render_scene(
                    question, focus, presentation, segment_index,
                    str(caption["text"]), state_applied,
                ).convert("RGB").save(path, quality=95)
                generated += 1
            transition, transition_duration = transition_for_state(segment_index, state_index)
            clips.append(Clip(
                image=path,
                hold=hold,
                transition=transition,
                transition_duration=transition_duration,
            ))
    difference = target_duration - sum(item.hold for item in clips)
    clips[-1].hold += difference
    return clips, target_duration, generated


def choose_encoder() -> list[str]:
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]


def encode(
    clips: list[Clip], audio: Path, output: Path, duration: float, fps: int
) -> None:
    command = ["ffmpeg", "-y", "-v", "warning"]
    for index, clip in enumerate(clips):
        next_transition = clips[index + 1].transition_duration if index + 1 < len(clips) else 0.0
        input_duration = clip.hold + next_transition + 0.05
        command.extend([
            "-loop", "1", "-framerate", str(fps), "-t", f"{input_duration:.3f}",
            "-i", str(clip.image),
        ])
    command.extend(["-itsoffset", "0.2", "-i", str(audio)])
    filters = []
    for index in range(len(clips)):
        filters.append(
            f"[{index}:v]scale={WIDTH}:{HEIGHT},format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{index}]"
        )
    current = "v0"
    elapsed = clips[0].hold
    for index in range(1, len(clips)):
        transition = clips[index].transition
        transition_duration = clips[index].transition_duration
        output_label = f"x{index}"
        filters.append(
            f"[{current}][v{index}]xfade=transition={transition}:duration={transition_duration:.3f}:offset={elapsed:.3f}[{output_label}]"
        )
        current = output_label
        elapsed += clips[index].hold
    filters.append(f"[{current}]fps={fps},format=yuv420p[vout]")
    audio_index = len(clips)
    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", f"{audio_index}:a:0",
        *choose_encoder(), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-af", "apad=pad_dur=0.5", "-t", f"{duration:.3f}", "-movflags", "+faststart",
        str(output),
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    run(command)


def parse_range(value: str) -> tuple[int, int]:
    start, end = (int(part) for part in value.split("-", 1))
    return start, end


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--focus-data", type=Path, default=DEFAULT_FOCUS)
    parser.add_argument("--voice-dir", type=Path, default=DEFAULT_VOICE)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--questions", default="1-1")
    parser.add_argument("--variant", default="fast-v1")
    parser.add_argument("--file-prefix", default="question")
    parser.add_argument("--background", choices=("white", "green"), default="white")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    set_theme(args.background)
    payload = json.loads(args.data.resolve().read_text(encoding="utf-8"))
    focus_payload = json.loads(args.focus_data.resolve().read_text(encoding="utf-8"))["questions"]
    questions = {int(item["number"]): item for item in payload["questions"]}
    presentation = payload.get("presentation", {})
    start, end = parse_range(args.questions)
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "renderer": RENDERER_VERSION,
        "background": args.background,
        "questions": {},
    }

    for number in range(start, end + 1):
        question_started = time.perf_counter()
        question = questions[number]
        manifest = json.loads(
            (args.voice_dir.resolve() / f"q{number:02d}" / "manifest.json").read_text(encoding="utf-8")
        )
        focus = focus_payload[str(number)]
        source_hash = hashlib.sha256(json.dumps(
            {
                "renderer": RENDERER_VERSION,
                "background": args.background,
                "question": question,
                "focus": focus,
                "manifest": manifest,
                "presentation": presentation,
            },
            ensure_ascii=False, sort_keys=True,
        ).encode("utf-8")).hexdigest()[:16]
        question_work = args.work_dir.resolve() / f"q{number:02d}-{source_hash}"
        clips, duration, generated = build_clips(
            question, manifest, focus, presentation, question_work / "frames"
        )
        output = args.output_dir.resolve() / f"{args.file_prefix}-q{number:02d}-{args.background}-{args.variant}-final.mp4"
        if output.exists() and not args.overwrite:
            raise FileExistsError(f"Refusing to overwrite: {output}")
        encode(clips, (ROOT / manifest["audio"]).resolve(), output, duration, args.fps)
        elapsed = time.perf_counter() - question_started
        report["questions"][f"q{number:02d}"] = {
            "output": str(output.relative_to(ROOT)),
            "duration": duration,
            "clips": len(clips),
            "framesGenerated": generated,
            "sourceHash": source_hash,
            "elapsedSeconds": round(elapsed, 3),
        }
        print(f"q{number:02d}: fast render {elapsed:.2f}s -> {output.name}", flush=True)

    report["elapsedSeconds"] = round(time.perf_counter() - started, 3)
    report_path = args.work_dir.resolve() / f"fast-render-report-{args.variant}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"FAST_RENDER_SECONDS={report['elapsedSeconds']}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
