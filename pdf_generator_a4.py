import base64
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
import textwrap
from qr_code_generator import create_qr_code, get_affiliate_link

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    filepath = os.path.join("static", filename)
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 15 * mm
    font_size = 11
    font = FONT_NAME
    wrapper = textwrap.TextWrapper(width=45)

    # === 表面 ===
    y = height - margin

    # 手相画像中央寄せ
    image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",", 1)[1]))
    c.drawImage(image_path, (width - 130 * mm) / 2, y - 100 * mm, width=130 * mm, height=100 * mm)
    y -= 110 * mm

    # 手相項目分割（5項目 + アドバイス）
    palm_parts = [p.strip() for p in palm_result.split("\n") if p.strip()]
    sections = []
    buffer = []
    for line in palm_parts:
        if line.startswith("1.") or line.startswith("2.") or line.startswith("3.") or line.startswith("4.") or line.startswith("5."):
            if buffer:
                sections.append("\n".join(buffer))
                buffer = []
        buffer.append(line)
    if buffer:
        sections.append("\n".join(buffer))

    main_parts = sections[:4]
    fifth_part = sections[4] if len(sections) > 4 else ""

    # 表面：4項目描画
    text = c.beginText(margin, y)
    text.setFont(font, font_size)
    text.textLine("■ 手相鑑定（代表4項目）")
    text.textLine("")
    for part in main_parts:
        for line in wrapper.wrap(part):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    # QRコード広告（左下）
    qr_path = create_qr_code(get_affiliate_link())
    if os.path.exists(qr_path):
        c.drawImage(qr_path, margin, margin, width=30 * mm, height=30 * mm)

    c.showPage()

    # === 裏面 ===
    y = height - margin
    text = c.beginText(margin, y)
    text.setFont(font, font_size)

    # 手相5項目目
    if fifth_part:
        text.textLine("■ 手相鑑定（5項目目）")
        text.textLine("")
        for line in wrapper.wrap(fifth_part):
            text.textLine(line)
        text.textLine("")

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

    # ラッキー情報
    text.textLine("■ ラッキーアイテム・カラー・ナンバー")
    text.textLine("")
    for line in lucky_info.split("\n"):
        for wrapped in wrapper.wrap(line.strip()):
            text.textLine(wrapped)

    c.drawText(text)

    # 裏面にもQR
    if os.path.exists(qr_path):
        c.drawImage(qr_path, margin, margin, width=30 * mm, height=30 * mm)

    c.save()
    return filepath
