# pdf_generator_aura.py

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import base64
import os

# IPAフォント登録（必要）
FONT_PATH = "ipaexg.ttf"
FONT_NAME = "IPAexGothic"

if not FONT_NAME in pdfmetrics.getRegisteredFontNames():
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
    else:
        raise FileNotFoundError("日本語フォント ipaexg.ttf が見つかりません。")

def create_aura_pdf(output_path, merged_image_data_base64, result_text):
    """
    オーラPDFを生成（A4縦1ページ：上部に合成画像、下部に診断テキスト）
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # ----------------------------
    # 合成画像（上半分）
    # ----------------------------
    try:
        # base64デコード
        img_data = base64.b64decode(merged_image_data_base64.split(",")[-1])
        image = ImageReader(BytesIO(img_data))

        image_width = width - 40 * mm
        image_height = height / 2 - 20 * mm
        x = 20 * mm
        y = height - image_height - 20 * mm

        c.drawImage(image, x, y, width=image_width, height=image_height, preserveAspectRatio=True)

    except Exception as e:
        c.setFont(FONT_NAME, 12)
        c.drawString(20 * mm, height - 30 * mm, f"画像読み込みエラー：{e}")

    # ----------------------------
    # 鑑定テキスト（下半分）
    # ----------------------------
    c.setFont(FONT_NAME, 12)
    textobject = c.beginText()
    textobject.setTextOrigin(20 * mm, height / 2 - 30 * mm)
    textobject.setLeading(16)

    for line in result_text.splitlines():
        textobject.textLine(line.strip())

    c.drawText(textobject)

    # 保存
    c.showPage()
    c.save()
