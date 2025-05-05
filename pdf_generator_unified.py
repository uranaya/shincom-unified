# 📄 pdf_generator_unified.py（Part 1/4: Imports & Utilities）
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, B4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from textwrap import wrap
from header_utils import draw_header
from lucky_utils import draw_lucky_section
import io
import datetime
from fortune_logic import generate_yearly_fortune

FONT_NAME = "IPAexGothic"
FONT_PATH = "./ipaexg.ttf"


def wrap_text(text, width=40):
    return "\n".join(wrap(text, width))


def draw_wrapped_text(c, text, x, y, max_width):
    lines = wrap(text, width=max_width)
    lines = wrap(text, width=max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= 12
    return y

# ===================== 通常版 A4 / B4 =====================

def draw_shincom_a4(c, data, include_yearly=False):
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    
    y = draw_header(c, width, margin, y)
# 表面（1ページ目）：手相3項目＋ラッキーまとめ
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "◆ 手相鑑定（特徴）")
    y -= 8 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["palm_result"]["item1"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["item2"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["item3"], margin, y, 40)
    y -= 4 * mm

    y = draw_lucky_section(c, width, margin, y, data["lucky_info"], data["lucky_direction"])

    c.showPage()

    # 裏面（2ページ目）：手相2項目＋総合＋性格・運勢
    y = height - 30 * mm
    
    y = draw_header(c, width, margin, y)
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "◆ 手相鑑定（続き）")
    y -= 8 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["palm_result"]["item4"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["item5"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["summary"], margin, y, 40)

    c.setFont(FONT_NAME, 12)
    y -= 6 * mm
    c.drawString(margin, y, "◆ 性格診断（四柱推命）")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["shichu_result"], margin, y, 40)

    c.setFont(FONT_NAME, 12)
    y -= 6 * mm
    c.drawString(margin, y, "◆ 今月・来月の運勢")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["iching_result"], margin, y, 40)

    c.showPage()

    # 年運（3～4ページ目）
    if include_yearly:
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])

def draw_shincom_b4(c, data, include_yearly=False):
    width, height = B4
    margin = 20 * mm
    y = height - 30 * mm

    
    y = draw_header(c, width, margin, y)
# 表面（1ページ目）：手相のみ
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "◆ 手相鑑定")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["palm_result"]["item1"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["item2"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["item3"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["item4"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["item5"], margin, y, 40)
    y = draw_wrapped_text(c, data["palm_result"]["summary"], margin, y, 40)

    c.showPage()

    # 裏面（2ページ目）：性格・運勢＋ラッキーまとめ
    y = height - 30 * mm
    
    y = draw_header(c, width, margin, y)
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "◆ 性格診断（四柱推命）")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["shichu_result"], margin, y, 40)

    c.setFont(FONT_NAME, 12)
    y -= 6 * mm
    c.drawString(margin, y, "◆ 今月・来月の運勢")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["iching_result"], margin, y, 40)

    c.setFont(FONT_NAME, 12)
    y -= 6 * mm
    c.drawString(margin, y, "◆ ラッキー情報（生年月日より）")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    for item in data["lucky_info"]:
        c.drawString(margin, y, f"・{item}")
        y -= 6 * mm

    c.showPage()

    if include_yearly:
        draw_yearly_pages_shincom(c, data["yearly_fortunes"])

# ===================== 恋愛版 A4 / B4 =====================

def draw_renai_a4(c, data, include_yearly=False):
    width, height = A4
    margin = 20 * mm
    y = height - 30 * mm

    
    y = draw_header(c, width, margin, y)
# 表面（1ページ目）：相性＋総合＋ラッキーまとめ
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "◆ 相性診断結果")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["compatibility_text"], margin, y, 40)

    c.setFont(FONT_NAME, 12)
    y -= 6 * mm
    c.drawString(margin, y, "◆ 総合恋愛運")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["overall_love_fortune"], margin, y, 40)

    c.setFont(FONT_NAME, 12)
    y -= 6 * mm
    c.drawString(margin, y, "◆ ラッキー情報（生年月日より）")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    for item in data["lucky_info"]:
        c.drawString(margin, y, f"・{item}")
        y -= 6 * mm

    c.showPage()

    # 裏面（2ページ目）：テーマ別恋愛運（3項目以内推奨）
    y = height - 30 * mm
    
    y = draw_header(c, width, margin, y)
    c.setFont(FONT_NAME, 12)
    for title, text in data["topic_fortunes"].items():
        c.drawString(margin, y, f"◆ {title}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        y = draw_wrapped_text(c, text, margin, y, 40)
        y -= 4 * mm
        c.setFont(FONT_NAME, 12)

    c.showPage()

    if include_yearly:
        draw_yearly_pages_renai(c, data["yearly_love_fortunes"])


def draw_renai_b4(c, data, include_yearly=False):
    width, height = B4
    margin = 20 * mm
    y = height - 30 * mm

    
    y = draw_header(c, width, margin, y)
# 表面（1ページ目）：相性＋総合＋ラッキーまとめ
    c.setFont(FONT_NAME, 12)
    c.drawString(margin, y, "◆ 相性診断結果")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["compatibility_text"], margin, y, 40)

    c.setFont(FONT_NAME, 12)
    y -= 6 * mm
    c.drawString(margin, y, "◆ 総合恋愛運")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    y = draw_wrapped_text(c, data["overall_love_fortune"], margin, y, 40)

    c.setFont(FONT_NAME, 12)
    y -= 6 * mm
    c.drawString(margin, y, "◆ ラッキー情報（生年月日より）")
    y -= 6 * mm
    c.setFont(FONT_NAME, 10)
    for item in data["lucky_info"]:
        c.drawString(margin, y, f"・{item}")
        y -= 6 * mm

    c.showPage()

    # 裏面（2ページ目）：テーマ別恋愛運
    y = height - 30 * mm
    
    y = draw_header(c, width, margin, y)
    c.setFont(FONT_NAME, 12)
    for title, text in data["topic_fortunes"].items():
        c.drawString(margin, y, f"◆ {title}")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        y = draw_wrapped_text(c, text, margin, y, 40)
        y -= 4 * mm
        c.setFont(FONT_NAME, 12)

    c.showPage()

    if include_yearly:
        draw_yearly_pages_renai(c, data["yearly_love_fortunes"])


def draw_yearly_pages_shincom(c, yearly_fortunes):
    width, height = A4
    margin = 20 * mm
    items = list(yearly_fortunes.items())
    for page_num in range(2):
        c.setFont(FONT_NAME, 12)
        y = height - 30 * mm
        
    y = draw_header(c, width, margin, y)
    c.drawString(margin, y, f"◆ 年間の運勢（{'前半' if page_num == 0 else '後半'}）")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for i in range(6):
            idx = page_num * 6 + i
            if idx >= len(items): break
            month, text = items[idx]
            c.drawString(margin, y, f"・{month}月")
            y -= 6 * mm
            y = draw_wrapped_text(c, text, margin + 10 * mm, y, 40)
            y -= 8 * mm
        c.showPage()

def draw_yearly_pages_renai(c, yearly_fortunes):
    width, height = A4
    margin = 20 * mm
    items = list(yearly_fortunes.items())
    for page_num in range(2):
        c.setFont(FONT_NAME, 12)
        y = height - 30 * mm
        
    y = draw_header(c, width, margin, y)
    c.drawString(margin, y, f"◆ 年間の恋愛運（{'前半' if page_num == 0 else '後半'}）")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)
        for i in range(6):
            idx = page_num * 6 + i
            if idx >= len(items): break
            month, text = items[idx]
            c.drawString(margin, y, f"・{month}月")
            y -= 6 * mm
            y = draw_wrapped_text(c, text, margin + 10 * mm, y, 40)
            y -= 8 * mm
        c.showPage()


# ===================== 年運ページ（共通） =====================

# 年運ページ描画をモードごとに分離c, yearly_fortunes):
    width, height = A4
    margin = 20 * mm
    items = list(yearly_fortunes.items())

    for page_num in range(2):  # 最大2ページ
        c.setFont(FONT_NAME, 12)
        y = height - 30 * mm
        
    y = draw_header(c, width, margin, y)
    c.drawString(margin, y, f"◆ 年間の運勢（{ '前半' if page_num == 0 else '後半' }）")
        y -= 6 * mm
        c.setFont(FONT_NAME, 10)

        for i in range(6):
            idx = page_num * 6 + i
            if idx >= len(items):
                break
            month, text = items[idx]
            c.drawString(margin, y, f"・{month}")
            y -= 6 * mm
            y = draw_wrapped_text(c, text, margin + 10 * mm, y, 40)
            y -= 8 * mm

        c.showPage()


# ===================== PDF生成ルート関数 =====================

def create_pdf(mode, size, data, filename, include_yearly=False):
    if size == "A4":
        c = canvas.Canvas(filename, pagesize=A4)
    else:
        c = canvas.Canvas(filename, pagesize=B4)

    if mode == "shincom":
        if size == "A4":
            draw_shincom_a4(c, data, include_yearly)
        else:
            draw_shincom_b4(c, data, include_yearly)
    else:
        if size == "A4":
            draw_renai_a4(c, data, include_yearly)
        else:
            draw_renai_b4(c, data, include_yearly)

    c.save()