# -*- coding: utf-8 -*-
"""English header utilities.

This module is intentionally separate from header_utils.py so the Japanese
output remains untouched.

Key points:
- QR code is drawn using ReportLab's built-in QR widget (no external dependency).
- Returns the updated y position, matching the call pattern in generators.
"""

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF


DEFAULT_QR_URL = "https://uranaya.wixsite.com/shin-comfortune"


def draw_qr(c, url: str, x: float, y: float, size: float) -> None:
    """Draw a QR code (square) with top-left at (x, y+size)."""
    widget = qr.QrCodeWidget(url)
    bounds = widget.getBounds()  # (x0, y0, x1, y1)
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    if w <= 0 or h <= 0:
        return
    # Scale via Drawing transform (QrCodeWidget itself doesn't reliably expose scale()).
    sx = size / w
    sy = size / h
    d = Drawing(size, size, transform=[sx, 0, 0, sy, 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, x, y)


def draw_header_en(c, page_width: float, margin: float, y_pos: float,
                   font_name: str,
                   qr_url: str = DEFAULT_QR_URL) -> float:
    """Draw an English header on the current page and return the next y."""

    # Top rule
    c.setLineWidth(0.5)
    top_y = y_pos
    c.line(margin, top_y, page_width - margin, top_y)

    # Title (centered)
    title = "Shin Computer Fortune"
    c.setFont(font_name, 12)
    tw = stringWidth(title, font_name, 12)
    c.drawString((page_width - tw) / 2, top_y + 2, title)

    # Left block text
    c.setFont(font_name, 9)
    left_x = margin + 2
    text_y = top_y - 12
    lines = [
        "Supervised by Fortune Teller 'Uranaya'",
        "Your future can change through your own actions.",
        "If you'd like a deeper reading or have personal concerns,",
        "we also offer in-person / phone / online sessions.",
        "Scan here for details →",
    ]
    for ln in lines:
        c.drawString(left_x, text_y, ln)
        text_y -= 11

    # QR (right)
    qr_size = 28 * mm
    qr_x = page_width - margin - qr_size
    qr_y = top_y - qr_size - 4
    try:
        draw_qr(c, qr_url, qr_x, qr_y, qr_size)
    except Exception:
        # If something unexpected happens, just skip QR without crashing.
        pass

    # "SCAN HERE" label (above QR, not under the rule)
    label = "SCAN HERE"
    c.setFont(font_name, 8)
    lw = stringWidth(label, font_name, 8)
    c.drawString(qr_x + (qr_size - lw) / 2, qr_y + qr_size + 2, label)

    # Bottom rule for header block
    bottom_y = qr_y - 6
    c.setLineWidth(0.5)
    c.line(margin, bottom_y, page_width - margin, bottom_y)

    # Return next y (below header)
    return bottom_y - 18
