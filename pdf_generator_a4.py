
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

pdfmetrics.registerFont(TTFont("IPAexGothic", "ipaexg.ttf"))

def create_qr_code(url, path="qr_affiliate.png"):
    img = qrcode.make(url)
    img.save(path)
    return path

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    c = canvas.Canvas(f"static/{filename}", pagesize=A4)
    width, height = A4
    margin = 20 * mm
    wrapper = textwrap.TextWrapper(width=50)
    font = "IPAexGothic"

    y = height - margin

    # 手相画像
    image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",")[1]))
    c.drawImage(image_path, (width - 120 * mm) / 2, y - 90 * mm, width=120 * mm, height=90 * mm)
    y -= 100 * mm

    # 手相結果
    text = c.beginText(margin, y)
    text.setFont(font, 11)
    text.textLine("■ 手相鑑定結果")
    text.textLine("")
    for paragraph in palm_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    # 次ページへ
    c.showPage()
    text = c.beginText(margin, height - margin)
    text.setFont(font, 11)

    # 四柱推命
    text.textLine("■ 四柱推命によるアドバイス")
    text.textLine("")
    for paragraph in shichu_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    # イーチン
    text.textLine("■ イーチン占い アドバイス")
    text.textLine("")
    for paragraph in iching_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    # ラッキー項目
    text.textLine("■ ラッキーアイテム・カラー・ナンバー")
    text.textLine("")
    for line in lucky_info.split("\n"):
        for wrapped in wrapper.wrap(line):
            text.textLine(wrapped)
    c.drawText(text)

    # QRコード
    qr_path = create_qr_code("https://uranaya.jp")
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width - margin - 30 * mm, margin, width=30 * mm, height=30 * mm)
        c.setFont(font, 10)
        c.drawString(margin, margin + 10 * mm, "📱 ラッキーアイテムはこちらから →")
        c.drawString(margin, margin, "https://uranaya.jp")

    c.save()
    return f"static/{filename}"
