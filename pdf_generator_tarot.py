from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import os

# 日本語フォントを登録
FONT_PATH = os.path.join("static", "ipaexg.ttf")
FONT_NAME = "IPAexGothic"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf_tarot(question: str, result_dict: dict, save_path: str):
    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4
    x_margin = 20 * mm
    bottom_margin = 30 * mm
    y = height - 30 * mm

    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        'Japanese',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=11,
        leading=14,
    )

    # ヘッダー：質問文
    c.setFont(FONT_NAME, 14)
    c.drawString(x_margin, y, f"📍 ご相談内容：{question}")
    y -= 25

    # 各質問とカード結果のリスト
    c.setFont(FONT_NAME, 12)
    for idx, item in enumerate(result_dict.get("questions", []), start=1):
        q_text = item.get("question", "")
        card = item.get("card", "")
        answer = item.get("answer", "")
        text = f"{idx}. カード: {card} （質問: {q_text}）\n{answer}"
        para = Paragraph(text, style)
        w, h = para.wrap(width - 2 * x_margin, y)
        if y - h < bottom_margin:
            # 余白に収まらない場合は改ページ
            c.showPage()
            y = height - 30 * mm
            c.setFont(FONT_NAME, 12)
            para = Paragraph(text, style)
            w, h = para.wrap(width - 2 * x_margin, y)
        para.drawOn(c, x_margin, y - h)
        y -= (h + 10)

    # 総合読み解きとアドバイス（同一ページ内）
    c.setFont(FONT_NAME, 14)
    c.drawString(x_margin, y, "🌟 総合読み解きとアドバイス")
    y -= 20
    advice = result_dict.get("summary_advice", "")
    para = Paragraph(advice, style)
    w, h = para.wrap(width - 2 * x_margin, y)
    # 必要なら改ページ（今回1ページに収まる想定）
    if y - h < bottom_margin:
        c.showPage()
        y = height - 30 * mm
    para.drawOn(c, x_margin, y - h)

    # PDF保存
    c.save()
    print(f"✅ PDF保存成功: {save_path}")
