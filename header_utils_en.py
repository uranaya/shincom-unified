import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

# Fallback JA font (if available)
JA_FONT_NAME = "IPAexGothic"
JA_FONT_CANDIDATES = [
    "ipaexg.ttf",
    "/opt/render/project/src/ipaexg.ttf",
    "/opt/render/project/src/static/fonts/ipaexg.ttf",
]

def _ensure_ja_font():
    try:
        if JA_FONT_NAME in pdfmetrics.getRegisteredFontNames():
            return True
        for p in JA_FONT_CANDIDATES:
            if os.path.exists(p):
                pdfmetrics.registerFont(TTFont(JA_FONT_NAME, p))
                return True
    except Exception:
        pass
    return False

def _has_non_ascii(s: str) -> bool:
    try:
        return any(ord(ch) > 127 for ch in (s or ""))
    except Exception:
        return False

def _font_for_text(text: str, default_font: str = "Times-Roman") -> str:
    if _has_non_ascii(text):
        if _ensure_ja_font():
            return JA_FONT_NAME
    return default_font

def _draw_qr(c, x, y, size, url):
    widget = QrCodeWidget(url or "")
    bounds = widget.getBounds()
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, x, y)

def draw_header(c, page_width, margin_or_page_height, y_or_qr=None, qr_url="https://uranaya.online", lang="en"):
    """
    Header for the English report.

    New signature (used by pdf_generator_unified_en):
        draw_header(c, page_width, margin, y_top) -> returns new y

    Backward-compatible signature:
        draw_header(c, page_width, page_height, qr_url="...") -> returns y after header
    """
    # --- signature normalization ---
    if y_or_qr is None:
        # called as (c, page_width, page_height)
        page_height = float(margin_or_page_height)
        margin = 40
        y_top = page_height - margin
        qr = qr_url
    elif isinstance(y_or_qr, (str, bytes)):
        # called as (c, page_width, page_height, qr_url)
        page_height = float(margin_or_page_height)
        margin = 40
        y_top = page_height - margin
        qr = y_or_qr.decode() if isinstance(y_or_qr, bytes) else y_or_qr
    else:
        # called as (c, page_width, margin, y_top)
        margin = float(margin_or_page_height)
        y_top = float(y_or_qr)
        qr = qr_url

    header_h = 42 * mm
    box_w = page_width - 2 * margin
    y0 = y_top - header_h

    # Outline box (JP-like)
    c.rect(margin, y0, box_w, header_h)

    # QR
    qr_size = 28 * mm
    qr_x = margin + box_w - qr_size - 6 * mm
    qr_y = y0 + (header_h - qr_size) / 2
    try:
        _draw_qr(c, qr_x, qr_y, qr_size, qr)
    except Exception:
        pass

    # Text block
    x_text = margin + 6 * mm
    y_text = y_top - 10 * mm

    title = "Uranaya Fortune Report"
    subtitle = "Palm & Fortune Reading"
    note = "Scan QR to reopen this report"

    # Title
    c.setFont(_font_for_text(title, "Times-Bold"), 18)
    c.drawString(x_text, y_text, title)
    y_text -= 8 * mm

    # Subtitle
    c.setFont(_font_for_text(subtitle, "Times-Roman"), 11)
    c.drawString(x_text, y_text, subtitle)
    y_text -= 7 * mm

    # Site + note
    site = "uranaya.online"
    c.setFont(_font_for_text(site, "Times-Roman"), 9.5)
    c.drawString(x_text, y_text, site)
    y_text -= 5.5 * mm

    c.setFont(_font_for_text(note, "Times-Roman"), 9)
    c.drawString(x_text, y_text, note)

    # Return baseline for content
    return y0 - 10 * mm

# Keep old name for backward compatibility (if used somewhere)
def draw_header_en(c, page_width, page_height, qr_url="https://uranaya.online"):
    return draw_header(c, page_width, page_height, qr_url)