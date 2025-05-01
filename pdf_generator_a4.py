import base64
import os
from reportlab.lib.pagesizes import A4
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
from PIL import Image
from io import BytesIO
import textwrap
from affiliate import create_qr_code, get_affiliate_link
from fortune_logic import generate_fortune
from kyusei_utils import get_kyusei_fortune_openai as get_kyusei_fortune
from yearly_fortune_utils import generate_yearly_fortune


FONT_NAME = "IPAexGothic"
FONT_PATH = "ipaexg.ttf"
pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

def save_image(image_data, filename):
    try:
        with open(filename, "wb") as f:
            f.write(base64.b64decode(image_data.split(",")[1]))
        return filename
    except Exception as e:
        print(f"❌ 画像保存失敗: {e}")
        return None


def compress_base64_image(base64_image_data, output_width=600):
    image_data = base64.b64decode(base64_image_data.split(",", 1)[1])
    image = Image.open(BytesIO(image_data))
    w_percent = output_width / float(image.size[0])
    h_size = int((float(image.size[1]) * float(w_percent)))
    image = image.resize((output_width, h_size), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    compressed_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{compressed_base64}"

def split_palm_sections(palm_text):
    sections = {}
    current_key = None
    buffer = []

    for line in palm_text.split("\n"):
        line = line.strip()
        if line.startswith("### 1."):
            if current_key:
                sections[current_key] = "\n".join(buffer).strip()
                buffer = []
            current_key = "1"
        elif line.startswith("### 2."):
            sections[current_key] = "\n".join(buffer).strip()
            current_key = "2"
            buffer = []
        elif line.startswith("### 3."):
            sections[current_key] = "\n".join(buffer).strip()
            current_key = "3"
            buffer = []
        elif line.startswith("### 4."):
            sections[current_key] = "\n".join(buffer).strip()
            current_key = "4"
            buffer = []
        elif line.startswith("### 5."):
            sections[current_key] = "\n".join(buffer).strip()
            current_key = "5"
            buffer = []
        elif line.startswith("### 総合的なアドバイス"):
            sections[current_key] = "\n".join(buffer).strip()
            current_key = "summary"
            buffer = []
        else:
            buffer.append(line)
    if current_key:
        sections[current_key] = "\n".join(buffer).strip()
    return sections

def create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    filepath = os.path.join("static", filename)
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    margin = 15 * mm
    font = FONT_NAME
    font_size = 11
    wrapper = textwrap.TextWrapper(width=45)
    y = height - margin

    # === 手相画像保存（圧縮付き）===
    image_data = compress_base64_image(image_data)
    image_path = f"palm_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    with open(image_path, "wb") as f:
        f.write(base64.b64decode(image_data.split(",", 1)[1]))

    # === 手相項目分割 ===
    sections = split_palm_sections(palm_result)

    # === 表面 ===
    # QR広告（右上）
    qr_ad_path = create_qr_code("https://uranaya.jp", path="qr_uranaya.png")
    if os.path.exists(qr_ad_path):
        c.drawImage(qr_ad_path, width - margin - 30 * mm, y - 30 * mm, width=30 * mm, height=30 * mm)
        ad_text = c.beginText(margin, y - 10)
        ad_text.setFont(font, 11)
        ad_text.textLine("───────── シン・コンピューター占い ─────────")
        ad_text.textLine("手相・四柱推命・イーチン占いで未来をサポート")
        ad_text.textLine("Instagram → @uranaya_official")
        ad_text.textLine("────────────────────────────")
        c.drawText(ad_text)
        y -= 50 * mm

    # 手相画像
    c.drawImage(image_path, (width - 150 * mm) / 2, y - 90 * mm, width=150 * mm, height=90 * mm)
    y -= 100 * mm

    # 手相項目1〜3
    text = c.beginText(margin, y)
    text.setFont(font, font_size)
    text.textLine("■ 手相鑑定（代表3項目）")
    text.textLine("")
    for i in ["1", "2", "3"]:
        if i in sections:
            for line in wrapper.wrap(sections[i]):
                text.textLine(line)
            text.textLine("")

    c.drawText(text)

    # === 裏面 ===
    c.showPage()
    y = height - margin
    text = c.beginText(margin, y)
    text.setFont(font, font_size)

    # 手相項目4〜5＋まとめ
    text.textLine("■ 手相鑑定（4〜5項目目 + 総合アドバイス）")
    text.textLine("")
    for i in ["4", "5", "summary"]:
        if i in sections:
            for line in wrapper.wrap(sections[i]):
                text.textLine(line)
            text.textLine("")

    # 四柱推命
    text.textLine("■ 四柱推命によるアドバイス")
    text.textLine("")
    for paragraph in shichu_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    # イーチン占い
    text.textLine("■ イーチン占い アドバイス")
    text.textLine("")
    for paragraph in iching_result.split("\n"):
        for line in wrapper.wrap(paragraph.strip()):
            text.textLine(line)
        text.textLine("")

    # ラッキー情報
    text.textLine("■ ラッキーアイテム・カラー・ナンバー")
    text.textLine("")
    for line in lucky_info.split("\n"):
        for wrapped in wrapper.wrap(line.strip()):
            text.textLine(wrapped)

    # 吉方位の追加（例：生年月日 1990年4月15日）
    fortune_text = get_kyusei_fortune(1990, 4, 15)
    text.textLine("")
    text.textLine("■ 吉方位（九星気学より）")
    text.textLine(fortune_text)

    c.drawText(text)

    c.save()
    return filepath

def create_pdf_a4(image_data, palm_result, shichu_result, iching_result, lucky_info, filename):
    c = canvas.Canvas(f"static/{filename}", pagesize=A4)
    width, height = A4
    margin = 20 * mm
    text_width = width - 2 * margin

    # タイトル
    c.setFont(FONT_NAME, 16)
    c.drawCentredString(width / 2, height - margin, "鑑定結果")

    # 手相画像
    image_path = save_image(image_data, "temp_hand.jpg")
    if image_path:
        c.drawImage(image_path, margin, height - 200, width=120, preserveAspectRatio=True)

    # 鑑定内容
    c.setFont(FONT_NAME, 10)
    y = height - 220

    for title, content in [
        ("【手相鑑定】", palm_result),
        ("【性格・今月・来月の運勢】", shichu_result),
        ("【今のあなたに必要なメッセージ】", iching_result),
        ("【ラッキー情報】", lucky_info)
    ]:
        c.drawString(margin, y, title)
        y -= 15
        for line in textwrap.wrap(content, width=45):
            c.drawString(margin, y, line)
            y -= 12
        y -= 10

    c.showPage()
    c.save()


def create_pdf_yearly(birthdate: str, filename: str):
    data = generate_yearly_fortune(birthdate)

    pdf = canvas.Canvas(filename, pagesize=A4)
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))

    y = 280 * mm
    y = _draw_block(pdf, data["year_label"], data["year_text"], y)

    for m in data["months"]:
        y = _draw_block(pdf, m["label"], m["text"], y)
        if y < 50 * mm:
            pdf.showPage()
            y = 280 * mm

    pdf.save()

def create_pdf_combined(image_data, birthdate, filename):
    os.makedirs("static", exist_ok=True)

    file_front = f"front_{filename}"
    file_year  = f"year_{filename}"

    print("📄 front作成開始:", file_front)
    try:
        palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
        create_pdf_a4(image_data, palm_result, shichu_result, iching_result, lucky_info, file_front)
        if not os.path.exists(file_front):
            print("❌ front PDFが作成されていません:", file_front)
    except Exception as e:
        print("❌ front PDF作成失敗:", e)
        raise

    print("📄 yearly作成開始:", file_year)
    try:
        create_pdf_yearly(birthdate, file_year)
        if not os.path.exists(file_year):
            print("❌ yearly PDFが作成されていません:", file_year)
    except Exception as e:
        print("❌ yearly PDF作成失敗:", e)
        raise

    try:
        print("📎 PDFマージ開始")
        merger = PdfMerger()
        merger.append(file_front)
        merger.append(file_year)
        merged_path = f"static/{filename}"
        merger.write(merged_path)
        merger.close()
        print("✅ マージ成功:", merged_path)

        # 不要な一時ファイルを削除
        os.remove(file_front)
        os.remove(file_year)

    except Exception as e:
        print("❌ PDFマージまたは削除失敗:", e)
        raise

# pdf_generator_a4.py の末尾に追加
create_pdf = create_pdf_combined