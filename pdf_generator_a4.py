from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from datetime import datetime
import base64
import os
import textwrap
import qrcode

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_qr_code(url, path="qr_affiliate.png"):
    img = qrcode.make(url)
    img.save(path)
    return path

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    wrapper = textwrap.TextWrapper(width=50)
    font = FONT_NAME
    y = height - margin

    # 表面：手相鑑定
    text = c.beginText(margin, y)
    text.setFont(font, 11)
    text.textLine("■ 手相鑑定（5項目）")
    text.textLine("")

    for line in palm_result.strip().split("\n"):
        for wrapped in wrapper.wrap(line):
            text.textLine(wrapped)
        text.textLine("")
    c.drawText(text)

    # QR広告
    qr_path = create_qr_code("https://uranaya.jp")
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width - margin - 30 * mm, margin, width=30 * mm, height=30 * mm)

    c.showPage()

    # 裏面：占いなど
    y = height - margin
    text = c.beginText(margin, y)
    text.setFont(font, 11)

    text.textLine("■ 四柱推命アドバイス")
    text.textLine("")
    for line in wrapper.wrap(shichu_result.strip()):
        text.textLine(line)
    text.textLine("")

    text.textLine("■ イーチン占いアドバイス")
    text.textLine("")
    for line in wrapper.wrap(iching_result.strip()):
        text.textLine(line)
    text.textLine("")

    text.textLine("■ ラッキーアイテム・カラー・ナンバー")
    text.textLine("")
    for line in wrapper.wrap(lucky_info.strip().replace("\n", " ")):
        text.textLine(line)

    c.drawText(text)
    c.save()
    return filename