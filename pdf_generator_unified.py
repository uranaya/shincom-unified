from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from textwrap import wrap
import base64
import io
import os
from datetime import datetime

from header_utils import draw_header
from lucky_utils import draw_lucky_section

from textwrap import wrap as _wrap

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))


def wrap(text, limit):
    return _wrap(text, limit)



def draw_lucky_section(c, width, margin, y, lucky_info):

    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "■ ラッキー情報（生年月日より）")
    y -= 8 * mm
    c.setFont(FONT_NAME, 10)

    if lucky_info:
        col_width = (width - 2 * margin) / 2
        x1 = margin + 10
        x2 = margin + 10 + col_width
        col = 0
        for item in lucky_info:
            if "：" in item:
                label, value = item.split("：", 1)
                label = label.replace("ラッキー", "").strip()
                item = f"{label}：{value.strip()}"
            x = x1 if col == 0 else x2
            c.drawString(x, y, item)
            if col == 1:
                y -= 6 * mm
            col = (col + 1) % 2
        if col == 1:
            y -= 6 * mm
    else:
        c.drawString(margin + 10, y, "情報が取得できませんでした。")
        y -= 6 * mm

    return y - 6 * mm






def draw_palm_image(c, base64_image, width, y, birthdate=None):

    from PIL import Image


    if not base64_image:
        return y

    try:
        image_data = base64.b64decode(base64_image.split(",")[1])
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((150 * mm, 100 * mm))
        img_io = io.BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)
        c.drawImage(ImageReader(img_io), width/2 - 75*mm, y - 100*mm, mask='auto')
        y -= 105 * mm

        if birthdate:
            c.setFont("IPAexGothic", 11)
            c.drawCentredString(width / 2, y, f"生年月日：{birthdate}")
            y -= 10 * mm
    except Exception as e:
        print("❌ draw_palm_image エラー:", e)

    return y





def draw_yearly_pages_shincom_a4(c, yearly):
    from reportlab.lib.units import mm
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(text or "", 46):
            c.drawString(margin, y, line)
            y -= 6 * mm
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
        y -= 4 * mm

    # ページ3：年運＋前半6か月
    c.showPage()
    y = height - 30 * mm
    draw_text_block(yearly["year_label"], yearly["year_text"])
    for month in yearly["months"][:6]:
        draw_text_block(month["label"], month["text"])

    # ページ4：後半6か月
    c.showPage()
    y = height - 30 * mm
    for month in yearly["months"][6:]:
        draw_text_block(month["label"], month["text"])


def draw_yearly_pages_shincom_b4(c, yearly):
    from reportlab.lib.units import mm
    width, height = B4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 11)
        from textwrap import wrap
        for line in wrap(text or "", 45):
            c.drawString(margin, y, line)
            y -= 7 * mm
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
        y -= 6 * mm

    # ページ3：年運＋前半6か月
    c.showPage()
    y = height - 30 * mm  # ← 必ず初期化
    draw_text_block(yearly["year_label"], yearly["year_text"])
    for month in yearly["months"][:6]:
        draw_text_block(month["label"], month["text"])

    # ページ4：後半6か月
    c.showPage()
    y = height - 30 * mm
    for month in yearly["months"][6:]:
        draw_text_block(month["label"], month["text"])




def draw_shincom_a4(c, data, include_yearly=False):
    from reportlab.lib.utils import ImageReader
    width, height = A4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)
    y = draw_palm_image(c, data["palm_image"], width, y)


    c.setFont(FONT_NAME, 12)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['palm_texts'][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    c.showPage()
    y = height - margin
    # ★ ヘッダーなし（2ページ目）

    c.setFont(FONT_NAME, 12)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['palm_texts'][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 36 if 'month' in key else 40
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['texts'][key], wrap_len):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # ラッキー情報を2ページ目末尾に移動
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    if include_yearly:
        draw_yearly_pages_shincom_a4(c, data['yearly_fortunes'])



def draw_shincom_b4(c, data, include_yearly=False):
    width, height = B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)
    y = draw_palm_image(c, data["palm_image"], width, y)

    c.setFont(FONT_NAME, 12)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['palm_texts'][i], 45):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    c.showPage()
    y = height - margin
    # ★ ヘッダーなし（2ページ目）

    c.setFont(FONT_NAME, 12)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['palm_texts'][i], 45):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 41 if 'month' in key else 45
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data['texts'][key], wrap_len):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # ラッキー情報を2ページ目末尾に移動
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    if include_yearly:
        draw_yearly_pages_shincom_b4(c, data['yearly_fortunes'])



def draw_yearly_pages_renai_a4(c, yearly):
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 5 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(text or "", 46):
            c.drawString(margin, y, line)
            y -= 5 * mm
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
        y -= 3 * mm

    c.showPage()
    y = height - 30 * mm
    draw_text_block(yearly["year_label"], yearly["year_text"])
    for month in yearly["months"][:6]:
        draw_text_block(month["label"], month["text"])

    c.showPage()
    y = height - 30 * mm
    for month in yearly["months"][6:]:
        draw_text_block(month["label"], month["text"])



def draw_yearly_pages_renai_b4(c, yearly):
    width, height = B4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {title}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(text or "", 45):
            c.drawString(margin, y, line)
            y -= 7 * mm
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
        y -= 6 * mm

    c.showPage()
    y = height - 30 * mm
    draw_text_block(yearly["year_label"], yearly["year_text"])
    for month in yearly["months"][:6]:
        draw_text_block(month["label"], month["text"])

    c.showPage()
    y = height - 30 * mm
    for month in yearly["months"][6:]:
        draw_text_block(month["label"], month["text"])


def draw_renai_pdf(c, data, size, include_yearly=False):
    from reportlab.lib.pagesizes import A4, B4
    from reportlab.lib.units import mm
    from header_utils import draw_header
    from pdf_generator_unified import draw_yearly_pages_renai_a4, draw_yearly_pages_renai_b4, draw_lucky_section, FONT_NAME
    from textwrap import wrap as wrap_text

    def wrap(text, limit):
        lines = []
        for line in text.splitlines():
            lines.extend(wrap_text(line, limit))
        return lines

    width, height = A4 if size == 'a4' else B4
    margin = 20 * mm
    wrap_len = 40 if size == 'a4' else 45
    y = draw_header(c, width, margin, height - margin)

    # 1ページ目：相性診断・恋愛運（年/月/来月）
    main_keys = [
        "compatibility",
        "year_love",
        "month_love",
        "next_month_love",
    ]
    c.setFont(FONT_NAME, 12)
    for key in main_keys:
        if key in data.get("texts", {}) and data["texts"][key].strip():
            c.drawString(margin, y, f"◆ {data['titles'].get(key, key)}")
            y -= 6 * mm
            c.setFont(FONT_NAME, 10)
            for line in wrap(data["texts"][key], wrap_len):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 4 * mm
            c.setFont(FONT_NAME, 12)

    c.showPage()
    y = height - margin

    # 2ページ目：恋愛テーマ3項目（注意点・距離感・結婚）
    if data.get("themes"):
        c.setFont(FONT_NAME, 12)
        for section in data["themes"]:
            c.drawString(margin, y, f"◆ {section['title']}")
            y -= 6 * mm
            c.setFont(FONT_NAME, 10)
            for line in wrap(section["content"], wrap_len):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 4 * mm
            c.setFont(FONT_NAME, 12)

    # ラッキー情報・吉方位（2ページ目末尾）
    y = draw_lucky_section(
        c, width, margin, y,
        data.get("lucky_info", []),
        data.get("lucky_direction", "")
    )

    # 年運（オプション）
    if include_yearly and data.get("yearly_love_fortunes"):
        if size == "a4":
            draw_yearly_pages_renai_a4(c, data["yearly_love_fortunes"])
        else:
            draw_yearly_pages_renai_b4(c, data["yearly_love_fortunes"])






def create_pdf_unified(filepath, data, mode, size="a4", include_yearly=False):

    pagesize = A4 if size.lower() == "a4" else B4
    c = canvas.Canvas(filepath, pagesize=pagesize)
    width, height = pagesize
    margin = 20 * mm
    y = height - 30 * mm

    draw_header(c, width, height)

    y = draw_palm_image(c, data["palm_image"], width, y, birthdate=data.get("birthdate"))

    for i in range(3):
        draw_title(c, data["palm_titles"][i], margin, y)
        y -= 10 * mm
        y = draw_wrapped_text(c, data["palm_texts"][i], margin, y)

    y = draw_lucky_info(c, width, margin, y, data.get("lucky_info"))

    y = draw_block(c, "吉方位（九星気学より）", data.get("lucky_direction"), margin, y)

    c.showPage()
    y = height - 30 * mm
    text = c.beginText(margin, y)
    text.setFont(FONT_NAME, 12)

    for i in range(3, 5):
        text.textLine(f"- {data['palm_titles'][i]}")
        text.setFont(FONT_NAME, 10)
        for line in wrap(data["palm_texts"][i], 45):
            text.textLine(line)
        text.textLine("")
        text.setFont(FONT_NAME, 12)

    text.textLine(f"- {data['titles']['palm_summary']}")
    text.setFont(FONT_NAME, 10)
    for line in wrap(data["texts"]["palm_summary"], 45):
        text.textLine(line)
    text.textLine("")

    for key in ["personality", "month_fortune", "next_month_fortune"]:
        text.setFont(FONT_NAME, 12)
        text.textLine(f"- {data['titles'][key]}")
        text.setFont(FONT_NAME, 10)
        for line in wrap(data["texts"][key], 45):
            text.textLine(line)
        text.textLine("")

    c.drawText(text)

    if include_yearly and "yearly_fortunes" in data:
        c.showPage()
        y = height - 30 * mm
        text = c.beginText(margin, y)
        text.setFont(FONT_NAME, 12)
        text.textLine(f"- {data['titles']['year_fortune']}")
        text.setFont(FONT_NAME, 10)
        for line in wrap(data["texts"]["year_fortune"], 45):
            text.textLine(line)
        c.drawText(text)

    c.save()
