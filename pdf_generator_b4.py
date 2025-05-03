import base64
import os
from reportlab.lib.pagesizes import B4
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
import textwrap
from qr_code_generator import create_qr_code, get_affiliate_link

from kyusei_utils import get_kyusei_fortune_openai as get_kyusei_fortune


FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    filepath = os.path.join("static", filename)  # ここを修正
    c = canvas.Canvas(filepath, pagesize=B4)
    width, height = B4
    margin = 15 * mm
    font = FONT_NAME
    wrapper = textwrap.TextWrapper(width=50)

    y_pos = height - margin


    # タイトル＋店舗情報広告
    qr_ad_path = create_qr_code("https://uranaya.jp", path="qr_uranaya.png")
    if os.path.exists(qr_ad_path):
        c.drawImage(qr_ad_path, width - margin - 30 * mm, y_pos - 30 * mm, width=30 * mm, height=30 * mm)
        ad_text = c.beginText(margin, y_pos - 10)
        ad_text.setFont(font, 11)
        ad_text.textLine("───────── シン・コンピューター占い ─────────")
        ad_text.textLine("手相・四柱推命・イーチン占いで未来をサポート")
        ad_text.textLine("Instagram → @uranaya_official")
        ad_text.textLine("────────────────────────────")
        c.drawText(ad_text)
        y_pos -= 50 * mm

    # 手相画像
    image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",", 1)[1]))
    c.drawImage(image_path, (width - 150 * mm) / 2, y_pos - 90 * mm, width=150 * mm, height=90 * mm)
    y_pos -= 100 * mm

    # 手相のテキスト整理
    palm_parts = [p.strip() for p in palm_result.split("\n") if p.strip()]
    advice_index = -1
    for i in reversed(range(len(palm_parts))):
        if "まとめ" in palm_parts[i] or "総合" in palm_parts[i]:
            advice_index = i
            break
    if advice_index != -1:
        advice_text = "\n".join(palm_parts[advice_index + 1:])
        main_parts = palm_parts[:advice_index]
    else:
        advice_text = ""
        main_parts = palm_parts

    # 手相鑑定（5項目）
    text = c.beginText(margin, y_pos)
    text.setFont(font, 11)
    text.textLine("■ 手相鑑定（5項目）")
    text.textLine("")
    for paragraph in main_parts:
        for line in wrapper.wrap(paragraph):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    # 裏面
    c.showPage()
    text = c.beginText(margin, height - margin)
    text.setFont(font, 11)

    # 総合アドバイス
    if advice_text:
        text.textLine("■ 手相からの総合的なアドバイス")
        text.textLine("")
        for line in wrapper.wrap(advice_text.strip()):
            text.textLine(line)
        text.textLine("")

    # 四柱推命
    text.textLine("■ 四柱推命によるアドバイス")
    text.textLine("")
    for paragraph in shichu_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    # イーチン
    text.textLine("■ イーチン占い アドバイス")
    text.textLine("")
    for paragraph in iching_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    # ラッキー項目
    text.textLine("■ ラッキーアイテム・カラー・ナンバー")
    text.textLine("")
    for line in lucky_info.split("\n"):
        for wrapped in wrapper.wrap(line):
            text.textLine(wrapped)

    # 吉方位の追加（例：生年月日 1990年4月15日）
    fortune_text = get_kyusei_fortune(1990, 4, 15)
    text.textLine("")
    text.textLine("■ 吉方位（九星気学より）")
    text.textLine(fortune_text)

    c.drawText(text)

    # QRコード広告（裏面）
    qr_path = create_qr_code(get_affiliate_link())
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width - margin - 30 * mm, margin, width=30 * mm, height=30 * mm)
        c.setFont(font, 10)
        c.drawString(margin, margin + 10 * mm, "📱 ラッキーアイテムはこちらから →")
        c.drawString(margin, margin, get_affiliate_link())

    c.save()
    return filepath

def create_pdf_b4_combined(image_data, palm_result, shichu_result, iching_result, lucky_info, birthdate, filename):
    # 通常の2ページを作成
    create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)

    # canvasを再開して追加ページ（3〜4）を挿入
    from yearly_fortune_utils import generate_yearly_fortune
    filepath = os.path.join("static", filename)
    c = canvas.Canvas(filepath, pagesize=B4)
    c.setFont(FONT_NAME, 11)
    wrapper = textwrap.TextWrapper(width=50)

    # 3ページ目（年運）
    c.showPage()
    y = B4[1] - 30 * mm
    fortunes = generate_yearly_fortune(birthdate, datetime.now())
    text = c.beginText(15 * mm, y)
    text.setFont(FONT_NAME, 11)
    text.textLine("■ あなたの1年の運勢（1〜6月）")
    text.textLine("")
    for i in range(6):
        for line in wrapper.wrap(fortunes[i]):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    # 4ページ目（年運 続き）
    c.showPage()
    y = B4[1] - 30 * mm
    text = c.beginText(15 * mm, y)
    text.setFont(FONT_NAME, 11)
    text.textLine("■ あなたの1年の運勢（7〜12月）")
    text.textLine("")
    for i in range(6, 12):
        for line in wrapper.wrap(fortunes[i]):
            text.textLine(line)
        text.textLine("")
    c.drawText(text)

    c.save()
