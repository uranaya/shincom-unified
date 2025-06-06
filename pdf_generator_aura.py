from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import base64
from io import BytesIO

# --- フォント設定 ---
FONT_PATH = os.path.join("static", "ipaexg.ttf")
FONT_NAME = "IPAexGothic"

if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_aura_pdf(output_path: str, image_base64: str, result_text: str):
    """
    オーラ鑑定PDFを生成（画像＋解説文）
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # ヘッダー
    c.setFont(FONT_NAME, 16)
    c.drawCentredString(width / 2, height - 50, "オーラ鑑定書")

    # 合成画像をデコードして描画
    try:
        image_data = base64.b64decode(image_base64.split(",")[-1])
        image = ImageReader(BytesIO(image_data))
        c.drawImage(image, x=50, y=height - 370, width=460, height=256)
    except Exception as e:
        c.setFont(FONT_NAME, 12)
        c.drawString(50, height - 400, f"画像表示エラー: {e}")

    # 結果テキストを折り返し描画
    c.setFont(FONT_NAME, 11)
    textobject = c.beginText(50, height - 400 - 40)
    textobject.setFont(FONT_NAME, 11)

    max_chars_per_line = 40
    lines = result_text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            textobject.textLine("")
            continue
        while len(line) > max_chars_per_line:
            textobject.textLine(line[:max_chars_per_line])
            line = line[max_chars_per_line:]
        textobject.textLine(line)

    c.drawText(textobject)
    c.showPage()
    c.save()
