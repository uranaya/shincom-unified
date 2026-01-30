# header_utils_en.py
# English header renderer (kept separate so Japanese output is unaffected)

from reportlab.lib.utils import ImageReader
from PIL import Image
import qrcode
from io import BytesIO


def create_qr_code(url: str, box_size: int = 3, border: int = 1):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=box_size, border=border)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img


def draw_header(c, page_width, page_height, logo_path=None, shop_name="Uranaya", sub_title="Fortune Report",
                url_for_qr=None, font_name="IPAexGothic"):
    """
    Draw header on the first page only.
    - shop_name / sub_title are English strings.
    - url_for_qr: if provided, draws a QR code at top-right.
    """
    y = page_height - 40

    # Title
    try:
        c.setFont(font_name, 16)
    except Exception:
        c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, shop_name)

    try:
        c.setFont(font_name, 12)
    except Exception:
        c.setFont("Helvetica", 12)
    c.drawString(40, y - 18, sub_title)

    # QR code (optional)
    if url_for_qr:
        img = create_qr_code(url_for_qr)
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        qr_reader = ImageReader(bio)
        qr_size = 48
        c.drawImage(qr_reader, page_width - 40 - qr_size, y - 8 - qr_size, qr_size, qr_size, mask='auto')

    # Divider line
    c.setLineWidth(1)
    c.line(40, y - 28, page_width - 40, y - 28)

    return y - 40
