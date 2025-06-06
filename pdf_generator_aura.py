# pdf_generator_aura.py

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from PIL import Image
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

def create_aura_pdf(output_path, image_base64, result_text):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # 🖼 base64 → PIL Image
    image_data = base64.b64decode(image_base64.split(",")[-1])
    image = Image.open(BytesIO(image_data)).convert("RGB")

    # 保存しておいて PDF に貼り付け
    temp_image_path = "/tmp/temp_aura.jpg"
    image.save(temp_image_path)

    # 📎 画像を貼り付け（サイズ調整含む）
    c.drawImage(temp_image_path, 50, height - 300, width=500, height=200)

    # ✏️ テキスト部分
    textobject = c.beginText(50, height - 330)
    textobject.setFont("HeiseiKakuGo-W5", 12)  # または ipaexg.ttf を使っているなら pdfmetrics 登録済で
    for line in result_text.split("\n"):
        textobject.textLine(line)
    c.drawText(textobject)

    c.showPage()
    c.save()

def split_text(text, max_chars=40):
    """長すぎる行を改行するユーティリティ"""
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]