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

from fortune_logic import generate_fortune
from renai_fortune_utils import generate_fortune as generate_renai_fortune
from yearly_fortune_utils import generate_yearly_fortune
from yearly_love_fortune_utils import generate_yearly_love_fortune
from header_utils import draw_header
from lucky_utils import draw_lucky_section

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def draw_wrapped_lines(text_obj, lines):
    for line in lines:
        text_obj.textLine(line)

def draw_lucky_info(c, data, x, y):
    c.setFont(FONT_NAME, 11)
    for label, content in data.items():
        wrapped = wrap(f"◆ {label}：{content}", width=40)
        for line in wrapped:
            c.drawString(x, y, line)
            y -= 12
    return y

def draw_shincom_a4(c, data, include_yearly=False):
    width, height = A4
    margin = 20 * mm
    # 1ページ目ヘッダー描画
    y_header_end = draw_header(c, width, margin, height - margin)
    # 手相画像をヘッダー直下にセンター配置で描画
    if data.get("image_data"):
        img_data = base64.b64decode(data["image_data"].split(",")[1])
        img = ImageReader(io.BytesIO(img_data))
        img_width = 130 * mm
        img_height = 100 * mm
        img_top_y = y_header_end - img_height - 5 * mm
        c.drawImage(img, (width - img_width) / 2, img_top_y, width=img_width, height=img_height)
        y = img_top_y - 5 * mm
    else:
        y = y_header_end
    # 1ページ目本文：手相の最初の3項目
    c.setFont(FONT_NAME, 12)
    for i in range(3):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["palm_texts"][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    # 2ページ目へ移行
    c.showPage()
    y = height - 30 * mm  # 2ページ目はヘッダーなし、上部に30mmの余白を確保
    # 2ページ目本文：残り2項目の手相結果
    c.setFont(FONT_NAME, 12)
    for i in range(3, 5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["palm_texts"][i], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    # 2ページ目本文：手相まとめ、性格診断、今月・来月の運勢
    for key in ["palm_summary", "personality", "month_fortune", "next_month_fortune"]:
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["texts"][key], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    # 2ページ目末尾：ラッキー情報（生年月日より）
    c.drawString(margin, y, "■ ラッキー情報（生年月日より）")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    if isinstance(data["lucky_info"], list):
        for item in data["lucky_info"]:
            c.drawString(margin + 10 * mm, y, item if item.startswith('・') else f"・{item}")
            y -= 6 * mm
    elif isinstance(data["lucky_info"], dict):
        for label, content in data["lucky_info"].items():
            c.drawString(margin + 10 * mm, y, f"・{label}：{content}")
            y -= 6 * mm
    else:
        # 型が想定外の場合のフォールバック
        c.drawString(margin + 10 * mm, y, str(data["lucky_info"]))
        y -= 6 * mm
    y -= 3 * mm
    # 2ページ目末尾：吉方位（九星気学より）
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "■ 吉方位（九星気学より）")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    c.drawString(margin + 10 * mm, y, str(data["lucky_direction"]))
    y -= 6 * mm
    y -= 3 * mm
    # 年間運勢ページ（オプション）
    if include_yearly:
        c.showPage()
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])

def draw_shincom_b4(c, data, include_yearly=False):
    width, height = B4
    margin = 20 * mm
    # 1ページ目ヘッダー描画
    y_header_end = draw_header(c, width, margin, height - 30 * mm)
    # 手相画像をヘッダー直下にセンター配置で描画
    if data.get("image_data"):
        img_data = base64.b64decode(data["image_data"].split(",")[1])
        img = ImageReader(io.BytesIO(img_data))
        img_width = 130 * mm
        img_height = 100 * mm
        img_top_y = y_header_end - img_height - 5 * mm
        c.drawImage(img, (width - img_width) / 2, img_top_y, width=img_width, height=img_height)
        y = img_top_y - 5 * mm
    else:
        y = y_header_end
    # 1ページ目本文：5項目すべての手相結果を描画
    text = c.beginText(margin, y)
    text.setFont(FONT_NAME, 11)
    for title, body in zip(data["palm_titles"], data["palm_texts"]):
        text.textLine(f"■ {title}")
        text.textLine("")
        for line in wrap(body, 40):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)
    # 2ページ目本文：手相まとめ、性格診断、今月・来月の運勢、易占い結果、ラッキー情報・吉方位
    c.showPage()
    text = c.beginText(margin, height - 30 * mm)
    def draw_block(title, content):
        text.setFont(FONT_NAME, 12)
        text.textLine(f"■ {title}")
        text.textLine("")
        text.setFont(FONT_NAME, 10)
        for paragraph in content.split("\n"):
            for line in wrap(paragraph.strip(), 40):
                text.textLine(line)
        text.textLine("")
    draw_block("手相からの総合的なアドバイス", data["texts"]["palm_summary"])
    draw_block("性格診断", data["texts"]["personality"])
    draw_block("今月の運勢", data["texts"]["month_fortune"])
    draw_block("来月の運勢", data["texts"]["next_month_fortune"])
    draw_block("易占いによるアドバイス", data["iching_result"])
    # ラッキー情報（複数行テキストを組み立て）
    if isinstance(data["lucky_info"], dict):
        lucky_text = "\n".join(f"◆ {k}：{v}" for k, v in data["lucky_info"].items())
    elif isinstance(data["lucky_info"], list):
        lucky_text = "\n".join("◆ " + item.lstrip('・') for item in data["lucky_info"])
    else:
        lucky_text = str(data["lucky_info"])
    draw_block("ラッキー情報", lucky_text)
    # 吉方位（本命星と吉方位の文章）
    if data.get("lucky_direction"):
        draw_block("吉方位（九星気学より）", str(data["lucky_direction"]))
    c.drawText(text)
    # 年間運勢ページ（オプション）
    if include_yearly:
        c.showPage()
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])

def draw_yearly_pages_shincom(c, yearly_data):
    width, height = c._pagesize
    margin = 25 * mm
    y = height - 30 * mm
    c.setFont(FONT_NAME, 13)
    c.drawString(margin, y, f"■ {yearly_data['year_label']}")
    y -= 10 * mm
    c.setFont(FONT_NAME, 11)
    for line in wrap(yearly_data['year_text'], 40):
        c.drawString(margin, y, line)
        y -= 6 * mm
    y -= 10 * mm
    # 月ごとの運勢を新しいページから開始
    c.showPage()
    y = height - 30 * mm
    for month in yearly_data["months"]:
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"■ {month['label']}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for line in wrap(month['text'], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 10 * mm
        if y < 50 * mm:
            c.showPage()
            y = height - 30 * mm

def draw_renai_pdf(c, data, size, include_yearly=False):
    width, height = A4 if size == "a4" else B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)
    c.setFont(FONT_NAME, 12)
    for key in ["compatibility", "love_summary"]:
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        lines = wrap(data["texts"][key], 40 if size == "a4" else 45)
        for line in lines:
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    y = draw_lucky_section(c, width, margin, y, data["lucky_info"], data["lucky_direction"])
    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)
    for text in data["themes"]:
        c.drawString(margin, y, f"◆ {text['title']}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        lines = wrap(text["content"], 40 if size == "a4" else 45)
        for line in lines:
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)
    if include_yearly:
        draw_yearly_pages_renai(c, data["yearly_fortunes"])

def create_pdf_unified(filepath, data, mode, size="a4", include_yearly=False):
    c = canvas.Canvas(filepath, pagesize=A4 if size == "a4" else B4)
    c.setTitle("占い結果")
    if mode == "shincom":
        if size == "a4":
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        draw_renai_pdf(c, data, size, include_yearly)
    c.save()
