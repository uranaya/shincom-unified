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
        print(f"📄 PDF生成開始: {save_path}")  # ログ出力（Render確認用）

        c = canvas.Canvas(save_path, pagesize=A4)
        width, height = A4
        margin = 50
        textobject = c.beginText(margin, height - margin)
        textobject.setFont(FONT_NAME, 12)

        # タイトル
        textobject.textLine("🔮 タロットスプレッド占い")
        textobject.textLine("")

        # ご相談内容
        textobject.textLine("【ご相談内容】")
        for line in simpleSplit(question, FONT_NAME, 12, width - 2 * margin):
            textobject.textLine(line)
        textobject.textLine("")

        # 鑑定結果（OpenAIからのテキスト）
        textobject.textLine("【鑑定結果】")
        result_text = fortune_dict.get("result_text", "")
        for line in simpleSplit(result_text, FONT_NAME, 12, width - 2 * margin):
            textobject.textLine(line)

        # 描画完了
        c.drawText(textobject)
        c.showPage()
        c.save()

        print(f"✅ PDF保存成功: {save_path}")  # 成功ログ
    except Exception as e:
        print(f"❌ PDF生成失敗: {e}")  # エラーログ
        raise