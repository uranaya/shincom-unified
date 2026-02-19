# -*- coding: utf-8 -*-
# NOTE: This is the JAPANESE PDF generator.
#       English output uses pdf_generator_unified_en.py.
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
    return 'en' if lang.startswith('en') else ('zh' if lang.startswith('zh') else 'ja')
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


from header_utils import draw_header


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
    # English text easily overruns the right margin (serif fonts are wide).
    # Wrap earlier to prevent "尻切れ".
    if str(lang).lower().startswith("en"):
        return max(28, int(base * 0.68))
    return base



def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction, lang='ja', page_height=None, **kwargs):
    """ラッキー情報セクション
    - 2列表示で横幅を有効活用（余白があるのに3ページ化する問題を抑制）
    - lucky_lines が 1行でも2行でも崩れない
    - 呼び出し側の互換（lang/page_height/kwargs）対応
    """
    if not lucky_lines:
        lucky_lines = []

    # A4 2ページ目末尾で収まりやすいよう、CJK は少しコンパクトに描画する。
    l = str(lang).lower()
    is_en = l.startswith("en")

    _set_font(c, lang, 12 if is_en else 11)
    if is_en:
        title = "■ Lucky Info (from birthdate)"
    elif l.startswith("zh"):
        title = "■ 幸运信息（根据出生日期）"
    else:
        title = "■ ラッキー情報（生年月日より）"
    c.drawString(margin, y, title)
    y -= 6 * mm

    # 2列レイアウト
    _set_font(c, lang, 10 if is_en else 9.2)
    col_gap = (8 * mm) if is_en else (6 * mm)
    col_w = (width - 2 * margin - col_gap) / 2.0
    line_h = (5.6 * mm) if is_en else (5.0 * mm)
    font_name = _font(lang)
    font_size = 10 if is_en else 9.2

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
        _set_font(c, lang, 10 if is_en else 9.2)
        l = str(lang).lower()
        if l.startswith("en"):
            direction_title = "■ Lucky Directions"
        elif l.startswith("zh"):
            direction_title = "■ 吉方位"
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

def draw_palm_image(c, base64_image, width, y, page_height=None):
    try:
        image_data = base64.b64decode(base64_image.split(',')[1])
        img = ImageReader(io.BytesIO(image_data))
        img_width, img_height = img.getSize()

        page_h = page_height or A4[1]

        # アスペクト比を保ちつつ、1ページ目の本文領域を確保するため少し小さめに配置
        # （手相文章量が増えても 1P の3項目が欠けにくいようにする）
        max_height = 0.24 * page_h  # 高さ制限（ページ高の24%）
        scale_w = (width * 0.62) / img_width  # 横幅62%を基準
        scale_h = max_height / img_height
        scale = min(scale_w, scale_h)

        img_width *= scale
        img_height *= scale

        x_center = (width - img_width) / 2
        y -= img_height + 4 * mm
        c.drawImage(img, x_center, y, width=img_width, height=img_height)
        y -= 6 * mm
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
    y = draw_palm_image(c, data["palm_image"], width, y, page_height=height)

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
        _set_font(c, lang, 10.2)
        for line in info_lines:
            c.drawString(margin, y, line)
            y -= 4.4 * mm
        y -= 2.2 * mm

    # 手相3項目（1ページ目）
    # 1ページ目は「画像 + 基本情報 + 3項目 + ラッキー情報」で下端ギリギリになりやすい。
    # ここは保険として、残りスペースが少ない場合は自動でコンパクト描画に切り替える。
    BOTTOM_P1 = 14 * mm

    def _draw_palm_block_p1(title: str, body: str, y: float) -> float:
        """1ページ目の手相ブロックは文章量のブレが大きいので、
        画像・基本情報とのバランスを見ながら自動で詰めて描画する。
        - 通常→コンパクト→最小の順でレイアウトを試す
        - それでも入らない場合は末尾を省略しつつ、最低限の行数を確保する
        """

        # (title_step, body_font_size, line_step, wrap_base, gap_after)
        presets = [
            (5.6 * mm, 9.6, 5.2 * mm, 48, 2.2 * mm),
            (5.2 * mm, 9.2, 4.9 * mm, 50, 2.0 * mm),
            (5.0 * mm, 8.8, 4.6 * mm, 52, 1.8 * mm),
        ]

        chosen = None
        chosen_lines = None

        for title_step, body_size, line_step, wrap_base, gap_after in presets:
            wrap_len = _wrap_len(wrap_base, lang)
            lines = smart_wrap(body or "", wrap_len, lang)
            need_h = title_step + (len(lines) * line_step) + gap_after
            if (y - need_h) >= BOTTOM_P1:
                chosen = (title_step, body_size, line_step, wrap_len, gap_after)
                chosen_lines = lines
                break

        if chosen is None:
            # どれでも入らない場合は最小レイアウトで切り詰めて必ず表示する
            title_step, body_size, line_step, wrap_base, gap_after = presets[-1]
            wrap_len = _wrap_len(wrap_base, lang)
            lines = smart_wrap(body or "", wrap_len, lang)

            # 「ほぼ文章が無い」を避けるため、最低でも数行は見せる
            min_lines = 4
            max_lines = int(max(0, (y - BOTTOM_P1 - title_step) // line_step))
            max_lines = max(min_lines, max_lines)

            if len(lines) > max_lines:
                lines = lines[:max_lines]
                if lines:
                    lines[-1] = (lines[-1].rstrip("…") + "…")

            chosen = (title_step, body_size, line_step, wrap_len, gap_after)
            chosen_lines = lines

        title_step, body_size, line_step, wrap_len, gap_after = chosen
        lines = chosen_lines or []

        _set_font(c, lang, 12)
        c.drawString(margin, y, f"◆ {title}")
        y -= title_step

        _set_font(c, lang, body_size)
        for line in lines:
            if y < BOTTOM_P1:
                break
            c.drawString(margin, y, line)
            y -= line_step

        return y - gap_after

    for i in range(3):
        y = _draw_palm_block_p1(data['palm_titles'][i], data['palm_texts'][i], y)
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

    # 四柱推命・まとめ等（A4 2ページ目はテキストが増えやすいので自動で詰める）
    # - 行間を少し詰める
    # - 必要ならフォントを段階的に落としてオーバーフローを防ぐ
    BOTTOM = 22 * mm

    def _draw_block(title: str, content: str, y: float, wrap_base: int) -> float:
        nonlocal c
        if title:
            _set_font(c, lang, 12)
            c.drawString(margin, y, f"◆ {title}")
            y -= 5.5 * mm

        if not content:
            return y - 2.5 * mm

        # まず通常モードで必要行数を見積もり、入りきらない場合は compact に切り替える。
        lines_normal = smart_wrap(content, _wrap_len(wrap_base, lang), lang)
        need_h_normal = len(lines_normal) * (5.6 * mm)

        compact = (y - need_h_normal) < BOTTOM
        if compact:
            body_size = 9.2
            line_step = 5.0 * mm
            wrap_len = _wrap_len(wrap_base + 2, lang)  # 少し横を使って縦を削る
        else:
            body_size = 10
            line_step = 5.6 * mm
            wrap_len = _wrap_len(wrap_base, lang)

        _set_font(c, lang, body_size)
        lines = smart_wrap(content, wrap_len, lang)

        # それでも入らない場合は最後を省略して…で閉じる（はみ出しを絶対に出さない）
        max_lines = int(max(0, (y - BOTTOM) // line_step))
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            if lines:
                lines[-1] = (lines[-1].rstrip("…") + "…")

        for line in lines:
            if y < BOTTOM:
                break
            c.drawString(margin, y, line)
            y -= line_step

        return y - 2.5 * mm

    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        # month/next は文字量が増えやすいので、以前の36→40へ（縦を削る）
        wrap_len = 40 if 'month' in key else 42
        title = data['titles'].get(key, "")
        content = data['texts'].get(key, "")
        y = _draw_block(title, content, y, wrap_len)

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
    y = draw_palm_image(c, data["palm_image"], width, y, page_height=height)

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
    c.setTitle('占い結果')
    if mode == 'shincom':
        if size == 'a4':
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        draw_renai_pdf(c, data, size, include_yearly)
    c.save()
