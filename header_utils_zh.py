import os
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# Chinese (Simplified) PDF header utils
# Use CID font bundled with ReportLab to avoid missing TTF on server.
FONT_NAME = "STSong-Light"
try:
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
except Exception as e:
    print("Font registration error in header_utils_zh:", e)


def create_qr_code(url, path="qr_uranaya.png"):
    """Create a QR code image file for the given URL if not already present."""
    if not os.path.exists(path):
        import qrcode
        img = qrcode.make(url)
        img.save(path)
    return path


def draw_header(c, width, margin, y_pos, font=FONT_NAME):
    """Draw common header (QR advertisement block) in Simplified Chinese."""
    qr_ad_path = create_qr_code("https://uranaya.wixsite.com/uranaya", path="qr_uranaya.png")
    if os.path.exists(qr_ad_path):
        c.drawImage(qr_ad_path, width - margin - 30 * mm, y_pos - 30 * mm, width=30 * mm, height=30 * mm)
        ad_text = c.beginText(margin, y_pos - 10)
        ad_text.setFont(font, 11)
        ad_text.textLine("───────── 新·电脑占卜 ────────────")
        ad_text.textLine("【占卜馆·占卜师「うらなや」监修】")
        ad_text.textLine("未来会因你的行动而改变")
        ad_text.textLine("想要更深入占卜，或有个人烦恼的人")
        ad_text.textLine("也可以选择「面对面」「电话」「在线」鉴定。")
        ad_text.textLine("详情请看这里 →")
        ad_text.textLine("──────────────────────────────────")
        c.drawText(ad_text)
        y_pos -= 50 * mm
    return y_pos
