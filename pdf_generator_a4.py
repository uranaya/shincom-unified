from pathlib import Path
from datetime import datetime
import os
import textwrap
import base64
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import B4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    filename = os.path.join("static", filename)
    c = canvas.Canvas(filename, pagesize=B4)
    width, height = B4
    margin = 20 * mm
    wrapper = textwrap.TextWrapper(width=50)
    font = FONT_NAME

    y = height - margin

    image_path = os.path.join("static", f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",", 1)[1]))
    c.drawImage(image_path, (width - 150 * mm) / 2, y - 90 * mm, width=150 * mm, height=90 * mm)
    y -= 100 * mm

    palm_parts = [p.strip() for p in palm_result.split("\n") if p.strip()]
    advice_index = -1
    for i in reversed(range(len(palm_parts))):
        if "まとめ" in palm_parts[i] or "総合" in palm_parts[i]:
            advice_index = i
            break
    advice_text = "\n".join(palm_parts[advice_index + 1:]) if advice_index != -1 else ""
    main_parts = palm_parts[:advice_index] if advice_index != -1 else palm_parts

    text = c.beginText(margin, y)
    text.setFont(font, 11)
    text.textLine("■ 手相鑑定（5項目）")
    text.textLine("")
    for paragraph in main_parts:
        for line in wrapper.wrap(paragraph):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    c.showPage()
    text = c.beginText(margin, height - margin)
    text.setFont(font, 11)

    if advice_text:
        text.textLine("■ 手相からの総合的なアドバイス")
        text.textLine("")
        for line in wrapper.wrap(advice_text.strip()):
            text.textLine(line)
        text.textLine("")

    text.textLine("■ 四柱推命によるアドバイス")
    text.textLine("")
    for paragraph in shichu_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    text.textLine("■ イーチン占い アドバイス")
    text.textLine("")
    for paragraph in iching_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    text.textLine("■ ラッキーアイテム・カラー・ナンバー")
    text.textLine("")
    for line in lucky_info.split("\n"):
        for wrapped in wrapper.wrap(line):
            text.textLine(wrapped)

    c.drawText(text)
    c.save()
    return filename
