from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from textwrap import wrap
import base64
import io
import os
from datetime import datetime
import re

def _t(lang: str, ja: str, en: str) -> str:
    return en if (lang or 'ja') == 'en' else ja

def _get_lang(data: dict) -> str:
    if not isinstance(data, dict):
        return 'ja'
    lang = (data.get('lang') or data.get('output_lang') or data.get('language') or 'ja')
    lang = (lang or 'ja').strip().lower()
    return 'en' if lang.startswith('en') else 'ja'
from textwrap import wrap
import base64
import io
import os
from datetime import datetime
import re

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


from header_utils import draw_header
from lucky_utils import draw_lucky_section

from textwrap import wrap as _wrap

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))


def wrap(text, limit):
    return _wrap(text, limit)


def draw_lucky_section(c, width, y, lucky_lines, lucky_direction=None, font_name="Helvetica", font_size=11, lang="ja"):
    """Draw lucky info + lucky direction in 2 columns. Lang-aware."""
    import re as _re

    col_gap = 20
    col_width = (width - 2*40 - col_gap) / 2
    x_left = 40
    x_right = x_left + col_width + col_gap

    is_en = (lang or "ja").lower().startswith("en")

    if is_en:
        title_info = "■ Lucky Info"
        title_dir = "■ Lucky Direction"
        label_map = {
            "アイテム": "Item", "カラー": "Color", "ナンバー": "Number", "フード": "Food", "デー": "Day",
            "Item": "Item", "Color": "Color", "Number": "Number", "Food": "Food", "Day": "Day",
        }
        desired = ["Item", "Color", "Number", "Food", "Day"]
    else:
        title_info = "■ ラッキー情報（生年月日より）"
        title_dir = "■ ラッキー方位"
        label_map = {"アイテム":"アイテム","カラー":"カラー","ナンバー":"ナンバー","フード":"フード","デー":"デー"}
        desired = ["アイテム", "カラー", "ナンバー", "フード", "デー"]

    c.setFont(font_name, font_size)
    c.drawString(x_left, y, title_info)
    y -= 14

    items = []
    for line in (lucky_lines or []):
        s = (line or "").strip()
        if not s:
            continue
        s = _re.sub(r"^[◆■・\-]+\s*", "", s)
        if "：" in s:
            k, v = s.split("：", 1)
        elif ":" in s:
            k, v = s.split(":", 1)
        else:
            continue
        k = label_map.get(k.strip(), k.strip())
        v = v.strip()
        items.append((k, v))

    items_sorted = []
    for dk in desired:
        for k, v in items:
            if k == dk and (k, v) not in items_sorted:
                items_sorted.append((k, v))
    for k, v in items:
        if (k, v) not in items_sorted:
            items_sorted.append((k, v))

    left_items = items_sorted[:3]
    right_items = items_sorted[3:]

    def draw_items(x, yy, pairs):
        for k, v in pairs:
            c.drawString(x, yy, f"◆ {k}: {v}")
            yy -= 14
        return yy

    y_left_end = draw_items(x_left, y, left_items)
    y_right_end = draw_items(x_right, y, right_items)
    y = min(y_left_end, y_right_end) - 8

    c.drawString(x_left, y, title_dir)
    y -= 14

    if lucky_direction:
        if is_en:
            max_w = width - 80
            for ln in wrap_en_by_width(str(lucky_direction), font_name, font_size, max_w, c):
                c.drawString(x_left, y, ln)
                y -= 14
        else:
            for ln in wrap(str(lucky_direction), 45):
                c.drawString(x_left, y, ln)
                y -= 14

    return y - 10

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