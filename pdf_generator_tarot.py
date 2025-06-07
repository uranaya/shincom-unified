from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import os

# IPAフォント登録（必ず /static/ipaexg.ttf に置いておくこと）
FONT_PATH = os.path.join("static", "ipaexg.ttf")
FONT_NAME = "IPAexGothic"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf_tarot(filename, question, tarot_result):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    x_margin = 20 * mm
    y = height - 30 * mm

    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        'Japanese',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        leading=14,
    )

    # 質問文
    c.setFont(FONT_NAME, 14)
    c.drawString(x_margin, y, f"📍 質問内容：{question}")
    y -= 25

    # ケルト十字スプレッド
    c.setFont(FONT_NAME, 13)
    for i in range(1, 11):
        card_info = tarot_result["celtic_cross"].get(str(i), {})
        if not card_info:
            continue
        card = card_info.get("card", "不明なカード")
        meaning = card_info.get("answer", "")
        text = f"【{i}】{card}：{meaning}"
        para = Paragraph(text, style)
        w, h = para.wrap(width - 2 * x_margin, y)
        if y - h < 30 * mm:
            c.showPage()
            y = height - 30 * mm
            c.setFont(FONT_NAME, 13)
        para.drawOn(c, x_margin, y - h)
        y -= h + 5

    # 総合読み解きとアドバイス
    c.showPage()
    y = height - 30 * mm
    c.setFont(FONT_NAME, 14)
    c.drawString(x_margin, y, "🌟 総合読み解きとアドバイス")
    y -= 20

    advice = tarot_result.get("summary_advice", "（未記入）")
    para = Paragraph(advice, style)
    w, h = para.wrap(width - 2 * x_margin, y)
    para.drawOn(c, x_margin, y - h)
    y -= h + 10

    # 補足質問
    extras = tarot_result.get("extra_questions", [])
    if extras:
        c.showPage()
        y = height - 30 * mm
        c.setFont(FONT_NAME, 14)
        c.drawString(x_margin, y, "🔍 補足質問とカードの答え")
        y -= 20
        for item in extras:
            q = item.get("question", "")
            card = item.get("card", "")
            ans = item.get("answer", "")
            text = f"Q. {q}<br/>→ {card}：{ans}"
            para = Paragraph(text, style)
            w, h = para.wrap(width - 2 * x_margin, y)
            if y - h < 30 * mm:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 14)
            para.drawOn(c, x_margin, y - h)
            y -= h + 10

    c.save()
