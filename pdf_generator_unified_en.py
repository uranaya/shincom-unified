from reportlab.lib.pagesizes import A4, B4
from header_utils import create_qr_code
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

# --- EN helpers --------------------------------------------------------------
KYUSEI_EN = {
    '一白水星': 'One White Water',
    '二黒土星': 'Two Black Earth',
    '三碧木星': 'Three Jade Wood',
    '四緑木星': 'Four Green Wood',
    '五黄土星': 'Five Yellow Earth',
    '六白金星': 'Six White Metal',
    '七赤金星': 'Seven Red Metal',
    '八白土星': 'Eight White Earth',
    '九紫火星': 'Nine Purple Fire',
}
DIR_EN = {
    '北': 'North',
    '北東': 'Northeast',
    '東': 'East',
    '南東': 'Southeast',
    '南': 'South',
    '南西': 'Southwest',
    '西': 'West',
    '北西': 'Northwest',
}

PALM_TITLE_EN = {
    '生命線': 'Life Line',
    '運命線': 'Fate Line',
    '金運線': 'Money Line',
    '太陽線': 'Sun Line',
    '幸運線': 'Lucky Line',
}

def _maybe_translate_title(title: str, lang: str) -> str:
    if not title or not str(lang).lower().startswith('en'):
        return title
    t = str(title)
    # Keep leading symbols (■◆ etc.) and translate the rest
    for jp, en in PALM_TITLE_EN.items():
        t = t.replace(jp, en)

    # Common section headings
    t = t.replace('手相の総合アドバイス', 'Overall Palm Reading')
    t = t.replace('性格診断', 'Personality')
    t = t.replace('ラッキー情報', 'Lucky Info')
    t = t.replace('吉方位', 'Lucky Directions')
    t = t.replace('総合運', 'Overall Fortune')
    t = t.replace('運勢', 'Fortune')

    # Patterns like "2026年1月の運勢"
    t = re.sub(r'(\d{4})年(\d{1,2})月の運勢', lambda m: f"Fortune for {m.group(1)}-{int(m.group(2)):02d}", t)
    t = re.sub(r'(\d{4})年の総合運', lambda m: f"Overall fortune for {m.group(1)}", t)

    return t


def _translate_lucky_direction_text(s: str, lang: str) -> str:
    if not s or not str(lang).lower().startswith('en'):
        return s
    t = str(s)
    for jp, en in KYUSEI_EN.items():
        t = t.replace(jp, en)
    # Replace longer direction tokens first
    for jp in sorted(DIR_EN.keys(), key=len, reverse=True):
        t = t.replace(jp, DIR_EN[jp])
    t = t.replace('あなたの本命星は', 'Your main star is')
    t = t.replace('です。', '.')
    t = t.replace('今年', 'This year')
    t = t.replace('今月', 'This month')
    t = t.replace('来月', 'Next month')
    return t
# ----------------------------------------------------------------------------

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
    """Return wrapping length (character-based) for textwrap.

    English text in a proportional font tends to look too narrow if we reuse the
    Japanese wrap length. We intentionally widen it so lines use most of the page
    width and reduce the chance of bottom truncation.
    """
    if str(lang).lower().startswith('en'):
        # About ~2x of the JP wrap length (caps to avoid absurdly long lines).
        return max(base, min(120, int(base * 2.35)))
    return base

# --- English-only header (keeps Japanese version untouched by not changing header_utils.py) ---
def draw_header(c, lang='en'):
    """English header for A4/B4.

    - Generates QR dynamically via header_utils.create_qr_code().
    - Places "SCAN HERE" as a QR caption (not inside the body text).
    """
    width, height = A4

    # Header frame
    left_margin = 20 * mm
    right_margin = 20 * mm
    header_top = height - 18 * mm
    header_bottom = header_top - 45 * mm

    # Title (center)
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    c.line(left_margin, header_top, width - right_margin, header_top)

    c.setFont('Helvetica', 12)
    c.drawCentredString(width / 2, header_top - 4.5 * mm, 'Shin · Computer Fortune')

    c.setLineWidth(0.3)
    c.line(left_margin, header_top - 7.5 * mm, width - right_margin, header_top - 7.5 * mm)

    # QR (right)
    qr_size = 28 * mm
    qr_x = width - right_margin - qr_size
    caption_y = header_bottom + 3.2 * mm
    qr_y = caption_y + 4.0 * mm

    qr_path = None
    try:
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        qr_path = create_qr_code(output_dir=static_dir)
    except Exception:
        qr_path = None

    if qr_path and os.path.exists(qr_path):
        c.drawImage(qr_path, qr_x, qr_y, width=qr_size, height=qr_size,
                    preserveAspectRatio=True, mask='auto')

    c.setFont('Helvetica-Bold', 9)
    caption = 'SCAN HERE'
    cap_w = stringWidth(caption, 'Helvetica-Bold', 9)
    c.drawString(qr_x + (qr_size - cap_w) / 2, caption_y, caption)

    # Left text block (kept compact so it doesn't collide with QR)
    text_left = left_margin
    text_right = qr_x - 8 * mm
    y = header_top - 12.5 * mm

    c.setFont('Helvetica', 10)
    lines = [
        "[Supervised by Fortune Hall / Fortune Teller 'Uranaya']",
        "Your fortune can change through your actions.",
        "For a deeper reading or private concerns,",
        "we also offer in-person / phone / online sessions.",
        "More details →"
    ]

    for line in lines:
        # Trim to avoid overlapping the QR block
        if stringWidth(line, 'Helvetica', 10) > (text_right - text_left):
            # soft-wrap once if needed
            wrapped = smart_wrap(line, 60)
            for w in wrapped[:2]:
                c.drawString(text_left, y, w)
                y -= 4.4 * mm
        else:
            c.drawString(text_left, y, line)
            y -= 4.4 * mm

    c.setLineWidth(0.5)
    c.line(left_margin, header_bottom, width - right_margin, header_bottom)

    return header_bottom - 8 * mm

def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction, lang='ja', page_height=None, **kwargs):
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
    lang = _get_lang(data)
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
        for line in smart_wrap(data['palm_texts'][i], _wrap_len(40, lang), lang):
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
        for line in smart_wrap(data['palm_texts'][i], _wrap_len(40, lang), lang):
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
            for line in smart_wrap(content, _wrap_len(wrap_len, lang), lang):
                c.drawString(margin, y, line)
                y -= 6 * mm
        y -= 3 * mm
        _set_font(c, lang, 12)

    # ラッキー情報を2ページ目末尾に移動
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    if include_yearly:
        draw_yearly_pages_shincom_a4(c, data['yearly_fortunes'], lang)


def draw_shincom_b4(c, data, include_yearly=False):
    lang = _get_lang(data)
    width, height = B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)
    y = draw_palm_image(c, data["palm_image"], width, y)

    _set_font(c, lang, 14)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 7 * mm
        _set_font(c, lang, 12)
        for line in smart_wrap(data['palm_texts'][i], _wrap_len(45, lang), lang):
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
        for line in smart_wrap(data['palm_texts'][i], _wrap_len(45, lang), lang):
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
            for line in smart_wrap(content, _wrap_len(wrap_len, lang), lang):
                c.drawString(margin, y, line)
                y -= 7 * mm
        y -= 4 * mm
        _set_font(c, lang, 14)

    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    if include_yearly:
        draw_yearly_pages_shincom_b4(c, data['yearly_fortunes'], lang)


def draw_yearly_pages_shincom_a4(c, yearly, lang="ja"):
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        title = _maybe_translate_title(title, lang)
        _set_font(c, lang, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 5 * mm
        _set_font(c, lang, 10)
        for line in smart_wrap(text or "", _wrap_len(45, lang), lang):
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
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        title = _maybe_translate_title(title, lang)
        _set_font(c, lang, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm
        _set_font(c, lang, 11)
        for line in smart_wrap(text or "", _wrap_len(45, lang), lang):
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
    data.setdefault('lang', _get_lang(data))
    size = size.lower()
    c = canvas.Canvas(filepath, pagesize=A4 if size == 'a4' else B4)
    c.setTitle('Fortune Result')
    if mode == 'shincom':
        if size == 'a4':
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        draw_renai_pdf(c, data, size, include_yearly)
    c.save()