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
import textwrap

# フォント設定
FONT_PATH = "ipaexg.ttf"
FONT_NAME = "IPAexGothic"

if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
    else:
        raise FileNotFoundError("日本語フォント ipaexg.ttf が見つかりません。")

def draw_header(c, width, height):
    """
    ページ冒頭にタイトルを描画（selfmob準拠）
    """
    c.setFont(FONT_NAME, 16)
    c.drawCentredString(width / 2, height - 20 * mm, "🔮 オーラ・前世・守護霊鑑定書 🔮")

def wrap_text(text, max_chars):
    """
    テキストを max_chars 文字で折り返してリストで返す
    """
    lines = []
    for paragraph in text.splitlines():
        if paragraph.strip():
            wrapped = textwrap.wrap(paragraph.strip(), width=max_chars)
            lines.extend(wrapped)
        else:
            lines.append("")
    return lines

def create_aura_pdf(output_path, merged_image_data_base64, result_text):
    """
    オーラPDFを生成（A4縦1ページ：上部に合成画像、下部に折返しテキスト）
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # --- ヘッダー ---
    draw_header(c, width, height)

    # --- 合成画像 ---
    try:
        img_data = base64.b64decode(merged_image_data_base64.split(",")[-1])
        image = ImageReader(BytesIO(img_data))
        image_width = width - 40 * mm
        image_height = height / 2 - 30 * mm
        x = 20 * mm
        y = height - image_height - 30 * mm
        c.drawImage(image, x, y, width=image_width, height=image_height, preserveAspectRatio=True)
    except Exception as e:
        c.setFont(FONT_NAME, 12)
        c.drawString(20 * mm, height - 40 * mm, f"画像読み込みエラー：{e}")

    # --- 鑑定テキスト ---
    c.setFont(FONT_NAME, 12)
    textobject = c.beginText()
    textobject.setTextOrigin(20 * mm, height / 2 - 35 * mm)
    textobject.setLeading(16)

    wrapped_lines = wrap_text(result_text, max_chars=42)
    for line in wrapped_lines:
        textobject.textLine(line)

    c.drawText(textobject)

    # 保存
    c.showPage()
    c.save()
