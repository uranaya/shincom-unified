
import datetime
from kyusei_utils import get_honmeisei, get_directions
import openai

def generate_lucky_info(nicchu_eto: str, birthdate: str) -> list[str]:
    prompt = f"""
あなたは占いのプロです。以下の干支と誕生日から、ラッキーアイテム、ラッキーカラー、ラッキーナンバー、ラッキーフード、ラッキーデーを1つずつ箇条書きで出力してください。
- 干支（日柱）: {nicchu_eto}
- 生年月日: {birthdate}
形式:
・ラッキーアイテム：〇〇
・ラッキーカラー：〇〇
・ラッキーナンバー：〇〇
・ラッキーフード：〇〇
・ラッキーデー：〇曜日
"""
    response = openai.client.chat.completions.create(
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
    c.setFont("IPAexGothic", 12)
    c.drawString(margin, y, "■ ラッキー情報（生年月日より）")
    y -= 12
    c.setFont("IPAexGothic", 12)
    for item in lucky_info:
        c.drawString(margin + 12, y, item)
        y -= 12
    y -= 6
    c.drawString(margin, y, f"■ 吉方位（九星気学より）{lucky_direction}")
    return y - 20
