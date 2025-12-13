"""
pdf_namefortune.py
------------------
姓名判断レポート（A4縦）のPDFを生成するモジュール。

・IPAexGothic フォント前提
・テキスト折り返し
・見出し「### 」付きのテキストを、
  1〜2ページにかけて描画する簡易レイアウト
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import os
from typing import Dict

FONT_NAME = "IPAexGothic"


def register_japanese_font(font_path: str = "ipaexg.ttf"):
    """
    IPAexGothic フォントを登録。
    すでに登録済みなら何もしない。
    """
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"フォントファイルが見つかりません: {font_path}")
    pdfmetrics.registerFont(TTFont(FONT_NAME, font_path))


def wrap_text(text, font_name, font_size, max_width, canvas_obj):
    """
    1行のテキストを指定幅で折り返す簡易関数。
    日本語を想定しているので、スペース単位ではなく
    文字単位で折り返します。
    """
    lines = []
    current = ""
    for ch in text:
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        w = canvas_obj.stringWidth(current + ch, font_name, font_size)
        if w <= max_width or current == "":
            current += ch
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def draw_heading(c, text, x, y, font_size=14):
    c.setFont(FONT_NAME, font_size)
    c.drawString(x, y, text)


def draw_paragraph(c, text, x, y, max_width, font_size=11, leading=14):
    """
    段落テキストを描画し、最終的な Y 座標を返す。
    必要ならここでページをまたぐ実装もできますが、
    ここでは「呼び出し側でページ切り替え」を行う前提で、
    単純に描画しています。
    """
    c.setFont(FONT_NAME, font_size)
    lines = []
    for raw_line in text.splitlines():
        if raw_line.strip() == "":
            lines.append("")
            continue
        wrapped = wrap_text(raw_line, FONT_NAME, font_size, max_width, c)
        lines.extend(wrapped)

    for line in lines:
        if y < 30 * mm:  # 下マージン
            c.showPage()
            c.setFont(FONT_NAME, font_size)
            y = 270 * mm
        if line == "":
            y -= leading
            continue
        c.drawString(x, y, line)
        y -= leading
    return y


def create_namefortune_pdf(output_path: str, data: Dict, fortune_text: str):
    """
    A4縦1〜2ページ程度の姓名判断レポートPDFを作成する。
    data には NameFortuneInput 相当の情報を dict で渡すことを想定。
    """
    register_japanese_font()

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    margin_x = 25 * mm
    margin_top = 280 * mm
    usable_width = width - 2 * margin_x

    # 1ページ目 ヘッダー
    y = margin_top
    c.setFont(FONT_NAME, 18)
    c.drawString(margin_x, y, "シン・コンピューター占い　姓名判断レポート")
    y -= 15 * mm

    # 基本情報
    c.setFont(FONT_NAME, 12)
    full_name = data.get("full_name", "")
    reading = data.get("reading", "")
    if reading:
        name_line = f"お名前：{full_name}（{reading}）"
    else:
        name_line = f"お名前：{full_name}"

    c.drawString(margin_x, y, name_line)
    y -= 8 * mm

    # 五運
    goun_line1 = (
        f"天格：{data.get('tenkaku')}画 / "
        f"人格：{data.get('jinkaku')}画 / "
        f"地格：{data.get('chikaku')}画"
    )
    goun_line2 = (
        f"外格：{data.get('gaikaku')}画 / "
        f"総格：{data.get('soukaku')}画"
    )

    c.setFont(FONT_NAME, 11)
    c.drawString(margin_x, y, goun_line1)
    y -= 6 * mm
    c.drawString(margin_x, y, goun_line2)
    y -= 10 * mm

    # 入れたい漢字
    kanji_candidates = data.get("kanji_candidates") or []
    kanji_str = "、".join(kanji_candidates) if kanji_candidates else "特になし"
    c.drawString(margin_x, y, f"ご希望の漢字：{kanji_str}")
    y -= 12 * mm

    # ここから AI テキスト（### 見出し 単位でパース）
    # fortune_text をセクションごとに分割
    sections = []
    current_title = None
    current_body_lines = []

    for line in fortune_text.splitlines():
        if line.startswith("### "):
            # 以前のセクションを保存
            if current_title is not None:
                sections.append((current_title, "\n".join(current_body_lines).strip()))
                current_body_lines = []
            current_title = line[4:].strip()
        else:
            current_body_lines.append(line)

    if current_title is not None:
        sections.append((current_title, "\n".join(current_body_lines).strip()))

    # 描画ループ
    for title, body in sections:
        # 見出し
        if y < 40 * mm:
            c.showPage()
            y = margin_top
            c.setFont(FONT_NAME, 12)
        draw_heading(c, f"■ {title}", margin_x, y, font_size=13)
        y -= 8 * mm

        # 本文
        y = draw_paragraph(
            c,
            body,
            x=margin_x,
            y=y,
            max_width=usable_width,
            font_size=11,
            leading=14,
        )
        y -= 4 * mm

    c.showPage()
    c.save()
