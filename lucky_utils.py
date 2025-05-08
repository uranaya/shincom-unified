import datetime
from kyusei_utils import get_honmeisei, get_directions
import openai
import os


# ✅ APIキーの指定（必須）
openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_lucky_info(nicchu_eto: str, birthdate: str) -> list[str]:
    prompt = f"""
あなたは占いのプロです。以下の干支と生年月日から、ラッキー情報を端的に1行ずつ出力してください。補足説明は不要です。

- 干支（日柱）: {nicchu_eto}
- 生年月日: {birthdate}

以下の形式で出力してください（各項目は1語または短文）：
・ラッキーアイテム：〇〇  
・ラッキーカラー：〇〇  
・ラッキーナンバー：〇〇  
・ラッキーフード：〇〇  
・ラッキーデー：〇曜日

"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response["choices"][0]["message"]["content"].splitlines()

def generate_lucky_direction(birthdate: str, today: datetime.date) -> str:
    honmeisei = get_honmeisei(birthdate)
    good_dir, bad_dir = get_directions(today.year, today.month, honmeisei)
    next_month = today + datetime.timedelta(days=30)
    good_dir_next, bad_dir_next = get_directions(next_month.year, next_month.month, honmeisei)
    return f"今年の吉方位は{good_dir}、今月は{good_dir}、来月は{good_dir_next}です。"

def draw_lucky_section(c, width, margin, y, lucky_info, lucky_direction):
    from reportlab.lib.units import mm
    c.setFont("IPAexGothic", 11)

    # ラッキー情報タイトル
    c.drawString(margin, y, "■ ラッキー情報（生年月日より）")
    y -= 8 * mm

    # ラッキー情報リスト（存在チェック）
    if lucky_info:
        for item in lucky_info:
            if item and isinstance(item, str):
                for line in wrap(item.strip(), 40):  # 横幅制限追加
                    c.drawString(margin + 10, y, line)
                    y -= 6 * mm
    else:
        c.drawString(margin + 10, y, "情報が取得できませんでした。")
        y -= 6 * mm

    y -= 4 * mm  # 少し余白

    # 吉方位タイトル＋中身（存在チェック）
    if lucky_direction and isinstance(lucky_direction, str) and lucky_direction.strip():
        c.drawString(margin, y, "■ 吉方位（九星気学より）")
        y -= 6 * mm
        for line in wrap(lucky_direction.strip(), 42):  # 横幅制限追加
            c.drawString(margin + 10, y, line)
            y -= 6 * mm
    else:
        c.drawString(margin, y, "■ 吉方位（九星気学より）情報未取得")
        y -= 6 * mm

    return y - 10 * mm
