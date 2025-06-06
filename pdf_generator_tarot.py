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
    try:
        c = canvas.Canvas(save_path, pagesize=A4)
        width, height = A4
        margin = 50
        textobject = c.beginText(margin, height - margin)
        textobject.setFont(FONT_NAME, 12)

        textobject.textLine("🔮 タロットスプレッド占い")
        textobject.textLine("")

        textobject.textLine("【ご相談内容】")
        for line in simpleSplit(question, FONT_NAME, 12, width - 2 * margin):
            textobject.textLine(line)
        textobject.textLine("")

        textobject.textLine("【鑑定結果】")
        for line in simpleSplit(fortune_dict.get("result_text", ""), FONT_NAME, 12, width - 2 * margin):
            textobject.textLine(line)

        c.drawText(textobject)
        c.showPage()
        c.save()
        print(f"✅ PDF保存成功: {save_path}")  # 成功ログ
    except Exception as e:
        print(f"❌ PDF生成失敗: {e}")  # エラーログ
        raise
