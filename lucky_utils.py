import datetime
from dateutil.relativedelta import relativedelta   # ★ この行を追加
from kyusei_utils import get_honmeisei, get_directions
import openai
import os
from reportlab.lib.units import mm


# ✅ APIキーの指定（必須）
openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result_raw, kyusei_text, lang: str = 'ja'):
    """Generate 5-line lucky info (items/colors/etc). Returns a list[str] lines."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    if (lang or 'ja').lower().startswith('en'):
        prompt = f"""Create a short 'Lucky Info' section for a fortune-telling PDF.
Return EXACTLY 5 lines, each as 'Label: value', in English, using these labels in this order:
1) Item
2) Color
3) Number
4) Food
5) Lucky day

Context:
- Day pillar (internal reference only): {nicchu_eto}
- Birthdate: {birthdate} (age {age})
- Palm summary: {palm_result}
- Shichu Suimei summary: {shichu_result_raw}
- Kyusei: {kyusei_text}

Rules:
- Keep each value concise (ideally under ~35 characters after the colon).
- Suggest realistic, shop-like spiritual items (cleansing goods, aroma, stones, small charms).
"""
    else:
        prompt = f"""占い結果PDFに載せる「ラッキー情報」を作ってください。

【出力形式】必ず5行、次の順で「ラベル：内容」の形にしてください：
1) アイテム：
2) カラー：
3) ナンバー：
4) フード：
5) ラッキーデー：

【参考情報】
日柱（内部参照）: {nicchu_eto}
生年月日: {birthdate}（年齢 {age}）
手相要約: {palm_result}
四柱推命要約: {shichu_result_raw}
九星: {kyusei_text}

【ルール】
- 1行は短め（コロン以降はできれば35文字程度まで）
- 実際のスピリチュアルショップにありそうな開運アイテムにする
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You generate short lucky info lines for a fortune-telling PDF."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
    )

    text = (res.choices[0].message.content or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Defensive: ensure 5 lines; pad / truncate
    if len(lines) < 5:
        # Add empty placeholders to keep layout stable
        lines += [""] * (5 - len(lines))
    elif len(lines) > 5:
        lines = lines[:5]
    return lines
def generate_lucky_direction(birthdate: str, today: datetime.date) -> str:
    """
    九星気学に基づく吉方位テキストを生成する。
    today の「20日以降」は翌月を「今月」とみなして計算する。
    """
    # 生年月日のパース
    try:
        bd = (
            birthdate
            if isinstance(birthdate, datetime.date)
            else datetime.datetime.strptime(birthdate, "%Y-%m-%d").date()
        )
    except Exception as e:
        print("⚠️ generate_lucky_direction birthdate parse error:", e)
        bd = today if isinstance(today, datetime.date) else datetime.date.today()

    # today を date 型に正規化
    base = today.date() if isinstance(today, datetime.datetime) else today

    # 20日以降は翌月ベース
    if base.day >= 20:
        base = base + relativedelta(months=1)

    # 本命星を取得
    honmeisei = get_honmeisei(bd.year, bd.month, bd.day)

    # 年盤（base.year）、今月（base.month）、来月（base.month+1）
    dir_year = get_directions(base.year, 0, honmeisei)
    dir_now = get_directions(base.year, base.month, honmeisei)
    next_month_date = base + relativedelta(months=1)
    dir_next = get_directions(next_month_date.year, next_month_date.month, honmeisei)

    good_dir_year = dir_year.get("good", "不明")
    good_dir_now = dir_now.get("good", "不明")
    good_dir_next = dir_next.get("good", "不明")

    return f"{base.year}年の吉方位は{good_dir_year}、今月は{good_dir_now}、来月は{good_dir_next}です。"



def draw_lucky_section(c, width, margin, y, lucky_info, lucky_direction, font_name="IPAexGothic"):
    """
    Draw the Lucky Info section (lucky items and lucky direction) at the current y position.
    Returns the updated y position.
    """
    # Section header
    c.setFont(font_name, 12)
    c.drawString(margin, y, "■ ラッキー情報（生年月日より）")
    y -= 8 * mm
    c.setFont(font_name, 10)
    # Lucky items (two-column layout)
    if lucky_info:
        col_width = (width - 2 * margin) / 2
        x1 = margin + 10
        x2 = margin + 10 + col_width
        col = 0
        for i, item in enumerate(lucky_info):
            if "：" in item:
                label, value = item.split("：", 1)
                label = label.replace("ラッキー", "").strip()
                item = f"{label}：{value.strip()}"
            x = x1 if col == 0 else x2
            c.drawString(x, y, item)
            if col == 1:
                y -= 6 * mm
            col = (col + 1) % 2
        if col == 1:
            y -= 6 * mm
    else:
        c.drawString(margin + 10, y, "情報が取得できませんでした。")
        y -= 6 * mm

    # Lucky direction (Nine-Star Ki) lines
    if lucky_direction and isinstance(lucky_direction, str) and lucky_direction.strip():
        for line in lucky_direction.strip().splitlines():
            c.drawString(margin + 10, y, line.strip())
            y -= 6 * mm
    else:
        c.drawString(margin + 10, y, "情報未取得")
        y -= 6 * mm

    return y - 10 * mm

    if lucky_info:
        for item in lucky_info:
            if item and isinstance(item, str):
                from textwrap import wrap
                for line in wrap(item.strip(), 40):
                    c.drawString(margin + 10, y, line)
                    y -= 6 * mm
    else:
        c.drawString(margin + 10, y, "情報が取得できませんでした。")
        y -= 6 * mm

    y -= 4 * mm

    if lucky_direction and isinstance(lucky_direction, str) and lucky_direction.strip():
        c.drawString(margin, y, "■ 吉方位（九星気学より）")
        y -= 6 * mm
        from textwrap import wrap
        for line in wrap(lucky_direction.strip(), 42):
            c.drawString(margin + 10, y, line)
            y -= 6 * mm
    else:
        c.drawString(margin, y, "■ 吉方位（九星気学より）情報未取得")
        y -= 6 * mm

    return y - 10 * mm


# 🆕 恋愛専用：手相なしの簡易版ラッキー情報
def generate_lucky_renai_info(nicchu_eto, birthdate, age, palm_result, shichu_result_raw, kyusei_text, lang: str = 'ja'):
    """Renai version lucky info; same format as generate_lucky_info."""
    return generate_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result_raw, kyusei_text, lang=lang)
