import os
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# Korean PDF header utils
# Use ReportLab bundled CID font to avoid missing TTF on server.
FONT_NAME = "HYGothic-Medium"
try:
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
except Exception as e:
    print("Font registration error in header_utils_ko:", e)


def create_qr_code(url, path="qr_uranaya.png"):
    """Create a QR code image file for the given URL if not already present."""
    if not os.path.exists(path):
        import qrcode
        img = qrcode.make(url)
        img.save(path)
    return path


def draw_header(c, width, margin, y_pos, font=FONT_NAME):
    """Draw common header (QR advertisement block) in Korean."""
    qr_ad_path = create_qr_code("https://uranaya.wixsite.com/uranaya", path="qr_uranaya.png")
    if os.path.exists(qr_ad_path):
        c.drawImage(qr_ad_path, width - margin - 30 * mm, y_pos - 30 * mm, width=30 * mm, height=30 * mm)
        ad_text = c.beginText(margin, y_pos - 10)
        ad_text.setFont(font, 11)
        ad_text.textLine("───────── 신(新) 컴퓨터 점술 ────────────")
        ad_text.textLine("【점술관 · 점술사 ‘うらなや’ 감수】")
        ad_text.textLine("미래는 당신의 행동으로 바뀝니다")
        ad_text.textLine("더 자세한 상담이나 개인적인 고민이 있다면")
        ad_text.textLine("‘대면 상담’ ‘전화 상담’ ‘온라인 상담’도 가능합니다.")
        ad_text.textLine("자세한 내용은 여기에서 →")
        ad_text.textLine("──────────────────────────────────")
        c.drawText(ad_text)
        y_pos -= 50 * mm
    return y_pos
