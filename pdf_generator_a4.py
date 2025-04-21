import base64
import os
from reportlab.lib.pagesizes import A4
from datetime import datetime
from reportlab.pdfgen import canvas
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
    filepath = os.path.join("static", filename)  # ここを修正
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 15 * mm
    font = FONT_NAME
    wrapper = textwrap.TextWrapper(width=50)

    y_pos = height - margin


    # QR広告
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
        y_pos -= 50 * mm

    # 手相画像
    image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",", 1)[1]))
    c.drawImage(image_path, (width - 150 * mm) / 2, y_pos - 90 * mm, width=150 * mm, height=90 * mm)
    y_pos -= 100 * mm

    # 手相のテキスト整理
    palm_parts = [p.strip() for p in palm_result.split("\n") if p.strip()]
    advice_index = -1
    for i in reversed(range(len(palm_parts))):
        if "まとめ" in palm_parts[i] or "総合" in palm_parts[i]:
            advice_index = i
            break
    if advice_index != -1:
        advice_text = "\n".join(palm_parts[advice_index + 1:])
        main_parts = palm_parts[:advice_index]
    else:
        advice_text = ""
        main_parts = palm_parts

    # 手相鑑定（5項目）
    text = c.beginText(margin, y_pos)
    text.setFont(font, 11)
    text.textLine("■ 手相鑑定（5項目）")
    text.textLine("")
    for paragraph in main_parts:
        for line in wrapper.wrap(paragraph):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    # 裏面
    c.showPage()
    text = c.beginText(margin, height - margin)
    text.setFont(font, 11)

    # 総合アドバイス
    if advice_text:
        text.textLine("■ 手相からの総合的なアドバイス")
        text.textLine("")
        for line in wrapper.wrap(advice_text.strip()):
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

    # ラッキー項目
    text.textLine("■ ラッキーアイテム・カラー・ナンバー")
    text.textLine("")
    for line in lucky_info.split("\n"):
        for wrapped in wrapper.wrap(line):
            text.textLine(wrapped)
    c.drawText(text)

    # QRコード広告（裏面）
    qr_path = create_qr_code(get_affiliate_link())
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width - margin - 30 * mm, margin, width=30 * mm, height=30 * mm)
        c.setFont(font, 10)
        c.drawString(margin, margin + 10 * mm, "📱 ラッキーアイテムはこちらから →")
        c.drawString(margin, margin, get_affiliate_link())

    c.save()
    return filepath
