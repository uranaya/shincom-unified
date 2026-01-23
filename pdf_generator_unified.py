from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from textwrap import wrap
import base64
import io
import os
from datetime import datetime
import re

def _t(lang: str, ja: str, en: str) -> str:
    return en if lang == 'en' else ja

def _get_lang(data: dict) -> str:
    if not isinstance(data, dict):
        return 'ja'
    lang = (data.get('lang') or data.get('output_lang') or data.get('language') or 'ja')
    lang = (lang or 'ja').strip().lower()
    return 'en' if lang.startswith('en') else 'ja'


def _normalize_month_fortune_text(text: str, kind: str, lang: str = 'ja') -> str:
    """Normalize month-fortune body text so it doesn't repeat the month already shown in the heading.

    - JA: remove leading 'YYYY年M月は' and add a gentle '今月は/来月は' prefix if missing.
    - EN: keep it concise and avoid redundant leading month phrases; add 'This month/Next month' if missing.
    kind: 'month' or 'next'
    """
    if not isinstance(text, str):
        return text
    s = (text or '').strip()

    # Remove Japanese leading date phrases like '2026年1月は、'
    s = re.sub(r'^\s*\d{4}年\s*\d{1,2}月\s*は\s*[、,]?\s*', '', s)

    if lang == 'en':
        # Remove simple English leading month phrases like 'In Jan 2026,' or 'January 2026:'
        s = re.sub(r'^\s*(in\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}\s*[:,-]?\s*',
                   '', s, flags=re.IGNORECASE)
        prefix = 'This month' if kind == 'month' else 'Next month'
        if re.match(r'^(this\s+month|next\s+month)\b', s, flags=re.IGNORECASE):
            return s
        return f"{prefix}: {s}" if s else f"{prefix}."

    # JA
    prefix = '今月は' if kind == 'month' else '来月は'
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


def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction, lang: str = 'ja'):
    # lang は result_data['lang']（'ja' / 'en'）を想定。未指定時は日本語。
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "■ " + _t(lang, "ラッキー情報（生年月日より）", "Lucky Info (based on birthdate)"))
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)

    # 2項目ずつ改行する形式（最大3行）
    for i in range(0, len(lucky_lines), 2):
        line1 = lucky_lines[i]
        line2 = lucky_lines[i + 1] if i + 1 < len(lucky_lines) else ""
        formatted = f"{line1:<38}    {line2}"
        c.drawString(margin, y, formatted)
        y -= 6 * mm

    if lucky_direction:
        y -= 2 * mm
        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, "■ " + _t(lang, "吉方位（九星気学より）", "Lucky Directions (Kyusei Kigaku)"))
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in lucky_direction.strip().splitlines():
            c.drawString(margin, y, line.strip())
            y -= 6 * mm

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
    lang = _get_lang(data)
    width, height = A4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y, lang=lang)
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
        line1_parts.append(f"{_t(lang, '生年月日', 'Birthdate')}：{birthdate}")
    if zodiac:
        line1_parts.append(f"{_t(lang, '星座', 'Zodiac')}：{zodiac}")
    if line1_parts:
        info_lines.append(" / ".join(line1_parts))

    # 2行目：干支番号＋動物占い＋本命星
    line2_parts = []
    if eto:
        if eto_number:
            line2_parts.append(f"{_t(lang, '干支', 'Zodiac (JPN)')}：{eto} ({eto_number})")
        else:
            line2_parts.append(f"{_t(lang, '干支', 'Zodiac (JPN)')}：{eto}")
    if animal:
        line2_parts.append(f"{_t(lang, '動物占い', 'Animal')}：{animal}")
    if honmeisei:
        line2_parts.append(f"{_t(lang, '本命星', 'Main Star')}：{honmeisei}")
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

        # Normalize month/next-month body to avoid duplicated date phrases
        if key in ('month_fortune', 'next_month_fortune'):
            kind = 'month' if key == 'month_fortune' else 'next'
            content = _normalize_month_fortune_text(content, kind, lang)
            if lang == 'en':
                wrap_len += 6

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
    lang = _get_lang(data)
    width, height = B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y, lang=lang)
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

        # Normalize month/next-month body to avoid duplicated date phrases
        if key in ('month_fortune', 'next_month_fortune'):
            kind = 'month' if key == 'month_fortune' else 'next'
            content = _normalize_month_fortune_text(content, kind, lang)
            if lang == 'en':
                wrap_len += 6
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
    lang = _get_lang(data)
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
    y = draw_header(c, width, margin, height - margin, lang=lang)

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
    y = draw_lucky_section(
        c, width, margin, y,
        data.get("lucky_info", []),
        data.get("lucky_direction", ""),
        lang=_get_lang(data)
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
    c.setTitle(_t(_get_lang(data), '占い結果', 'Fortune Result'))
    if mode == 'shincom':
        if size == 'a4':
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        draw_renai_pdf(c, data, size, include_yearly)
    c.save()
