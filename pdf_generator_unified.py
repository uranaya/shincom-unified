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
from header_utils import draw_header
from lucky_utils import draw_lucky_section

# Register Japanese font (IPAexGothic)
FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
except Exception as e:
    print("Font registration error:", e)

def draw_palm_image(c, base64_image, width, y, birthdate=None):
    """
    Draw the palm image (from base64 data) at the current y position.
    If birthdate is provided, print it below the image.
    Returns the updated y position.
    """
    try:
        # Decode base64 image data
        image_data = base64.b64decode(base64_image.split(',')[1])
        img = ImageReader(io.BytesIO(image_data))
        img_width, img_height = img.getSize()
        # Scale image to 60% of page width
        scale = (width * 0.6) / img_width
        img_width *= scale
        img_height *= scale
        x_center = (width - img_width) / 2
        # Draw image and move y below it
        y -= img_height + 5 * mm
        c.drawImage(img, x_center, y, width=img_width, height=img_height)
        y -= 10 * mm
        # Draw birthdate centered below the image
        if birthdate:
            c.setFont(FONT_NAME, 10)
            c.drawCentredString(width / 2, y, f"生年月日：{birthdate}")
            y -= 8 * mm
    except Exception as e:
        print("Image decode error:", e)
    return y

def draw_yearly_pages_shincom_a4(c, yearly_data):
    """
    Draw additional pages for yearly fortunes (normal mode, A4).
    """
    width, height = A4
    margin = 20 * mm
    # Each month fortune on a new page
    for entry in yearly_data.get("months", []):
        c.showPage()
        y = height - margin
        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, f"◆ {entry['label']}")
        y -= 8 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(entry["text"], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm

def draw_yearly_pages_shincom_b4(c, yearly_data):
    """
    Draw additional pages for yearly fortunes (normal mode, B4).
    """
    width, height = B4
    margin = 20 * mm
    for entry in yearly_data.get("months", []):
        c.showPage()
        y = height - margin
        c.setFont(FONT_NAME, 14)
        c.drawString(margin, y, f"◆ {entry['label']}")
        y -= 8 * mm
        c.setFont(FONT_NAME, 12)
        for line in wrap(entry["text"], width=45):
            c.drawString(margin, y, line)
            y -= 7 * mm

def draw_yearly_pages_renai_a4(c, yearly_data):
    """
    Draw additional pages for yearly love fortunes (A4).
    """
    width, height = A4
    margin = 20 * mm
    for entry in yearly_data.get("months", []):
        c.showPage()
        y = height - margin
        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, f"◆ {entry['label']}")
        y -= 8 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(entry["text"], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm

def draw_yearly_pages_renai_b4(c, yearly_data):
    """
    Draw additional pages for yearly love fortunes (B4).
    """
    width, height = B4
    margin = 20 * mm
    for entry in yearly_data.get("months", []):
        c.showPage()
        y = height - margin
        c.setFont(FONT_NAME, 14)
        c.drawString(margin, y, f"◆ {entry['label']}")
        y -= 8 * mm
        c.setFont(FONT_NAME, 12)
        for line in wrap(entry["text"], 45):
            c.drawString(margin, y, line)
            y -= 7 * mm

def draw_shincom_a4(c, data, include_yearly=False):
    """
    Draw the contents for normal fortune (shincom) PDF in A4 size.
    """
    width, height = A4
    margin = 20 * mm
    y = height - margin
    # Header with QR code
    y = draw_header(c, width, margin, y)
    # Palm image and birthdate
    y = draw_palm_image(c, data["palm_image"], width, y, birthdate=data.get("birthdate"))

    # Page 1: main palm lines
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

    # Start new page for rest of content
    c.showPage()
    y = height - margin
    # Page 2: remaining palm lines and fortunes
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

    # Four Pillars & summary sections
    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 36 if 'month' in key else 40
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['texts'][key], wrap_len):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # Lucky info and lucky direction at end of page 2
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    # Append yearly fortune pages if needed
    if include_yearly and data.get('yearly_fortunes'):
        draw_yearly_pages_shincom_a4(c, data['yearly_fortunes'])

def draw_shincom_b4(c, data, include_yearly=False):
    """
    Draw the contents for normal fortune (shincom) PDF in B4 size.
    """
    width, height = B4
    margin = 20 * mm
    y = height - margin
    # Header
    y = draw_header(c, width, margin, y)
    # Palm image and birthdate
    y = draw_palm_image(c, data["palm_image"], width, y, birthdate=data.get("birthdate"))

    # Page 1: main palm lines (B4 uses slightly larger wrap length)
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

    # New page for remaining content
    c.showPage()
    y = height - margin
    # Page 2: remaining palm lines and fortunes
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

    # Four Pillars & summary sections
    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 40 if 'month' in key else 45
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 7 * mm
        c.setFont(FONT_NAME, 12)
        for line in wrap(data['texts'][key], wrap_len):
            c.drawString(margin, y, line)
            y -= 7 * mm
        y -= 4 * mm
        c.setFont(FONT_NAME, 14)

    # Lucky info and direction (page 2)
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    if include_yearly and data.get('yearly_fortunes'):
        draw_yearly_pages_shincom_b4(c, data['yearly_fortunes'])

def draw_renai_pdf(c, data, size, include_yearly=False):
    """
    Draw the contents for love fortune (renai) PDF (A4 or B4).
    """
    from textwrap import wrap as wrap_text
    def wrap_lines(text, limit):
        lines = []
        for ln in text.splitlines():
            lines.extend(wrap_text(ln, limit))
        return lines

    width, height = A4 if size == 'a4' else B4
    margin = 20 * mm
    wrap_main = 40 if size == 'a4' else 45
    wrap_theme = 40 if size == 'a4' else 45

    y = draw_header(c, width, margin, height - margin)
    # Page 1: compatibility + year/month love fortunes
    main_keys = ["compatibility", "year_love", "month_love", "next_month_love"]
    c.setFont(FONT_NAME, 12)
    for key in main_keys:
        text = data["texts"].get(key, "").strip()
        if text:
            c.drawString(margin, y, f"◆ {data['titles'].get(key, key)}")
            y -= 6 * mm if size == 'a4' else 7 * mm
            c.setFont(FONT_NAME, 10 if size == 'a4' else 12)
            for line in wrap_lines(text, wrap_main):
                c.drawString(margin, y, line)
                y -= 6 * mm if size == 'a4' else 7 * mm
            y -= 4 * mm
            c.setFont(FONT_NAME, 12 if size == 'a4' else 14)

    c.showPage()
    y = height - margin
    # Page 2: love themes (3 topics)
    if data.get("themes"):
        c.setFont(FONT_NAME, 12 if size == 'a4' else 14)
        for section in data["themes"]:
            title = section.get("title", "")
            content = section.get("content", "")
            if title and content:
                c.drawString(margin, y, f"◆ {title}")
                y -= 6 * mm if size == 'a4' else 7 * mm
                c.setFont(FONT_NAME, 10 if size == 'a4' else 12)
                for line in wrap_lines(content, wrap_theme):
                    c.drawString(margin, y, line)
                    y -= 6 * mm if size == 'a4' else 7 * mm
                y -= 4 * mm
                c.setFont(FONT_NAME, 12 if size == 'a4' else 14)

    # Lucky info & direction (bottom of page 2)
    y = draw_lucky_section(c, width, margin, y, data.get("lucky_info", []), data.get("lucky_direction", ""))

    # If yearly option, add pages for yearly love fortunes
    if include_yearly and data.get("yearly_love_fortunes"):
        if size == 'a4':
            draw_yearly_pages_renai_a4(c, data["yearly_love_fortunes"])
        else:
            draw_yearly_pages_renai_b4(c, data["yearly_love_fortunes"])

def create_pdf_unified(filepath, data, mode, size='a4', include_yearly=False):
    """
    Unified PDF generation: creates a PDF file at the given filepath for the specified mode.
    mode = 'shincom' (normal fortune) or 'renai' (love fortune).
    size = 'a4' or 'b4'.
    """
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
