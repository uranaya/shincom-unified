# pdf_generator_unified_en.py（要約）
import io, base64
from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
# フォント登録と言語ヘルパー（英語: Times, 日本語: IPAexGothic）
FONT_NAME_JA = "IPAexGothic"; FONT_NAME_EN = "Times-Roman"
# ...（省略：フォント登録と_wrap_lines実装）...

def draw_header_en(c, page_width, margin_left, margin_right, y):
    # ヘッダー描画（上部ライン、タイトル、監修）※日本語タイトルはIPAexで
    c.setLineWidth(0.5)
    c.line(margin_left, y, page_width - margin_right, y); y -= 12
    c.setFont(FONT_NAME_JA, 12)
    c.drawCentredString(page_width/2, y, "シン・コンピューター占い"); y -= 16
    c.setFont(FONT_NAME_JA, 10)
    c.drawString(margin_left, y, "占いの館・占い師『うらなや』監修"); y -= 14
    return y

def draw_palm_image(c, base64_image, page_width, y):
    # 手相画像の描画（幅70%に縮小して中央配置）
    # ...（省略：画像デコードと縮小処理）...
    x_center = (page_width - img_width) / 2
    y -= img_height + 5*mm
    c.drawImage(img, x_center, y, width=img_width, height=img_height)
    y -= 10*mm
    return y

def create_pdf_unified_en(filepath, data, mode, size='a4', include_yearly=False):
    """英語版PDF生成メイン関数"""
    c = canvas.Canvas(filepath, pagesize=A4 if size.lower()=='a4' else B4)
    c.setTitle("Fortune Result")  # PDFタイトルを英語表記に設定
    if mode == 'shincom':
        _draw_shincom_en(c, data, page_size=size.lower(), include_yearly=include_yearly)
    else:
        # 恋愛占い等はデフォルト生成を呼び出し
        from pdf_generator_unified import create_pdf_unified
        data.setdefault('lang', 'en')
        create_pdf_unified(filepath, data, mode, size=size.lower(), include_yearly=include_yearly)
        return
    c.save()

def _draw_shincom_en(c, data, page_size='a4', include_yearly=False):
    lang = 'en'
    width, height = (A4 if page_size=='a4' else B4)
    margin_left = 14*mm; margin_right = 8*mm
    top_margin = margin_left; bottom_margin = 10*mm
    y = draw_header_en(c, width, margin_left, margin_right, height - top_margin)
    y = draw_palm_image(c, data.get("palm_image", ""), width, y)
    # 生年月日・星座・干支など情報を1～2行で表示
    info_lines = []
    # ...（省略：birthdate, zodiac, eto 等から info_lines を作成）...
    if info_lines:
        _set_font(c, lang, 11)
        for line in info_lines:
            c.drawString(margin_left, y, line); y -= 5*mm
        y -= 3*mm
    # ◆手相項目 1～3（1ページ目）
    _set_font(c, lang, 12)
    for i in range(3):
        c.drawString(margin_left, y, f"◆ {data['palm_titles'][i]}")
        y -= 6*mm
        _set_font(c, lang, 10)
        for line in wrap_lines(data['palm_texts'][i], lang, _font(lang), 10, width - margin_left - margin_right, 100):
            if y < bottom_margin + 5*mm:
                c.showPage(); y = height - top_margin; _set_font(c, lang, 10)
            c.drawString(margin_left, y, line); y -= 5*mm
        y -= 3*mm
        _set_font(c, lang, 12)
    # 1ページ目下部にQRコードとラベルを配置
    qr_size = 30*mm; qr_x = width - margin_right - qr_size; qr_y = bottom_margin
    c.setFont(FONT_NAME_EN, 9)
    c.drawCentredString(qr_x + qr_size/2, qr_y + qr_size + 3*mm, "SCAN HERE")
    qr_content = os.getenv("QR_URL", os.getenv("BASE_URL", ""))  # 埋め込むURL
    if qr_content:
        # ReportLabでQRコード生成
        from reportlab.graphics import renderPDF
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics.barcode import qr
        qr_code = qr.QrCodeWidget(qr_content)
        bounds = qr_code.getBounds()
        scale = qr_size / (bounds[2] - bounds[0])
        d = Drawing(qr_size, qr_size, transform=[scale,0,0,scale,0,0])
        d.add(qr_code)
        renderPDF.draw(d, c, qr_x, qr_y)
    # 2ページ目以降に残り項目と結果を描画
    c.showPage(); y = height - top_margin
    _set_font(c, lang, 12)
    for i in range(3, 5):
        c.drawString(margin_left, y, f"◆ {data['palm_titles'][i]}")
        y -= 6*mm
        _set_font(c, lang, 10)
        for line in wrap_lines(data['palm_texts'][i], lang, _font(lang), 10, width - margin_left - margin_right, 100):
            if y < bottom_margin + 5*mm:
                c.showPage(); y = height - top_margin; _set_font(c, lang, 10)
            c.drawString(margin_left, y, line); y -= 5*mm
        y -= 3*mm
        _set_font(c, lang, 12)
    # ◆手相総合アドバイス・性格診断・年/月/来月運勢
    sections = ['palm_summary','personality','year_fortune','month_fortune','next_month_fortune']
    for key in sections:
        title = data.get('titles', {}).get(key, '')
        content = data.get('texts', {}).get(key, '')
        if title:
            c.drawString(margin_left, y, f"◆ {title}"); y -= 6*mm
        _set_font(c, lang, 10)
        if content:
            for line in wrap_lines(content, lang, _font(lang), 10, width - margin_left - margin_right, 100):
                if y < bottom_margin + 5*mm:
                    c.showPage(); y = height - top_margin; _set_font(c, lang, 10)
                c.drawString(margin_left, y, line); y -= 5*mm
        y -= 4*mm
        _set_font(c, lang, 12)
    # ラッキー情報・吉方位セクション（英語表記で出力）
    from pdf_generator_unified import draw_lucky_section
    y = draw_lucky_section(c, width, margin_left, y, data.get('lucky_info', []), data.get('lucky_direction', ""), lang=lang)
