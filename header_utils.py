def draw_header(c, width, margin, y_pos, font=FONT_NAME):
    from common_qr import create_qr_code  # QR作成ユーティリティ（既存利用）
    import os

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
        return y_pos - 50 * mm
    return y_pos