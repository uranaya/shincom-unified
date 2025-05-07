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

from fortune_logic import generate_fortune
from renai_fortune_utils import generate_fortune as generate_renai_fortune
from yearly_fortune_utils import generate_yearly_fortune
from yearly_love_fortune_utils import generate_yearly_love_fortune
from header_utils import draw_header
from lucky_utils import draw_lucky_section

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))


def draw_wrapped_lines(text_obj, lines):
    for line in lines:
        text_obj.textLine(line)


def draw_lucky_info(c, data, x, y):
    c.setFont(FONT_NAME, 11)
    for label, content in data.items():
        wrapped = wrap(f"◆ {label}：{content}", width=40)
        for line in wrapped:
            c.drawString(x, y, line)
            y -= 12
    return y


def create_pdf_unified(filepath, data, mode, size=A4, include_yearly=False):
    c = canvas.Canvas(filepath, pagesize=size)

    if mode == "shincom":
        if size == B4:
            draw_shincom_b4(c, data, include_yearly)
        else:
            draw_shincom_a4(c, data, include_yearly)
    elif mode == "renai":
        if size == B4:
            draw_renai_b4(c, data, include_yearly)
        else:
            draw_renai_a4(c, data, include_yearly)

    c.save()


def draw_header(c, width, height):
    c.setFont(FONT_NAME, 16)
    c.drawString(20 * mm, height - 20 * mm, "鑑定結果")

def draw_shincom_a4(c, data, include_yearly):
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    draw_header(c, width, height)

    # 手相画像（存在確認）
    img_path = data.get("image_path")
    if img_path:
        img_width = 120 * mm
        img_height = 90 * mm
        img_top_y = y - 10 * mm
        c.drawImage(img_path, (width - img_width) / 2, img_top_y - img_height, width=img_width, height=img_height)
        y = img_top_y - img_height - 5 * mm

    # 手相1〜3項目
    for i in range(3):
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(data["palm_texts"][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 4 * mm

    # ラッキー情報まとめ
    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, "◆ ラッキー情報まとめ")
    y -= 10 * mm
    c.setFont(FONT_NAME, 11)
    for key in ["lucky_info", "lucky_direction"]:
        for line in wrap(data["texts"][key], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 4 * mm

    # 2ページ目へ
    c.showPage()
    y = height - 30 * mm

    # 手相4・5項目
    for i in [3, 4]:
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(data["palm_texts"][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 4 * mm

    # 手相総合アドバイス
    advice = data["palm_sections"].get("summary")
    if advice:
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, "◆ 手相からの総合的なアドバイス")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(advice, 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 4 * mm

    # 性格・今月・来月の運勢
    for key in ["personality", "month_fortune", "next_month_fortune"]:
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(data["texts"][key], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 4 * mm

    # 年運ページ描画（3〜4ページ）
    if include_yearly:
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])


def draw_shincom_b4(c, data, include_yearly):
    width, height = B4
    margin = 20 * mm

    # ヘッダー
    draw_header(c, width, height)

    # 手相画像
    img_path = data["image_path"]
    img_width = 120 * mm
    img_height = 90 * mm
    y_header_end = height - 30 * mm
    img_top_y = y_header_end - img_height - 3 * mm
    c.drawImage(img_path, (width - img_width) / 2, img_top_y, width=img_width, height=img_height)
    y = img_top_y - 3 * mm

    # 1ページ目：手相 1〜3項目
    text = c.beginText(margin, y)
    text.setFont(FONT_NAME, 11)

    for idx in range(3):
        text.textLine(f"■ {data['palm_titles'][idx]}")
        text.textLine("")
        for line in wrap(data["palm_texts"][idx], 40):
            text.textLine(line)
        text.textLine("")

    c.drawText(text)

    # 2ページ目：手相4〜5項目＋手相総合
    c.showPage()
    text = c.beginText(margin, height - 30 * mm)
    text.setFont(FONT_NAME, 11)

    text.textLine("■ 手相鑑定（4〜5項目目 + 総合アドバイス）")
    text.textLine("")
    for key in ["4", "5", "summary"]:
        if key in data["palm_sections"]:
            for line in wrap(data["palm_sections"][key], 40):
                text.textLine(line)
            text.textLine("")

    # 性格・運勢・ラッキー情報
    for key in ["personality", "month_fortune", "next_month_fortune", "lucky_info", "lucky_direction"]:
        text.textLine(f"■ {data['titles'][key]}")
        text.textLine("")
        for line in wrap(data["texts"][key], 40):
            text.textLine(line)
        text.textLine("")

    c.drawText(text)

    # 年運ページ（必要な場合）
    if include_yearly:
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])

def draw_yearly_pages_shincom(c, yearly_data):
    width, height = c._pagesize
    margin = 25 * mm
    y = height - 30 * mm

    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, f"■ {yearly_data['year_label']}")
    y -= 5 * mm
    c.setFont(FONT_NAME, 11)
    for line in wrap(yearly_data['year_text'], 40):
        c.drawString(margin, y, line)
        y -= 6 * mm

    y -= 5 * mm
    y -= 5 * mm

    months = yearly_data['months']
    for i, month in enumerate(months):
        if i == 5:
            c.showPage()
            y = height - 30 * mm
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {month['label']}")
        y -= 5 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(month['text'], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 5 * mm

        if i < len(months) - 1 and y < 50 * mm:
            y -= 5 * mm

def draw_renai_pdf(c, data, size, include_yearly=False):
    width, height = A4 if size == "a4" else B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)

    c.setFont(FONT_NAME, 12)
    for key in ["compatibility", "love_summary"]:
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        lines = wrap(data["texts"][key], 40 if size == "a4" else 45)
        for line in lines:
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    y = draw_lucky_section(c, width, margin, y, data["lucky_info"], data["lucky_direction"])

    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)

    for text in data["themes"]:
        c.drawString(margin, y, f"◆ {text['title']}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        lines = wrap(text["content"], 40 if size == "a4" else 45)
        for line in lines:
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    if include_yearly:
        draw_yearly_pages_renai(c, data["yearly_fortunes"])
