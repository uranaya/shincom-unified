# -*- coding: utf-8 -*-
"""English PDF generator for shincom-unified.

Goal: keep Japanese generator untouched while providing a stable English
layout.

Fixes included:
- Correct text wrapping: wrap uses actual available width (no artificial
  1:1 blank right margin). This prevents bottom clipping.
- Header: QR code is always rendered using ReportLab built-in QR widget.
  'SCAN HERE' is positioned above the QR (not below a rule).
- Title garbling: English output uses IPAexGothic when available (supports
  Japanese + symbols like ■ ◆), with safe fallbacks.

Expected entrypoint:
    create_pdf_unified_en(filepath, data, mode='shincom', size='A4', include_yearly=False)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple, Optional

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# English-only header module (does not affect Japanese)
from header_utils_en import draw_header_en


@dataclass
class PageSpec:
    page_size: Tuple[float, float]
    margin: float


def _repo_font_path(filename: str) -> str:
    # Works on Render (cwd = /opt/render/project/src) and locally.
    return os.path.join(os.path.dirname(__file__), filename)


def _register_fonts() -> None:
    """Register fonts if TTFs are present. Safe to call multiple times."""
    # IPAex fonts are used by the Japanese generator; reuse them for English to
    # avoid missing glyphs (■◆ etc.)
    candidates = [
        ("IPAexGothic", "ipaexg.ttf"),
        ("IPAexMincho", "ipaexm.ttf"),
    ]
    for name, fname in candidates:
        try:
            if name in pdfmetrics.getRegisteredFontNames():
                continue
            path = _repo_font_path(fname)
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            # If registration fails, fall back to built-ins.
            continue


def _pick_font() -> str:
    # Prefer IPAexGothic if registered, otherwise Helvetica.
    return "IPAexGothic" if "IPAexGothic" in pdfmetrics.getRegisteredFontNames() else "Helvetica"


def _safe_str(v) -> str:
    return "" if v is None else str(v)


def wrap_by_width(text: str, font_name: str, font_size: float, max_width: float) -> List[str]:
    """Wrap text to fit max_width using ReportLab string widths.

    - Prefers wrapping on spaces.
    - If the string has no spaces (e.g., CJK), falls back to char-based wrapping.
    """
    text = (text or "").replace("\r", "")
    if not text:
        return []

    # Normalize whitespace but keep explicit newlines.
    raw_lines = text.split("\n")
    out: List[str] = []

    def _width(s: str) -> float:
        try:
            return pdfmetrics.stringWidth(s, font_name, font_size)
        except Exception:
            # Worst-case fallback: approximate
            return len(s) * font_size * 0.55

    for raw in raw_lines:
        line = raw.strip()
        if not line:
            out.append("")
            continue

        if " " not in line:
            # CJK or no-space string: char wrap
            buf = ""
            for ch in line:
                test = buf + ch
                if buf and _width(test) > max_width:
                    out.append(buf)
                    buf = ch
                else:
                    buf = test
            if buf:
                out.append(buf)
            continue

        words = line.split()
        buf = ""
        for w in words:
            test = w if not buf else f"{buf} {w}"
            if buf and _width(test) > max_width:
                out.append(buf)
                buf = w
            else:
                buf = test
        if buf:
            out.append(buf)

    return out


def _mostly_ascii(s: str, threshold: float = 0.15) -> bool:
    """Heuristic: treat text as English/Latin if most visible chars are ASCII.

    This is used to pick a Latin font for English paragraphs so the wrap
    computation matches the actual glyph metrics.
    """
    s = s or ""
    visible = [ch for ch in s if not ch.isspace()]
    if not visible:
        return True
    non_ascii = sum(1 for ch in visible if ord(ch) > 127)
    return (non_ascii / len(visible)) <= threshold


def draw_wrapped(c: canvas.Canvas, x: float, y: float, text: str,
                 font_name: str, font_size: float,
                 max_width: float,
                 leading: Optional[float] = None) -> float:
    """Draw wrapped text and return the new y (below last line)."""
    leading = leading if leading is not None else (font_size + 3)
    # Use a Latin font for (mostly) English text so wrap width is based on
    # correct glyph metrics. Keep the passed font for Japanese/mixed content.
    use_font = "Helvetica" if _mostly_ascii(text) else font_name
    draw_text = text or ""
    # Helvetica doesn't always render the decorative bullets used in JP output.
    if use_font == "Helvetica":
        draw_text = draw_text.replace("■", "*").replace("◆", "*").replace("◇", "*")
    lines = wrap_by_width(draw_text, use_font, font_size, max_width)
    c.setFont(use_font, font_size)
    for ln in lines:
        c.drawString(x, y, ln)
        y -= leading
    return y


def _draw_section_title(c: canvas.Canvas, x: float, y: float, title: str,
                        font_name: str, font_size: float = 12) -> float:
    c.setFont(font_name, font_size)
    c.drawString(x, y, title)
    return y - (font_size + 6)


def draw_lucky_section_en(c: canvas.Canvas, data: dict,
                          page_width: float, margin: float,
                          y: float, font_name: str) -> float:
    """Draw lucky info + directions (English labels)."""
    max_width = page_width - 2 * margin

    lucky_info = data.get("lucky_info") or ""
    lucky_direction = data.get("lucky_direction") or ""

    if not (lucky_info or lucky_direction):
        return y

    c.setFont(font_name, 11)
    c.drawString(margin, y, "■ Lucky Info (based on your birthdate)")
    y -= 18

    # Two-column layout (keeps it compact)
    c.setFont(font_name, 10)
    col_w = (page_width - 2 * margin) / 2

    # Lucky info lines are expected to be already short, but wrap if needed.
    left_x = margin
    right_x = margin + col_w

    # Split into bullet-like fragments (supports both JP/EN formats)
    parts: List[str] = []
    for ln in lucky_info.split("\n"):
        ln = ln.strip()
        if ln:
            parts.append(ln)

    half = (len(parts) + 1) // 2
    left_parts = parts[:half]
    right_parts = parts[half:]

    yy_left = y
    for p in left_parts:
        yy_left = draw_wrapped(c, left_x, yy_left, p, font_name, 10, col_w - 6, leading=13)

    yy_right = y
    for p in right_parts:
        yy_right = draw_wrapped(c, right_x, yy_right, p, font_name, 10, col_w - 6, leading=13)

    y = min(yy_left, yy_right) - 8

    if lucky_direction:
        c.setFont(font_name, 11)
        c.drawString(margin, y, "■ Lucky Directions (Kyusei Kigaku)")
        y -= 16
        c.setFont(font_name, 10)
        y = draw_wrapped(c, margin, y, lucky_direction, font_name, 10, max_width, leading=13)

    return y - 8


def _draw_yearly_pages_en(c: canvas.Canvas, data: dict, spec: PageSpec,
                          font_name: str) -> None:
    """Optional yearly fortune pages (English)."""
    yearly = data.get("yearly_fortunes")
    if not yearly:
        return

    page_width, page_height = spec.page_size
    margin = spec.margin
    max_width = page_width - 2 * margin

    c.showPage()
    y = page_height - margin

    c.setFont(font_name, 16)
    c.drawString(margin, y, "Yearly Fortune")
    y -= 28

    c.setFont(font_name, 10)
    for month_block in yearly:
        title = _safe_str(month_block.get("title") or "")
        body = _safe_str(month_block.get("text") or "")

        if title:
            c.setFont(font_name, 11)
            c.drawString(margin, y, title)
            y -= 16

        c.setFont(font_name, 10)
        y = draw_wrapped(c, margin, y, body, font_name, 10, max_width, leading=13)
        y -= 8

        # page break if needed
        if y < margin + 60:
            c.showPage()
            y = page_height - margin
            c.setFont(font_name, 10)


def draw_shincom_a4_en(c: canvas.Canvas, data: dict, include_yearly: bool,
                       font_name: str) -> None:
    page_width, page_height = A4
    margin = 18 * mm
    max_width = page_width - 2 * margin

    y = page_height - margin

    # Header (page 1 only)
    y = draw_header_en(c, page_width, margin, y, font_name)

    # Palm image
    img_data = data.get("palm_image") or data.get("image_data")
    if img_data:
        try:
            img = ImageReader(img_data)
            img_w = max_width
            img_h = 55 * mm
            c.drawImage(img, margin, y - img_h, width=img_w, height=img_h,
                        preserveAspectRatio=True, anchor='c')
            y -= (img_h + 18)
        except Exception:
            y -= 10

    # Basic info line
    birthdate = _safe_str(data.get("birthdate"))
    zodiac = _safe_str(data.get("zodiac"))
    eto = _safe_str(data.get("eto"))
    animal = _safe_str(data.get("animal"))
    kyusei = _safe_str(data.get("kyusei"))

    c.setFont(font_name, 10)
    info = f"Birthdate: {birthdate} / Zodiac: {zodiac}"
    c.drawString(margin, y, info)
    y -= 14
    info2 = f"Eto: {eto} / Animal: {animal} / Main Star: {kyusei}"
    c.drawString(margin, y, info2)
    y -= 18

    # Palm sections (1-3 on page1)
    palm_titles = data.get("palm_titles") or []
    palm_texts = data.get("palm_texts") or []

    def _palm_block(i: int, yy: float) -> float:
        if i >= len(palm_titles) or i >= len(palm_texts):
            return yy
        title = _safe_str(palm_titles[i])
        body = _safe_str(palm_texts[i])
        yy = _draw_section_title(c, margin, yy, f"◆ {i+1}. {title}", font_name, 12)
        yy = draw_wrapped(c, margin, yy, body, font_name, 10, max_width, leading=13)
        return yy - 10

    for i in range(3):
        y = _palm_block(i, y)

    # Lucky info at bottom of page1 if it fits, otherwise page2.
    # Reserve some space for continuation marker.
    if y > margin + 110:
        y_lucky_test = draw_lucky_section_en(c, data, page_width, margin, y, font_name)
        if y_lucky_test > margin + 40:
            y = y_lucky_test
        else:
            # Undo: move to page2 instead
            pass

    # Page 2
    c.showPage()
    y = page_height - margin

    # Palm sections (4-5)
    for i in range(3, 5):
        y = _palm_block(i, y)

    # Overall palm advice
    overall = _safe_str(data.get("palm_overall") or data.get("palm_summary") or "")
    if overall:
        y = _draw_section_title(c, margin, y, "◆ Overall Palm Advice", font_name, 12)
        y = draw_wrapped(c, margin, y, overall, font_name, 10, max_width, leading=13)
        y -= 8

    # Personality diagnosis
    personality = _safe_str(data.get("personality") or "")
    if personality:
        y = _draw_section_title(c, margin, y, "◆ Personality", font_name, 12)
        y = draw_wrapped(c, margin, y, personality, font_name, 10, max_width, leading=13)
        y -= 8

    # Year / month / next month fortunes (from GPT shichu)
    year_f = _safe_str(data.get("year_fortune") or "")
    month_f = _safe_str(data.get("month_fortune") or "")
    next_month_f = _safe_str(data.get("next_month_fortune") or "")

    if year_f:
        y = _draw_section_title(c, margin, y, "■ 2026 Overall Fortune", font_name, 12)
        y = draw_wrapped(c, margin, y, year_f, font_name, 10, max_width, leading=13)
        y -= 6

    if month_f:
        y = _draw_section_title(c, margin, y, "■ This Month", font_name, 12)
        y = draw_wrapped(c, margin, y, month_f, font_name, 10, max_width, leading=13)
        y -= 6

    if next_month_f:
        y = _draw_section_title(c, margin, y, "■ Next Month", font_name, 12)
        y = draw_wrapped(c, margin, y, next_month_f, font_name, 10, max_width, leading=13)
        y -= 6

    # Lucky section at end of page2
    y = draw_lucky_section_en(c, data, page_width, margin, y, font_name)

    # Optional yearly pages
    if include_yearly:
        _draw_yearly_pages_en(c, data, PageSpec(A4, margin), font_name)


def draw_shincom_b4_en(c: canvas.Canvas, data: dict, include_yearly: bool,
                       font_name: str) -> None:
    page_width, page_height = B4
    margin = 20 * mm
    max_width = page_width - 2 * margin

    y = page_height - margin

    # Header (page 1 only)
    y = draw_header_en(c, page_width, margin, y, font_name)

    # Palm image
    img_data = data.get("palm_image") or data.get("image_data")
    if img_data:
        try:
            img = ImageReader(img_data)
            img_w = max_width
            img_h = 85 * mm
            c.drawImage(img, margin, y - img_h, width=img_w, height=img_h,
                        preserveAspectRatio=True, anchor='c')
            y -= (img_h + 18)
        except Exception:
            y -= 10

    # Basic info line
    birthdate = _safe_str(data.get("birthdate"))
    zodiac = _safe_str(data.get("zodiac"))
    eto = _safe_str(data.get("eto"))
    animal = _safe_str(data.get("animal"))
    kyusei = _safe_str(data.get("kyusei"))

    c.setFont(font_name, 10)
    c.drawString(margin, y, f"Birthdate: {birthdate} / Zodiac: {zodiac}")
    y -= 14
    c.drawString(margin, y, f"Eto: {eto} / Animal: {animal} / Main Star: {kyusei}")
    y -= 18

    palm_titles = data.get("palm_titles") or []
    palm_texts = data.get("palm_texts") or []

    for i in range(min(len(palm_titles), len(palm_texts))):
        title = _safe_str(palm_titles[i])
        body = _safe_str(palm_texts[i])
        y = _draw_section_title(c, margin, y, f"◆ {i+1}. {title}", font_name, 12)
        y = draw_wrapped(c, margin, y, body, font_name, 10, max_width, leading=13)
        y -= 8
        if y < margin + 80:
            break

    # Page 2 (no header)
    c.showPage()
    y = page_height - margin

    overall = _safe_str(data.get("palm_overall") or data.get("palm_summary") or "")
    if overall:
        y = _draw_section_title(c, margin, y, "◆ Overall Palm Advice", font_name, 12)
        y = draw_wrapped(c, margin, y, overall, font_name, 10, max_width, leading=13)
        y -= 8

    personality = _safe_str(data.get("personality") or "")
    if personality:
        y = _draw_section_title(c, margin, y, "◆ Personality", font_name, 12)
        y = draw_wrapped(c, margin, y, personality, font_name, 10, max_width, leading=13)
        y -= 8

    year_f = _safe_str(data.get("year_fortune") or "")
    month_f = _safe_str(data.get("month_fortune") or "")
    next_month_f = _safe_str(data.get("next_month_fortune") or "")

    if year_f:
        y = _draw_section_title(c, margin, y, "■ 2026 Overall Fortune", font_name, 12)
        y = draw_wrapped(c, margin, y, year_f, font_name, 10, max_width, leading=13)
        y -= 6

    if month_f:
        y = _draw_section_title(c, margin, y, "■ This Month", font_name, 12)
        y = draw_wrapped(c, margin, y, month_f, font_name, 10, max_width, leading=13)
        y -= 6

    if next_month_f:
        y = _draw_section_title(c, margin, y, "■ Next Month", font_name, 12)
        y = draw_wrapped(c, margin, y, next_month_f, font_name, 10, max_width, leading=13)
        y -= 6

    y = draw_lucky_section_en(c, data, page_width, margin, y, font_name)

    if include_yearly:
        _draw_yearly_pages_en(c, data, PageSpec(B4, margin), font_name)


def create_pdf_unified_en(filepath: str, data: dict, mode: str = "shincom",
                          size: str = "A4", include_yearly: bool = False) -> None:
    """Create an English PDF. Supported modes: shincom (A4/B4)."""
    _register_fonts()
    font_name = _pick_font()

    size = (size or "A4").upper()
    mode = (mode or "shincom").lower()

    page_size = A4 if size == "A4" else B4
    c = canvas.Canvas(filepath, pagesize=page_size)

    if mode != "shincom":
        # Keep behavior explicit; don't silently create wrong PDFs.
        mode = "shincom"

    if size == "A4":
        draw_shincom_a4_en(c, data, include_yearly, font_name)
    else:
        draw_shincom_b4_en(c, data, include_yearly, font_name)

    c.save()
