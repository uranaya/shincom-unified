from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from textwrap import wrap
import base64
import io

FONT_NAME = "ipaexg"
UPLOAD_FOLDER = "static/uploads"

def wrap_text(text, width=40):
    return "\n".join(wrap(text, width=width))

def draw_wrapped_text(c, text, x, y, max_width):
    lines = wrap(text, width=max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= 12
    return y

def draw_lucky_info(c, data, x, y):
    c.setFont(FONT_NAME, 11)
    for label, content in data.items():
        line = f"◆ {label}：{content}"
        lines = wrap(line, width=40)
        for l in lines:
            c.drawString(x, y, l)
            y -= 14
    return y

def draw_yearly_pages_shincom(c, texts):
    c.setFont(FONT_NAME, 13)
    c.drawString(25 * mm, 270 * mm, "◆ 1年分の運勢")
    y = 255 * mm
    c.setFont(FONT_NAME, 11)
    for text in texts:
        y = draw_wrapped_text(c, text, 25 * mm, y, 40)
        y -= 10  # 空行として
        if y < 50 * mm:
            c.showPage()
            c.setFont(FONT_NAME, 11)
            y = 270 * mm

def draw_shincom_b4(c, data, include_yearly):
    width, height = B4
    margin = 20 * mm
    y = height - 30 * mm

    # 1ページ目：手相画像
    c.setFont(FONT_NAME, 11)
    if data.get("image_data"):
        img_data = base64.b64decode(data["image_data"].split(",")[1])
        img = ImageReader(io.BytesIO(img_data))
        img_width = 130 * mm
        img_height = 100 * mm
        img_x = (width - img_width) / 2
        img_y = height - img_height - 50 * mm
        c.drawImage(img, img_x, img_y, width=img_width, height=img_height)

    c.showPage()
    c.setFont(FONT_NAME, 11)
    y = height - 30 * mm

    # 2ページ目：手相の総合アドバイスから開始
    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, "◆ 手相の総合アドバイス")
    y -= 14
    c.setFont(FONT_NAME, 11)
    y = draw_wrapped_text(c, data["texts"]["palm_summary"], margin, y, 40)
    y -= 12

    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, "◆ 性格診断")
    y -= 14
    c.setFont(FONT_NAME, 11)
    y = draw_wrapped_text(c, data["texts"]["personality"], margin, y, 40)
    y -= 12

    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, "◆ 今月の運勢")
    y -= 14
    c.setFont(FONT_NAME, 11)
    y = draw_wrapped_text(c, data["texts"]["month_fortune"], margin, y, 40)
    y -= 12

    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, "◆ 来月の運勢")
    y -= 14
    c.setFont(FONT_NAME, 11)
    y = draw_wrapped_text(c, data["texts"]["next_month_fortune"], margin, y, 40)
    y -= 12

    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, "◆ ラッキー情報")
    y -= 14
    c.setFont(FONT_NAME, 11)
    y = draw_lucky_info(c, data.get("lucky_info", {}), margin, y)

    if include_yearly:
        c.showPage()
        draw_yearly_pages_shincom(c, data.get("yearly_fortunes", []))

def create_pdf_unified(filepath, data, mode, size="B4", include_yearly=False):
    c = canvas.Canvas(filepath, pagesize=B4)
    if mode == "shincom":
        draw_shincom_b4(c, data, include_yearly)
    c.save()
