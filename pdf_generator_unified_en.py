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



def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction, lang='en', page_height=None, **kwargs):
    """ラッキー情報セクション
    - 2列表示で横幅を有効活用（余白があるのに3ページ化する問題を抑制）
    - lucky_lines が 1行でも2行でも崩れない
    - 呼び出し側の互換（lang/page_height/kwargs）対応
    """
    if not lucky_lines:
        lucky_lines = []

    _set_font(c, lang, 12)
    title = "■ Lucky Info (from birthdate)" if (str(lang).lower().startswith("en")) else "■ ラッキー情報（生年月日より）"
    c.drawString(margin, y, title)
    y -= 6 * mm

    # 2列レイアウト
    _set_font(c, lang, 10)
    col_gap = 8 * mm
    col_w = (width - 2 * margin - col_gap) / 2.0
    line_h = 5.6 * mm
    font_name = _font(lang)
    font_size = 10

    def _fit_one_line(s: str, max_w: float) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        # 収まるならそのまま
        if stringWidth(s, font_name, font_size) <= max_w:
            return s
        # 末尾省略
        ell = "…"
        while s and stringWidth(s + ell, font_name, font_size) > max_w:
            s = s[:-1]
        return (s + ell) if s else ell

    # 2つずつ（左・右）描画。奇数なら右は空。
    for i in range(0, len(lucky_lines), 2):
        left = _fit_one_line(lucky_lines[i], col_w)
        right = _fit_one_line(lucky_lines[i + 1] if i + 1 < len(lucky_lines) else "", col_w)

        c.drawString(margin, y, left)
        if right:
            c.drawString(margin + col_w + col_gap, y, right)
        y -= line_h

    # 方位（必要なら最後に）
    if lucky_direction:
        y -= 1.5 * mm
        _set_font(c, lang, 10)
        direction_title = "■ Lucky Directions" if (str(lang).lower().startswith("en")) else "■ ラッキー方位"
        c.drawString(margin, y, direction_title)
        y -= 5.5 * mm

        dir_text = (lucky_direction or "").strip()
        # 1行で無理なら折り返し（左列幅いっぱいで）
        # Keep some extra right padding for English to avoid clipping.
        max_w = width - 2 * margin - (6 * mm if str(lang).lower().startswith("en") else 0)
        if stringWidth(dir_text, font_name, font_size) <= max_w:
            c.drawString(margin, y, dir_text)
            y -= line_h
        else:
            # 簡易折り返し
            words = dir_text.split()
            cur = ""
            for w in words:
                candidate = (cur + " " + w).strip()
                if stringWidth(candidate, font_name, font_size) <= max_w:
                    cur = candidate
                else:
                    c.drawString(margin, y, cur)
                    y -= line_h
                    cur = w
            if cur:
                c.drawString(margin, y, cur)
                y -= line_h

    return y

def draw_palm_image(c, base64_image, width, y):
    try:
        image_data = base64.b64decode(base64_image.split(',')[1])
        img = ImageReader(io.BytesIO(image_data))
        img_width, img_height = img.getSize()

        # アスペクト比を保ちつつ、A4用紙の高さの約30%に収まるよう縮小
        max_height = 0.3 * A4[1]  # 高さ制限（A4用紙の30%）
        scale_w = (width * 0.7) / img_width  # 横幅70%を基準
        scale_h = max_height / img_height
        scale = min(scale_w, scale_h)

        img_width *= scale
        img_height *= scale

        x_center = (width - img_width) / 2
        y -= img_height + 5 * mm
        c.drawImage(img, x_center, y, width=img_width, height=img_height)
        y -= 10 * mm
    except Exception as e:
        print("Image decode error:", e)

    return y


# =========================
# 恋愛版 年運ページ（A4）
# =========================
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


def draw_shincom_a4(c, data, include_yearly=False):
    """English (shincom) A4 layout.
    Page 1: Palm image + first 3 palm sections + Lucky info
    Page 2: Remaining 2 palm sections + Overall + Personality + This/Next month
    Header is drawn ONLY on page 1.
    """
    from reportlab.lib.pagesizes import A4

    page_width, page_height = A4
    margin = 20 * mm
    y = page_height - margin

    lang = "en"
    font_name = select_font_for_lang(lang)

    # Header (page 1 only)
    y = draw_header(c, page_width, margin, y)

    # Palm image
    y = draw_palm_image(c, data, page_width, margin, y, font_name=font_name)

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

    # --- Page 1: first 3 sections ---
    for i in range(3):
        title = palm_titles[i] if i < len(palm_titles) else ""
        text = palm_texts[i] if i < len(palm_texts) else ""
        write_block(title, text)

    # Lucky info on page 1
    y = draw_lucky_section(
        c,
        page_width,
        margin,
        y,
        data.get("lucky_info", []) or [],
        data.get("lucky_direction", "") or "",
        lang=lang,
        page_height=page_height,
        font_name=font_name,
    )

    # Start page 2 (no header)
    c.showPage()
    y = page_height - margin

    # --- Page 2: remaining 2 sections ---
    for i in range(3, 5):
        title = palm_titles[i] if i < len(palm_titles) else ""
        text = palm_texts[i] if i < len(palm_texts) else ""
        write_block(title, text)

    titles = data.get("titles", {}) or {}
    texts = data.get("texts", {}) or {}

    # Overall palm summary
    write_block(titles.get("palm_summary", "Overall Palm Reading"), texts.get("palm_summary", ""))

    # Personality (Four Pillars)
    write_block(titles.get("personality", "Personality"), data.get("shichu_personality", ""))

    # This month / next month
    month_text = _normalize_month_fortune_text(data.get("shichu_month_fortune", ""), data.get("birthdate", ""), lang=lang)
    next_month_text = _normalize_next_month_fortune_text(data.get("shichu_next_month_fortune", ""), data.get("birthdate", ""), lang=lang)

    write_block(titles.get("month_fortune", "This Month"), month_text)
    write_block(titles.get("next_month_fortune", "Next Month"), next_month_text)

def draw_shincom_b4(c, data, include_yearly=False):
    """English (shincom) B4 layout.
    Page 1: Palm image + palm sections (all 5)
    Page 2: Overall + Personality + This/Next month + Lucky info
    Header is drawn ONLY on page 1.
    """
    from reportlab.lib.pagesizes import B4

    page_width, page_height = B4
    margin = 18 * mm
    y = page_height - margin

    lang = "en"
    font_name = select_font_for_lang(lang)

    # Header (page 1 only)
    y = draw_header(c, page_width, margin, y)

    # Palm image
    y = draw_palm_image(c, data, page_width, margin, y, font_name=font_name)

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
    write_block(titles.get("palm_summary", "Overall Palm Reading"), texts.get("palm_summary", ""))

    # Personality
    write_block(titles.get("personality", "Personality"), data.get("shichu_personality", ""))

    # This month / next month
    month_text = _normalize_month_fortune_text(data.get("shichu_month_fortune", ""), data.get("birthdate", ""), lang=lang)
    next_month_text = _normalize_next_month_fortune_text(data.get("shichu_next_month_fortune", ""), data.get("birthdate", ""), lang=lang)
    write_block(titles.get("month_fortune", "This Month"), month_text)
    write_block(titles.get("next_month_fortune", "Next Month"), next_month_text)

    # Lucky info at the end of page 2
    y = draw_lucky_section(
        c,
        page_width,
        margin,
        y,
        data.get("lucky_info", []) or [],
        data.get("lucky_direction", "") or "",
        lang=lang,
        page_height=page_height,
        font_name=font_name,
    )

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