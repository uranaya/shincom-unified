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
from fortune_logic import generate_renai_fortune
from yearly_fortune_utils import generate_yearly_fortune
from yearly_love_fortune_utils import generate_yearly_love_fortune
from header_utils import draw_header
from lucky_utils import draw_lucky_section

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def draw_yearly_pages_shincom_a4(c, yearly):
    from reportlab.lib.units import mm
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in text.splitlines():
            c.drawString(margin, y, line)
            y -= 7 * mm
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm

    c.showPage()
    y = height - 30 * mm
    draw_text_block(yearly["year_label"], yearly["year_text"])
    for month in yearly["months"]:
        draw_text_block(month["label"], month["text"])


def draw_yearly_pages_shincom_b4(c, yearly):
    from reportlab.lib.units import mm
    width, height = B4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in text.splitlines():
            c.drawString(margin, y, line)
            y -= 7 * mm
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm

    c.showPage()
    y = height - 30 * mm
    draw_text_block(yearly["year_label"], yearly["year_text"])
    for month in yearly["months"]:
        draw_text_block(month["label"], month["text"])


def draw_shincom_a4(c, data, include_yearly=False):
    from reportlab.lib.utils import ImageReader
    width, height = A4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)

    # 手相画像表示（センター）
    if 'image_path' in data:
        try:
            image_data = base64.b64decode(data['image_path'].split(',')[1])
            img = ImageReader(io.BytesIO(image_data))
            img_width, img_height = img.getSize()
            scale = (width * 0.6) / img_width
            img_width *= scale
            img_height *= scale
            x_center = (width - img_width) / 2
            y -= img_height + 5 * mm
            c.drawImage(img, x_center, y, width=img_width, height=img_height)
            y -= 10 * mm
        except Exception as e:
            print("Image decode error:", e)

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

    c.showPage()
    y = height - margin
    # ★ ヘッダーなし（2ページ目）

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

    for key in ['palm_summary', 'personality', 'month_fortune', 'next_month_fortune']:
        wrap_len = 36 if 'month' in key else 40
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['texts'][key], wrap_len):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # ラッキー情報を2ページ目末尾に移動
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    if include_yearly:
        c.showPage()
        draw_yearly_pages_shincom(c, data['yearly_fortunes'])


def draw_shincom_b4(c, data, include_yearly=False):
    width, height = B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)

    # 手相画像表示（センター）
    if 'image_path' in data:
        try:
            image_data = base64.b64decode(data['image_path'].split(',')[1])
            img = ImageReader(io.BytesIO(image_data))
            img_width, img_height = img.getSize()
            scale = (width * 0.6) / img_width
            img_width *= scale
            img_height *= scale
            x_center = (width - img_width) / 2
            y -= img_height + 5 * mm
            c.drawImage(img, x_center, y, width=img_width, height=img_height)
            y -= 10 * mm
        except Exception as e:
            print("Image decode error:", e)

    c.setFont(FONT_NAME, 12)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['palm_texts'][i], 45):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    c.showPage()
    y = height - margin
    # ★ ヘッダーなし（2ページ目）

    c.setFont(FONT_NAME, 12)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['palm_texts'][i], 45):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    for key in ['palm_summary', 'personality', 'month_fortune', 'next_month_fortune']:
        wrap_len = 41 if 'month' in key else 45
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['texts'][key], wrap_len):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # ラッキー情報を2ページ目末尾に移動
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    if include_yearly:
        c.showPage()
        draw_yearly_pages_shincom(c, data['yearly_fortunes'])


def draw_renai_pdf(c, data, size, include_yearly=False):
    width, height = A4 if size == 'a4' else B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)
    c.setFont(FONT_NAME, 12)
    for key in ['compatibility', 'love_summary']:
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        lines = wrap(data['texts'][key], 40 if size == 'a4' else 45)
        for line in lines:
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))
    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)
    for text in data['themes']:
        c.drawString(margin, y, f"◆ {text['title']}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        lines = wrap(text['content'], 40 if size == 'a4' else 45)
        for line in lines:
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    if include_yearly:
        draw_yearly_pages_shincom(c, data['yearly_fortunes'])

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