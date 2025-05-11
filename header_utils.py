import os
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))


def create_qr_code(url, path="qr_uranaya.png"):
    if not os.path.exists(path):
        import qrcode
        img = qrcode.make(url)
        img.save(path)
    return path


def draw_header(c, width, margin, y_pos, font=FONT_NAME):
    qr_ad_path = create_qr_code("https://uranaya.wixsite.com/uranaya", path="qr_uranaya.png")
    if os.path.exists(qr_ad_path):
        c.drawImage(qr_ad_path, width - margin - 30 * mm, y_pos - 30 * mm, width=30 * mm, height=30 * mm)
        ad_text = c.beginText(margin, y_pos - 10)
        ad_text.setFont(font, 11)
        ad_text.textLine("───────── シン・コンピューター占い ────────────")
        ad_text.textLine("　　　　　　【占いの館・占い師「うらなや」監修】")
        ad_text.textLine("　　　　　　　未来はあなたの行動で変化していきます")
        ad_text.textLine("　　　　　　　より詳しく占いたい方、個人的な悩みは")
        ad_text.textLine("　　　　　　　「対面鑑定」「電話鑑定」「オンライン鑑定」も可能です。")
        ad_text.textLine("　　　　　　　詳しくはこちらから →")
        ad_text.textLine("──────────────────────────────────")
        c.drawText(ad_text)
        y_pos -= 60 * mm  # 必要に応じて微調整
    return y_pos

