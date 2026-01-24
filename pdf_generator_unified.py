from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
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

from textwrap import wrap as _wrap

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))


def wrap(text, limit):
    return _wrap(text, limit)


def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction_text, lang: str = 'ja', page_height=None):
    """
    Lucky info block (two columns) with simple line-fitting.
    """
    lang = (lang or 'ja').lower()
    FONT_NAME = 'IPAexGothic'
    title = "■ " + _t(lang, "ラッキー情報（生年月日より）", "Lucky Info (based on birthdate)")
    c.setFont(FONT_NAME, 11)
    c.drawString(margin, y, title)
    y -= 14

    if not lucky_lines:
        c.setFont(FONT_NAME, 10)
        c.drawString(margin, y, _t(lang, "（情報なし）", "(no data)"))
        return y - 14

    font_size = 10
    leading = 12
    col_gap = 14
    usable_w = width - margin * 2
    col_w = (usable_w - col_gap) / 2.0
    max_rows = 3  # 3 rows x 2 columns

    def fit_one_line(s: str, max_w: float) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        if stringWidth(s, FONT_NAME, font_size) <= max_w:
            return s
        ell = "…"
        for cut in range(len(s), 0, -1):
            cand = s[:cut].rstrip() + ell
            if stringWidth(cand, FONT_NAME, font_size) <= max_w:
                return cand
        return ell

    c.setFont(FONT_NAME, font_size)

    lines = [str(x).strip() for x in lucky_lines if str(x).strip()]
    lines = lines[:6]
    while len(lines) < max_rows * 2:
        lines.append("")

    for r in range(max_rows):
        left = fit_one_line(lines[r], col_w)
        right = fit_one_line(lines[r + max_rows], col_w)
        if left:
            c.drawString(margin, y, "• " + left)
        if right:
            c.drawString(margin + col_w + col_gap, y, "• " + right)
        y -= leading

    if lucky_direction_text:
        y -= 2
        c.setFont(FONT_NAME, 10)
        c.drawString(margin, y, "■ " + _t(lang, "ラッキー方位", "Lucky Direction"))
        y -= 12

        txt = (lucky_direction_text or "").replace("\n", " ").strip()
        if txt:
            # two-line wrap max
            max_w = usable_w
            words = txt.split()
            cur = ""
            out = []
            for w in words:
                cand = (cur + " " + w).strip()
                if stringWidth(cand, FONT_NAME, 10) <= max_w:
                    cur = cand
                else:
                    out.append(cur)
                    cur = w
                if len(out) >= 2:
                    break
            if cur and len(out) < 2:
                out.append(cur)
            for s in out[:2]:
                c.drawString(margin, y, s)
                y -= 12

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
def draw_yearly_pages_renai_a4(c, yearly):
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

        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 5 * mm

        c.setFont(FONT_NAME, 10)
        for line in wrap(text or "", 46):
            if y < bottom:
                c.showPage()
                y = top
                c.setFont(FONT_NAME, 10)
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
def draw_yearly_pages_renai_b4(c, yearly):
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

        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm

        c.setFont(FONT_NAME, 11)
        for line in wrap(text or "", 45):
            if y < bottom:
                c.showPage()
                y = top
                c.setFont(FONT_NAME, 11)
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
    width, height = A4
    margin = 20 * mm
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
        c.setFont(FONT_NAME, 11)
        for line in info_lines:
            c.drawString(margin, y, line)
            y -= 5 * mm
        y -= 3 * mm

    # 手相3項目（1ページ目）
    c.setFont(FONT_NAME, 12)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['palm_texts'][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # 新ページ：手相残り2項目 + 鑑定結果
    c.showPage()
    y = height - margin

    c.setFont(FONT_NAME, 12)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['palm_texts'][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # 四柱推命・まとめ等（タイトルのみでも出す）
    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 36 if 'month' in key else 40
        title = data['titles'].get(key, "")
        content = data['texts'].get(key, "")

        if title:
            c.drawString(margin, y, f"◆ {title}")
            y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        if content:
            for line in wrap(content, wrap_len):
                c.drawString(margin, y, line)
                y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # ラッキー情報を2ページ目末尾に移動
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''), lang=_get_lang(data))

    if include_yearly:
        draw_yearly_pages_shincom_a4(c, data['yearly_fortunes'])


def draw_shincom_b4(c, data, include_yearly=False):
    width, height = B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)
    y = draw_palm_image(c, data["palm_image"], width, y)

    c.setFont(FONT_NAME, 14)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 7 * mm
        c.setFont(FONT_NAME, 12)
        for line in wrap(data['palm_texts'][i], 45):
            c.drawString(margin, y, line)
            y -= 7 * mm
        y -= 4 * mm
        c.setFont(FONT_NAME, 14)

    c.showPage()
    y = height - margin
    c.setFont(FONT_NAME, 14)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 7 * mm
        c.setFont(FONT_NAME, 12)
        for line in wrap(data['palm_texts'][i], 45):
            c.drawString(margin, y, line)
            y -= 7 * mm
        y -= 4 * mm
        c.setFont(FONT_NAME, 14)

    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:

        wrap_len = 40 if 'month' in key else 45
        title = data['titles'].get(key, "")
        content = data['texts'].get(key, "")
        if title:
            c.drawString(margin, y, f"◆ {title}")
            y -= 7 * mm
        c.setFont(FONT_NAME, 12)
        if content:
            for line in wrap(content, wrap_len):
                c.drawString(margin, y, line)
                y -= 7 * mm
        y -= 4 * mm
        c.setFont(FONT_NAME, 14)

    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''), lang=_get_lang(data))

    if include_yearly:
        draw_yearly_pages_shincom_b4(c, data['yearly_fortunes'])


def draw_yearly_pages_shincom_a4(c, yearly):
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 5 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(text or "", 45):
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 10)
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


def draw_yearly_pages_shincom_b4(c, yearly):
    width, height = B4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(text or "", 45):
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 11)
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
    from reportlab.lib.pagesizes import A4, B4
    from reportlab.lib.units import mm
    from header_utils import draw_header
    from pdf_generator_unified import draw_yearly_pages_renai_a4, draw_yearly_pages_renai_b4, draw_lucky_section, FONT_NAME
    from textwrap import wrap as wrap_text

    def wrap(text, limit):
        lines = []
        for line in text.splitlines():
            lines.extend(wrap_text(line, limit))
        return lines

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
    c.setFont(FONT_NAME, 12)
    for key in main_keys:
        if key in data.get("texts", {}) and data["texts"][key].strip():
            c.drawString(margin, y, f"◆ {data['titles'].get(key, key)}")
            y -= 6 * mm
            c.setFont(FONT_NAME, 10)
            for line in wrap(data["texts"][key], wrap_len):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 4 * mm
            c.setFont(FONT_NAME, 12)

    c.showPage()
    y = height - margin

    # 2ページ目：恋愛テーマ3項目（注意点・距離感・結婚）
    if data.get("themes"):
        c.setFont(FONT_NAME, 12)
        for section in data["themes"]:
            c.drawString(margin, y, f"◆ {section['title']}")
            y -= 6 * mm
            c.setFont(FONT_NAME, 10)
            for line in wrap(section["content"], wrap_len):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 4 * mm
            c.setFont(FONT_NAME, 12)

    # ラッキー情報・吉方位（2ページ目末尾）
    y = draw_lucky_section(c, width, margin, y, data.get('lucky_info', []), data.get('lucky_direction', ''), lang=_get_lang(data))

    # 年運（オプション）
    if include_yearly and data.get("yearly_love_fortunes"):
        if size == "a4":
            draw_yearly_pages_renai_a4(c, data["yearly_love_fortunes"])
        else:
            draw_yearly_pages_renai_b4(c, data["yearly_love_fortunes"])


def create_pdf_unified(filepath, data, mode, size='a4', include_yearly=False):
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