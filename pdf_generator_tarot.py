from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# フォント登録（前提）
FONT_NAME = "IPAexGothic"
pdfmetrics.registerFont(TTFont(FONT_NAME, "ipaexg.ttf"))
addMapping(FONT_NAME, 0, 0, FONT_NAME)

def create_pdf_tarot(question: str, result_dict: dict, save_path: str):
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
    add_paragraph("🔮 タロット占い鑑定書", "")

    # 📝 質問
    add_paragraph("【ご相談内容】", question)

    # 🧭 ケルト十字
    add_paragraph("【ケルト十字スプレッドによる全体鑑定】", result_dict.get("spread_result", ""))

    # ❓ 個別質問
    for i, q in enumerate(result_dict.get("extra_questions", []), 1):
        label = f"【Q{i}】{q['question']}（{q['card']}）"
        add_paragraph(label, q["answer"])

    # 💬 総合まとめ
    add_paragraph("【総合読み解きとアドバイス】", result_dict.get("summary_advice", ""))

    # 終了
    c.drawText(textobject)
    c.save()
    print(f"✅ PDF保存成功: {save_path}")
