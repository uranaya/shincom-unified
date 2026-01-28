from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
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



def is_en(lang: str | None) -> bool:
    """Return True if language code indicates English."""
    return str(lang or "").strip().lower().startswith("en")

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


def wrap_text_by_width(text: str, font_name: str, font_size: int, max_w: float):
    """Word-wrap by actual rendered width (ReportLab stringWidth). Best for English."""
    if not text:
        return []
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []

    for para in text.split("\n"):
        para = para.strip()
        if not para:
            out.append("")
            continue

        words = [w for w in para.split(" ") if w != ""]
        line = ""
        for w in words:
            cand = (line + " " + w).strip() if line else w
            if stringWidth(cand, font_name, font_size) <= max_w:
                line = cand
                continue

            if line:
                out.append(line)
                line = w
            else:
                line = w

            # hard-wrap a single too-long token
            while stringWidth(line, font_name, font_size) > max_w and len(line) > 1:
                lo, hi = 1, len(line)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if stringWidth(line[:mid], font_name, font_size) <= max_w:
                        lo = mid + 1
                    else:
                        hi = mid
                cut = max(1, lo - 1)
                out.append(line[:cut])
                line = line[cut:].lstrip()

        if line:
            out.append(line)

    return out

def wrap_lines(text: str, lang: str, font_name: str, font_size: int, max_w: float, base_chars: int):
    """JA: char-wrap (existing). EN: width-wrap (fills page and avoids early breaks)."""
    if is_en(lang):
        return wrap_text_by_width(text, font_name, font_size, max_w)
    return smart_wrap(text, base_chars, lang=lang)
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
    # Keep Japanese conservative; give English more horizontal capacity.
    if str(lang).lower().startswith("en"):
        return max(base + 18, int(base * 1.5))
    return base



def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction, lang='ja', page_height=None, **kwargs):
    font_name = _font(lang)
    font_size = 10 if not is_en(lang) else 11
    leading = 13 if not is_en(lang) else 14
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

    def _fit_one_line(s: str, max_w: float) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        # 収まるならそのまま
        if stringWidth(s, font_name, font_size) <= max_w:
            return s
        # 末尾省略
        ell = "…"
        while s and stringWidth(s + ell, FONT_NAME, 10) > max_w:
            s = s[:-1]
        return (s + ell) if s else ell

    # 2つずつ（左・右）描画。奇数なら右は空。
    for i in range(0, len(lucky_lines), 2):
        left = _fit_one_line(lucky_lines[i], col_w, font_name, font_size)
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
        max_w = width - 2 * margin
        if stringWidth(dir_text, FONT_NAME, 10) <= max_w:
            c.drawString(margin, y, dir_text)
            y -= line_h
        else:
            # 簡易折り返し
            words = dir_text.split()
            cur = ""
            for w in words:
                candidate = (cur + " " + w).strip()
                if stringWidth(candidate, FONT_NAME, 10) <= max_w:
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


# ======================
# Fonts / Language helpers
# ======================

# Font names used in this project
FONT_NAME_JA = "IPAexGothic"
FONT_NAME_EN = "Times-Roman"

def is_en(lang) -> bool:
    """Return True if language is English-like."""
    return str(lang or "").lower().startswith("en")

def _font(lang) -> str:
    return FONT_NAME_EN if is_en(lang) else FONT_NAME_JA

def _set_font(c, lang, size: int):
    c.setFont(_font(lang), size)

# ======================
# Wrapping utilities (robust)
# ======================

def wrap_text_by_width(text: str, font_name: str, font_size: int, max_w: float):
    """Word-wrap by actual rendered width. Falls back if max_w is suspiciously small."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return [""]
    # Safety: if someone accidentally passes a tiny width for EN, expand it.
    if max_w is None:
        max_w = 500
    if max_w < 200:  # too small for A4 text blocks; likely a bug upstream
        max_w = 500

    lines = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            test = cur + " " + w
            if stringWidth(test, font_name, font_size) <= max_w:
                cur = test
            else:
                lines.append(cur)
                cur = w
        # If a single 'word' is wider than max_w, hard-wrap it.
        while stringWidth(cur, font_name, font_size) > max_w and len(cur) > 1:
            # take as many chars as fit
            acc = ""
            for ch in cur:
                if stringWidth(acc + ch, font_name, font_size) <= max_w:
                    acc += ch
                else:
                    break
            if acc:
                lines.append(acc)
                cur = cur[len(acc):].lstrip()
            else:
                break
        lines.append(cur)
    return lines

def smart_wrap(text: str, max_chars: int = 40):
    """Simple char-based wrap for Japanese."""
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for para in s.split("\n"):
        para = para.strip()
        if not para:
            out.append("")
            continue
        while len(para) > max_chars:
            out.append(para[:max_chars])
            para = para[max_chars:]
        out.append(para)
    return out

def _wrap_len(base: int, lang) -> int:
    # Japanese: keep strict, English: allow longer lines (use width-based wrap anyway)
    if is_en(lang):
        return max(int(base * 1.8), base + 28)
    return base

def wrap_lines(text: str, lang, font_name: str, font_size: int, max_width: float, base_chars: int):
    """Unified wrapper: EN uses width wrap, JA uses char wrap."""
    if is_en(lang):
        return wrap_text_by_width(text, font_name, font_size, max_width)
    return smart_wrap(text, max_chars=base_chars)

# ======================
# Header (page 1 only)
# ======================

def draw_header(c, page_width, margin, y):
    """Draw the standard header lines & QR placeholder area. Returns new y."""
    # Keep it conservative: do not break existing JP layout.
    c.setLineWidth(0.5)
    c.line(margin, y, page_width - margin, y)
    y -= 12
    c.setFont(FONT_NAME_JA, 12)
    c.drawCentredString(page_width/2, y, "シン・コンピューター占い")
    y -= 16
    c.setFont(FONT_NAME_JA, 10)
    c.drawString(margin, y, "【占いの館・占い師『うらなや』監修】")
    y -= 14
    return y

# ======================
# Lucky section (shared)
# ======================

def draw_lucky_section(c, page_width, margin, y, lucky_info: str, lucky_direction: str = "", lang="ja"):
    """Draw lucky info (2 columns) + optional direction line. Returns new y."""
    font_name = _font(lang)
    # Title
    _set_font(c, lang, 12)
    c.drawString(margin, y, "■ Lucky Information" if is_en(lang) else "■ ラッキー情報")
    y -= 16

    # Compose lines (keep order stable)
    def _as_text(v):
        if v is None:
            return ""
        # Some generators return list[str] for lucky_info; normalize to a single string.
        if isinstance(v, list):
            return "\n".join(str(x) for x in v if str(x).strip())
        if isinstance(v, tuple):
            return "\n".join(str(x) for x in v if str(x).strip())
        if isinstance(v, dict):
            # Keep deterministic order for common keys if present; fallback to values.
            keys = [k for k in ["title","text","body","content","info"] if k in v] or list(v.keys())
            return "\n".join(str(v[k]) for k in keys if str(v[k]).strip())
        return str(v)

    info = _as_text(lucky_info).strip()
    dir_txt = _as_text(lucky_direction).strip()
    lines = []
    if dir_txt:
        lines.append(("Lucky direction: " + dir_txt) if is_en(lang) else ("ラッキー方位：" + dir_txt))
    if info:
        # Split into reasonable units for 2 columns: prefer newlines, else ' / '
        chunks = []
        if "\n" in info:
            chunks = [t.strip() for t in info.split("\n") if t.strip()]
        elif " / " in info:
            chunks = [t.strip() for t in info.split("/") if t.strip()]
        else:
            chunks = [info]
        lines.extend(chunks)

    if not lines:
        _set_font(c, lang, 10)
        c.drawString(margin, y, "(no data)" if is_en(lang) else "（データなし）")
        return y - 14

    usable_w = page_width - 2 * margin
    col_w = (usable_w - 14) / 2  # gutter 14pt
    col1_x = margin
    col2_x = margin + col_w + 14

    def fit_one_line(s: str, max_w: float) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        if stringWidth(s, font_name, 10) <= max_w:
            return s
        ell = "..." if is_en(lang) else "…"
        # Trim until fits
        while s and stringWidth(s + ell, font_name, 10) > max_w:
            s = s[:-1]
        return s + ell if s else ell

    _set_font(c, lang, 10)
    i = 0
    while i < len(lines):
        left = fit_one_line(lines[i], col_w)
        right = fit_one_line(lines[i + 1], col_w) if i + 1 < len(lines) else ""
        c.drawString(col1_x, y, left)
        if right:
            c.drawString(col2_x, y, right)
        y -= 14
        i += 2

    return y - 4

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
    margin = (14 * mm) if is_en(lang) else (20 * mm)
    body_size = 11 if is_en(lang) else 10
    body_leading = 14 if is_en(lang) else 13
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
        for line in wrap_lines(text or "", lang, _font(lang), 10, width - 2*margin, _wrap_len(46, lang)):
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
    margin = (14 * mm) if is_en(lang) else (20 * mm)
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
        for line in wrap_lines(text or "", lang, _font(lang), 10, width - 2*margin, _wrap_len(45, lang)):
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
    lang = _get_lang(data)
    width, height = A4
    margin = (14 * mm) if is_en(lang) else (20 * mm)
    y = height - margin
    y = draw_header(c, width, margin, y)
    y = draw_palm_image(c, data["palm_image"], width, y)

    # 生年月日・星座・干支・動物占い・本命星（手相画像の直下に表示）
    birthdate = data.get("birthdate")
    zodiac = data.get("zodiac")
    eto = data.get("eto")
    eto_number = data.get("eto_number")
    animal = data.get("animal")
    honmeisei = data.get("honmeisei")

    info_lines = []

    # 1行目：生年月日＋星座
    line1_parts = []
    if birthdate:
        line1_parts.append(f"生年月日：{birthdate}")
    if zodiac:
        line1_parts.append(f"星座：{zodiac}")
    if line1_parts:
        info_lines.append(" / ".join(line1_parts))

    # 2行目：干支番号＋動物占い＋本命星
    line2_parts = []
    if eto:
        if eto_number:
            line2_parts.append(f"干支：{eto}（{eto_number}番）")
        else:
            line2_parts.append(f"干支：{eto}")
    if animal:
        line2_parts.append(f"動物占い：{animal}")
    if honmeisei:
        line2_parts.append(f"本命星：{honmeisei}")
    if line2_parts:
        info_lines.append(" / ".join(line2_parts))

    if info_lines:
        _set_font(c, lang, 11)
        for line in info_lines:
            c.drawString(margin, y, line)
            y -= 5 * mm
        y -= 3 * mm

    # 手相3項目（1ページ目）
    _set_font(c, lang, 12)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        _set_font(c, lang, 10)
        for line in wrap_lines(data['palm_texts'][i], lang, _font(lang), body_size, width - 2*margin, _wrap_len(60, lang) if is_en(lang) else _wrap_len(40, lang)):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        _set_font(c, lang, 12)

    # 新ページ：手相残り2項目 + 鑑定結果
    c.showPage()
    y = height - margin

    _set_font(c, lang, 12)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        _set_font(c, lang, 10)
        for line in wrap_lines(data['palm_texts'][i], lang, _font(lang), body_size, width - 2*margin, _wrap_len(60, lang) if is_en(lang) else _wrap_len(40, lang)):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        _set_font(c, lang, 12)

    # 四柱推命・まとめ等（タイトルのみでも出す）
    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 36 if 'month' in key else 40
        title = data['titles'].get(key, "")
        content = data['texts'].get(key, "")

        if title:
            c.drawString(margin, y, f"◆ {title}")
            y -= 6 * mm
        _set_font(c, lang, 10)
        if content:
            for line in wrap_lines(content, lang, _font(lang), 10, width - 2*margin, _wrap_len(wrap_len, lang)):
                c.drawString(margin, y, line)
                y -= 6 * mm
        y -= 3 * mm
        _set_font(c, lang, 12)

    # ラッキー情報を2ページ目末尾に移動
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''), lang=lang)

    if include_yearly:
        draw_yearly_pages_shincom_a4(c, data['yearly_fortunes'], lang)


def draw_shincom_b4(c, data, include_yearly=False):
    lang = _get_lang(data)
    width, height = B4
    margin = (14 * mm) if is_en(lang) else (20 * mm)
    y = height - margin
    y = draw_header(c, width, margin, y)
    y = draw_palm_image(c, data["palm_image"], width, y)

    _set_font(c, lang, 14)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 7 * mm
        _set_font(c, lang, 12)
        for line in wrap_lines(data['palm_texts'][i], lang, _font(lang), 10, width - 2*margin, _wrap_len(45, lang)):
            c.drawString(margin, y, line)
            y -= 7 * mm
        y -= 4 * mm
        _set_font(c, lang, 14)

    c.showPage()
    y = height - margin
    _set_font(c, lang, 14)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 7 * mm
        _set_font(c, lang, 12)
        for line in wrap_lines(data['palm_texts'][i], lang, _font(lang), 10, width - 2*margin, _wrap_len(45, lang)):
            c.drawString(margin, y, line)
            y -= 7 * mm
        y -= 4 * mm
        _set_font(c, lang, 14)

    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:

        wrap_len = 40 if 'month' in key else 45
        title = data['titles'].get(key, "")
        content = data['texts'].get(key, "")
        if title:
            c.drawString(margin, y, f"◆ {title}")
            y -= 7 * mm
        _set_font(c, lang, 12)
        if content:
            for line in wrap_lines(content, lang, _font(lang), 10, width - 2*margin, _wrap_len(wrap_len, lang)):
                c.drawString(margin, y, line)
                y -= 7 * mm
        y -= 4 * mm
        _set_font(c, lang, 14)

    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''), lang=lang)

    if include_yearly:
        draw_yearly_pages_shincom_b4(c, data['yearly_fortunes'], lang)


def draw_yearly_pages_shincom_a4(c, yearly, lang="ja"):
    width, height = A4
    margin = (14 * mm) if is_en(lang) else (20 * mm)
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        _set_font(c, lang, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 5 * mm
        _set_font(c, lang, 10)
        for line in wrap_lines(text or "", lang, _font(lang), 10, width - 2*margin, _wrap_len(45, lang)):
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                _set_font(c, lang, 10)
            c.drawString(margin, y, line)
            y -= 5 * mm
        y -= 3 * mm

    c.showPage()
    y = height - 30 * mm
    draw_text_block(yearly["year_label"], yearly["year_text"])
    for month in yearly["months"][:6]:
        draw_text_block(month["label"], month["text"])
    c.showPage()
    y = height - 30 * mm
    for month in yearly["months"][6:]:
        draw_text_block(month["label"], month["text"])


def draw_yearly_pages_shincom_b4(c, yearly, lang="ja"):
    width, height = B4
    margin = (14 * mm) if is_en(lang) else (20 * mm)
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        _set_font(c, lang, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm
        _set_font(c, lang, 11)
        for line in wrap_lines(text or "", lang, _font(lang), 10, width - 2*margin, _wrap_len(45, lang)):
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                _set_font(c, lang, 11)
            c.drawString(margin, y, line)
            y -= 7 * mm
        y -= 6 * mm

    c.showPage()
    y = height - 30 * mm
    draw_text_block(yearly["year_label"], yearly["year_text"])
    for month in yearly["months"][:6]:
        draw_text_block(month["label"], month["text"])
    c.showPage()
    y = height - 30 * mm
    for month in yearly["months"][6:]:
        draw_text_block(month["label"], month["text"])


def draw_renai_pdf(c, data, size, include_yearly=False):
    lang = _get_lang(data)
    from reportlab.lib.pagesizes import A4, B4
    from reportlab.lib.units import mm
    from header_utils import draw_header
    from pdf_generator_unified import draw_yearly_pages_renai_a4, draw_yearly_pages_renai_b4, draw_lucky_section, FONT_NAME

    width, height = A4 if size == 'a4' else B4
    margin = (14 * mm) if is_en(lang) else (20 * mm)
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
            for line in wrap_lines(data["texts"][key], lang, _font(lang), 10, width - 2*margin, _wrap_len(wrap_len, lang)):
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
            for line in wrap_lines(section["content"], lang, _font(lang), 10, width - 2*margin, _wrap_len(wrap_len, lang)):
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
# HOTFIX (2026-01-28): stabilize lucky_info types + body_size
# - lucky_info may be list[str] or str depending on generator
# - draw_shincom_a4 used body_size without defining it
# These re-definitions override earlier buggy versions.
# ============================================================

def _normalize_lucky_lines(lucky_info):
    """Return list[str] lines for lucky_info (accepts str/list/tuple/None)."""
    if lucky_info is None:
        return []
    # Already list/tuple of lines
    if isinstance(lucky_info, (list, tuple)):
        out = []
        for x in lucky_info:
            if x is None:
                continue
            out.append(str(x).strip())
        return [s for s in out if s]
    # Dict -> pretty JSON-ish lines
    if isinstance(lucky_info, dict):
        out = []
        for k, v in lucky_info.items():
            s = f"{k}: {v}"
            s = str(s).strip()
            if s:
                out.append(s)
        return out
    # Fallback: treat as text blob
    s = str(lucky_info)
    # Normalize newlines
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in s.split("\n")]
    return [ln for ln in lines if ln]

def draw_lucky_section(c, page_width, margin, y, lucky_info, lucky_direction: str = "", lang="ja"):
    """Draw lucky info (2 columns) + optional direction line. Returns new y."""
    font_name = _font(lang)
    title_size = 11 if is_en(lang) else 12
    body_size = 10 if is_en(lang) else 10

    # Title
    c.setFont(font_name, title_size)
    c.drawString(margin, y, "Lucky Information" if is_en(lang) else "ラッキー情報")
    y -= (title_size + 4)

    # Direction (optional)
    if lucky_direction:
        c.setFont(font_name, body_size)
        for line in wrap_lines(str(lucky_direction), lang, font_name, body_size, page_width - 2*margin, _wrap_len(60, lang) if is_en(lang) else _wrap_len(40, lang)):
            c.drawString(margin, y, line)
            y -= (body_size + 2)
        y -= 4

    lines = _normalize_lucky_lines(lucky_info)
    if not lines:
        return y

    col_gap = 14
    col_w = (page_width - 2*margin - col_gap) / 2
    left_x = margin
    right_x = margin + col_w + col_gap

    # Two-column flow
    c.setFont(font_name, body_size)
    left_y = y
    right_y = y
    use_left = True

    for raw in lines:
        # Wrap each logical line to fit in a column
        wrapped = wrap_lines(raw, lang, font_name, body_size, col_w, _wrap_len(60, lang) if is_en(lang) else _wrap_len(40, lang))
        for wline in wrapped:
            if use_left:
                c.drawString(left_x, left_y, wline)
                left_y -= (body_size + 2)
            else:
                c.drawString(right_x, right_y, wline)
                right_y -= (body_size + 2)
        # Alternate columns by paragraph
        use_left = not use_left

    # Continue from the lower column
    y = min(left_y, right_y) - 6
    return y

def draw_shincom_a4(c, data, include_yearly=False):
    """A4: 1P (3 palm items + lucky), 2P (2 palm + overall + shichu + month/next) (+ yearly pages)."""
    # Keep layout consistent with existing implementation, but fix body_size and lucky_info types.
    lang = data.get("lang", "ja")
    width, height = A4
    margin = 38
    title_size = 12 if is_en(lang) else 13
    body_size = 10  # <-- FIX: define

    # Page 1 header only
    draw_header(c, width, height, data.get("title", ""), lang=lang)

    # Palm image
    y = height - 90
    img_path = data.get("palm_image_path") or data.get("palm_image") or data.get("image_path")
    if img_path:
        try:
            c.drawImage(img_path, margin, y-220, width=240, height=220, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Palm texts (first 3)
    x_text = margin + 260
    y_text = height - 110
    c.setFont(_font(lang), title_size)
    c.drawString(x_text, y_text, "Palm Reading" if is_en(lang) else "手相鑑定")
    y_text -= 18

    for i in range(min(3, len(data.get("palm_titles", [])))):
        title = data.get("palm_titles", ["", "", ""])[i]
        textv = data.get("palm_texts", ["", "", ""])[i]
        c.setFont(_font(lang), 11)
        c.drawString(x_text, y_text, str(title))
        y_text -= 14
        c.setFont(_font(lang), body_size)
        for line in wrap_lines(str(textv), lang, _font(lang), body_size, width - x_text - margin, _wrap_len(60, lang) if is_en(lang) else _wrap_len(40, lang)):
            c.drawString(x_text, y_text, line)
            y_text -= (body_size + 2)
        y_text -= 8

    # Lucky section (page 1 bottom)
    y = 210
    y = draw_lucky_section(c, width, margin, y, data.get("lucky_info"), data.get("lucky_direction", ""), lang=lang)

    c.showPage()

    # Page 2 (no header per spec)
    y = height - 60

    # Remaining palm (2 items)
    c.setFont(_font(lang), title_size)
    c.drawString(margin, y, "Palm Reading (continued)" if is_en(lang) else "手相鑑定（続き）")
    y -= 18

    for i in range(3, min(5, len(data.get("palm_titles", [])))):
        title = data.get("palm_titles", ["", "", "", "", ""])[i]
        textv = data.get("palm_texts", ["", "", "", "", ""])[i]
        c.setFont(_font(lang), 11)
        c.drawString(margin, y, str(title))
        y -= 14
        c.setFont(_font(lang), body_size)
        for line in wrap_lines(str(textv), lang, _font(lang), body_size, width - 2*margin, _wrap_len(60, lang) if is_en(lang) else _wrap_len(40, lang)):
            c.drawString(margin, y, line)
            y -= (body_size + 2)
        y -= 8

    # Palm overall
    if data.get("palm_overall"):
        c.setFont(_font(lang), 11)
        c.drawString(margin, y, "Overall" if is_en(lang) else "手相総合")
        y -= 14
        c.setFont(_font(lang), body_size)
        for line in wrap_lines(str(data.get("palm_overall")), lang, _font(lang), body_size, width - 2*margin, _wrap_len(60, lang) if is_en(lang) else _wrap_len(40, lang)):
            c.drawString(margin, y, line)
            y -= (body_size + 2)
        y -= 10

    # Shichu personality
    if data.get("shichu_personality"):
        c.setFont(_font(lang), 11)
        c.drawString(margin, y, "Personality" if is_en(lang) else "性格診断")
        y -= 14
        c.setFont(_font(lang), body_size)
        for line in wrap_lines(str(data.get("shichu_personality")), lang, _font(lang), body_size, width - 2*margin, _wrap_len(70, lang) if is_en(lang) else _wrap_len(40, lang)):
            c.drawString(margin, y, line)
            y -= (body_size + 2)
        y -= 10

    # Month fortunes
    for key, label_en, label_ja in [
        ("month_fortune", "This month", "今月の運勢"),
        ("next_month_fortune", "Next month", "来月の運勢"),
    ]:
        if data.get(key):
            c.setFont(_font(lang), 11)
            c.drawString(margin, y, label_en if is_en(lang) else label_ja)
            y -= 14
            c.setFont(_font(lang), body_size)
            for line in wrap_lines(str(data.get(key)), lang, _font(lang), body_size, width - 2*margin, _wrap_len(70, lang) if is_en(lang) else _wrap_len(40, lang)):
                c.drawString(margin, y, line)
                y -= (body_size + 2)
            y -= 10

    # Yearly pages (delegated to existing helpers if present)
    if include_yearly and data.get("yearly_fortunes") and "draw_yearly_pages_shincom_a4" in globals():
        c.showPage()
        try:
            draw_yearly_pages_shincom_a4(c, data, lang=lang)
        except Exception:
            pass
