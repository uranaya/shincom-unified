# -*- coding: utf-8 -*-
# NOTE: This is the JAPANESE PDF generator.
#       English output uses pdf_generator_unified_en.py.
from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
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
    return 'en' if lang.startswith('en') else ('zh' if lang.startswith('zh') else ('ko' if (lang.startswith('ko') or lang.startswith('kr')) else 'ja'))

# ----------------------------
# Korean label mapping helpers
# ----------------------------
# In KO mode we want key labels (zodiac / 九星) to appear in Korean.
# These helpers are intentionally defensive: if the input is already Korean
# or unknown, we return it unchanged.

_KO_ZODIAC_MAP = {
    '牡羊座': '양자리',
    '牡牛座': '황소자리',
    '双子座': '쌍둥이자리',
    '蟹座': '게자리',
    '獅子座': '사자자리',
    '乙女座': '처녀자리',
    '天秤座': '천칭자리',
    '蠍座': '전갈자리',
    '射手座': '사수자리',
    '山羊座': '염소자리',
    '水瓶座': '물병자리',
    '魚座': '물고기자리',
}

_KO_KYUSEI_MAP = {
    '一白水星': '일백수성',
    '二黒土星': '이흑토성',
    '三碧木星': '삼벽목성',
    '四緑木星': '사록목성',
    '五黄土星': '오황토성',
    '六白金星': '육백금성',
    '七赤金星': '칠적금성',
    '八白土星': '팔백토성',
    '九紫火星': '구자화성',
}


def _ko_map_zodiac(z: str) -> str:
    if not z:
        return z
    s = str(z).strip()
    return _KO_ZODIAC_MAP.get(s, s)


def _ko_map_star(star: str) -> str:
    if not star:
        return star
    s = str(star).strip()
    return _KO_KYUSEI_MAP.get(s, s)
import base64
import io
import os
from datetime import datetime
import re
import textwrap


def smart_wrap(text: str, limit: int, lang: str | None = None):
    """Wrap text safely for PDF rendering.

    - Japanese/Chinese: wrapped by fixed character count (no spaces).
    - Korean: wrapped with word-aware wrapping (Korean uses spaces).
    - English: wrapped with textwrap.wrap.
    """
    if text is None:
        return []
    s = str(text)
    if not s:
        return []
    lang = (lang or '').strip().lower() or None

    # Normalize newlines first
    parts = s.splitlines() or ['']
    out: list[str] = []

    for p in parts:
        if p == '':
            out.append('')
            continue

        # Korean: use space-aware wrapping to avoid overly short lines.
        if lang in ('ko', 'kr') or bool(re.search(r"[\uac00-\ud7af]", p)):
            out.extend(textwrap.wrap(
                p,
                width=max(1, limit),
                break_long_words=True,
                break_on_hyphens=False,
            ))
            continue

        # Japanese/Chinese: no spaces → fixed-width split by characters.
        is_ja_zh = (lang in ('ja', 'zh')) or bool(re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]", p))
        if is_ja_zh:
            for k in range(0, len(p), max(1, limit)):
                out.append(p[k:k+limit])
            continue

        # Default (English etc.)
        out.extend(textwrap.wrap(
            p,
            width=max(1, limit),
            break_long_words=True,
            break_on_hyphens=True,
        ))

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


from header_utils_ko import draw_header


# Fonts
# - Japanese: IPAexGothic (bundled TTF in this project)
# - Korean: ReportLab bundled CID font (no external TTF required)
FONT_NAME_JA = "IPAexGothic"
FONT_PATH_JA = "ipaexg.ttf"
FONT_NAME_EN = "Times-Roman"
FONT_NAME_KO = "HYGothic-Medium"

# Register fonts (safe on servers where some fonts may be missing)
try:
    pdfmetrics.registerFont(TTFont(FONT_NAME_JA, FONT_PATH_JA))
except Exception as e:
    print("Font registration error (JA):", e)

try:
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME_KO))
except Exception as e:
    print("Font registration error (KO):", e)

def _font(lang: str) -> str:
    l = str(lang).lower()
    if l.startswith("en"):
        return FONT_NAME_EN
    if l.startswith("ko") or l.startswith("kr"):
        return max(36, int(base * 1.10))
    return FONT_NAME_JA

def _set_font(c, lang: str, size: float):
    c.setFont(_font(lang), size)

def _wrap_len(base: int, lang: str) -> int:
    l = str(lang).lower()
    # English text easily overruns the right margin (serif fonts are wide).
    if l.startswith("en"):
        return max(28, int(base * 0.68))
    # Korean glyphs are wide; wrap a bit earlier.
    if l.startswith("ko") or l.startswith("kr"):
        # Korean can use longer lines (space-separated words). Keep close to base.
        return max(32, int(base * 1.10))
    # Chinese also benefits from slightly earlier wrapping.
    if l.startswith("zh"):
        return max(30, int(base * 0.85))
    return base



def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction, lang='ja', page_height=None, **kwargs):
    """ラッキー情報セクション
    - 2列表示で横幅を有効活用（余白があるのに3ページ化する問題を抑制）
    - lucky_lines が 1行でも2行でも崩れない
    - 呼び出し側の互換（lang/page_height/kwargs）対応
    """
    if not lucky_lines:
        lucky_lines = []

    _set_font(c, lang, 12)
    l = str(lang).lower()
    if l.startswith("en"):
        title = "■ Lucky Info (from birthdate)"
    elif l.startswith("zh"):
        title = "■ 幸运信息（根据出生日期）"
    elif l.startswith("ko") or l.startswith("kr"):
        title = "■ 행운 정보(생년월일 기준)"
    else:
        title = "■ ラッキー情報（生年月日より）"
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
        l = str(lang).lower()
        if l.startswith("en"):
            direction_title = "■ Lucky Directions"
        elif l.startswith("zh"):
            direction_title = "■ 吉方位"
        elif l.startswith("ko") or l.startswith("kr"):
            direction_title = "■ 행운 방향"
        else:
            direction_title = "■ ラッキー方位"
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
    # KO page2 can overflow due to longer Korean text; tighten spacing to match EN/ZH successful layout.
    is_ko = str(lang).lower().startswith(('ko','kr'))
    txt_size = 9 if is_ko else 10
    line_step = (5 * mm) if is_ko else (6 * mm)
    title_step = (5 * mm) if is_ko else (6 * mm)
    block_gap = (2 * mm) if is_ko else (3 * mm)
    y = draw_header(c, width, margin, y)
    y = draw_palm_image(c, data["palm_image"], width, y)

    # 生年月日・星座・干支・動物占い・本命星（手相画像の直下に表示）
    birthdate = data.get("birthdate")
    zodiac = data.get("zodiac")
    eto = data.get("eto")
    eto_number = data.get("eto_number")
    animal = data.get("animal")
    honmeisei = data.get("honmeisei")
    # KO: avoid mixed Japanese values and omit animal fortune (A)
    zodiac = _ko_map_zodiac(zodiac)
    honmeisei = _ko_map_star(honmeisei)
    animal = ""

    info_lines = []

    def _lang_is_ko(v: str) -> bool:
        l = str(v).lower()
        return l.startswith('ko') or l.startswith('kr')

    # Label translations for the info block
    if _lang_is_ko(lang):
        _lbl_birth = "생년월일"
        _lbl_zodiac = "별자리"
        _lbl_eto = "간지"
        _lbl_animal = "동물점"
        _lbl_star = "본명성"
        _eto_num_suffix = "번"
    else:
        _lbl_birth = "生年月日"
        _lbl_zodiac = "星座"
        _lbl_eto = "干支"
        _lbl_animal = "動物占い"
        _lbl_star = "本命星"
        _eto_num_suffix = "番"

    # 1行目：生年月日＋星座
    line1_parts = []
    if birthdate:
        line1_parts.append(f"{_lbl_birth}：{birthdate}")
    if zodiac:
        line1_parts.append(f"{_lbl_zodiac}：{zodiac}")
    if line1_parts:
        info_lines.append(" / ".join(line1_parts))

    # 2行目：干支番号＋動物占い＋本命星
    line2_parts = []
    if eto:
        if eto_number:
            line2_parts.append(f"{_lbl_eto}：{eto}（{eto_number}{_eto_num_suffix}）")
        else:
            line2_parts.append(f"{_lbl_eto}：{eto}")
    if animal:
        line2_parts.append(f"{_lbl_animal}：{animal}")
    if honmeisei:
        line2_parts.append(f"{_lbl_star}：{honmeisei}")
    if line2_parts:
        info_lines.append(" / ".join(line2_parts))

    if info_lines:
        _set_font(c, lang, 11)
        for line in info_lines:
            c.drawString(margin, y, line)
            y -= (4 * mm if is_ko else 5 * mm)
        y -= block_gap

    # 手相3項目（1ページ目）
    _set_font(c, lang, 12)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= title_step
        _set_font(c, lang, txt_size)
        for line in smart_wrap(data['palm_texts'][i], _wrap_len(40, lang), lang):
            c.drawString(margin, y, line)
            y -= line_step
        y -= block_gap
        _set_font(c, lang, 12)

    # 新ページ：手相残り2項目 + 鑑定結果
    c.showPage()
    y = height - margin

    _set_font(c, lang, 12)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= title_step
        _set_font(c, lang, txt_size)
        for line in smart_wrap(data['palm_texts'][i], _wrap_len(40, lang), lang):
            c.drawString(margin, y, line)
            y -= line_step
        y -= block_gap
        _set_font(c, lang, 12)

    # 四柱推命・まとめ等（タイトルのみでも出す）
    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 36 if 'month' in key else 40
        title = data['titles'].get(key, "")
        content = data['texts'].get(key, "")

        if title:
            c.drawString(margin, y, f"◆ {title}")
            y -= title_step
        _set_font(c, lang, txt_size)
        if content:
            for line in smart_wrap(content, _wrap_len(wrap_len, lang), lang):
                c.drawString(margin, y, line)
                y -= line_step
        y -= block_gap
        _set_font(c, lang, 12)

    # ラッキー情報を2ページ目末尾に移動
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''), lang=lang)

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

    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''), lang=lang)

    if include_yearly:
        draw_yearly_pages_shincom_b4(c, data['yearly_fortunes'], lang)


def draw_yearly_pages_shincom_a4(c, yearly, lang="ja"):
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
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
    from header_utils_ko import draw_header
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
    c.setTitle('占い結果')
    if mode == 'shincom':
        if size == 'a4':
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        draw_renai_pdf(c, data, size, include_yearly)
    c.save()
