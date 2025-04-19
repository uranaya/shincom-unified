from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
import textwrap
import os
import base64
from datetime import datetime

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
if not os.path.exists(FONT_PATH):
    raise FileNotFoundError("日本語フォント ipaexg.ttf が見つかりません。")
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    filepath = os.path.join("static", filename)
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - margin

    def draw_wrapped(title, text, y):
        c.setFont(FONT_NAME, 14)
        c.drawString(margin, y, f"【{title}】")
        y -= 16
        c.setFont(FONT_NAME, 11)
        lines = textwrap.wrap(text, 50)
        for line in lines:
            c.drawString(margin, y, line)
            y -= 14
        y -= 10
        return y

    # 手相画像のデコードと描画
    try:
        base64_data = image_data.split(",")[1]
        image_binary = base64.b64decode(base64_data)
        image = ImageReader(io.BytesIO(image_binary))
        img_width = width - 2 * margin
        img_height = img_width * 0.6
        c.drawImage(image, margin, y - img_height, width=img_width, height=img_height)
        y -= img_height + 20
    except Exception as e:
        y = draw_wrapped("画像読み込みエラー", str(e), y)

    # 四柱推命の抽出と描画
    def extract_section(text, start_marker, end_marker):
        try:
            return text.split(start_marker)[1].split(end_marker)[0].strip()
        except IndexError:
            return "(このセクションは取得できませんでした)"

    seikaku = extract_section(shichu_result, "■ 性格", "■ 今月の運勢")
    kongetsu = extract_section(shichu_result, "■ 今月の運勢", "■ 来月の運勢")
    raigetsu = shichu_result.split("■ 来月の運勢")[-1].strip() if "■ 来月の運勢" in shichu_result else "(来月の運勢が取得できませんでした)"

    y = draw_wrapped("性格", seikaku, y)
    y = draw_wrapped("今月の運勢", kongetsu, y)
    y = draw_wrapped("来月の運勢", raigetsu, y)
    y = draw_wrapped("易占い", iching_result, y)
    y = draw_wrapped("ラッキー情報", lucky_info, y)

    c.save()
    return filepath
