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


def _wrap_by_width(text: str, font_name: str, font_size: float, max_w: float) -> list[str]:
    """PDF上の実幅で折り返す。日本語のように空白が無い文も右端で切らさない。"""
    s = (text or "").strip()
    if not s:
        return []

    lines: list[str] = []
    for raw in s.splitlines() or [s]:
        raw = raw.strip()
        if not raw:
            continue
        cur = ""
        for ch in raw:
            candidate = cur + ch
            if cur and stringWidth(candidate, font_name, font_size) > max_w:
                lines.append(cur.rstrip())
                cur = ch.lstrip()
            else:
                cur = candidate
        if cur.strip():
            lines.append(cur.strip())
    return lines


def _estimate_lucky_section_height(width, margin, lucky_lines, lucky_direction, lang='ja') -> float:
    """2ページ目末尾のラッキー情報＋方位に必要な高さを事前計算する。"""
    lucky_lines = lucky_lines or []
    l = str(lang).lower()
    is_en = l.startswith("en")
    font_name = _font(lang)
    font_size = 10 if is_en else 9.2
    line_h = (5.6 * mm) if is_en else (5.0 * mm)

    h = 6 * mm  # ラッキー情報見出し分
    h += ((len(lucky_lines) + 1) // 2) * line_h
    if lucky_direction:
        max_w = width - 2 * margin - (6 * mm if is_en else 0)
        dir_lines = _wrap_by_width((lucky_direction or "").strip(), font_name, font_size, max_w)
        h += 1.5 * mm + 5.5 * mm + max(1, len(dir_lines)) * line_h
    return h + 2 * mm



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
        # 日本語は空白が無いことが多いため、PDF上の実幅で必ず折り返す。
        # これにより「ラッキー方位」が右端・下端で切れる事故を避ける。
        max_w = width - 2 * margin - (6 * mm if str(lang).lower().startswith("en") else 0)
        for line in _wrap_by_width(dir_text, font_name, font_size, max_w) or [dir_text]:
            c.drawString(margin, y, line)
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



def draw_neko_uranai_page(c, data, lang="ja", page_size=A4):
    # 猫占いオプション用の追加1ページ。
    # 通常占い側のレイアウトやページ数には触れず、このページ内だけを拡張する。
    neko = (data or {}).get("neko_uranai") or {}
    if not neko:
        return

    width, height = page_size
    margin = 18 * mm
    bottom = 16 * mm
    wrap_chars = 43 if width <= A4[0] + 1 else 54

    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)

    _set_font(c, lang, 18)
    c.drawCentredString(width / 2, y, "猫占い")
    y -= 9 * mm

    number = neko.get("number") or ""
    name = neko.get("name") or "猫"
    tag = neko.get("tag") or ""
    description = (
        neko.get("description")
        or neko.get("personality")
        or neko.get("性質")
        or neko.get("性格")
        or ""
    )
    love_style = neko.get("love_style") or ""
    love_iching = neko.get("love_iching") or {}
    domain_ichings = neko.get("domain_ichings") or {}

    _set_font(c, lang, 12)
    c.drawString(margin, y, f"◆ あなたの猫タイプ：{number}. {name}")
    y -= 5.5 * mm

    _set_font(c, lang, 10)
    if tag:
        c.drawString(margin, y, f"猫キャラの一言：{tag}")
        y -= 5.5 * mm

    # 既存の猫画像は残しつつ、情報量を増やすため少しコンパクトに表示する。
    image_path = neko.get("image_path") or ""
    try:
        if image_path and os.path.exists(image_path):
            img = ImageReader(image_path)
            iw, ih = img.getSize()
            max_w = 40 * mm if width <= A4[0] + 1 else 46 * mm
            max_h = 40 * mm if width <= A4[0] + 1 else 46 * mm
            scale = min(max_w / iw, max_h / ih)
            draw_w, draw_h = iw * scale, ih * scale
            x = (width - draw_w) / 2
            c.drawImage(img, x, y - draw_h, width=draw_w, height=draw_h, mask='auto')
            y -= draw_h + 5 * mm
        else:
            c.drawCentredString(width / 2, y, "（猫画像が見つかりません）")
            y -= 8 * mm
    except Exception as e:
        print("Neko image draw error:", e)
        c.drawCentredString(width / 2, y, "（猫画像の読み込みに失敗しました）")
        y -= 8 * mm

    def draw_section(title, text, y_pos, body_size=9.4, max_lines=None, gap=2.0 * mm):
        if not text or y_pos <= bottom + 8 * mm:
            return y_pos
        _set_font(c, lang, 12.3)
        c.drawString(margin, y_pos, f"◆ {title}")
        y_pos -= 5.5 * mm
        _set_font(c, lang, body_size)
        lines = smart_wrap(str(text), wrap_chars, lang)
        if max_lines:
            lines = lines[:max_lines]
        for line in lines:
            if y_pos < bottom:
                break
            c.drawString(margin, y_pos, line)
            y_pos -= 4.6 * mm
        return y_pos - gap

    if not description:
        description = f"{name}は、自分らしい感覚と猫のような勘を大切にするタイプです。無理に周囲へ合わせすぎず、心が落ち着く場所と人を選ぶことで本来の魅力が伸びていきます。"

    y = draw_section("性質・性格", description, y, max_lines=5)
    y = draw_section("恋愛傾向", love_style, y, max_lines=4)

    # 猫占い専用の恋愛イーチン。通常占いの iching_result とは完全に別データ。
    if isinstance(love_iching, dict) and love_iching:
        _set_font(c, lang, 12.3)
        c.drawString(margin, y, "◆ 今日の恋愛イーチン")
        y -= 5.5 * mm

        label = love_iching.get("label") or ""
        if label:
            _set_font(c, lang, 10.3)
            c.drawString(margin, y, label)
            y -= 5.0 * mm

        iching_text = " ".join(
            x for x in [love_iching.get("cat_line", ""), love_iching.get("love", "")] if x
        )
        _set_font(c, lang, 9.4)
        for line in smart_wrap(iching_text, wrap_chars, lang)[:6]:
            if y < bottom:
                break
            c.drawString(margin, y, line)
            y -= 4.6 * mm
        y -= 1.5 * mm

        action = love_iching.get("action") or ""
        if action and y >= bottom + 8 * mm:
            _set_font(c, lang, 10.2)
            c.drawString(margin, y, f"恋の一手：{action}")
            y -= 6.0 * mm

    omikuji = neko.get("omikuji") or "今日はひげの向く方へ、ゆっくり進むにゃ。"

    # 仕事運・金運・対人運が生成できた場合だけ、猫占い専用の2ページ目を追加する。
    # 拡張モジュールに不具合があって domain_ichings が無い場合は、従来通り1ページで完結する。
    if isinstance(domain_ichings, dict) and any(
        isinstance(domain_ichings.get(key), dict) and domain_ichings.get(key)
        for key in ("work", "money", "relations")
    ):
        c.showPage()
        y = height - margin
        y = draw_header(c, width, margin, y)

        _set_font(c, lang, 18)
        c.drawCentredString(width / 2, y, "猫占い － 今日のイーチン運勢")
        y -= 9 * mm
        _set_font(c, lang, 10)
        c.drawCentredString(width / 2, y, f"{number}. {name} の仕事運・金運・対人運")
        y -= 10 * mm

        domain_labels = {
            "work": ("仕事運", "仕事の一手"),
            "money": ("金運", "金運の一手"),
            "relations": ("対人運", "対人の一手"),
        }

        for key in ("work", "money", "relations"):
            fortune = domain_ichings.get(key) or {}
            if not isinstance(fortune, dict) or not fortune:
                continue
            section_title, action_title = domain_labels[key]
            _set_font(c, lang, 12.3)
            c.drawString(margin, y, f"◆ 今日の{section_title}イーチン")
            y -= 5.5 * mm

            label = fortune.get("label") or ""
            if label:
                _set_font(c, lang, 10.3)
                c.drawString(margin, y, label)
                y -= 5.0 * mm

            domain_text = " ".join(
                x for x in [fortune.get("cat_line", ""), fortune.get("text", "")] if x
            )
            _set_font(c, lang, 9.4)
            for line in smart_wrap(domain_text, wrap_chars, lang)[:5]:
                if y < bottom:
                    break
                c.drawString(margin, y, line)
                y -= 4.6 * mm

            action = fortune.get("action") or ""
            if action and y >= bottom + 8 * mm:
                y -= 0.5 * mm
                _set_font(c, lang, 10.2)
                c.drawString(margin, y, f"{action_title}：{action}")
                y -= 6.5 * mm

        y = draw_section("猫御籤", omikuji, y, max_lines=5, gap=1.5 * mm)

        if y >= bottom + 8 * mm:
            _set_font(c, lang, 10.2)
            c.drawString(margin, y, "◆ 今日の合言葉")
            y -= 5.0 * mm
            _set_font(c, lang, 9.4)
            c.drawString(margin, y, "焦らず、すり寄りすぎず、必要な時だけ爪を出すにゃん。")
    else:
        y = draw_section("猫御籤", omikuji, y, max_lines=6, gap=1.5 * mm)

        if y >= bottom + 8 * mm:
            _set_font(c, lang, 10.2)
            c.drawString(margin, y, "◆ 今日の合言葉")
            y -= 5.0 * mm
            _set_font(c, lang, 9.4)
            c.drawString(margin, y, "焦らず、すり寄りすぎず、必要な時だけ爪を出すにゃん。")

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

    # A4 2ページ目は「手相2項目 + 鑑定本文 + ラッキー方位」が同居するため、
    # 先に全ブロックの高さを見積もり、必要な時だけ全体を段階的にコンパクト化する。
    # 重要：本文を「…」で省略しない。最後まで描画したうえで、最終手段として縦方向のみ縮尺をかける。
    top_y = height - margin
    BOTTOM = 18 * mm
    available_h = top_y - BOTTOM

    page2_blocks_src = []
    for i in range(3, 5):
        page2_blocks_src.append({
            "kind": "palm",
            "title": data['palm_titles'][i],
            "content": data['palm_texts'][i],
            "wrap_base": 40,
        })

    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        page2_blocks_src.append({
            "kind": "fortune",
            "title": data['titles'].get(key, ""),
            "content": data['texts'].get(key, ""),
            "wrap_base": 40 if 'month' in key else 42,
        })

    # 通常 → コンパクト → 最小の順。通常時の見た目は極力変えず、
    # 長文時だけ文字サイズ・行間・折返し幅で吸収する。
    page2_presets = [
        {"title_size": 12.0, "title_step": 6.0 * mm, "body_size": 10.0, "line_step": 5.6 * mm, "gap": 3.0 * mm, "wrap_boost": 0},
        {"title_size": 11.5, "title_step": 5.4 * mm, "body_size": 9.2,  "line_step": 4.9 * mm, "gap": 2.2 * mm, "wrap_boost": 3},
        {"title_size": 11.0, "title_step": 5.0 * mm, "body_size": 8.5,  "line_step": 4.4 * mm, "gap": 1.8 * mm, "wrap_boost": 6},
        {"title_size": 10.2, "title_step": 4.6 * mm, "body_size": 7.8,  "line_step": 3.9 * mm, "gap": 1.4 * mm, "wrap_boost": 10},
        {"title_size": 9.5,  "title_step": 4.2 * mm, "body_size": 7.0,  "line_step": 3.5 * mm, "gap": 1.0 * mm, "wrap_boost": 14},
    ]

    def _build_page2_layout(preset):
        blocks = []
        total_h = 0.0
        for src in page2_blocks_src:
            wrap_len = _wrap_len(src["wrap_base"] + preset["wrap_boost"], lang)
            lines = smart_wrap(src.get("content", "") or "", wrap_len, lang)
            block_h = (preset["title_step"] if src.get("title") else 0) + (len(lines) * preset["line_step"]) + preset["gap"]
            total_h += block_h
            blocks.append({**src, "lines": lines, "height": block_h})

        lucky_h = _estimate_lucky_section_height(
            width, margin, data.get('lucky_info', []), data.get('lucky_direction', ''), lang
        )
        total_h += lucky_h
        return total_h, blocks

    chosen_preset = page2_presets[-1]
    chosen_total_h, chosen_blocks = _build_page2_layout(chosen_preset)
    for preset in page2_presets:
        total_h, blocks = _build_page2_layout(preset)
        if total_h <= available_h:
            chosen_preset = preset
            chosen_total_h = total_h
            chosen_blocks = blocks
            break

    # どのプリセットでも入り切らない非常時だけ、ページ上端を基準に縦方向へ縮尺。
    # 省略はしないため、文末が「…」で未完になることはない。
    scale_y = 1.0
    if chosen_total_h > 0 and chosen_total_h > available_h:
        scale_y = available_h / chosen_total_h

    if scale_y < 1.0:
        c.saveState()
        c.translate(0, top_y)
        c.scale(1, scale_y)
        c.translate(0, -top_y)

    y = top_y
    for block in chosen_blocks:
        title = block.get("title", "")
        if title:
            _set_font(c, lang, chosen_preset["title_size"])
            c.drawString(margin, y, f"◆ {title}")
            y -= chosen_preset["title_step"]

        _set_font(c, lang, chosen_preset["body_size"])
        for line in block.get("lines", []):
            c.drawString(margin, y, line)
            y -= chosen_preset["line_step"]
        y -= chosen_preset["gap"]

    # ラッキー情報を2ページ目末尾に移動。本文が長い場合でも本文省略ではなく全体縮尺で収める。
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''), lang=lang, page_height=height)

    if scale_y < 1.0:
        c.restoreState()

    if include_yearly:
        draw_yearly_pages_shincom_a4(c, data['yearly_fortunes'], lang)

    if data.get('neko_uranai'):
        draw_neko_uranai_page(c, data, lang, page_size=A4)


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

    if data.get('neko_uranai'):
        draw_neko_uranai_page(c, data, lang, page_size=B4)


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
