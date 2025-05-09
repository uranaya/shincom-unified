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


def draw_header(c, width, margin, y):
    c.setFont(FONT_NAME, 14)
    c.drawString(margin, y, "💖 恋愛運鑑定書")
    return y - 15 * mm


def draw_lucky_section(c, width, margin, y, lucky_info, lucky_direction):
    from reportlab.lib.units import mm
    c.setFont("IPAexGothic", 12)
    c.drawString(margin, y, "■ ラッキー情報（生年月日より）")
    y -= 8 * mm
    c.setFont("IPAexGothic", 10)

    if lucky_info:
        for item in lucky_info:
            if item and isinstance(item, str):
                # 「：」で区切って右側を1文に制限（句点で区切る）
                if '：' in item:
                    title, content = item.split('：', 1)
                    content_short = content.split('。')[0] + '。' if '。' in content else content
                    text = f"{title}：{content_short.strip()}"
                    c.drawString(margin + 10, y, text)
                    y -= 6 * mm
    else:
        c.drawString(margin + 10, y, "情報が取得できませんでした。")
        y -= 6 * mm

    y -= 4 * mm

    c.setFont("IPAexGothic", 12)
    if lucky_direction and isinstance(lucky_direction, str) and lucky_direction.strip():
        c.drawString(margin, y, "■ 吉方位（九星気学より）")
        y -= 6 * mm
        c.setFont("IPAexGothic", 10)
        for line in lucky_direction.strip().splitlines():
            c.drawString(margin + 10, y, line)
            y -= 6 * mm
    else:
        c.drawString(margin, y, "■ 吉方位（九星気学より）情報未取得")
        y -= 6 * mm

    return y - 10 * mm


def draw_palm_image(c, base64_image, width, y):

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

    for key in ['palm_summary', 'personality', 'month_fortune', 'next_month_fortune']:
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

    for key in ['palm_summary', 'personality', 'month_fortune', 'next_month_fortune']:
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
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(text or "", 46):
            c.drawString(margin, y, line)
            y -= 6 * mm
            if y < 30 * mm:
                c.showPage()
                y = height - 30 * mm
        y -= 4 * mm

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
    from pdf_utils import wrap, FONT_NAME, draw_header, draw_lucky_section
    from pdf_generator_unified import draw_yearly_pages_renai_a4, draw_yearly_pages_renai_b4

    width, height = A4 if size == 'a4' else B4
    margin = 20 * mm
    wrap_len = 40 if size == 'a4' else 45
    y = height - margin

    # ページ1：相性など
    y = draw_header(c, width, margin, y)

    main_keys = ['compatibility', 'overall_love_fortune']
    if data.get('overall_love_fortune') == "":
        main_keys.remove('overall_love_fortune')

    c.setFont(FONT_NAME, 12)
    for key in main_keys:
        if key in data["texts"]:
            c.drawString(margin, y, f"◆ {data['titles'].get(key, key)}")
            y -= 6 * mm
            c.setFont(FONT_NAME, 10)
            for line in wrap(data['texts'][key], wrap_len):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 3 * mm
            c.setFont(FONT_NAME, 12)

    # 新規：四柱推命ベースの年・月・来月の恋愛運（year_love など）
    for key, title in [("year_love", "今年の恋愛運"), ("month_love", "今月の恋愛運"), ("next_month_love", "来月の恋愛運")]:
        if data.get(key):
            c.drawString(margin, y, f"◆ {title}")
            y -= 6 * mm
            c.setFont(FONT_NAME, 10)
            for line in wrap(data[key], wrap_len):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 3 * mm
            c.setFont(FONT_NAME, 12)

    c.showPage()
    y = height - margin

    # ページ2：トピック占い（注意点、復縁、結婚）
    c.setFont(FONT_NAME, 12)
    if data.get("themes"):
        for section in data["themes"]:
            c.drawString(margin, y, f"◆ {section['title']}")
            y -= 6 * mm
            c.setFont(FONT_NAME, 10)
            for line in wrap(section['content'], wrap_len):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 3 * mm
            c.setFont(FONT_NAME, 12)

    # ページ2末尾：ラッキー情報＋吉方位
    y = draw_lucky_section(c, width, margin, y, data.get('lucky_info', []), data.get('lucky_direction', ''))

    # 年運ページ（3〜4ページ目）
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
