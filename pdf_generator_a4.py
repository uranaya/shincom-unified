
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import base64
import io
import os
import textwrap
from datetime import datetime

# フォント登録
FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    os.makedirs("static", exist_ok=True)
    filepath = os.path.join("static", filename)
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - margin

    c.setFont(FONT_NAME, 14)
    c.drawString(margin, y, "鑑定結果PDF")
    y -= 10 * mm

    try:
        # バナー（上部）
        if os.path.exists("banner.jpg"):
            banner = ImageReader("banner.jpg")
            c.drawImage(banner, margin, y - 20 * mm, width - 2 * margin, 20 * mm, preserveAspectRatio=True, mask='auto')
        y -= 25 * mm

        # 手相画像
        if image_data.startswith("data:image"):
            header, encoded = image_data.split(",", 1)
            image = ImageReader(io.BytesIO(base64.b64decode(encoded)))
            c.drawImage(image, margin + 30 * mm, y - 70 * mm, width=110 * mm, height=70 * mm, preserveAspectRatio=True, mask='auto')
        y -= 75 * mm
    except Exception as e:
        c.drawString(margin, y, f"[画像読み込みエラー]")
        y -= 10 * mm

    c.setFont(FONT_NAME, 10)

    def draw_wrapped(title, content, y):
        c.setFont(FONT_NAME, 11)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        lines = textwrap.wrap(content, 50)
        for line in lines:
            c.drawString(margin, y, line)
            y -= 5 * mm
        y -= 4 * mm
        return y

    y = draw_wrapped("手相鑑定（5項目）", palm_result, y)

    if "■ 今月の運勢" in shichu_result and "■ 来月の運勢" in shichu_result:
        seikaku = shichu_result.split("■ 今月の運勢")[0].replace("■ 性格", "").strip()
        kongetsu = shichu_result.split("■ 今月の運勢")[1].split("■ 来月の運勢")[0].strip()
        raigetsu = shichu_result.split("■ 来月の運勢")[1].strip()
    else:
        seikaku = kongetsu = raigetsu = "取得できませんでした"

    y = draw_wrapped("性格", seikaku, y)
    y = draw_wrapped("今月の運勢", kongetsu, y)
    y = draw_wrapped("来月の運勢", raigetsu, y)
    y = draw_wrapped("易占い", iching_result, y)
    y = draw_wrapped("ラッキー情報", lucky_info.replace("\n", " ").replace("\", ""), y)

    c.save()
    return filepath
