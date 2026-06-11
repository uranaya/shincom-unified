# -*- coding: utf-8 -*-
# 猫占いPDF表示の最終修正パッチ。
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "pdf_generator_unified.py"

if not PDF.exists():
    raise SystemExit("pdf_generator_unified.py が見つかりません。shincom-unified のルートで実行してください。")

text = PDF.read_text(encoding="utf-8")
bak = PDF.with_suffix(PDF.suffix + ".bak_neko_pdf_detail")
if not bak.exists():
    shutil.copy2(PDF, bak)

new_func = """
def draw_neko_uranai_page(c, data, lang="ja", page_size=A4):
    # 猫占いオプション用の追加1ページ。
    # PDF上では動物占い名は出さず、猫占いとして独立表示する。
    neko = (data or {}).get("neko_uranai") or {}
    if not neko:
        return

    width, height = page_size
    margin = 18 * mm
    c.showPage()
    y = height - margin
    y = draw_header(c, width, margin, y)

    _set_font(c, lang, 18)
    c.drawCentredString(width / 2, y, "猫占い")
    y -= 10 * mm

    number = neko.get("number") or ""
    name = neko.get("name") or "猫"
    tag = neko.get("tag") or ""
    description = (
        neko.get("description")
        or neko.get("personality")
        or neko.get("性質")
        or neko.get("性格")
        or ""
    )

    _set_font(c, lang, 12)
    c.drawString(margin, y, f"◆ あなたの猫タイプ：{number}. {name}")
    y -= 6 * mm

    _set_font(c, lang, 10.2)
    if tag:
        c.drawString(margin, y, f"猫キャラの一言：{tag}")
        y -= 6 * mm

    # 猫画像。説明文を厚く入れるため、以前より少し小さめにする。
    image_path = neko.get("image_path") or ""
    try:
        if image_path and os.path.exists(image_path):
            img = ImageReader(image_path)
            iw, ih = img.getSize()
            max_w = 50 * mm
            max_h = 50 * mm
            scale = min(max_w / iw, max_h / ih)
            draw_w, draw_h = iw * scale, ih * scale
            x = (width - draw_w) / 2
            c.drawImage(img, x, y - draw_h, width=draw_w, height=draw_h, mask='auto')
            y -= draw_h + 7 * mm
        else:
            c.drawCentredString(width / 2, y, "（猫画像が見つかりません）")
            y -= 9 * mm
    except Exception as e:
        print("Neko image draw error:", e)
        c.drawCentredString(width / 2, y, "（猫画像の読み込みに失敗しました）")
        y -= 9 * mm

    bottom = 18 * mm

    # 性質・性格
    _set_font(c, lang, 13)
    c.drawString(margin, y, "◆ 性質・性格")
    y -= 6 * mm

    if not description:
        description = f"{name}は、自分らしい感覚と猫のような勘を大切にするタイプです。無理に周囲へ合わせすぎず、心が落ち着く場所と人を選ぶことで本来の魅力が伸びていきます。"

    _set_font(c, lang, 9.7)
    for line in smart_wrap(description, 42, lang):
        if y < bottom + 44 * mm:
            break
        c.drawString(margin, y, line)
        y -= 5.0 * mm

    y -= 3 * mm

    # 猫御籤
    _set_font(c, lang, 13)
    c.drawString(margin, y, "◆ 猫御籤")
    y -= 6 * mm

    omikuji = neko.get("omikuji") or "今日はひげの向く方へ、ゆっくり進むにゃ。"
    _set_font(c, lang, 9.7)
    for line in smart_wrap(omikuji, 42, lang):
        if y < bottom:
            break
        c.drawString(margin, y, line)
        y -= 5.0 * mm

    y -= 3 * mm
    if y >= bottom + 10 * mm:
        _set_font(c, lang, 10.5)
        c.drawString(margin, y, "◆ 今日の合言葉")
        y -= 5.5 * mm
        _set_font(c, lang, 9.7)
        c.drawString(margin, y, "焦らず、すり寄りすぎず、必要な時だけ爪を出すにゃん。")
"""

pattern = re.compile(
    r'def draw_neko_uranai_page\(c, data, lang="ja", page_size=A4\):.*?(?=\ndef draw_shincom_a4\(c, data, include_yearly=False\):)',
    re.S,
)
new_text, n = pattern.subn(new_func.strip() + "\n\n", text)
if n != 1:
    raise SystemExit("draw_neko_uranai_page の置換に失敗しました。pdf_generator_unified.py の構造が想定と違います。")

PDF.write_text(new_text, encoding="utf-8")
print("OK: pdf_generator_unified.py の猫占いPDF表示を修正しました。")
print("バックアップ:", bak)
