from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from textwrap import wrap
from PIL import Image
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


def draw_lucky_section(c, width, margin, y, lucky_lines, lucky_direction):
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "■ ラッキー情報（生年月日より）")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)

    # 2項目ずつ改行する形式（最大3行）
    for i in range(0, len(lucky_lines), 2):
        line1 = lucky_lines[i]
        line2 = lucky_lines[i + 1] if i + 1 < len(lucky_lines) else ""
        formatted = f"{line1:<38}    {line2}"
        c.drawString(margin, y, formatted)
        y -= 6 * mm

    if lucky_direction:
        y -= 2 * mm
        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, "■ 吉方位（九星気学より）")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in lucky_direction.strip().splitlines():
            c.drawString(margin, y, line.strip())
            y -= 6 * mm

    return y



def draw_palm_image(c, base64_image, width, y):
    try:
        # ✅ base64の先頭確認
        if ',' not in base64_image:
            raise ValueError("base64形式が不正")

        image_data = base64.b64decode(base64_image.split(',')[1])
        image = Image.open(io.BytesIO(image_data))

        # ✅ 自動リサイズ処理（最大サイズ 1000px）
        max_pixel = 1000
        if max(image.size) > max_pixel:
            ratio = max_pixel / max(image.size)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        # ✅ 再エンコードしてImageReaderへ
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)
        img = ImageReader(buffer)

        img_width, img_height = img.getSize()

        # 🔧 PDF上の表示サイズ
        max_width = 210
        max_height = 160
        scale = min(max_width / img_width, max_height / img_height)
        resized_width = img_width * scale
        resized_height = img_height * scale

        x_center = (width - resized_width) / 2
        y -= resized_height + 5 * mm

        c.drawImage(
            img,
            x_center,
            y,
            width=resized_width,
            height=resized_height,
            preserveAspectRatio=True,
            anchor='nw'
        )

        y -= 10 * mm

    except Exception as e:
        print("Image decode or resize error:", e)

    return y







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
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 10)
            c.drawString(margin, y, line)
            y -= 5 * mm
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
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 11)
            c.drawString(margin, y, line)
            y -= 7 * mm
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




def draw_shincom_a4(c, data, include_yearly=False):
    width, height = A4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)
    y = draw_palm_image(c, data["palm_image"], width, y)

    # 手相3項目（1ページ目）
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

    # 新ページ：手相残り2項目 + 鑑定結果
    c.showPage()
    y = height - margin

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

    # 四柱推命・まとめ等（タイトルのみでも出す）
    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 36 if 'month' in key else 40
        title = data['titles'].get(key, "")
        content = data['texts'].get(key, "")

        if title:
            c.drawString(margin, y, f"◆ {title}")
            y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        if content:
            for line in wrap(content, wrap_len):
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

    c.setFont(FONT_NAME, 14)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 7 * mm
        c.setFont(FONT_NAME, 12)
        for line in wrap(data['palm_texts'][i], 45):
            c.drawString(margin, y, line)
            y -= 7 * mm
        y -= 4 * mm
        c.setFont(FONT_NAME, 14)

    c.showPage()
    y = height - margin
    c.setFont(FONT_NAME, 14)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 7 * mm
        c.setFont(FONT_NAME, 12)
        for line in wrap(data['palm_texts'][i], 45):
            c.drawString(margin, y, line)
            y -= 7 * mm
        y -= 4 * mm
        c.setFont(FONT_NAME, 14)

    for key in ['palm_summary', 'personality', 'year_fortune', 'month_fortune', 'next_month_fortune']:
        wrap_len = 40 if 'month' in key else 45
        title = data['titles'].get(key, "")
        content = data['texts'].get(key, "")
        if title:
            c.drawString(margin, y, f"◆ {title}")
            y -= 7 * mm
        c.setFont(FONT_NAME, 12)
        if content:
            for line in wrap(content, wrap_len):
                c.drawString(margin, y, line)
                y -= 7 * mm
        y -= 4 * mm
        c.setFont(FONT_NAME, 14)

    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    if include_yearly:
        draw_yearly_pages_shincom_b4(c, data['yearly_fortunes'])



def draw_yearly_pages_shincom_a4(c, yearly):
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    def draw_text_block(title, text):
        nonlocal y
        c.setFont(FONT_NAME, 12)
        c.drawString(margin, y, f"■ {title}")
        y -= 5 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(text or "", 45):
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 10)
            c.drawString(margin, y, line)
            y -= 5 * mm
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


def draw_yearly_pages_shincom_b4(c, yearly):
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
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 11)
            c.drawString(margin, y, line)
            y -= 7 * mm
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





def create_pdf_unified(filepath, data, mode, size='a4', include_yearly=False):
    size = size.lower()
    c = canvas.Canvas(filepath, pagesize=A4 if size == 'a4' else B4)
    c.setTitle('占い結果')
    if mode == 'shincom':
        if size == 'a4':
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        draw_renai_pdf(c, data, size, include_yearly)
    c.save()
