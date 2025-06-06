from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# IPAフォントの登録
FONT_NAME = "IPAexGothic"
pdfmetrics.registerFont(TTFont(FONT_NAME, "ipaexg.ttf"))
addMapping(FONT_NAME, 0, 0, FONT_NAME)

def create_pdf_tarot(question: str, fortune_dict: dict, save_path: str):
    c = canvas.Canvas(save_path, pagesize=A4)
    width, height = A4
    margin = 50
    line_height = 16
    max_lines_per_page = int((height - 2 * margin) / line_height)

    textobject = c.beginText(margin, height - margin)
    textobject.setFont(FONT_NAME, 12)
    line_count = 0

    def add_paragraph(label, content):
        nonlocal line_count, textobject
        if label:
            lines = [label]
        else:
            lines = []
        lines += simpleSplit(content, FONT_NAME, 12, width - 2 * margin)

        for line in lines:
            if line_count >= max_lines_per_page:
                c.drawText(textobject)
                c.showPage()
                textobject = c.beginText(margin, height - margin)
                textobject.setFont(FONT_NAME, 12)
                line_count = 0
            textobject.textLine(line)
            line_count += 1
        textobject.textLine("")
        line_count += 1

    # 🔮 ヘッダー
    add_paragraph("🔮 タロットスプレッド占い", "")

    # 📝 質問文
    add_paragraph("【ご相談内容】", question)

    # 📖 結果本文
    result_text = fortune_dict.get("result_text", "")
    add_paragraph("【鑑定結果】", result_text)

    # 最終描画と保存
    c.drawText(textobject)
    c.save()
    print(f"✅ PDF保存成功: {save_path}")