import base64
import os
import textwrap
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from app import create_qr_code, get_affiliate_link

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
if not os.path.exists(FONT_PATH):
    raise FileNotFoundError("日本語フォント ipaexg.ttf が見つかりません。")
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    save_path = os.path.join("static", filename)
    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    wrapper = textwrap.TextWrapper(width=50)
    font = FONT_NAME
    y = height - margin

    # バナー画像
    banner_path = "banner.jpg"
    if os.path.exists(banner_path):
        banner = ImageReader(banner_path)
        c.drawImage(banner, margin, y - 25 * mm, width=width - 2 * margin, height=20 * mm)
        y -= 30 * mm

    # 手相画像
    image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",", 1)[1]))
    c.drawImage(image_path, (width - 150 * mm) / 2, y - 90 * mm, width=150 * mm, height=90 * mm)
    y -= 100 * mm

    # 手相5項目とまとめの分離
    palm_lines = [line.strip() for line in palm_result.split("\n") if line.strip()]
    advice_index = -1
    for i in reversed(range(len(palm_lines))):
        if "まとめ" in palm_lines[i] or "総合" in palm_lines[i]:
            advice_index = i
            break
    if advice_index != -1:
        advice_text = "\n".join(palm_lines[advice_index + 1:])
        main_parts = palm_lines[:advice_index]
    else:
        advice_text = ""
        main_parts = palm_lines

    # 表面：手相5項目
    text = c.beginText(margin, y)
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

    def draw_wrapped(title, content):
        text.textLine(f"■ {title}")
        text.textLine("")
        for line in wrapper.wrap(content.strip()):
            text.textLine(line)
        text.textLine("")

    # 各パート分離処理
    if "■ 今月の運勢" in shichu_result and "■ 来月の運勢" in shichu_result:
        draw_wrapped("性格", shichu_result.split("■ 今月の運勢")[0].replace("性格：", "").strip())
        draw_wrapped("今月の運勢", shichu_result.split("■ 今月の運勢")[1].split("■ 来月の運勢")[0].strip())
        draw_wrapped("来月の運勢", shichu_result.split("■ 来月の運勢")[1].strip())
    else:
        draw_wrapped("四柱推命", shichu_result)

    draw_wrapped("イーチン占い", iching_result)
    draw_wrapped("ラッキー情報", lucky_info)
    draw_wrapped("手相まとめアドバイス", advice_text)

    # QRコード
    qr_path = create_qr_code(get_affiliate_link(), path="affiliate_qr.png")
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width - margin - 30 * mm, margin, width=30 * mm, height=30 * mm)
        c.setFont(font, 10)
        c.drawString(margin, margin + 10 * mm, "📱 ラッキーアイテムはこちらから →")
        c.drawString(margin, margin, get_affiliate_link())

    c.drawText(text)
    c.save()
    return save_path
