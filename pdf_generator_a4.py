import os
import base64
import textwrap
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from affiliate import create_qr_code, get_affiliate_link  # ← 修正済み

pdfmetrics.registerFont(TTFont("IPAexGothic", "ipaexg.ttf"))

def draw_wrapped(c, title, text, y, max_width=50):
    wrapper = textwrap.TextWrapper(width=max_width)
    lines = wrapper.wrap(text)
    c.setFont("IPAexGothic", 11)
    c.drawString(20 * mm, y, f"■ {title}")
    y -= 7 * mm
    for line in lines:
        c.drawString(20 * mm, y, line)
        y -= 6 * mm
    y -= 5 * mm
    return y

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    if not os.path.exists("static"):
        os.makedirs("static")
    filepath = os.path.join("static", filename)
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    y = height - 20 * mm

    # --- QR広告 ---
    c.setFont("IPAexGothic", 11)
    c.drawString(20 * mm, y, "───────── シン・コンピューター占い ─────────")
    y -= 6 * mm
    c.drawString(20 * mm, y, "手相・四柱推命・イーチン占いで未来をサポート")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Instagram → @uranaya_official")
    y -= 12 * mm
    qr_path = create_qr_code(get_affiliate_link())
    if os.path.exists(qr_path):
        c.drawImage(qr_path, width - 50 * mm, y - 10 * mm, width=30 * mm, height=30 * mm)

    y -= 40 * mm

    # --- 手相画像 ---
    image_path = os.path.join("static", f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",", 1)[1]))
    c.drawImage(image_path, 30 * mm, y - 90 * mm, width=150 * mm, height=90 * mm)
    y -= 100 * mm

    # --- 手相鑑定 ---
    c.setFont("IPAexGothic", 11)
    c.drawString(20 * mm, y, "■ 手相鑑定（5項目）")
    y -= 8 * mm
    wrapper = textwrap.TextWrapper(width=50)
    for line in palm_result.strip().split("\n"):
        if line.strip():
            for l in wrapper.wrap(line.strip()):
                c.drawString(20 * mm, y, l)
                y -= 6 * mm
            y -= 2 * mm

    # --- 次ページ ---
    c.showPage()
    y = height - 20 * mm

    # --- 手相まとめ（抽出） ---
    if "まとめ" in palm_result:
        summary_lines = palm_result.split("まとめ")[-1].strip()
        if summary_lines:
            y = draw_wrapped(c, "手相からのアドバイス", summary_lines, y)

    # --- 四柱推命 ---
    if shichu_result.strip():
        y = draw_wrapped(c, "四柱推命によるアドバイス", shichu_result.strip(), y)

    # --- イーチン占い ---
    if iching_result.strip():
        y = draw_wrapped(c, "イーチン占い アドバイス", iching_result.strip(), y)

    # --- ラッキー情報 ---
    if lucky_info.strip():
        lucky_clean = lucky_info.replace("\n", " ").replace("\"", "")
        y = draw_wrapped(c, "ラッキー情報", lucky_clean, y)

    # --- QRコード再掲 ---
    qr_path2 = create_qr_code(get_affiliate_link(), path="static/affiliate_qr_back.png")
    if os.path.exists(qr_path2):
        c.drawImage(qr_path2, width - 50 * mm, 20 * mm, width=30 * mm, height=30 * mm)
        c.setFont("IPAexGothic", 10)
        c.drawString(20 * mm, 30 * mm, "📱 ラッキーアイテムはこちら →")
        c.drawString(20 * mm, 24 * mm, get_affiliate_link())

    c.save()
    return filepath
