import base64
import os
import re
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

def compress_base64_image(base64_image_data, output_width=400):
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

    # 画像保存（圧縮付き）
    try:
        image_data = compress_base64_image(image_data)
        image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        with open(image_path, "wb") as f:
            base64_data = image_data.split(",", 1)[1]
            f.write(base64.b64decode(base64_data))
    except Exception as e:
        print("❌ 画像保存エラー:", e)
        image_path = None

    # 手相の項目とアドバイスを分離
    sections = re.split(r"\*\*\s*\d\.\s*", palm_result)
    sections = [s.strip() for s in sections if s.strip()]
    main_parts = sections[:5] if len(sections) >= 5 else sections
    advice_match = re.search(r"\*\*総合的なアドバイス\*\*(.*)", palm_result, re.DOTALL)
    advice_part = advice_match.group(1).strip() if advice_match else ""

    front_parts = main_parts[:3]
    back_parts = main_parts[3:]

    # === 表面 ===
    # QR広告（右上）
    y_pos = y
    qr_ad_path = create_qr_code("https://uranaya.jp", path="qr_uranaya.png")
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

    # 手相画像
    if image_path:
        c.drawImage(image_path, (width - 150 * mm) / 2, y - 90 * mm, width=150 * mm, height=90 * mm)
        y -= 100 * mm

    # 手相1〜3
    text = c.beginText(margin, y)
    text.setFont(font, font_size)
    text.textLine("■ 手相鑑定（代表3項目）")
    text.textLine("")
    for part in front_parts:
        for line in wrapper.wrap(part):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    # === 裏面 ===
    c.showPage()
    y = height - margin
    text = c.beginText(margin, y)
    text.setFont(font, font_size)

    # 手相4〜5項目
    if back_parts:
        text.textLine("■ 手相鑑定（4〜5項目目）")
        text.textLine("")
        for part in back_parts:
            for line in wrapper.wrap(part):
                text.textLine(line)
            text.textLine("")

    # 総合的なアドバイス
    if advice_part:
        text.textLine("■ 手相からの総合的なアドバイス")
        text.textLine("")
        for line in wrapper.wrap(advice_part):
            text.textLine(line)
        text.textLine("")

    # 四柱推命
    text.textLine("■ 四柱推命によるアドバイス")
    text.textLine("")
    for paragraph in shichu_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    # イーチン占い
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
    c.save()
    return filepath
