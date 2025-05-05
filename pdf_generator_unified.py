import os
from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from textwrap import wrap
from lucky_utils import draw_lucky_section
from header_utils import draw_header
from yearly_fortune_utils import generate_yearly_fortune
from yearly_love_fortune_utils import generate_yearly_love_fortune


FONT_NAME = "IPAexGothic"


def wrap_text(text, width=45):
    return "\n".join(wrap(text, width))


def draw_wrapped_text(c, text, x, y, max_width):
    lines = wrap(text, width=max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= 12
    return y


def draw_yearly_pages_shincom(c, yearly_fortunes):
    c.showPage()
    c.setFont(FONT_NAME, 12)
    c.drawString(20 * mm, 275 * mm, "◆ 年間運勢（四柱推命）")
    y = 265 * mm
    c.setFont(FONT_NAME, 10)
    for month, text in yearly_fortunes.items():
        c.drawString(20 * mm, y, f"◉ {month}月")
        y -= 12
        y = draw_wrapped_text(c, text, 25 * mm, y, 40)
        y -= 6
        if y < 40 * mm:
            c.showPage()
            y = 275 * mm
            c.setFont(FONT_NAME, 10)


def draw_yearly_pages_renai(c, yearly_fortunes):
    c.showPage()
    c.setFont(FONT_NAME, 12)
    c.drawString(20 * mm, 275 * mm, "◆ 年間恋愛運（四柱推命）")
    y = 265 * mm
    c.setFont(FONT_NAME, 10)
    for month, text in yearly_fortunes.items():
        c.drawString(20 * mm, y, f"◉ {month}月")
        y -= 12
        y = draw_wrapped_text(c, text, 25 * mm, y, 40)
        y -= 6
        if y < 40 * mm:
            c.showPage()
            y = 275 * mm
            c.setFont(FONT_NAME, 10)


def draw_shincom_a4(c, data, include_yearly=False):
    width, height = A4
    margin = 20 * mm
    y = height - margin

    # 広告ヘッダー
    y = draw_header(c, width, margin, y)

    # 手相主要3項目
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

    # ラッキー情報
    y -= 3 * mm
    y = draw_lucky_section(c, width, margin, y, data["lucky_info"], data["lucky_direction"])

    # 2ページ目
    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)

    # 手相残り2項目
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

    # 手相総合＋性格診断＋月運
    for key in ["palm_summary", "personality", "month_fortune", "next_month_fortune"]:
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["texts"][key], 40):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    if include_yearly:
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])


def draw_shincom_b4(c, data, include_yearly=False):
    width, height = B4
    margin = 20 * mm
    y = height - margin
    y = draw_header(c, width, margin, y)

    c.setFont(FONT_NAME, 12)
    for i in range(5):
        c.drawString(margin, y, f"◆ {data['palm_titles'][i]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["palm_texts"][i], 45):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)

    for key in ["palm_summary", "personality", "month_fortune", "next_month_fortune"]:
        c.drawString(margin, y, f"◆ {data['titles'][key]}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for line in wrap(data["texts"][key], 45):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 3 * mm
        c.setFont(FONT_NAME, 12)

    y = draw_lucky_section(c, width, margin, y, data["lucky_info"], data["lucky_direction"])

    if include_yearly:
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])


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
        for line in wrap(data["texts"][key], 40 if size == "a4" else 45):
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
        for line in wrap(text["content"], 40 if size == "a4" else 45):
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
