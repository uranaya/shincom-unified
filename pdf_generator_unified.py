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

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))


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


def draw_renai_pdf(c, data, size, include_yearly=False):
    width, height = A4 if size == 'a4' else B4
    margin = 20 * mm

    # ヘッダー描画（各ページ共通）と（存在すれば）手相画像描画
    y = height - margin
    y = draw_header(c, width, margin, y)
    if data.get("palm_image"):
        y = draw_palm_image(c, data["palm_image"], width, y)

    # 1ページ目：メイン占い結果（2～3項目）
    c.setFont(FONT_NAME, 12)
    if 'feelings' in data['titles'] and 'future' in data['titles']:
        # お相手ありの場合（相性・気持ち・今後）
        main_keys = ['compatibility', 'feelings', 'future']
    else:
        # お相手なしの場合（性格・恋愛傾向、理想の相手と出会い）
        main_keys = ['compatibility', 'love_summary']
    for key in main_keys:
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        # テキストを適宜折り返して描画
        wrap_len = 40 if size == 'a4' else 45
        for line in wrap(data['texts'][key] or "", wrap_len):
            c.drawString(margin, y, line)
            y -= 6 * mm
            if y < 30 * mm:  # ページ下部に達したら改ページ
                c.showPage()
                y = height - margin
                y = draw_header(c, width, margin, y)
                c.setFont(FONT_NAME, 10)
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # ラッキー情報・吉方位（1ページ目末尾）
    y = draw_lucky_section(c, width, margin, y, data['lucky_info'], data.get('lucky_direction', ''))

    # 2ページ目：トピック別占い結果
    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)
    c.setFont(FONT_NAME, 12)
    for section in data['themes']:
        c.drawString(margin, y, f"◆ {section['title']}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(section['content'] or "", wrap_len):
            c.drawString(margin, y, line)
            y -= 6 * mm
            if y < 30 * mm:  # ページ末尾で改ページ
                c.showPage()
                y = height - margin
                y = draw_header(c, width, margin, y)
                c.setFont(FONT_NAME, 10)
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    # 年運＋月運（オプション：include_yearly=True の場合、3～4ページ目に出力）
    if include_yearly and data.get('yearly_fortunes'):
        if size == 'a4':
            draw_yearly_pages_renai_a4(c, data['yearly_fortunes'])
        else:
            draw_yearly_pages_renai_b4(c, data['yearly_fortunes'])


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