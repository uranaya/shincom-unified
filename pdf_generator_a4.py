from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
import textwrap
import os
import base64

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"

if not os.path.exists(FONT_PATH):
    raise FileNotFoundError("日本語フォント ipaexg.ttf が見つかりません。")

pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    filepath = os.path.join(os.getcwd(), filename)
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    # バナー画像
    if os.path.exists("banner.jpg"):
        banner = ImageReader("banner.jpg")
        c.drawImage(banner, 0, height - 30 * mm, width=width, height=30 * mm)

    # 手相画像
    base64_img = image_data.split(",")[1]
    img_bytes = base64.b64decode(base64_img)
    with open("temp_image.png", "wb") as f:
        f.write(img_bytes)
    image_reader = ImageReader("temp_image.png")
    c.drawImage(image_reader, (width - 80 * mm) / 2, height - 110 * mm, width=80 * mm, height=60 * mm)

    # 鑑定結果テキスト
    c.setFont(FONT_NAME, 10)
    y = height - 120 * mm
    line_width = 45

    def draw_wrapped(title, text, y):
        c.setFont(FONT_NAME, 11)
        c.drawString(20 * mm, y, f"■ {title}")
        y -= 5 * mm
        c.setFont(FONT_NAME, 10)
        for line in textwrap.wrap(text, line_width):
            c.drawString(20 * mm, y, line)
            y -= 5 * mm
        y -= 3 * mm
        return y

    y = draw_wrapped("手相の特徴", palm_result, y)
    y = draw_wrapped("性格", shichu_result.split("■ 今月の運勢")[0].replace("■ 性格", "").strip(), y)
    y = draw_wrapped("今月の運勢", shichu_result.split("■ 今月の運勢")[1].split("■ 来月の運勢")[0].strip(), y)
    y = draw_wrapped("来月の運勢", shichu_result.split("■ 来月の運勢")[1].strip(), y)
    y = draw_wrapped("易占い", iching_result, y)
    y = draw_wrapped("ラッキー情報", lucky_info, y)

    c.save()
    os.remove("temp_image.png")
    return filepath
