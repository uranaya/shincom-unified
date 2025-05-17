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



def draw_lucky_section(c, width, margin, y, lucky_info, lucky_direction):
    from reportlab.lib.units import mm
    c.setFont("IPAexGothic", 12)
    c.drawString(margin, y, "■ ラッキー情報（生年月日より）")
    y -= 8 * mm
    c.setFont("IPAexGothic", 10)

    if lucky_info:
        col_width = (width - 2 * margin) / 2
        x1 = margin + 10
        x2 = margin + 10 + col_width
        col = 0
        for i, item in enumerate(lucky_info):
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

    y -= 4 * mm
    c.setFont("IPAexGothic", 11)

    if lucky_direction and isinstance(lucky_direction, str) and lucky_direction.strip():
        try:
            lines = lucky_direction.strip().splitlines()
            simplified = []
            for text in lines:
                if "吉方位" in text:
                    parts = text.split("：")
                    if len(parts) == 2:
                        simplified.append(f"{parts[0].replace('の吉方位', '')}：{parts[1]}")

            for i in range(0, len(simplified), 2):
                row = simplified[i:i+2]
                c.drawString(margin, y, "　　".join(row))
                y -= 6 * mm
        except Exception as e:
            print("❌ 吉方位整形失敗:", e)
            c.drawString(margin + 10, y, "吉方位情報の取得に失敗しました")
            y -= 6 * mm
    else:
        c.drawString(margin + 10, y, "■ 吉方位（九星気学より）情報未取得")
        y -= 6 * mm

    return y - 10 * mm





def draw_palm_image(c, base64_image, width, y, birthdate=None):

    try:
        image_data = base64.b64decode(base64_image.split(',')[1])
        img = ImageReader(io.BytesIO(image_data))
        img_width, img_height = img.getSize()
        scale = (width * 0.6) / img_width
        img_width *= scale
        img_height *= scale
        x_center = (width - img_width) / 2
        y -= img_height + 5 * mm
        c.drawImage(img, x_center, y, width=img_width, height=img_height)
        y -= 10 * mm

        if birthdate:
            c.setFont("IPAexGothic", 10)
            c.drawCentredString(width / 2, y, f"生年月日：{birthdate}")
            y -= 8 * mm
    except Exception as e:
        print("Image decode error:", e)

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
    from reportlab.lib.pagesizes import A4, B4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from textwrap import wrap
    from PIL import Image
    import io
    import base64

    FONT_NAME = "IPAexGothic"
    FONT_PATH = "ipaexg.ttf"

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

    pagesize = A4 if size.lower() == "a4" else B4
    c = canvas.Canvas(filepath, pagesize=pagesize)
    width, height = pagesize
    margin = 20 * mm
    y = height - 30 * mm

    def draw_title(title):
        nonlocal y
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"◆ {title}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)

    def draw_wrapped_text(text, limit=45):
        nonlocal y
        for line in wrap(text, limit):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 4 * mm

    # 1ページ目：手相画像＋項目（A4は3項目）
    if "palm_image" in data and data["palm_image"]:
        image_data = base64.b64decode(data["palm_image"].split(",")[1])
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail((150 * mm, 100 * mm))
        img_io = io.BytesIO()
        img.save(img_io, format="PNG")
        img_io.seek(0)
        c.drawImage(ImageReader(img_io), width/2 - 75*mm, y - 100*mm, mask='auto')
        y -= 105 * mm

    # 生年月日
    if "birthdate" in data:
        c.setFont(FONT_NAME, 11)
        c.drawCentredString(width / 2, y, f"生年月日：{data['birthdate']}")
        y -= 10 * mm

    # 手相3項目（前半）
    c.setFont(FONT_NAME, 13)
    for i in range(3):
        draw_title(data["palm_titles"][i])
        draw_wrapped_text(data["palm_texts"][i])

    # ラッキー情報（前半）
    if "lucky_info" in data and data["lucky_info"]:
        draw_title("ラッキー情報（生年月日より）")
        lines = data["lucky_info"]
        for i in range(0, len(lines), 2):
            line = lines[i]
            line2 = lines[i+1] if i+1 < len(lines) else ""
            combined = f"{line}　　{line2}" if line2 else line
            c.drawString(margin, y, combined)
            y -= 6 * mm
        y -= 4 * mm

    # 吉方位（九星気学）
    if "lucky_direction" in data and isinstance(data["lucky_direction"], str) and "吉方位" in data["lucky_direction"]:
        draw_title("吉方位（九星気学より）")
        lines = data["lucky_direction"].split("\n")
        for line in lines:
            c.drawString(margin, y, line)
            y -= 6 * mm

    c.showPage()

    # 2ページ目：手相後半＋総合アドバイス＋四柱推命＋イーチン
    y = height - 30 * mm
    text = c.beginText(margin, y)
    text.setFont(FONT_NAME, 12)

    # 残りの手相2項目
    for i in range(3, 5):
        text.textLine(f"- {data['palm_titles'][i]}")
        text.setFont(FONT_NAME, 10)
        for line in wrap(data["palm_texts"][i], 45):
            text.textLine(line)
        text.textLine("")
        text.setFont(FONT_NAME, 12)

    # 手相の総合
    text.textLine("- " + data["titles"]["palm_summary"])
    text.setFont(FONT_NAME, 10)
    for line in wrap(data["texts"]["palm_summary"], 45):
        text.textLine(line)
    text.textLine("")
    text.setFont(FONT_NAME, 12)

    # 四柱推命
    for key in ["personality", "month_fortune", "next_month_fortune"]:
        text.textLine(f"- {data['titles'][key]}")
        text.setFont(FONT_NAME, 10)
        for line in wrap(data["texts"][key], 45):
            text.textLine(line)
        text.textLine("")
        text.setFont(FONT_NAME, 12)

    # イーチン
    if "iching_result" in data:
        text.textLine("■ 易占いアドバイス")
        text.setFont(FONT_NAME, 10)
        for line in wrap(data["iching_result"], 45):
            text.textLine(line)
        text.textLine("")

    c.drawText(text)

    # 3ページ目（年運）
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
