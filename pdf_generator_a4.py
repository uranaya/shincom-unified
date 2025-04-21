
import base64
import os
from reportlab.lib.pagesizes import A4
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
from PIL import Image
from io import BytesIO
import textwrap
from affiliate import create_qr_code, get_affiliate_link

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def compress_base64_image(base64_image_data, output_width=600):
    image_data = base64.b64decode(base64_image_data.split(",", 1)[1])
    image = Image.open(BytesIO(image_data))
    w_percent = output_width / float(image.size[0])
    h_size = int((float(image.size[1]) * float(w_percent)))
    image = image.resize((output_width, h_size), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    compressed_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{compressed_base64}"

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    filepath = os.path.join("static", filename)
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 15 * mm
    font = FONT_NAME
    font_size = 11
    wrapper = textwrap.TextWrapper(width=45)
    y = height - margin

    # 圧縮付き画像保存（明示的に600px指定）
    try:
        image_data = compress_base64_image(image_data, output_width=600)
        image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        with open(image_path, "wb") as f:
            base64_data = image_data.split(",", 1)[1]
            f.write(base64.b64decode(base64_data))
    except Exception as e:
        print("❌ 画像保存エラー:", e)
        image_path = None

    # 手相5項目分割
    palm_parts = [p.strip() for p in palm_result.split("\n") if p.strip()]
    sections = []
    buffer = []
    for line in palm_parts:
        if any(line.startswith(f"{i}.") for i in range(1, 6)):
            if buffer:
                sections.append("\n".join(buffer))
                buffer = []
        buffer.append(line)
    if buffer:
        sections.append("\n".join(buffer))
    first_parts = sections[:3]
    back_parts = sections[3:5]

    # 表面
    qr_ad_path = create_qr_code("https://uranaya.jp", path="qr_uranaya.png")
    y_pos = y
    if os.path.exists(qr_ad_path):
        c.drawImage(qr_ad_path, width - margin - 30 * mm, y_pos - 30 * mm, width=30 * mm, height=30 * mm)
        ad_text = c.beginText(margin, y_pos - 10)
        ad_text.setFont(font, 11)
        ad_text.textLine("───────── シン・コンピューター占い ─────────")
        ad_text.textLine("手相・四柱推命・イーチン占いで未来をサポート")
        ad_text.textLine("Instagram → @uranaya_official")
        ad_text.textLine("────────────────────────────")
        c.drawText(ad_text)
        y -= 50 * mm

    if image_path:
        c.drawImage(image_path, (width - 150 * mm) / 2, y - 90 * mm, width=150 * mm, height=90 * mm)
        y -= 100 * mm

    text = c.beginText(margin, y)
    text.setFont(font, font_size)
    text.textLine("■ 手相鑑定（代表3項目）")
    text.textLine("")
    for part in first_parts:
        for line in wrapper.wrap(part):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    # 裏面
    c.showPage()
    y = height - margin
    text = c.beginText(margin, y)
    text.setFont(font, font_size)

    if back_parts:
        text.textLine("■ 手相鑑定（4〜5項目目）")
        text.textLine("")
        for part in back_parts:
            for line in wrapper.wrap(part):
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
        for wrapped in wrapper.wrap(line.strip()):
            text.textLine(wrapped)

    c.drawText(text)
    c.save()
    return filepath
