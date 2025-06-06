from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
import textwrap

# IPAフォントの登録
FONT_NAME = "IPAexGothic"
pdfmetrics.registerFont(TTFont(FONT_NAME, "ipaexg.ttf"))
addMapping(FONT_NAME, 0, 0, FONT_NAME)

def split_text_to_lines(text, max_chars=40):
    """長文を40文字ごとに分割（段落単位で処理）"""
    paragraphs = text.split("\n")
    lines = []
    for para in paragraphs:
        para = para.strip()
        if para:
            lines.extend(textwrap.wrap(para, width=max_chars))
        else:
            lines.append("")
    return lines

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
        combined = label + "\n" + content if label else content
        lines = split_text_to_lines(combined)

        for line in lines:
            if line_count >= max_lines_per_page:
                c.drawText(textobject)
                c.showPage()
                textobject = c.beginText(margin, height - margin)
                textobject.setFont(FONT_NAME, 12)
                line_count = 0
            textobject.textLine(line)
            line_count += 1

        textobject.textLine("")  # 段落の余白
        line_count += 1

    # 🔮 ヘッダー
    add_paragraph("🔮 タロットスプレッド占い", "")

    # 📝 ご相談内容
    add_paragraph("【ご相談内容】", question)

    # 📖 鑑定結果（改行＆ページ制御付き）
    result_text = fortune_dict.get("result_text", "")
    add_paragraph("【鑑定結果】", result_text)

    c.drawText(textobject)
    c.save()
    print(f"✅ PDF保存成功: {save_path}")
