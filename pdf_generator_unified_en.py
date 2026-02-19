from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# Debug marker to verify EN PDF generator is actually used (printed only when this module is invoked)
EN_PDFGEN_MARKER = 'ENPDFGEN|wrap=90|2026-01-31'

from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
import base64
import io
import os
from datetime import datetime
import re
import json
import ast
import textwrap

def _t(lang: str, ja: str, en: str) -> str:
    return en if (lang or 'ja') == 'en' else ja

def _get_lang(data: dict) -> str:
    if not isinstance(data, dict):
        return 'ja'
    lang = (data.get('lang') or data.get('output_lang') or data.get('language') or 'ja')
    lang = (lang or 'ja').strip().lower()
    return 'en' if lang.startswith('en') else 'ja'
import base64
import io
import os
from datetime import datetime
import re
import textwrap


def smart_wrap(text: str, limit: int, lang: str | None = None):
    """Wrap text safely for PDF rendering.

    - Japanese (and other CJK) text is wrapped by character count (no spaces).
    - English is wrapped using textwrap.wrap with a width of `limit`.
    """
    if text is None:
        return []
    s = str(text)
    if not s:
        return []
    lang = (lang or '').strip() or None
    # Normalize newlines first
    parts = s.splitlines() or ['']
    out = []
    for p in parts:
        if not p:
            out.append('')
            continue
        # Detect CJK if lang is ja OR the string contains CJK chars.
        is_cjk = (lang == 'ja') or bool(re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]", p))
        if is_cjk:
            # simple fixed-width split
            for k in range(0, len(p), max(1, limit)):
                out.append(p[k:k+limit])
        else:
            out.extend(textwrap.wrap(p, width=limit, break_long_words=True, break_on_hyphens=True))
    return out
def _normalize_month_fortune_text(text: str, kind: str) -> str:
    """Remove leading 'YYYY年M月は' style prefixes to avoid heading/body month mismatches.
    kind: 'month' or 'next'
    """
    if not isinstance(text, str):
        return text
    s = text.strip()
    # Match patterns like '2026年1月は' or '2026年1月は、'
    s = re.sub(r'^\s*\d{4}年\s*\d{1,2}月\s*は\s*[、,]?\s*', '', s)
    prefix = '今月は' if kind == 'month' else '来月は'
    # If the text already starts with 今月/来月, don't double-prefix.
    if s.startswith('今月') or s.startswith('来月'):
        return s
    return prefix + '、' + s if s else prefix + '。'


try:
    from header_utils_en import draw_header
except Exception:
    from header_utils import draw_header
from lucky_utils import draw_lucky_section


FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

# English uses built-in PDF fonts for clean rendering and predictable metrics.
FONT_NAME_JA = FONT_NAME
FONT_NAME_EN = "Times-Roman"


def select_font_for_lang(lang: str) -> str:
    """
    Compatibility shim for this EN PDF generator.

    NOTE:
      - This module’s `_set_font(c, lang, size)` expects a language key ("en"/"ja"),
        not an actual font face name.
      - Some call sites do:
            font_name = select_font_for_lang(lang)
            _set_font(c, font_name, size)
        so we return "en"/"ja" here for maximum compatibility.

    Returns:
      "en" if lang starts with "en", else "ja"
    """
    return "en" if (lang or "").lower().startswith("en") else "ja"


def _font(lang: str) -> str:
    return FONT_NAME_EN if str(lang).lower().startswith("en") else FONT_NAME_JA

def _set_font(c, lang: str, size: float):
    c.setFont(_font(lang), size)

def _wrap_len(base: int, lang: str) -> int:
    # IMPORTANT:
    # - Japanese output stays in pdf_generator_unified.py (stable).
    # - This English module enforces 90 chars/line for EN paragraphs.
    if (lang or "ja").lower().startswith("en"):
        return 90
    return base
def _has_non_ascii(s: str) -> bool:
    return any(ord(ch) > 127 for ch in (s or ""))

def _draw_info_line_auto(c, margin: float, y: float, parts, font_name: str, size: float = 9, step: float = 12) -> float:
    """Draw a single info line; auto-switch to JP font when the text contains non-ASCII.

    `font_name` is a language key ("en"/"ja") used by `_set_font`.
    """
    if not parts:
        return y
    s = " / ".join([p for p in parts if p])
    if not s:
        return y
    use_lang = "ja" if _has_non_ascii(s) else font_name
    _set_font(c, use_lang, size)
    c.drawString(margin, y, s)
    return y - step


def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction, lang='en', page_height=None, **kwargs):
    """Lucky info + lucky directions section (EN module).

    Notes:
      - This is the EN generator, so section headings are always English.
      - Individual lines auto-switch fonts (JA font if non-ASCII) to avoid tofu.
      - Lucky direction text is normalized to a compact English format when the input is Japanese.
    """
    if not lucky_lines:
        lucky_lines = []

    # --- Headings (always English here) ---
    c.setFont(FONT_NAME_EN, 12)
    c.drawString(margin, y, "■ Lucky Info (from birthdate)")
    y -= 6 * mm

    # --- 2-column layout for lucky info lines ---
    col_gap = 8 * mm
    col_w = (width - 2 * margin - col_gap) / 2.0
    line_h = 5.6 * mm
    font_size = 10

    def _pick_font(s: str) -> str:
        return FONT_NAME_JA if _has_non_ascii(s) else FONT_NAME_EN

    def _fit_one_line(s: str, max_w: float) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        fn = _pick_font(s)
        if stringWidth(s, fn, font_size) <= max_w:
            return s
        ell = "…"
        while s and stringWidth(s + ell, fn, font_size) > max_w:
            s = s[:-1]
        return (s + ell) if s else ell

    for i in range(0, len(lucky_lines), 2):
        left = _fit_one_line(lucky_lines[i], col_w)
        right = _fit_one_line(lucky_lines[i + 1] if i + 1 < len(lucky_lines) else "", col_w)

        if left:
            c.setFont(_pick_font(left), font_size)
            c.drawString(margin, y, left)
        if right:
            c.setFont(_pick_font(right), font_size)
            c.drawString(margin + col_w + col_gap, y, right)
        y -= line_h

    # --- Lucky directions ---
    if lucky_direction:
        y -= 1.5 * mm
        c.setFont(FONT_NAME_EN, 10)
        c.drawString(margin, y, "■ Lucky Directions")
        y -= 5.5 * mm

        def _jp_dir_to_en(d: str) -> str:
            d = (d or "").strip()
            mapping = {
                "北東": "NE",
                "南東": "SE",
                "南西": "SW",
                "北西": "NW",
                "北": "N",
                "東": "E",
                "南": "S",
                "西": "W",
            }
            return mapping.get(d, d)

        def _format_lucky_direction_text(t: str) -> str:
            t = (t or "").replace("\x00", "").replace("\u0000", "").replace("\0", "")
            t = t.replace(chr(0), "").strip()
            if not t:
                return ""
            # If it already looks like English, keep it.
            if not _has_non_ascii(t):
                return t

            # Typical JP format:
            # あなたの本命星は「五黄土星」です。2026年の吉方位：北東 今月：南西 来月：南西 です。
            m = re.search(
                r"(\d{4})年の吉方位[:：]\s*([^\s　]+)\s*今月[:：]\s*([^\s　]+)\s*来月[:：]\s*([^\s　]+)",
                t
            )
            if m:
                year, year_dir, this_dir, next_dir = m.groups()
                return (
                    f"Year {year}: {_jp_dir_to_en(year_dir)}  |  "
                    f"This month: {_jp_dir_to_en(this_dir)}  |  "
                    f"Next month: {_jp_dir_to_en(next_dir)}"
                )

            # Fallback: just replace direction tokens if present
            repl = [
                ("北東", "NE"), ("南東", "SE"), ("南西", "SW"), ("北西", "NW"),
                ("北", "N"), ("東", "E"), ("南", "S"), ("西", "W"),
            ]
            for jp, en in repl:
                t = t.replace(jp, en)
            return t

        dir_text = _format_lucky_direction_text(lucky_direction)

        # Draw (wrap if needed)
        max_w = width - 2 * margin - 6 * mm  # extra padding avoids right-edge clipping
        fn = _pick_font(dir_text)
        if stringWidth(dir_text, fn, font_size) <= max_w:
            c.setFont(fn, font_size)
            c.drawString(margin, y, dir_text)
            y -= line_h
        else:
            # ASCII: wrap by words; Non-ASCII: wrap by characters
            if not _has_non_ascii(dir_text):
                words = dir_text.split()
                cur = ""
                for w in words:
                    candidate = (cur + " " + w).strip()
                    if stringWidth(candidate, fn, font_size) <= max_w:
                        cur = candidate
                    else:
                        c.setFont(fn, font_size)
                        c.drawString(margin, y, cur)
                        y -= line_h
                        cur = w
                if cur:
                    c.setFont(fn, font_size)
                    c.drawString(margin, y, cur)
                    y -= line_h
            else:
                cur = ""
                for ch in dir_text:
                    candidate = cur + ch
                    if stringWidth(candidate, fn, font_size) <= max_w:
                        cur = candidate
                    else:
                        c.setFont(fn, font_size)
                        c.drawString(margin, y, cur)
                        y -= line_h
                        cur = ch
                if cur:
                    c.setFont(fn, font_size)
                    c.drawString(margin, y, cur)
                    y -= line_h

    return y

def draw_palm_image(c, data_or_base64, width, margin_or_y=None, y=None, font_name=None):
    """Draw palm image (EN module).

    Compatible with both call styles:
      - draw_palm_image(c, base64_image, width, y)
      - draw_palm_image(c, data_dict, page_width, margin, y, font_name=...)

    Notes:
      - `font_name` is unused here (image-only), but accepted to match callers.
      - Returns updated y (float).
    """
    # New call style: (c, data_dict, page_width, margin, y, font_name=...)
    # Old call style: (c, base64_image, width, y)
    if y is None:
        base64_image = data_or_base64
        y = margin_or_y
    else:
        data = data_or_base64 or {}
        base64_image = (
            data.get("palm_image")
            or data.get("image_data")
            or data.get("image_data_b64")
            or data.get("image_base64")
            or data.get("image")
            or data.get("palm_image_path")
            or data.get("image_path")
            or ""
        )

    if not base64_image:
        return y

    # If a local file path is provided, load it directly (covers newer upload flows).
    try:
        if isinstance(base64_image, str) and len(base64_image) < 512 and os.path.exists(base64_image):
            img = ImageReader(base64_image)
            img_width, img_height = img.getSize()

            # Determine page height from width (A4 vs B4)
            is_b4 = abs(width - B4[0]) < 1e-6
            page_height = B4[1] if is_b4 else A4[1]

            # Fit image: B4 is larger; A4 is tighter to leave room for text
            max_height = (0.30 if is_b4 else 0.24) * page_height
            max_width_ratio = 0.70 if is_b4 else 0.62

            scale_w = (width * max_width_ratio) / float(img_width)
            scale_h = max_height / float(img_height)
            scale = min(scale_w, scale_h)

            draw_w = float(img_width) * scale
            draw_h = float(img_height) * scale

            x_center = (width - draw_w) / 2.0
            y_draw = float(y) - draw_h - 5 * mm
            c.drawImage(img, x_center, y_draw, width=draw_w, height=draw_h)
            return y_draw - 10 * mm
    except Exception:
        pass

    try:
        # Handle data URL ("data:image/...;base64,XXXX") or raw base64
        if "," in base64_image:
            base64_part = base64_image.split(",", 1)[1]
        else:
            base64_part = base64_image

        image_data = base64.b64decode(base64_part)
        img = ImageReader(io.BytesIO(image_data))
        img_width, img_height = img.getSize()

        # Determine page height from width (A4 vs B4)
        page_height = B4[1] if abs(width - B4[0]) < 1e-6 else A4[1]

        # Keep aspect ratio; fit within 30% of page height; use 70% of page width as baseline
        max_height = (0.30 if abs(width - B4[0]) < 1e-6 else 0.24) * page_height
        max_width_ratio = 0.70 if abs(width - B4[0]) < 1e-6 else 0.62
        scale_w = (width * max_width_ratio) / float(img_width)
        scale_h = max_height / float(img_height)
        scale = min(scale_w, scale_h)

        draw_w = float(img_width) * scale
        draw_h = float(img_height) * scale

        x_center = (width - draw_w) / 2.0
        y = float(y) - draw_h - 5 * mm
        c.drawImage(img, x_center, y, width=draw_w, height=draw_h)
        y -= 10 * mm
    except Exception as e:
        print("Image decode error:", e, flush=True)

    return y

def draw_yearly_pages_renai_a4(c, yearly, lang="ja"):
    """恋愛版 A4：年運＋12か月恋愛運を、テキスト量に応じて自動で複数ページに描画する。"""
    width, height = A4
    margin = 20 * mm
    top = height - 30 * mm
    bottom = 30 * mm

    def draw_text_block(title, text, y):
        # 必要ならページを切り替え
        if y < bottom + 15 * mm:
            c.showPage()
            y = top

        _set_font(c, lang, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 5 * mm

        _set_font(c, lang, 10)
        for line in smart_wrap(text or "", _wrap_len(46, lang), lang):
            if y < bottom:
                c.showPage()
                y = top
                _set_font(c, lang, 10)
            c.drawString(margin, y, line)
            y -= 5 * mm

        y -= 3 * mm
        return y

    # 年運 → 12か月分の順に描画
    c.showPage()
    y = top
    y = draw_text_block(yearly.get("year_label", ""), yearly.get("year_text", ""), y)
    for month in yearly.get("months", []):
        y = draw_text_block(month.get("label", ""), month.get("text", ""), y)


# =========================
# 恋愛版 年運ページ（B4）
# =========================
def draw_yearly_pages_renai_b4(c, yearly, lang="ja"):
    """恋愛版 B4：年運＋12か月恋愛運を、テキスト量に応じて自動で複数ページに描画する。"""
    width, height = B4
    margin = 20 * mm
    top = height - 30 * mm
    bottom = 30 * mm

    def draw_text_block(title, text, y):
        # 必要ならページを切り替え
        if y < bottom + 18 * mm:
            c.showPage()
            y = top

        _set_font(c, lang, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm

        _set_font(c, lang, 11)
        for line in smart_wrap(text or "", _wrap_len(45, lang), lang):
            if y < bottom:
                c.showPage()
                y = top
                _set_font(c, lang, 11)
            c.drawString(margin, y, line)
            y -= 7 * mm

        y -= 4 * mm
        return y

    # 年運 → 12か月分の順に描画
    c.showPage()
    y = top
    y = draw_text_block(yearly.get("year_label", ""), yearly.get("year_text", ""), y)
    for month in yearly.get("months", []):
        y = draw_text_block(month.get("label", ""), month.get("text", ""), y)



def _has_non_ascii(s: str) -> bool:
    try:
        return any(ord(ch) > 127 for ch in (s or ""))
    except Exception:
        return False


def split_text(text: str, lang: str = "en", base: int = 46):
    """Split text into wrapped lines for PDF drawing.
    EN module enforces wrap=90 via _wrap_len().
    """
    return smart_wrap(text or "", _wrap_len(base, lang), lang)


def _normalize_month_fortune_text(text: str, birthdate: str = "", lang: str = "en") -> str:
    """EN shim: keep text as-is (signature-compatible with callers)."""
    return (text or "").strip()


def _normalize_next_month_fortune_text(text: str, birthdate: str = "", lang: str = "en") -> str:
    """EN shim: keep text as-is (signature-compatible with callers)."""
    return (text or "").strip()

def draw_shincom_a4(c, data, include_yearly=False):
    """English (shincom) A4 layout aligned with the Japanese A4 layout.
    Page 1: Header + Palm image + Birth info + Palm sections (1-3)
    Page 2: Palm sections (4-5) + Palm summary + Personality + Year/Month/Next month + Lucky info
    (Optional) Yearly pages: 2 pages for 12 months (6 months per page)
    Header is drawn ONLY on page 1.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    page_width, page_height = A4
    margin = 20 * mm
    y = page_height - margin

    lang = (data.get("lang") or "en").lower()
    font_name = select_font_for_lang(lang)

    # Header (page 1 only)
    y = draw_header(c, page_width, margin, y)

    # Palm image
    y = draw_palm_image(c, data, page_width, margin, y, font_name=font_name)
    y -= 4

    # Birth info (optional, shown under the image)
    birthdate = (data.get("birthdate") or "").strip()
    zodiac = (data.get("zodiac_sign") or data.get("zodiac") or "").strip()
    eto = (data.get("eto") or "").strip()
    eto_number = data.get("eto_number")
    animal = (data.get("animal") or "").strip()
    honmeisei = (data.get("honmeisei") or "").strip()

    line1_parts = []
    if birthdate:
        line1_parts.append(f"Birthdate: {birthdate}")
    if zodiac:
        line1_parts.append(f"Zodiac: {zodiac}")
    line2_parts = []
    if eto:
        if eto_number is not None and str(eto_number).strip() != "":
            line2_parts.append(f"Eto: {eto} ({eto_number})")
        else:
            line2_parts.append(f"Eto: {eto}")
    if animal:
        line2_parts.append(f"Animal: {animal}")
    if honmeisei:
        line2_parts.append(f"Main Star: {honmeisei}")

    if line1_parts:
        y = _draw_info_line_auto(c, margin, y, line1_parts, font_name, 9)
    if line2_parts:
        y = _draw_info_line_auto(c, margin, y, line2_parts, font_name, 9)
    _set_font(c, font_name, 9)
    y -= 2

    palm_titles = data.get("palm_titles", []) or []
    palm_texts = data.get("palm_texts", []) or []

    def write_block(title: str, body: str, font_size=10, title_size=12):
        nonlocal y
        if title:
            _set_font(c, font_name, title_size)
            c.drawString(margin, y, f"◆ {title}")
            y -= 14
        if body:
            _set_font(c, font_name, font_size)
            for line in split_text(body):
                c.drawString(margin, y, line)
                y -= 12
        y -= 8

    # --- Page 1: Palm sections 1-3 ---
    for i in range(3):
        title = palm_titles[i] if i < len(palm_titles) else ""
        text = palm_texts[i] if i < len(palm_texts) else ""
        write_block(title, text)

    # --- Page 2 (no header) ---
    c.showPage()
    y = page_height - margin

    titles = data.get("titles", {}) or {}
    texts = data.get("texts", {}) or {}

    # Remaining palm sections 4-5
    for i in range(3, 5):
        title = palm_titles[i] if i < len(palm_titles) else ""
        text = palm_texts[i] if i < len(palm_texts) else ""
        write_block(title, text)

    # Overall palm summary
    write_block("Overall Palm Reading", texts.get("palm_summary", ""))

    # Personality
    personality_text = data.get("shichu_personality") or data.get("personality") or texts.get("personality", "")
    write_block("Personality", personality_text)

    # Overall fortune for the year
    year_text_raw = data.get("shichu_year_fortune") or data.get("year_fortune") or texts.get("year_fortune", "")
    if year_text_raw:
        year_title = titles.get("year_fortune", "Overall fortune")
        m = re.search(r"\b(20\d{2})\b", str(year_text_raw))
        if m:
            year_title = f"Overall fortune for {m.group(1)}"
        write_block(year_title, str(year_text_raw))

    # This month / next month fortunes (support multiple key names)
    month_src = data.get("shichu_month_fortune") or data.get("month_fortune") or texts.get("month_fortune", "")
    next_month_src = data.get("shichu_next_month_fortune") or data.get("next_month_fortune") or texts.get("next_month_fortune", "")

    month_text = _normalize_month_fortune_text(month_src, birthdate, lang=lang)
    next_month_text = _normalize_next_month_fortune_text(next_month_src, birthdate, lang=lang)

    write_block(titles.get("month_fortune", "This Month"), month_text)
    write_block(titles.get("next_month_fortune", "Next Month"), next_month_text)

    # Lucky info at the end of page 2 (auto font if Japanese sneaks in)
    lucky_lines = data.get("lucky_info", []) or []
    lucky_direction = data.get("lucky_direction", "") or ""
    lucky_text_blob = " ".join([str(x) for x in lucky_lines]) + " " + str(lucky_direction)
    lucky_lang = "ja" if _has_non_ascii(lucky_text_blob) else "en"

    y = draw_lucky_section(
        c,
        page_width,
        margin,
        y,
        lucky_lines,
        lucky_direction,
        lang=lucky_lang,
        page_height=page_height,
        font_name=select_font_for_lang(lucky_lang),
    )

    # Optional yearly pages (2 pages / 12 months)
    if include_yearly:
        draw_yearly_pages_shincom_a4(c, data, lang=lang)

def draw_shincom_b4(c, data, include_yearly=False):
    """English (shincom) B4 layout aligned with the Japanese B4 layout.
    Page 1: Header + Palm image + Birth info + Palm sections (1-5)
    Page 2: Palm summary + Personality + Year/Month/Next month + Lucky info
    (Optional) Yearly pages: 2 pages for 12 months (6 months per page)
    Header is drawn ONLY on page 1.
    """
    from reportlab.lib.pagesizes import B4
    from reportlab.lib.units import mm

    page_width, page_height = B4
    margin = 18 * mm
    y = page_height - margin

    lang = (data.get("lang") or "en").lower()
    font_name = select_font_for_lang(lang)

    # Header (page 1 only)
    y = draw_header(c, page_width, margin, y)

    # Palm image
    y = draw_palm_image(c, data, page_width, margin, y, font_name=font_name)
    y -= 4

    # Birth info under the image
    birthdate = (data.get("birthdate") or "").strip()
    zodiac = (data.get("zodiac_sign") or data.get("zodiac") or "").strip()
    eto = (data.get("eto") or "").strip()
    eto_number = data.get("eto_number")
    animal = (data.get("animal") or "").strip()
    honmeisei = (data.get("honmeisei") or "").strip()

    line1_parts = []
    if birthdate:
        line1_parts.append(f"Birthdate: {birthdate}")
    if zodiac:
        line1_parts.append(f"Zodiac: {zodiac}")
    line2_parts = []
    if eto:
        if eto_number is not None and str(eto_number).strip() != "":
            line2_parts.append(f"Eto: {eto} ({eto_number})")
        else:
            line2_parts.append(f"Eto: {eto}")
    if animal:
        line2_parts.append(f"Animal: {animal}")
    if honmeisei:
        line2_parts.append(f"Main Star: {honmeisei}")

    if line1_parts:
        y = _draw_info_line_auto(c, margin, y, line1_parts, font_name, 10, 14)
    if line2_parts:
        y = _draw_info_line_auto(c, margin, y, line2_parts, font_name, 10, 14)
    _set_font(c, font_name, 10)
    y -= 2

    palm_titles = data.get("palm_titles", []) or []
    palm_texts = data.get("palm_texts", []) or []

    def ensure_space(min_needed: float):
        nonlocal y
        if y < (margin + min_needed):
            c.showPage()
            y = page_height - margin
        return y

    def write_block(title: str, body: str):
        nonlocal y
        if title:
            ensure_space(18)
            _set_font(c, font_name, 12)
            c.drawString(margin, y, f"◆ {title}")
            y -= 14
        if body:
            _set_font(c, font_name, 10)
            for line in split_text(body):
                ensure_space(14)
                c.drawString(margin, y, line)
                y -= 12
        y -= 8

    # --- Page 1: all 5 palm sections ---
    for i in range(5):
        title = palm_titles[i] if i < len(palm_titles) else ""
        text = palm_texts[i] if i < len(palm_texts) else ""
        write_block(title, text)

    # Start page 2 (no header)
    c.showPage()
    y = page_height - margin

    titles = data.get("titles", {}) or {}
    texts = data.get("texts", {}) or {}

    # Overall palm summary
    write_block("Overall Palm Reading", texts.get("palm_summary", ""))

    # Personality
    personality_text = data.get("shichu_personality") or data.get("personality") or texts.get("personality", "")
    write_block("Personality", personality_text)

    # Overall fortune for the year
    year_text_raw = data.get("shichu_year_fortune") or data.get("year_fortune") or texts.get("year_fortune", "")
    if year_text_raw:
        year_title = titles.get("year_fortune", "Overall fortune")
        m = re.search(r"\b(20\d{2})\b", str(year_text_raw))
        if m:
            year_title = f"Overall fortune for {m.group(1)}"
        write_block(year_title, str(year_text_raw))

    # This month / next month
    month_src = data.get("shichu_month_fortune") or data.get("month_fortune") or texts.get("month_fortune", "")
    next_month_src = data.get("shichu_next_month_fortune") or data.get("next_month_fortune") or texts.get("next_month_fortune", "")

    month_text = _normalize_month_fortune_text(month_src, birthdate, lang=lang)
    next_month_text = _normalize_next_month_fortune_text(next_month_src, birthdate, lang=lang)

    write_block(titles.get("month_fortune", "This Month"), month_text)
    write_block(titles.get("next_month_fortune", "Next Month"), next_month_text)

    # Lucky info at the end of page 2
    lucky_lines = data.get("lucky_info", []) or []
    lucky_direction = data.get("lucky_direction", "") or ""
    lucky_text_blob = " ".join([str(x) for x in lucky_lines]) + " " + str(lucky_direction)
    lucky_lang = "ja" if _has_non_ascii(lucky_text_blob) else "en"

    y = draw_lucky_section(
        c,
        page_width,
        margin,
        y,
        lucky_lines,
        lucky_direction,
        lang=lucky_lang,
        page_height=page_height,
        font_name=select_font_for_lang(lucky_lang),
    )

    # Optional yearly pages
    if include_yearly:
        draw_yearly_pages_shincom_b4(c, data, lang=lang)

def _coerce_yearly_payload(value):
    """
    Normalize yearly fortune payload into:
      - year_label: str
      - year_text : str
      - months    : list[{"label": str, "text": str}]
    Accepts a wide range of shapes:
      - list of dicts (label/text)
      - dict with keys months/year_label/year_text (months may be list, dict, or a serialized string)
      - legacy dicts where months are embedded as { "2026-02": "...", ... }
      - stringified JSON / Python repr of the above
    """
    def _to_str(x):
        return "" if x is None else str(x)

    def _try_parse_structured_string(s):
        if not isinstance(s, str):
            return s
        ss = s.strip()
        if not ss:
            return None
        # Try JSON first (true/false/null), then Python literal repr.
        if (ss[0] in "[{") and (ss[-1] in "]}"):
            try:
                return json.loads(ss)
            except Exception:
                pass
            try:
                return ast.literal_eval(ss)
            except Exception:
                pass
        return None

    def _month_sort_key(label):
        if not label:
            return (9999, 99, label)
        m = re.search(r"(\d{4})[-/](\d{1,2})", str(label))
        if not m:
            return (9999, 99, str(label))
        y = int(m.group(1))
        mo = int(m.group(2))
        return (y, mo, str(label))

    if value is None:
        return "", "", []

    # If we got a string, try to parse it first.
    if isinstance(value, str):
        parsed = _try_parse_structured_string(value)
        if parsed is not None:
            value = parsed
        else:
            # plain text fallback
            return "", _to_str(value), []

    # list => months only
    if isinstance(value, list):
        months = []
        for it in value:
            months.append(_norm_month_item(it))
        months.sort(key=lambda d: _month_sort_key(d.get("label", "")))
        return "", "", months

    # dict => try to interpret structured layout first
    if isinstance(value, dict):
        # 1) Prefer explicit structure if present
        structure_keys = {"months", "year_label", "year_text", "monthly", "items", "fortunes", "month_fortunes"}
        if any(k in value for k in structure_keys):
            year_label = _to_str(value.get("year_label") or value.get("year") or value.get("label"))
            year_text = _to_str(value.get("year_text") or value.get("text") or value.get("yearly_text") or value.get("yearly"))

            months_raw = None
            for k in ("months", "monthly", "month_fortunes", "fortunes", "items"):
                if k in value and value.get(k) is not None:
                    months_raw = value.get(k)
                    break

            months_parsed = _try_parse_structured_string(months_raw) if isinstance(months_raw, str) else months_raw

            months = []
            if isinstance(months_parsed, list):
                for it in months_parsed:
                    months.append(_norm_month_item(it))
            elif isinstance(months_parsed, dict):
                for k, v in months_parsed.items():
                    months.append(_norm_month_item({"label": _to_str(k), "text": _to_str(v)}))
            elif months_parsed is None:
                months = []
            else:
                # months provided as plain text; keep as a single entry
                months.append(_norm_month_item({"label": "months", "text": _to_str(months_parsed)}))

            # 2) If months is still empty, fall back to "month-like" keys inside dict
            if not months:
                month_like = []
                for k, v in value.items():
                    kk = str(k)
                    if re.match(r"^\d{4}[-/]\d{1,2}$", kk) or re.match(r"^\d{4}-\d{2}", kk):
                        month_like.append((kk, v))
                if month_like:
                    for kk, vv in month_like:
                        months.append(_norm_month_item({"label": kk, "text": _to_str(vv)}))

            months.sort(key=lambda d: _month_sort_key(d.get("label", "")))
            return year_label, year_text, months

        # 2) Otherwise interpret as a mapping of month-like keys or generic label->text
        month_items = []
        for k, v in value.items():
            month_items.append(_norm_month_item({"label": _to_str(k), "text": _to_str(v)}))
        month_items.sort(key=lambda d: _month_sort_key(d.get("label", "")))
        return "", "", month_items

    # fallback
    return "", _to_str(value), []
def _coerce_yearly_fortunes(yearly_data):
    """
    Backward-compatible helper: returns {month: text} mapping.
    (Kept because older code paths may still call it.)
    """
    payload = _coerce_yearly_payload(yearly_data)
    return {m["label"]: m["text"] for m in payload.get("months") or []}

def draw_yearly_pages_shincom_a4(c, data, lang="en"):
    """
    A4 yearly fortunes (2 pages / 12 months), aligned with the Japanese A4 layout:
      - Page 3: Yearly title + year summary + Feb..Jul (6 months)
      - Page 4: Yearly title + Aug..Jan (6 months)
    """
    page_width, page_height = A4

    # Match the Japanese layout geometry
    x = 20 * mm
    y_top = page_height - 30 * mm
    usable_width = page_width - 40 * mm

    year_label, year_text, month_items = _coerce_yearly_fortunes(data)

    def _format_month_label(label):
        s = (label or "").strip()
        if not s:
            return "Monthly fortune"
        # If the model already gave "Fortune for XXXX-XX", keep it as-is
        if s.lower().startswith("fortune for"):
            return s
        return f"Fortune for {s}"

    def _draw_title_and_year_block():
        y = y_top
        _set_font(c, lang, 12)
        c.drawString(x, y, "Yearly Fortunes")
        y -= 8 * mm

        # Year label (optional)
        if year_label:
            _set_font(c, lang, 10)
            c.drawString(x, y, str(year_label))
            y -= 6 * mm

        # Year text (optional)
        if year_text:
            _set_font(c, lang, 10)
            for line in smart_wrap(str(year_text), _wrap_len(90, lang)):
                c.drawString(x, y, line)
                y -= 5 * mm
            y -= 2 * mm

        return y

    def _draw_months(months, y_start):
        y = y_start
        _set_font(c, lang, 10)

        for item in months:
            label = _format_month_label(item.get("label", ""))
            text = item.get("text", "")

            # Month header
            c.drawString(x, y, f"■ {label}")
            y -= 5 * mm

            # Month body
            for line in smart_wrap(str(text), _wrap_len(90, lang)):
                c.drawString(x, y, line)
                y -= 5 * mm

            y -= 2 * mm

            # Safety: don't overrun the page
            if y < 20 * mm:
                break

        return y

    # Split into two pages
    first_page_months = month_items[:6]
    second_page_months = month_items[6:]

    # Page 3
    c.showPage()
    y_after_header = _draw_title_and_year_block()
    _draw_months(first_page_months, y_after_header)

    # Page 4 (only if there's content)
    if second_page_months:
        c.showPage()
        y_after_header = _draw_title_and_year_block()
        _draw_months(second_page_months, y_after_header)
def draw_yearly_pages_shincom_b4(c, data, lang="en"):
    """
    B4 landscape yearly pages (2 pages max): year overview + 12 monthly fortunes (6 per page).
    """
    page_width, page_height = landscape(B4)
    margin = 45

    yearly_val = (
        data.get("yearly_fortunes")
        or data.get("yearly_fortune")
        or data.get("yearly")
        or None
    )

    payload = _coerce_yearly_payload(
        yearly_val,
        fallback_year_label=None,
        fallback_year_text=None
    )
    months = payload.get("months") or []
    year_label = payload.get("year_label")
    year_text = payload.get("year_text")

    if not months and not (year_text or "").strip():
        return

    def _set_line_font(text, size):
        use_lang = "ja" if _has_non_ascii(text) else lang
        _set_font(c, select_font_for_lang(use_lang), size)

    def _draw_header(y):
        _set_line_font("Yearly Fortunes", 18)
        c.drawString(margin, y, "Yearly Fortunes")
        y -= 11 * mm

        if year_label and str(year_label).strip() and str(year_label).strip().lower() != "yearly fortunes":
            _set_line_font(str(year_label), 13)
            c.drawString(margin, y, str(year_label))
            y -= 8 * mm

        if year_text and str(year_text).strip():
            lines = split_text(str(year_text), 120, lang if not _has_non_ascii(str(year_text)) else "ja")
            for line in lines:
                _set_line_font(line, 10.5)
                c.drawString(margin, y, line)
                y -= 6.2 * mm
            y -= 4 * mm

        return y

    def _format_month_label(lbl: str) -> str:
        s = (lbl or "").strip()
        if not s:
            return "Monthly Fortune"
        if s.lower().startswith("fortune"):
            return s
        if re.match(r"^\d{4}[-/]\d{1,2}$", s):
            return f"Fortune for {s}"
        return s

    def _draw_months(month_items):
        y = page_height - margin
        y = _draw_header(y)

        for m in month_items:
            label = _format_month_label(m.get("label", ""))
            text = m.get("text", "")

            _set_line_font(label, 12)
            c.drawString(margin, y, label)
            y -= 7.5 * mm

            body_lang = "ja" if _has_non_ascii(text) else lang
            wrap_len = 120 if body_lang == "en" else 60
            lines = split_text(text, wrap_len, body_lang)
            for line in lines:
                _set_line_font(line, 10.5)
                c.drawString(margin, y, line)
                y -= 6.1 * mm
                if y < margin + 20 * mm:
                    c.showPage()
                    y = page_height - margin
            y -= 4.5 * mm

    c.showPage()
    _draw_months(months[:6])

    if len(months) > 6:
        c.showPage()
        _draw_months(months[6:12])

def draw_yearly_pages_renai_a4(c, yearly, lang="ja"):
    """恋愛版 A4：年運＋12か月恋愛運を、テキスト量に応じて自動で複数ページに描画する。"""
    width, height = A4
    margin = 20 * mm
    top = height - 30 * mm
    bottom = 30 * mm

    def draw_text_block(title, text, y):
        # 必要ならページを切り替え
        if y < bottom + 15 * mm:
            c.showPage()
            y = top

        _set_font(c, lang, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 5 * mm

        _set_font(c, lang, 10)
        for line in smart_wrap(text or "", _wrap_len(46, lang), lang):
            if y < bottom:
                c.showPage()
                y = top
                _set_font(c, lang, 10)
            c.drawString(margin, y, line)
            y -= 5 * mm

        y -= 3 * mm
        return y

    # 年運 → 12か月分の順に描画
    c.showPage()
    y = top
    y = draw_text_block(yearly.get("year_label", ""), yearly.get("year_text", ""), y)
    for month in yearly.get("months", []):
        y = draw_text_block(month.get("label", ""), month.get("text", ""), y)


# =========================
# 恋愛版 年運ページ（B4）
# =========================
def draw_yearly_pages_renai_b4(c, yearly, lang="ja"):
    """恋愛版 B4：年運＋12か月恋愛運を、テキスト量に応じて自動で複数ページに描画する。"""
    width, height = B4
    margin = 20 * mm
    top = height - 30 * mm
    bottom = 30 * mm

    def draw_text_block(title, text, y):
        # 必要ならページを切り替え
        if y < bottom + 18 * mm:
            c.showPage()
            y = top

        _set_font(c, lang, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm

        _set_font(c, lang, 11)
        for line in smart_wrap(text or "", _wrap_len(45, lang), lang):
            if y < bottom:
                c.showPage()
                y = top
                _set_font(c, lang, 11)
            c.drawString(margin, y, line)
            y -= 7 * mm

        y -= 4 * mm
        return y

    # 年運 → 12か月分の順に描画
    c.showPage()
    y = top
    y = draw_text_block(yearly.get("year_label", ""), yearly.get("year_text", ""), y)
    for month in yearly.get("months", []):
        y = draw_text_block(month.get("label", ""), month.get("text", ""), y)



def _has_non_ascii(s: str) -> bool:
    try:
        return any(ord(ch) > 127 for ch in (s or ""))
    except Exception:
        return False


def split_text(text: str, lang: str = "en", base: int = 46):
    """Split text into wrapped lines for PDF drawing.
    EN module enforces wrap=90 via _wrap_len().
    """
    return smart_wrap(text or "", _wrap_len(base, lang), lang)


def _normalize_month_fortune_text(text: str, birthdate: str = "", lang: str = "en") -> str:
    """EN shim: keep text as-is (signature-compatible with callers)."""
    return (text or "").strip()


def _normalize_next_month_fortune_text(text: str, birthdate: str = "", lang: str = "en") -> str:
    """EN shim: keep text as-is (signature-compatible with callers)."""
    return (text or "").strip()

def draw_shincom_a4(c, data, include_yearly=False):
    """English (shincom) A4 layout aligned with the Japanese A4 layout.
    Page 1: Header + Palm image + Birth info + Palm sections (1-3)
    Page 2: Palm sections (4-5) + Palm summary + Personality + Year/Month/Next month + Lucky info
    (Optional) Yearly pages: 2 pages for 12 months (6 months per page)
    Header is drawn ONLY on page 1.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    page_width, page_height = A4
    margin = 20 * mm
    y = page_height - margin

    lang = "en"
    font_name = select_font_for_lang(lang)

    # Header (page 1 only)
    y = draw_header(c, page_width, margin, y)

    # Palm image
    y = draw_palm_image(c, data, page_width, margin, y, font_name=font_name)
    y -= 4

    # Birth info (optional, shown under the image)
    birthdate = (data.get("birthdate") or "").strip()
    zodiac = (data.get("zodiac_sign") or data.get("zodiac") or "").strip()
    eto = (data.get("eto") or "").strip()
    eto_number = data.get("eto_number")
    animal = (data.get("animal") or "").strip()
    honmeisei = (data.get("honmeisei") or "").strip()

    line1_parts = []
    if birthdate:
        line1_parts.append(f"Birthdate: {birthdate}")
    if zodiac:
        line1_parts.append(f"Zodiac: {zodiac}")
    line2_parts = []
    if eto:
        if eto_number is not None and str(eto_number).strip() != "":
            line2_parts.append(f"Eto: {eto} ({eto_number})")
        else:
            line2_parts.append(f"Eto: {eto}")
    if animal:
        line2_parts.append(f"Animal: {animal}")
    if honmeisei:
        line2_parts.append(f"Main Star: {honmeisei}")

    if line1_parts:
        y = _draw_info_line_auto(c, margin, y, line1_parts, font_name, 9)
    if line2_parts:
        y = _draw_info_line_auto(c, margin, y, line2_parts, font_name, 9)
    _set_font(c, font_name, 9)
    y -= 2

    palm_titles = data.get("palm_titles", []) or []
    palm_texts = data.get("palm_texts", []) or []

    # --- Wrapping & font fallback (EN pages may still include Japanese labels) ---
    _cjk_re = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
    def _is_cjk(s: str) -> bool:
        return bool(_cjk_re.search(s or ""))

    max_w = page_width - 2 * margin
    bottom_y = margin  # keep bottom margin

    def _wrap_text_to_width(text, font_size: float):
        """Wrap text to the available width using stringWidth.

        - If a paragraph contains CJK, wrap by character while measuring with JA font.
        - Otherwise wrap by words while measuring with EN font.
        """
        if text is None:
            return []
        s = str(text)
        if not s:
            return []
        out = []
        for para in s.splitlines():
            if para == "":
                out.append("")
                continue
            if _is_cjk(para):
                face = _font("ja")
                cur = ""
                for ch in para:
                    test = cur + ch
                    if stringWidth(test, face, font_size) <= max_w:
                        cur = test
                    else:
                        if cur:
                            out.append(cur)
                        cur = ch
                if cur:
                    out.append(cur)
            else:
                face = _font("en")
                words = para.split(" ")
                cur = ""
                for w in words:
                    test = w if not cur else (cur + " " + w)
                    if stringWidth(test, face, font_size) <= max_w:
                        cur = test
                    else:
                        if cur:
                            out.append(cur)
                        # break long words if needed
                        if stringWidth(w, face, font_size) <= max_w:
                            cur = w
                        else:
                            chunk = ""
                            for ch in w:
                                t2 = chunk + ch
                                if stringWidth(t2, face, font_size) <= max_w:
                                    chunk = t2
                                else:
                                    if chunk:
                                        out.append(chunk)
                                    chunk = ch
                            cur = chunk
                if cur:
                    out.append(cur)
        return out

    def write_block(title: str, body: str):
        """Draw one titled text block with auto fitting.

        English A4 often needs tighter spacing; if it still doesn't fit, truncate with ellipsis.
        """
        nonlocal y

        title = title or ""
        body = body or ""

        styles = [
            dict(title_size=12, title_step=14, body_size=10, line_step=12, gap=8),
            dict(title_size=11, title_step=13, body_size=9.5, line_step=11, gap=6),
            dict(title_size=10.5, title_step=12, body_size=9.0, line_step=10.5, gap=5),
        ]

        chosen = styles[0]
        lines = _wrap_text_to_width(body, chosen["body_size"])

        # Pick the first style that fits; otherwise truncate in the most compact style.
        for st in styles:
            st_lines = _wrap_text_to_width(body, st["body_size"])
            need = (st["title_step"] if title else 0) + len(st_lines) * st["line_step"] + st["gap"]
            if (y - need) >= bottom_y:
                chosen, lines = st, st_lines
                break
        else:
            chosen = styles[-1]
            all_lines = _wrap_text_to_width(body, chosen["body_size"])
            avail = y - bottom_y - (chosen["title_step"] if title else 0) - chosen["gap"]
            max_lines = max(1, int(avail // chosen["line_step"]))
            lines = all_lines[:max_lines]
            if len(all_lines) > max_lines and lines:
                ell = "..."
                last = lines[-1]
                face = _font("ja") if _is_cjk(last) else _font("en")
                while last and stringWidth(last + ell, face, chosen["body_size"]) > max_w:
                    last = last[:-1]
                lines[-1] = (last + ell) if last else ell

        if title:
            t_lang = "ja" if _is_cjk(title) else "en"
            _set_font(c, t_lang, chosen["title_size"])
            c.drawString(margin, y, f"◆ {title}")
            y -= chosen["title_step"]

        if body:
            for line in lines:
                l_lang = "ja" if _is_cjk(line) else "en"
                _set_font(c, l_lang, chosen["body_size"])
                c.drawString(margin, y, line)
                y -= chosen["line_step"]

        y -= chosen["gap"]


    # --- Page 1: Palm sections 1-3 ---
    for i in range(3):
        title = palm_titles[i] if i < len(palm_titles) else ""
        text = palm_texts[i] if i < len(palm_texts) else ""
        write_block(title, text)

    # --- Page 2 (no header) ---
    c.showPage()
    y = page_height - margin

    titles = data.get("titles", {}) or {}
    texts = data.get("texts", {}) or {}

    # Remaining palm sections 4-5
    for i in range(3, 5):
        title = palm_titles[i] if i < len(palm_titles) else ""
        text = palm_texts[i] if i < len(palm_texts) else ""
        write_block(title, text)

    # Overall palm summary
    write_block("Overall Palm Reading", texts.get("palm_summary", ""))

    # Personality
    personality_text = data.get("shichu_personality") or data.get("personality") or texts.get("personality", "")
    write_block("Personality", personality_text)

    # Overall fortune for the year
    year_text_raw = data.get("shichu_year_fortune") or data.get("year_fortune") or texts.get("year_fortune", "")
    if year_text_raw:
        year_title = titles.get("year_fortune", "Overall fortune")
        m = re.search(r"\b(20\d{2})\b", str(year_text_raw))
        if m:
            year_title = f"Overall fortune for {m.group(1)}"
        write_block(year_title, str(year_text_raw))

    # This month / next month fortunes (support multiple key names)
    month_src = data.get("shichu_month_fortune") or data.get("month_fortune") or texts.get("month_fortune", "")
    next_month_src = data.get("shichu_next_month_fortune") or data.get("next_month_fortune") or texts.get("next_month_fortune", "")

    month_text = _normalize_month_fortune_text(month_src, birthdate, lang=lang)
    next_month_text = _normalize_next_month_fortune_text(next_month_src, birthdate, lang=lang)

    write_block(titles.get("month_fortune", "This Month"), month_text)
    write_block(titles.get("next_month_fortune", "Next Month"), next_month_text)

    # Lucky info at the end of page 2 (auto font if Japanese sneaks in)
    lucky_lines = data.get("lucky_info", []) or []
    lucky_direction = data.get("lucky_direction", "") or ""
    lucky_text_blob = " ".join([str(x) for x in lucky_lines]) + " " + str(lucky_direction)
    lucky_lang = "ja" if _has_non_ascii(lucky_text_blob) else "en"

    y = draw_lucky_section(
        c,
        page_width,
        margin,
        y,
        lucky_lines,
        lucky_direction,
        lang=lucky_lang,
        page_height=page_height,
        font_name=select_font_for_lang(lucky_lang),
    )

    # Optional yearly pages (2 pages / 12 months)
    if include_yearly:
        draw_yearly_pages_shincom_a4(c, data, lang="en")

def draw_shincom_b4(c, data, include_yearly=False):
    """English (shincom) B4 layout aligned with the Japanese B4 layout.
    Page 1: Header + Palm image + Birth info + Palm sections (1-5)
    Page 2: Palm summary + Personality + Year/Month/Next month + Lucky info
    (Optional) Yearly pages: 2 pages for 12 months (6 months per page)
    Header is drawn ONLY on page 1.
    """
    from reportlab.lib.pagesizes import B4
    from reportlab.lib.units import mm

    page_width, page_height = B4
    margin = 18 * mm
    y = page_height - margin

    lang = "en"
    font_name = select_font_for_lang(lang)

    # Header (page 1 only)
    y = draw_header(c, page_width, margin, y)

    # Palm image
    y = draw_palm_image(c, data, page_width, margin, y, font_name=font_name)
    y -= 4

    # Birth info under the image
    birthdate = (data.get("birthdate") or "").strip()
    zodiac = (data.get("zodiac_sign") or data.get("zodiac") or "").strip()
    eto = (data.get("eto") or "").strip()
    eto_number = data.get("eto_number")
    animal = (data.get("animal") or "").strip()
    honmeisei = (data.get("honmeisei") or "").strip()

    line1_parts = []
    if birthdate:
        line1_parts.append(f"Birthdate: {birthdate}")
    if zodiac:
        line1_parts.append(f"Zodiac: {zodiac}")
    line2_parts = []
    if eto:
        if eto_number is not None and str(eto_number).strip() != "":
            line2_parts.append(f"Eto: {eto} ({eto_number})")
        else:
            line2_parts.append(f"Eto: {eto}")
    if animal:
        line2_parts.append(f"Animal: {animal}")
    if honmeisei:
        line2_parts.append(f"Main Star: {honmeisei}")

    if line1_parts:
        y = _draw_info_line_auto(c, margin, y, line1_parts, font_name, 10, 14)
    if line2_parts:
        y = _draw_info_line_auto(c, margin, y, line2_parts, font_name, 10, 14)
    _set_font(c, font_name, 10)
    y -= 2

    palm_titles = data.get("palm_titles", []) or []
    palm_texts = data.get("palm_texts", []) or []

    def ensure_space(min_needed: float):
        nonlocal y
        if y < (margin + min_needed):
            c.showPage()
            y = page_height - margin
        return y

    # --- Wrapping & font fallback (EN pages may still include Japanese labels) ---
    _cjk_re = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
    def _is_cjk(s: str) -> bool:
        return bool(_cjk_re.search(s or ""))

    max_w = page_width - 2 * margin

    def _wrap_text_to_width(text, font_size: float):
        if text is None:
            return []
        s = str(text)
        if not s:
            return []
        out = []
        for para in s.splitlines():
            if para == "":
                out.append("")
                continue
            if _is_cjk(para):
                face = _font("ja")
                cur = ""
                for ch in para:
                    test = cur + ch
                    if stringWidth(test, face, font_size) <= max_w:
                        cur = test
                    else:
                        if cur:
                            out.append(cur)
                        cur = ch
                if cur:
                    out.append(cur)
            else:
                face = _font("en")
                words = para.split(" ")
                cur = ""
                for w in words:
                    test = w if not cur else (cur + " " + w)
                    if stringWidth(test, face, font_size) <= max_w:
                        cur = test
                    else:
                        if cur:
                            out.append(cur)
                        if stringWidth(w, face, font_size) <= max_w:
                            cur = w
                        else:
                            chunk = ""
                            for ch in w:
                                t2 = chunk + ch
                                if stringWidth(t2, face, font_size) <= max_w:
                                    chunk = t2
                                else:
                                    if chunk:
                                        out.append(chunk)
                                    chunk = ch
                            cur = chunk
                if cur:
                    out.append(cur)
        return out

    def write_block(title: str, body: str):
        nonlocal y
        title = title or ""
        body = body or ""

        title_size = 12
        body_size = 10
        title_step = 14
        line_step = 12
        gap = 8

        if title:
            ensure_space(title_step + 2)
            t_lang = "ja" if _is_cjk(title) else "en"
            _set_font(c, t_lang, title_size)
            c.drawString(margin, y, f"◆ {title}")
            y -= title_step

        if body:
            lines = _wrap_text_to_width(body, body_size)
            for line in lines:
                ensure_space(line_step + 2)
                l_lang = "ja" if _is_cjk(line) else "en"
                _set_font(c, l_lang, body_size)
                c.drawString(margin, y, line)
                y -= line_step

        y -= gap


    # --- Page 1: all 5 palm sections ---
    for i in range(5):
        title = palm_titles[i] if i < len(palm_titles) else ""
        text = palm_texts[i] if i < len(palm_texts) else ""
        write_block(title, text)

    # Start page 2 (no header)
    c.showPage()
    y = page_height - margin

    titles = data.get("titles", {}) or {}
    texts = data.get("texts", {}) or {}

    # Overall palm summary
    write_block("Overall Palm Reading", texts.get("palm_summary", ""))

    # Personality
    personality_text = data.get("shichu_personality") or data.get("personality") or texts.get("personality", "")
    write_block("Personality", personality_text)

    # Overall fortune for the year
    year_text_raw = data.get("shichu_year_fortune") or data.get("year_fortune") or texts.get("year_fortune", "")
    if year_text_raw:
        year_title = titles.get("year_fortune", "Overall fortune")
        m = re.search(r"\b(20\d{2})\b", str(year_text_raw))
        if m:
            year_title = f"Overall fortune for {m.group(1)}"
        write_block(year_title, str(year_text_raw))

    # This month / next month
    month_src = data.get("shichu_month_fortune") or data.get("month_fortune") or texts.get("month_fortune", "")
    next_month_src = data.get("shichu_next_month_fortune") or data.get("next_month_fortune") or texts.get("next_month_fortune", "")

    month_text = _normalize_month_fortune_text(month_src, birthdate, lang=lang)
    next_month_text = _normalize_next_month_fortune_text(next_month_src, birthdate, lang=lang)

    write_block(titles.get("month_fortune", "This Month"), month_text)
    write_block(titles.get("next_month_fortune", "Next Month"), next_month_text)

    # Lucky info at the end of page 2
    lucky_lines = data.get("lucky_info", []) or []
    lucky_direction = data.get("lucky_direction", "") or ""
    lucky_text_blob = " ".join([str(x) for x in lucky_lines]) + " " + str(lucky_direction)
    lucky_lang = "ja" if _has_non_ascii(lucky_text_blob) else "en"

    y = draw_lucky_section(
        c,
        page_width,
        margin,
        y,
        lucky_lines,
        lucky_direction,
        lang=lucky_lang,
        page_height=page_height,
        font_name=select_font_for_lang(lucky_lang),
    )

    # Optional yearly pages
    if include_yearly:
        draw_yearly_pages_shincom_b4(c, data, lang="en")


def _coerce_yearly_fortunes(data):
    """
    Accepts several possible shapes:
    - dict: {"2026-02": "...", "2026-03": "...", ...}
    - list: [{"month":"2026-02","text":"..."}, ...] or ["...", ...]
    Returns dict[str,str].
    """
    yearly = (
        data.get("yearly_fortunes")
        or data.get("yearly_fortune")
        or data.get("yearly_fortunes_text")
        or {}
    )
    if isinstance(yearly, dict):
        return {str(k): str(v) for k, v in yearly.items() if str(v).strip()}
    if isinstance(yearly, list):
        out = {}
        for i, item in enumerate(yearly):
            if isinstance(item, dict):
                m = item.get("month") or item.get("ym") or item.get("title") or item.get("key")
                t = item.get("text") or item.get("body") or item.get("fortune") or ""
                if m and str(t).strip():
                    out[str(m)] = str(t)
            else:
                t = str(item).strip()
                if t:
                    out[f"month-{i+1:02d}"] = t
        return out
    return {}

def draw_yearly_pages_shincom_a4(c, data, lang="en"):
    """Yearly fortunes for shincom (A4). Draws 2 pages (6 months per page) without headers."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm

    yearly = _coerce_yearly_fortunes(data)
    if not yearly:
        return

    page_width, page_height = A4
    margin = 20 * mm
    font_name = select_font_for_lang(lang)

    def _key(m):
        mmatch = re.match(r"(\d{4})-(\d{2})", m)
        if mmatch:
            return (int(mmatch.group(1)), int(mmatch.group(2)))
        return (9999, 99, m)

    months = sorted(yearly.keys(), key=_key)

    def draw_page(sub_months):
        y = page_height - margin
        _set_font(c, font_name, 12)
        c.drawString(margin, y, "Yearly Fortunes")
        y -= 18

        for mth in sub_months:
            title = f"■ Fortune for {mth}"
            _set_font(c, font_name, 11)
            c.drawString(margin, y, title)
            y -= 14

            body = yearly.get(mth, "")
            body_lang = "ja" if _has_non_ascii(body) else lang
            body_font = select_font_for_lang(body_lang)

            _set_font(c, body_font, 10)
            for line in smart_wrap(body, _wrap_len(90, body_lang), body_lang):
                c.drawString(margin, y, line)
                y -= 12
            y -= 10

    c.showPage()
    draw_page(months[:6])
    c.showPage()
    draw_page(months[6:12])

def draw_yearly_pages_shincom_b4(c, data, lang="en"):
    """Yearly fortunes for shincom (B4). Draws 2 pages (6 months per page) without headers."""
    from reportlab.lib.pagesizes import B4
    from reportlab.lib.units import mm

    yearly = _coerce_yearly_fortunes(data)
    if not yearly:
        return

    page_width, page_height = B4
    margin = 18 * mm
    font_name = select_font_for_lang(lang)

    def _key(m):
        mmatch = re.match(r"(\d{4})-(\d{2})", m)
        if mmatch:
            return (int(mmatch.group(1)), int(mmatch.group(2)))
        return (9999, 99, m)

    months = sorted(yearly.keys(), key=_key)

    def draw_page(sub_months):
        y = page_height - margin
        _set_font(c, font_name, 13)
        c.drawString(margin, y, "Yearly Fortunes")
        y -= 20

        for mth in sub_months:
            title = f"■ Fortune for {mth}"
            _set_font(c, font_name, 12)
            c.drawString(margin, y, title)
            y -= 16

            body = yearly.get(mth, "")
            body_lang = "ja" if _has_non_ascii(body) else lang
            body_font = select_font_for_lang(body_lang)

            _set_font(c, body_font, 11)
            for line in smart_wrap(body, _wrap_len(95, body_lang), body_lang):
                c.drawString(margin, y, line)
                y -= 13
            y -= 12

    c.showPage()
    draw_page(months[:6])
    c.showPage()
    draw_page(months[6:12])


def draw_renai_pdf(c, data, size, include_yearly=False):
    lang = _get_lang(data)
    from reportlab.lib.pagesizes import A4, B4
    from reportlab.lib.units import mm
    from header_utils import draw_header
    from pdf_generator_unified import draw_yearly_pages_renai_a4, draw_yearly_pages_renai_b4, draw_lucky_section, FONT_NAME

    width, height = A4 if size == 'a4' else B4
    margin = 20 * mm
    wrap_len = 40 if size == 'a4' else 45
    y = draw_header(c, width, margin, height - margin)

    # 1ページ目：相性診断・恋愛運（年/月/来月）
    main_keys = [
        "compatibility",
        "year_love",
        "month_love",
        "next_month_love",
    ]
    _set_font(c, lang, 12)
    for key in main_keys:
        if key in data.get("texts", {}) and data["texts"][key].strip():
            c.drawString(margin, y, f"◆ {data['titles'].get(key, key)}")
            y -= 6 * mm
            _set_font(c, lang, 10)
            for line in smart_wrap(data["texts"][key], _wrap_len(wrap_len, lang), lang):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 4 * mm
            _set_font(c, lang, 12)

    c.showPage()
    y = height - margin

    # 2ページ目：恋愛テーマ3項目（注意点・距離感・結婚）
    if data.get("themes"):
        _set_font(c, lang, 12)
        for section in data["themes"]:
            c.drawString(margin, y, f"◆ {section['title']}")
            y -= 6 * mm
            _set_font(c, lang, 10)
            for line in smart_wrap(section["content"], _wrap_len(wrap_len, lang), lang):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 4 * mm
            _set_font(c, lang, 12)

    # ラッキー情報・吉方位（2ページ目末尾）
    y = draw_lucky_section(
        c, width, margin, y,
        data.get("lucky_info", []),
        data.get("lucky_direction", "")
    )

    # 年運（オプション）
    if include_yearly and data.get("yearly_love_fortunes"):
        if size == "a4":
            draw_yearly_pages_renai_a4(c, data["yearly_love_fortunes"])
        else:
            draw_yearly_pages_renai_b4(c, data["yearly_love_fortunes"])


def create_pdf_unified(filepath, data, mode, size='a4', include_yearly=False):
    data = data or {}
    print(f"[ENPDF] {EN_PDFGEN_MARKER} file={__file__} mode={mode} size={size} include_yearly={include_yearly}", flush=True)
    data.setdefault('lang', _get_lang(data))
    size = size.lower()
    c = canvas.Canvas(filepath, pagesize=A4 if size == 'a4' else B4)
    c.setTitle('占い結果')
    if mode == 'shincom':
        if size == 'a4':
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        draw_renai_pdf(c, data, size, include_yearly)
    c.save()

# ============================================================
# PATCH v9: Robust yearly fortunes parsing + JP-like pagination
# - Fix: yearly data sometimes arrives as {"months": [...], "year_label":..., "year_text":...}
#        or stringified Python/JSON. This previously rendered as "Fortune for months" and blank page.
# - This patch normalizes months into { "YYYY-MM": "text", ... } and draws year summary on the first yearly page.
# ============================================================

import ast as _ast
import json as _json
import re as _re
import textwrap as _textwrap

def _try_parse_list(value):
    """
    Accept:
      - list
      - JSON string of list
      - Python repr string of list (e.g., "[{'label':...}, ...]")
    Return list or None.
    """
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return None
    # Try JSON first
    try:
        return _json.loads(s)
    except Exception:
        pass
    # Then Python literal
    try:
        return _ast.literal_eval(s)
    except Exception:
        return None

def _normalize_month_label(label: str) -> str:
    s = (label or "").strip()
    # Common patterns:
    # "Fortune for 2026-02" -> "2026-02"
    s = _re.sub(r"^\s*fortune\s+for\s+", "", s, flags=_re.I)
    return s.strip()

def _month_sort_key(k: str):
    m = _re.match(r"^\s*(\d{4})[-/](\d{1,2})", (k or "").strip())
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (9999, 99, (k or "").strip())

def _coerce_yearly_summary(data: dict):
    """
    Returns (year_label, year_text) if available from:
      - top-level keys
      - nested yearly dict (yearly_fortunes / yearly_fortunes_text / etc.)
    """
    if not isinstance(data, dict):
        return ("", "")
    year_label = (data.get("year_label") or data.get("yearly_label") or data.get("year_title") or "").strip()
    year_text  = (data.get("year_text")  or data.get("yearly_text")  or data.get("year_fortune") or "").strip()

    yearly = (data.get("yearly_fortunes_text")
              or data.get("yearly_fortunes")
              or data.get("yearly")
              or data.get("yearly_fortune"))
    if isinstance(yearly, dict):
        if not year_label:
            year_label = (yearly.get("year_label") or yearly.get("yearly_label") or yearly.get("year_title") or "").strip()
        if not year_text:
            year_text = (yearly.get("year_text") or yearly.get("yearly_text") or yearly.get("year_text_en") or "").strip()
    return (year_label, year_text)

def _coerce_yearly_fortunes(data):
    """
    Normalize yearly fortunes into dict: { "YYYY-MM": "text", ... }
    Supports:
      A) yearly dict already: {"2026-02": "...", ...}
      B) yearly dict wrapped: {"months": [ {"label": "Fortune for 2026-02", "text": "..."}, ... ],
                              "year_label": "...", "year_text": "..."}
      C) months list stringified (JSON or Python repr)
    """
    if not isinstance(data, dict):
        return {}

    yearly = (data.get("yearly_fortunes_text")
              or data.get("yearly_fortunes")
              or data.get("yearly")
              or data.get("yearly_fortune")
              or data.get("yearly_fortunes_en"))

    # Also accept top-level months payload
    if yearly is None:
        if any(k in data for k in ("months", "fortune_for_months")):
            yearly = data

    # If yearly is a string that may contain JSON/dict, try parse
    if isinstance(yearly, str):
        s = yearly.strip()
        # Try JSON object
        try:
            yearly = _json.loads(s)
        except Exception:
            # Try python dict literal
            try:
                yearly = _ast.literal_eval(s)
            except Exception:
                yearly = None

    if not isinstance(yearly, dict):
        return {}

    # If wrapped "months" style
    months_raw = yearly.get("months")
    if months_raw is None:
        months_raw = yearly.get("fortune_for_months")
    if months_raw is None:
        months_raw = yearly.get("monthly")
    if months_raw is None:
        months_raw = yearly.get("month_fortunes")

    month_map = {}

    # Months list-of-dicts
    months_list = _try_parse_list(months_raw)
    if months_list is None and isinstance(months_raw, list):
        months_list = months_raw

    if isinstance(months_list, list):
        for it in months_list:
            if isinstance(it, dict):
                label = it.get("label") or it.get("month") or it.get("title") or it.get("key")
                text  = it.get("text")  or it.get("fortune") or it.get("value") or ""
                if label:
                    mk = _normalize_month_label(str(label))
                    month_map[mk] = str(text or "").strip()
            elif isinstance(it, (list, tuple)) and len(it) >= 2:
                mk = _normalize_month_label(str(it[0]))
                month_map[mk] = str(it[1] or "").strip()
            elif isinstance(it, str) and it.strip():
                # Fallback: treat as a line with unknown month
                mk = f"month-{len(month_map)+1:02d}"
                month_map[mk] = it.strip()
        return month_map

    # Otherwise assume direct month->text mapping; filter out meta keys
    META = {
        "months", "fortune_for_months", "monthly", "month_fortunes",
        "year_label", "year_text", "year", "label", "text", "title"
    }
    for k, v in yearly.items():
        if k in META:
            continue
        if v is None:
            continue
        month_map[str(k).strip()] = str(v).strip()

    return month_map

def draw_yearly_pages_shincom_a4(c, data, lang="en"):
    """
    v9 override: JP-like structure
      - New page for yearly (page3), then another page (page4)
      - Print year summary at top of page3 (if available)
      - Print 12 months, split 6/6
    """
    yearly = _coerce_yearly_fortunes(data)
    year_label, year_text = _coerce_yearly_summary(data)

    if not yearly and not year_text:
        return

    months = sorted(yearly.keys(), key=_month_sort_key)
    # Keep deterministic, but don't explode if fewer than 12
    first = months[:6]
    second = months[6:]

    # layout constants
    left = 50
    top = 785
    bottom = 70
    font_size = 11
    line_height = 14
    max_chars = 96
    max_lines_year = 10
    max_lines_month = 6

    font_name = select_font_for_lang(lang)
    _set_font(c, font_name, font_size)

    # PAGE 3
    c.showPage()
    _set_font(c, font_name, 14)
    c.drawString(left, top, "Yearly Fortunes")
    _set_font(c, font_name, font_size)

    y = top - 30

    # Year summary block (optional)
    if year_text:
        label = year_label or "Overall fortune"
        c.drawString(left, y, f"■ {label}")
        y -= line_height
        lines = _textwrap.wrap(year_text.replace("\n", " ").strip(), max_chars)
        if len(lines) > max_lines_year:
            lines = lines[:max_lines_year]
            if lines:
                lines[-1] = lines[-1].rstrip() + "..."
        for ln in lines:
            c.drawString(left, y, ln)
            y -= line_height
            if y < bottom:
                # If summary overflows, start months on next page (rare)
                c.showPage()
                _set_font(c, font_name, 14)
                c.drawString(left, top, "Yearly Fortunes (continued)")
                _set_font(c, font_name, font_size)
                y = top - 30
        y -= 6

    def _draw_month_block(month_key, y):
        c.drawString(left, y, f"■ Fortune for {month_key}")
        y -= line_height
        txt = (yearly.get(month_key) or "").replace("\n", " ").strip()
        lines = _textwrap.wrap(txt, max_chars)
        if len(lines) > max_lines_month:
            lines = lines[:max_lines_month]
            if lines:
                lines[-1] = lines[-1].rstrip() + "..."
        for ln in lines:
            c.drawString(left, y, ln)
            y -= line_height
        y -= 6
        return y

    for m in first:
        if y < bottom + (line_height * 6):
            c.showPage()
            _set_font(c, font_name, 14)
            c.drawString(left, top, "Yearly Fortunes (continued)")
            _set_font(c, font_name, font_size)
            y = top - 30
        y = _draw_month_block(m, y)

    # PAGE 4 (only if there is content)
    if second:
        c.showPage()
        _set_font(c, font_name, 14)
        c.drawString(left, top, "Yearly Fortunes")
        _set_font(c, font_name, font_size)
        y = top - 30
        for m in second:
            if y < bottom + (line_height * 6):
                c.showPage()
                _set_font(c, font_name, 14)
                c.drawString(left, top, "Yearly Fortunes (continued)")
                _set_font(c, font_name, font_size)
                y = top - 30
            y = _draw_month_block(m, y)

def draw_yearly_pages_shincom_b4(c, data, lang="en"):
    """
    v9 override for B4: same as A4 but slightly wider.
    """
    yearly = _coerce_yearly_fortunes(data)
    year_label, year_text = _coerce_yearly_summary(data)

    if not yearly and not year_text:
        return

    months = sorted(yearly.keys(), key=_month_sort_key)
    first = months[:6]
    second = months[6:]

    left = 60
    top = 1120
    bottom = 90
    font_size = 11
    line_height = 14
    max_chars = 108
    max_lines_year = 12
    max_lines_month = 7

    font_name = select_font_for_lang(lang)
    _set_font(c, font_name, font_size)

    # PAGE 3
    c.showPage()
    _set_font(c, font_name, 16)
    c.drawString(left, top, "Yearly Fortunes")
    _set_font(c, font_name, font_size)

    y = top - 35

    if year_text:
        label = year_label or "Overall fortune"
        c.drawString(left, y, f"■ {label}")
        y -= line_height
        lines = _textwrap.wrap(year_text.replace("\n", " ").strip(), max_chars)
        if len(lines) > max_lines_year:
            lines = lines[:max_lines_year]
            if lines:
                lines[-1] = lines[-1].rstrip() + "..."
        for ln in lines:
            c.drawString(left, y, ln)
            y -= line_height
            if y < bottom:
                c.showPage()
                _set_font(c, font_name, 16)
                c.drawString(left, top, "Yearly Fortunes (continued)")
                _set_font(c, font_name, font_size)
                y = top - 35
        y -= 8

    def _draw_month_block(month_key, y):
        c.drawString(left, y, f"■ Fortune for {month_key}")
        y -= line_height
        txt = (yearly.get(month_key) or "").replace("\n", " ").strip()
        lines = _textwrap.wrap(txt, max_chars)
        if len(lines) > max_lines_month:
            lines = lines[:max_lines_month]
            if lines:
                lines[-1] = lines[-1].rstrip() + "..."
        for ln in lines:
            c.drawString(left, y, ln)
            y -= line_height
        y -= 8
        return y

    for m in first:
        if y < bottom + (line_height * 7):
            c.showPage()
            _set_font(c, font_name, 16)
            c.drawString(left, top, "Yearly Fortunes (continued)")
            _set_font(c, font_name, font_size)
            y = top - 35
        y = _draw_month_block(m, y)

    if second:
        c.showPage()
        _set_font(c, font_name, 16)
        c.drawString(left, top, "Yearly Fortunes")
        _set_font(c, font_name, font_size)
        y = top - 35
        for m in second:
            if y < bottom + (line_height * 7):
                c.showPage()
                _set_font(c, font_name, 16)
                c.drawString(left, top, "Yearly Fortunes (continued)")
                _set_font(c, font_name, font_size)
                y = top - 35
            y = _draw_month_block(m, y)

