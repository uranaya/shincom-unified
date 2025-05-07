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
        for line in wrap(data['palm_texts'][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    y -= 3 * mm
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))
    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)
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
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['texts'][key], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    if include_yearly:
        c.showPage()
        draw_yearly_pages_shincom(c, data['yearly_fortunes'])

def draw_shincom_b4(c, data, include_yearly=False):
    width, height = B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)
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
    y -= 3 * mm
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))
    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)
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
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['texts'][key], 45):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    if include_yearly:
        c.showPage()
        draw_yearly_pages_shincom(c, data['yearly_fortunes'])

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
    y -= 10 * mm
    months = yearly_data.get('months', [])
    for i, month in enumerate(months):
        if i == 5:
            c.showPage()
            width, height = c._pagesize
            y = height - 30 * mm
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {month['label']}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(month['text'], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 5 * mm
        if i < len(months) - 1 and y < 50 * mm:
            y -= 5 * mm

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
