from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import textwrap
from affiliate import create_qr_code
import os
from reportlab.lib.pagesizes import B4

# フォント設定
FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def wrap_text(text, width=40):
    return textwrap.fill(text, width=width)

def create_pdf(result_data, filepath):
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    # ---------- ヘルパー ----------
    def draw_title(title):
        nonlocal y
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"◆ {title}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)

    def draw_wrapped_text(text):
        nonlocal y
        for line in wrap_text(text).split("\n"):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 4 * mm
    # -----------------------------

    # === 表面 ヘッダー（QR + 広告） ===
    qr_ad_path = create_qr_code("https://uranaya.jp", path="qr_uranaya.png")
    if os.path.exists(qr_ad_path):
        c.drawImage(qr_ad_path, width - margin - 30 * mm, y - 30 * mm, width=30 * mm, height=30 * mm)
        ad_text = c.beginText(margin, y - 10)
        ad_text.setFont(FONT_NAME, 11)
        ad_text.textLine("───────── シン・コンピューター占い ─────────")
        ad_text.textLine("手相・四柱推命・イーチン占いで未来をサポート")
        ad_text.textLine("Instagram → @uranaya_official")
        ad_text.textLine("────────────────────────────")
        c.drawText(ad_text)
        y -= 50 * mm

    # === 表面 本文 ===
    draw_title("相性占い／おすすめタイプ")
    draw_wrapped_text(result_data["compatibility_text"])

    draw_title("恋愛運全般（今年・今月・今日）")
    draw_wrapped_text(result_data["overall_love_fortune"])

    draw_title("ラッキー情報")
    draw_wrapped_text(result_data["lucky_info"])

    draw_title("吉方位（九星気学）")
    draw_wrapped_text(result_data["lucky_direction"])

    # === 裏面 ===
    c.showPage()
    y = height - 30 * mm

    draw_title("選択テーマ別の恋愛占い")
    for topic, text in result_data["topic_fortunes"].items():
        draw_title(f"【{topic}】")
        draw_wrapped_text(text)

    # ✅ 年間恋愛運ページを追加（3〜4ページ目）
    if result_data.get("yearly_love_fortunes"):
        c.showPage()
        y = height - 30 * mm
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, "◆ あなたの1年の恋愛運（前半）")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for i, (month, fortune) in enumerate(result_data["yearly_love_fortunes"].items()):
            if i == 6:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 13)
                c.drawString(margin, y, "◆ あなたの1年の恋愛運（後半）")
                y -= 10 * mm
                c.setFont(FONT_NAME, 11)
            c.drawString(margin, y, f"● {month}")
            y -= 6 * mm
            for line in wrap_text(fortune).split("\n"):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 4 * mm

    # PDF保存
    c.save()

def create_pdf_b4(result_data, filepath):
    c = canvas.Canvas(filepath, pagesize=B4)
    width, height = B4
    margin = 20 * mm

    # === ヘッダー広告（QRコード＋テキスト） ===
    qr_ad_path = create_qr_code("https://uranaya.jp", path="qr_uranaya.png")
    if os.path.exists(qr_ad_path):
        c.drawImage(qr_ad_path, width - 30 * mm - margin, height - 30 * mm - margin,
                    width=30 * mm, height=30 * mm)

        ad_text = c.beginText(margin, height - 10 * mm)
        ad_text.setFont(FONT_NAME, 11)
        ad_text.textLine("───────── シン・コンピューター占い ─────────")
        ad_text.textLine("手相・四柱推命・イーチン占いで未来をサポート")
        ad_text.textLine("Instagram → @uranaya_official")
        ad_text.textLine("────────────────────────────")
        c.drawText(ad_text)

        y = height - 50 * mm
    else:
        y = height - 30 * mm

    def draw_title(title):
        nonlocal y
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, f"◆ {title}")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)

    def draw_wrapped_text(text):
        nonlocal y
        for line in wrap_text(text).split("\n"):
            c.drawString(margin, y, line)
            y -= 6 * mm
        y -= 4 * mm

    # === 表面 ===
    draw_title("相性占い／おすすめタイプ")
    draw_wrapped_text(result_data["compatibility_text"])

    draw_title("恋愛運全般（今年・今月・今日）")
    draw_wrapped_text(result_data["overall_love_fortune"])

    draw_title("ラッキー情報")
    draw_wrapped_text(result_data["lucky_info"])

    draw_title("吉方位（九星気学）")
    draw_wrapped_text(result_data["lucky_direction"])

    # === 裏面 ===
    c.showPage()
    y = height - 30 * mm

    draw_title("選択テーマ別の恋愛占い")
    for topic, text in result_data["topic_fortunes"].items():
        draw_title(f"【{topic}】")
        draw_wrapped_text(text)

    # === 年間恋愛運ページ（任意） ===
    if result_data.get("yearly_love_fortunes"):
        c.showPage()
        y = height - 30 * mm
        c.setFont(FONT_NAME, 13)
        c.drawString(margin, y, "◆ あなたの1年の恋愛運（前半）")
        y -= 10 * mm
        c.setFont(FONT_NAME, 11)
        for i, (month, fortune) in enumerate(result_data["yearly_love_fortunes"].items()):
            if i == 6:
                c.showPage()
                y = height - 30 * mm
                c.setFont(FONT_NAME, 13)
                c.drawString(margin, y, "◆ あなたの1年の恋愛運（後半）")
                y -= 10 * mm
                c.setFont(FONT_NAME, 11)
            c.drawString(margin, y, f"● {month}")
            y -= 6 * mm
            for line in wrap_text(fortune).split("\n"):
                c.drawString(margin, y, line)
                y -= 6 * mm
            y -= 4 * mm

    c.save()
