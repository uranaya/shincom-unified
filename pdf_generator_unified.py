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

def draw_shincom_a4(c, data, include_yearly=False):
    width, height = A4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)

    c.setFont(FONT_NAME, 12)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["palm_texts"][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    y -= 3 * mm
    y = draw_lucky_section(c, width, margin, y, data["lucky_info"], data["lucky_direction"])

    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)

    c.setFont(FONT_NAME, 12)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["palm_texts"][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    for key in ["palm_summary", "personality", "month_fortune", "next_month_fortune"]:
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["texts"][key], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    if include_yearly:
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])

def draw_shincom_b4(c, data, include_yearly):
    width, height = B4
    margin = 20 * mm
    y = height - 30 * mm
    y = draw_header(c, width, margin, y)

    if data.get("image_data"):
        img_data = base64.b64decode(data["image_data"].split(",")[1])
        img = ImageReader(io.BytesIO(img_data))
        img_width = 130 * mm
        img_height = 100 * mm
        img_x = (width - img_width) / 2
        img_y = y - img_height - 10 * mm
        c.drawImage(img, img_x, img_y, width=img_width, height=img_height)
        y = img_y - 10 * mm

    # 表面：手相5項目（項目ごとに表示）
    text = c.beginText(margin, y)
    text.setFont(FONT_NAME, 11)
    for title, body in zip(data["palm_titles"], data["palm_texts"]):
        text.textLine(f"■ {title}")
        text.textLine("")
        for line in wrap(body, 40):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    # 裏面
    c.showPage()
    text = c.beginText(margin, height - 30 * mm)
    text.setFont(FONT_NAME, 11)

    text.textLine("■ 手相からの総合的なアドバイス")
    text.textLine("")
    for line in data["texts"]["palm_summary"].split("\n"):
        for wrapped in wrap(line, 40):
            text.textLine(wrapped)
    text.textLine("")

    text.textLine("■ 四柱推命によるアドバイス")
    text.textLine("")
    for line in data["shichu_result"].split("\n"):
        for wrapped in wrap(line, 40):
            text.textLine(wrapped)
    text.textLine("")

    text.textLine("■ 易占いによるアドバイス")
    text.textLine("")
    for line in data["iching_result"].split("\n"):
        for wrapped in wrap(line, 40):
            text.textLine(wrapped)
    text.textLine("")

    text.textLine("■ ラッキー情報")
    text.textLine("")
    for label, content in data["lucky_info"].items():
        for line in wrap(f"◆ {label}：{content}", 40):
            text.textLine(line)
        text.textLine("")

    c.drawText(text)

    if include_yearly:
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])


def draw_yearly_pages_shincom(c, yearly_data):
    width, height = c._pagesize
    margin = 25 * mm
    y = height - 30 * mm

    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, f"■ {yearly_data['year_label']}")
    y -= 10 * mm
    c.setFont(FONT_NAME, 11)
    for line in wrap(yearly_data['year_text'], 40):
        c.drawString(margin, y, line)
        y -= 6 * mm

    y -= 10
    c.showPage()
    y = height - 30 * mm

    for month in yearly_data["months"]:
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {month['label']}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(month['text'], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 10

        if y < 50 * mm:
            c.showPage()
            y = height - 30 * mm

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

def create_pdf_unified(filepath, data, mode, size="a4", include_yearly=False):
    c = canvas.Canvas(filepath, pagesize=A4 if size == "a4" else B4)
    c.setTitle("占い結果")
    if mode == "shincom":
        if size == "a4":
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        draw_renai_pdf(c, data, size, include_yearly)
    c.save()
