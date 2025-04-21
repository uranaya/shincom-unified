import base64
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import B4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import textwrap
from app import create_qr_code, get_affiliate_link

pdfmetrics.registerFont(TTFont("IPAexGothic", "ipaexg.ttf"))
font = "IPAexGothic"
wrapper = textwrap.TextWrapper(width=50)

def draw_wrapped(c, title, content, y, max_width):
    text = c.beginText(20 * mm, y)
    text.setFont(font, 11)
    text.textLine(f"■ {title}")
    text.textLine("")
    for line in content.split("\n"):
        for wrapped in wrapper.wrap(line.strip()):
            text.textLine(wrapped)
        text.textLine("")
    c.drawText(text)
    return text.getY()

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    filepath = os.path.join("static", filename)
    c = canvas.Canvas(filepath, pagesize=B4)
    width, height = B4

    y = height - 20 * mm

    # === QR広告 ===
    qr_path = create_qr_code(get_affiliate_link())
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width - 50 * mm, y - 30 * mm, width=30 * mm, height=30 * mm)
        ad = c.beginText(20 * mm, y)
        ad.setFont(font, 11)
        ad.textLine("───────── シン・コンピューター占い ─────────")
        ad.textLine("手相・四柱推命・イーチン占いで未来をサポート")
        ad.textLine("Instagram → @uranaya_official")
        ad.textLine("────────────────────────────")
        c.drawText(ad)
        y -= 50 * mm

    # === 手相画像 ===
    image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",", 1)[1]))
    c.drawImage(image_path, (width - 150 * mm) / 2, y - 90 * mm, width=150 * mm, height=90 * mm)
    y -= 100 * mm

    # === 手相鑑定文分離 ===
    palm_lines = [l.strip() for l in palm_result.split("\n") if l.strip()]
    advice_index = -1
    for i in reversed(range(len(palm_lines))):
        if "まとめ" in palm_lines[i] or "総合" in palm_lines[i]:
            advice_index = i
            break
    if advice_index != -1:
        main_palm = "\n".join(palm_lines[:advice_index])
        palm_advice = "\n".join(palm_lines[advice_index:])
    else:
        main_palm = "\n".join(palm_lines)
        palm_advice = ""

    # === 手相5項目 ===
    y = draw_wrapped(c, "手相鑑定（5項目）", main_palm, y, width - 40 * mm)

    # === 裏面へ ===
    c.showPage()
    y = height - 20 * mm

    # === 手相まとめ ===
    if palm_advice.strip():
        y = draw_wrapped(c, "手相からの総合的なアドバイス", palm_advice, y, width - 40 * mm)

    # === 四柱推命 ===
    y = draw_wrapped(c, "四柱推命によるアドバイス", shichu_result, y, width - 40 * mm)

    # === イーチン ===
    y = draw_wrapped(c, "イーチン占いアドバイス", iching_result, y, width - 40 * mm)

    # === ラッキー項目 ===
    y = draw_wrapped(c, "ラッキーアイテム・カラー・ナンバー", lucky_info, y, width - 40 * mm)

    # === 裏面のQRコード再掲 ===
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width - 50 * mm, 20 * mm, width=30 * mm, height=30 * mm)
        c.setFont(font, 10)
        c.drawString(20 * mm, 25 * mm, "📱 ラッキーアイテムはこちら →")
        c.drawString(20 * mm, 20 * mm, get_affiliate_link())

    c.save()
    return filepath
