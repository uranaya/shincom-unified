
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import textwrap
import qrcode
import os
import io
from datetime import datetime
from base64 import b64decode

# フォント登録
FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_qr_code(url, path):
    img = qrcode.make(url)
    img.save(path)

def get_affiliate_link():
    return "https://www.amazon.co.jp/dp/B00EXAMPLE?tag=uranayashop-22"

def draw_wrapped(c, title, text, x, y, max_width, max_lines=15, fontsize=11):
    c.setFont(FONT_NAME, fontsize)
    wrapped = textwrap.wrap(text, width=45)
    c.drawString(x, y, f"■ {title}")
    y -= 6
    for line in wrapped[:max_lines]:
        y -= fontsize + 2
        c.drawString(x, y, line)
    return y - 10

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    output_path = f"static/{filename}"
    os.makedirs("static", exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    x = margin
    y = height - margin

    # 日時
    c.setFont(FONT_NAME, 10)
    c.drawRightString(width - margin, height - 10 * mm, datetime.now().strftime("作成日時：%Y-%m-%d %H:%M"))

    # タイトル
    c.setFont(FONT_NAME, 16)
    c.drawCentredString(width / 2, y - 30, "鑑定結果")

    # 手相画像
    try:
        base64_data = image_data.split(",")[1]
        palm_image = ImageReader(io.BytesIO(b64decode(base64_data)))
        c.drawImage(palm_image, x, y - 100 * mm, width=170 * mm, preserveAspectRatio=True, mask='auto')
    except Exception as e:
        c.setFont(FONT_NAME, 12)
        c.drawString(x, y - 100, "画像読み込みエラー")

    # QRコード＋リンク
    qr_path = "static/temp_qr.png"
    affiliate_url = get_affiliate_link()
    create_qr_code(affiliate_url, qr_path)
    c.drawImage(qr_path, width - 50 * mm, margin + 10, width=30 * mm, preserveAspectRatio=True)
    c.setFont(FONT_NAME, 8)
    c.drawString(width - 50 * mm, margin, affiliate_url)

    c.showPage()  # 2ページ目

    y = height - margin
    c.setFont(FONT_NAME, 12)
    c.drawCentredString(width / 2, y, "占い結果の詳細")
    y -= 20

    y = draw_wrapped(c, "手相鑑定", palm_result, x, y, width - 2 * margin)
    y = draw_wrapped(c, "性格", extract_section(shichu_result, "■ 性格", "■ 今月の運勢"), x, y, width - 2 * margin)
    y = draw_wrapped(c, "今月の運勢", extract_section(shichu_result, "■ 今月の運勢", "■ 来月の運勢"), x, y, width - 2 * margin)
    y = draw_wrapped(c, "来月の運勢", extract_section(shichu_result, "■ 来月の運勢", None), x, y, width - 2 * margin)
    y = draw_wrapped(c, "イーチン占い", iching_result, x, y, width - 2 * margin)
    y = draw_wrapped(c, "ラッキー情報", lucky_info.replace("\n", " ").replace("\"", ""), y)


    c.save()

def extract_section(text, start_marker, end_marker):
    try:
        start = text.index(start_marker) + len(start_marker)
        if end_marker:
            end = text.index(end_marker)
            return text[start:end].strip()
        return text[start:].strip()
    except ValueError:
        return "取得できませんでした"
