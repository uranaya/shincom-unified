# -*- coding: utf-8 -*-
"""English header utilities.

This module is intentionally **API-compatible** with the Japanese `header_utils.draw_header`
so that English PDF generators can call:

    y = draw_header(c, page_width, margin, y_pos)

It also supports the older experimental signature:

    draw_header(c, page_width, page_height, title=...)

"""

from __future__ import annotations

from reportlab.lib.units import mm

try:
    import qrcode
    from reportlab.lib.utils import ImageReader
except Exception:  # pragma: no cover
    qrcode = None
    ImageReader = None


def _make_qr_image(qr_text: str):
    if qrcode is None or ImageReader is None:
        return None
    try:
        img = qrcode.make(qr_text)
        return ImageReader(img)
    except Exception:
        return None


def draw_header(
    c,
    page_width: float,
    *args,
    title: str = "Uranaya Fortune Report",
    subtitle: str | None = "Palm & Fortune Reading",
    tokyo_mode: bool = False,
    qr_text: str = "https://uranaya.jp",
):
    """Draw header and return updated y position.

    Supported call patterns:
      1) (c, page_width, margin, y_pos, ...)
      2) (c, page_width, page_height, ...)  # legacy experimental form
    """

    # Resolve args
    margin = None
    y_pos = None
    if len(args) >= 2:
        margin, y_pos = args[0], args[1]
    elif len(args) == 1:
        page_height = args[0]
        margin = 20 * mm
        y_pos = page_height - margin
    else:
        # Fallback to canvas size
        page_height = getattr(c, "_pagesize", (page_width, 297 * mm))[1]
        margin = 20 * mm
        y_pos = page_height - margin

    # Title
    try:
        c.setFont("Helvetica-Bold", 18)
    except Exception:
        pass
    c.drawString(margin, y_pos, title)

    # Subtitle / location
    y_after = y_pos - 14
    if subtitle:
        try:
            c.setFont("Helvetica", 10)
        except Exception:
            pass
        c.drawString(margin, y_after, subtitle)
        y_after -= 12

    if tokyo_mode:
        try:
            c.setFont("Helvetica", 9)
        except Exception:
            pass
        c.drawString(margin, y_after, "Tokyo / Asakusa")
        y_after -= 10

    # QR code (optional)
    qr_img = _make_qr_image(qr_text)
    if qr_img is not None:
        qr_size = 20 * mm
        qr_x = page_width - margin - qr_size
        # Align visually near the top block
        qr_y = y_pos - 18 * mm
        try:
            c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size)
        except Exception:
            pass

    return y_after - 4
