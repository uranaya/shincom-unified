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
from header_utils import draw_header  # selfmobと同様


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

def create_aura_pdf(output_path, image_base64: str, text: str):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # 1. ヘッダー描画
    draw_header(c, "オーラ・前世・守護霊鑑定書", FONT_NAME)

    # 2. 合成画像描画（中央やや上に配置）
    img_data = base64.b64decode(image_base64.split(",")[-1])
    img_reader = ImageReader(BytesIO(img_data))
    image_width = 460
    image_height = 140
    x = (width - image_width) / 2
    y = height - 180
    c.drawImage(img_reader, x, y, width=image_width, height=image_height)

    # 3. テキスト描画（余白を詰めて配置）
    c.setFont(FONT_NAME, 11)
    textobject = c.beginText(50, y - 20)
    lines = text.split("\n")
    for line in lines:
        for sub in split_text(line, max_chars=40):
            textobject.textLine(sub)
    c.drawText(textobject)

    c.showPage()
    c.save()

    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

def split_text(text, max_chars=40):
    """長すぎる行を改行するユーティリティ"""
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]