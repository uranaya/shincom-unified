from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import os

from header_utils import draw_header  # ← 追加

# フォント定義（header_utilsと共通）
FONT_NAME = "IPAexGothic"
FONT_PATH = os.path.join("static", "ipaexg.ttf")
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf_tarot(question: str, result_dict: dict, save_path: str):
    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4
    x_margin = 20 * mm
    bottom_margin = 30 * mm
    y = height - 20 * mm

    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        'Japanese',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        leading=14,
    )

    # 📌 ヘッダー追加（QRコード付き広告ブロック）
    y = draw_header(c, width, x_margin, y, font=FONT_NAME)

    # 🟣 ご相談内容
    c.setFont(FONT_NAME, 13)
    c.drawString(x_margin, y, f"📍 ご相談内容：")
    y -= 18

    para_question = Paragraph(question, style)
    w, h = para_question.wrap(width - 2 * x_margin, y)
    if y - h < bottom_margin:
        c.showPage()
        y = height - 30 * mm
        c.setFont(FONT_NAME, 13)
        c.drawString(x_margin, y, f"📍 ご相談内容：")
        y -= 18
    para_question.drawOn(c, x_margin, y - h)
    y -= (h + 15)

    # 🔮 カードと解釈
    c.setFont(FONT_NAME, 12)
    for idx, item in enumerate(result_dict.get("questions", []), start=1):
        q_text = item.get("question", "")
        card = item.get("card", "")
        answer = item.get("answer", "")
        text = f"{idx}. カード: {card}（質問: {q_text}）\n{answer}"
        para = Paragraph(text, style)
        w, h = para.wrap(width - 2 * x_margin, y)
        if y - h < bottom_margin:
            c.showPage()
            y = height - 30 * mm
            para = Paragraph(text, style)
            w, h = para.wrap(width - 2 * x_margin, y)
        para.drawOn(c, x_margin, y - h)
        y -= (h + 10)

    # 🌟 総合読み解きとアドバイス
    if y < 80 * mm:  # ページ末なら改ページしてスペース確保
        c.showPage()
        y = height - 30 * mm

    c.setFont(FONT_NAME, 14)
    c.drawString(x_margin, y, "🌟 総合読み解きとアドバイス")
    y -= 20

    advice = result_dict.get("summary_advice", "")
    para = Paragraph(advice, style)
    w, h = para.wrap(width - 2 * x_margin, y)
    if y - h < bottom_margin:
        c.showPage()
        y = height - 30 * mm
    para.drawOn(c, x_margin, y - h)

    # PDF保存
    c.save()
    print(f"✅ PDF保存成功: {save_path}")
