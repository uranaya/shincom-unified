from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
import os
import textwrap
from datetime import datetime
from io import BytesIO
import base64

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
if not os.path.exists(FONT_PATH):
    raise FileNotFoundError("フォントファイルが見つかりません: ipaexg.ttf")
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    if not os.path.exists("static"):
        os.makedirs("static")
    filepath = os.path.join("static", filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    line_height = 13
    max_chars = 50

    def draw_wrapped(title, text, y):
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= line_height
        for line in textwrap.wrap(text, max_chars):
            c.drawString(margin, y, line)
            y -= line_height
        y -= 5
        return y

    # 1ページ目
    banner_path = "banner.jpg"
    if os.path.exists(banner_path):
        banner = ImageReader(banner_path)
        c.drawImage(banner, margin, height - 60, width=width - 2 * margin, height=40, preserveAspectRatio=True, mask='auto')

    # palm image
    base64data = image_data.split(",")[1]
    imgdata = base64.b64decode(base64data)
    img = ImageReader(BytesIO(imgdata))
    img_width = width * 0.6
    c.drawImage(img, (width - img_width) / 2, height / 2, width=img_width, preserveAspectRatio=True, mask='auto')

    # palm_result
    y = height / 2 - 20
    c.setFont(FONT_NAME, 13)
    for line in textwrap.wrap(palm_result, max_chars):
        c.drawString(margin, y, line)
        y -= line_height
        if y < 50:
            c.showPage()
            y = height - margin

    c.showPage()

    # 2ページ目
    y = height - margin
    c.setFont(FONT_NAME, 14)
    c.drawString(margin, y, "【総合鑑定結果】")
    y -= 2 * line_height

    # 安全にセクション分け
    def extract_section(label, content, fallback="取得できませんでした"):
        try:
            parts = content.split(f"■ {label}")
            if len(parts) > 1:
                next_part = parts[1]
                next_label_index = next_part.find("■ ")
                if next_label_index != -1:
                    return next_part[:next_label_index].strip()
                else:
                    return next_part.strip()
        except Exception:
            pass
        return fallback

    # 四柱推命
    y = draw_wrapped("性格", extract_section("性格", shichu_result), y)
    y = draw_wrapped("今月の運勢", extract_section("今月の運勢", shichu_result), y)
    y = draw_wrapped("来月の運勢", extract_section("来月の運勢", shichu_result), y)

    # 易占い
    y = draw_wrapped("イーチン占い", iching_result, y)

    # ラッキー情報
    y = draw_wrapped("ラッキー情報", lucky_info, y)

    c.save()
    return filepath
