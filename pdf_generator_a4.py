import os
import base64
import textwrap
from datetime import datetime
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from affiliate import create_qr_code, get_affiliate_link
from fortune_logic import generate_fortune
from kyusei_utils import get_kyusei_fortune
from kyusei_utils import get_kyusei_fortune_openai as get_kyusei_fortune
from yearly_fortune_utils import generate_yearly_fortune  # ←必要
from PyPDF2 import PdfMerger  # ←冒頭で

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def _draw_block(c, title, body, y):
    c.setFont(FONT_NAME, 12)
    c.drawString(10 * mm, y, title)
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    for line in textwrap.wrap(body, 45):
        c.drawString(10 * mm, y, line)
        y -= 5 * mm
    y -= 4 * mm
    return y

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename, birthdate=None):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFont(FONT_NAME, 12)

    c.drawImage("banner.jpg", 0, 282 * mm, width=210 * mm, height=30 * mm)

    if image_data:
        image_binary = base64.b64decode(image_data.split(",")[1])
        image = ImageReader(BytesIO(image_binary))
        c.drawImage(image, 35 * mm, 140 * mm, width=140 * mm, height=105 * mm)

    c.setFont(FONT_NAME, 10)
    text = c.beginText(10 * mm, 135 * mm)
    wrapper = textwrap.TextWrapper(width=45)

    text.textLine("■ 手相鑑定結果")
    text.textLine("")
    for line in palm_result.split("\n"):
        for wrapped in wrapper.wrap(line.strip()):
            text.textLine(wrapped)
    c.drawText(text)
    c.showPage()

    c.setFont(FONT_NAME, 10)
    text = c.beginText(10 * mm, 282 * mm)

    text.textLine("■ 四柱推命：性格と今月・来月の運勢")
    text.textLine("")
    for line in shichu_result.split("\n"):
        for wrapped in wrapper.wrap(line.strip()):
            text.textLine(wrapped)

    text.textLine("")
    text.textLine("■ 易占いアドバイス")
    text.textLine("")
    for line in iching_result.split("\n"):
        for wrapped in wrapper.wrap(line.strip()):
            text.textLine(wrapped)

    text.textLine("")
    text.textLine("■ ラッキーアイテム・カラー・ナンバー")
    text.textLine("")
    for line in lucky_info.split("\n"):
        for wrapped in wrapper.wrap(line.strip()):
            text.textLine(wrapped)

    try:
        if birthdate:
            y, m, d = map(int, birthdate.split("-"))
            fortune_text = get_kyusei_fortune(y, m, d)
        else:
            fortune_text = "生年月日が未指定のため取得できませんでした"
    except Exception as e:
        print("❌ 方位取得失敗:", e)
        fortune_text = "取得できませんでした"

    text.textLine("")
    text.textLine("■ 吉方位（九星気学より）")
    text.textLine(fortune_text)

    c.drawText(text)
    c.save()

    with open(f"static/{filename}", "wb") as f:
        f.write(buffer.getvalue())

    return f"static/{filename}"

def create_pdf_yearly(birthdate: str, filename: str):
    now = datetime.now()
    data = generate_yearly_fortune(birthdate, now)

    c = canvas.Canvas(f"static/{filename}", pagesize=A4)
    c.setFont(FONT_NAME, 12)

    c.drawImage("banner.jpg", 0, 282 * mm, width=210 * mm, height=30 * mm)
    y = 270 * mm
    y = _draw_block(c, data["year_label"], data["year_text"], y)
    for m in data["months"][:4]:
        y = _draw_block(c, m["label"], m["text"], y)

    c.showPage()
    y = 282 * mm
    for m in data["months"][4:]:
        y = _draw_block(c, m["label"], m["text"], y)

    c.save()
<<<<<<< HEAD

def create_pdf_combined(image_data, birthdate, filename):
    file_front = f"front_{filename}"
    file_year = f"year_{filename}"

    palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)

    create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, file_front, birthdate)
    create_pdf_yearly(birthdate, file_year)

    merger = PdfMerger()
    merger.append(file_front)
    merger.append(file_year)
    merger.write(f"static/{filename}")
    merger.close()

    return f"static/{filename}"

create_pdf_a4 = create_pdf
=======
    return filepath

def create_pdf_yearly(birthdate: str, filename: str):
    data = generate_yearly_fortune(birthdate, datetime.now())

    pdf = canvas.Canvas(filename, pagesize=A4)
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

    y = 280 * mm
    wrapper = textwrap.TextWrapper(width=40)

    # 年運
    pdf.setFont(FONT_NAME, 12)
    pdf.drawString(10*mm, y, data["year_label"])
    y -= 6*mm
    pdf.setFont(FONT_NAME, 10)
    for line in wrapper.wrap(data["year_text"]):
        pdf.drawString(10*mm, y, line)
        y -= 5*mm
    y -= 4*mm

    # 1〜4月
    for m in data["months"][:4]:
        pdf.setFont(FONT_NAME, 12)
        pdf.drawString(10*mm, y, m["label"])
        y -= 6*mm
        pdf.setFont(FONT_NAME, 10)
        for line in wrapper.wrap(m["text"]):
            pdf.drawString(10*mm, y, line)
            y -= 5*mm
        y -= 4*mm

    pdf.showPage()
    y = 280 * mm

    # 5〜12月
    for m in data["months"][4:]:
        pdf.setFont(FONT_NAME, 12)
        pdf.drawString(10*mm, y, m["label"])
        y -= 6*mm
        pdf.setFont(FONT_NAME, 10)
        for line in wrapper.wrap(m["text"]):
            pdf.drawString(10*mm, y, line)
            y -= 5*mm
        y -= 4*mm

    pdf.save()
    return filename

def create_pdf_combined(image_data: str, birthdate: str, filename: str):
    file_front = f"front_{filename}"
    file_year = f"year_{filename}"

    # 既存2ページ（表裏）
    palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
    create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, file_front)

    # 年運+月運2ページ
    create_pdf_yearly(birthdate, file_year)

    # 合体
    merger = PdfMerger()
    merger.append(file_front)
    merger.append(file_year)
    output_path = f"static/{filename}"
    merger.write(output_path)
    merger.close()

    # 中間ファイル削除（任意）
    os.remove(file_front)
    os.remove(file_year)

    return output_path
>>>>>>> c97330d (Fix: handle month=0 as annual in get_directions prompt)
