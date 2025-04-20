from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
import os
import io
import base64
import textwrap
from datetime import datetime
from PIL import Image

# フォント設定
FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
if not os.path.exists(FONT_PATH):
    raise FileNotFoundError("日本語フォント ipaexg.ttf が見つかりません。")
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

# テキスト描画関数（段組処理付き）
def draw_wrapped(c, title, text, y, max_width):
    c.setFont(FONT_NAME, 14)
    c.drawString(20 * mm, y, f"■ {title}")
    y -= 7
    c.setFont(FONT_NAME, 12)
    lines = textwrap.wrap(text, width=50)
    for line in lines:
        c.drawString(20 * mm, y, line)
        y -= 6
    y -= 4
    return y

# PDF作成本体
def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    output_path = os.path.join("static", filename)
    os.makedirs("static", exist_ok=True)

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    y = height - 20 * mm

    c.setFont(FONT_NAME, 16)
    c.drawString(20 * mm, y, "【手相鑑定結果】")
    y -= 10 * mm

    if image_data.startswith("data:image"):
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image.thumbnail((int(width - 40 * mm), 1000))
        img_io = io.BytesIO()
        image.save(img_io, format="PNG")
        img_io.seek(0)
        c.drawImage(ImageReader(img_io), 30 * mm, y - image.height, width=image.width, height=image.height)
        y -= image.height + 10

    y = draw_wrapped(c, "手相の特徴とアドバイス", palm_result.replace("\n", " "), y, 450)
    c.showPage()

    y = height - 20 * mm
    c.setFont(FONT_NAME, 16)
    c.drawString(20 * mm, y, "【総合鑑定結果】")
    y -= 10 * mm

    if "■" in shichu_result:
        try:
            seikaku = shichu_result.split("■ 今月の運勢")[0].replace("■ 性格", "").strip()
            kongetsu = shichu_result.split("■ 今月の運勢")[1].split("■ 来月の運勢")[0].strip()
            raigetsu = shichu_result.split("■ 来月の運勢")[1].strip()
        except Exception:
            seikaku = kongetsu = raigetsu = "取得できませんでした"
    else:
        seikaku = kongetsu = raigetsu = "取得できませんでした"

    y = draw_wrapped(c, "性格", seikaku, y, 450)
    y = draw_wrapped(c, "今月の運勢", kongetsu, y, 450)
    y = draw_wrapped(c, "来月の運勢", raigetsu, y, 450)
    y = draw_wrapped(c, "イーチン占い", iching_result.replace("\n", " "), y, 450)
    y = draw_wrapped(c, "ラッキー情報", lucky_info.replace("\n", " ").replace("\"", "").replace("：", ":").strip(), y, 450)

    c.save()
    return output_path
