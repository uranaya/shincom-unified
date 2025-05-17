import datetime
from kyusei_utils import get_honmeisei, get_directions
import openai
import os
from reportlab.lib.units import mm


# ✅ APIキーの指定（必須）
openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result, kyusei_text):
    prompt = f"""あなたは占いの専門家です。
相談者は現在{age}歳です。以下の3つの鑑定結果を参考にしてください。

【手相】\n{palm_result}\n
【四柱推命】\n{shichu_result}\n
【九星気学の方位】\n{kyusei_text}

この内容を元に、相談者にとって今最も運気を高めるための
ラッキーアイテム・ラッキーカラー・ラッキーナンバー・ラッキーフード・ラッキーデー
をそれぞれ1つずつ、以下の形式で提案してください：

・ラッキーアイテム：〇〇
・ラッキーカラー：〇〇
・ラッキーナンバー：〇〇
・ラッキーフード：〇〇
・ラッキーデー：〇曜日

自然で前向きな言葉で書いてください。"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"].strip().splitlines()
    except Exception as e:
        print("❌ ラッキー情報取得失敗:", e)
        return ["取得できませんでした。"]


def generate_lucky_direction(birthdate: str, today: datetime.date) -> str:
    try:
        bd = (birthdate if isinstance(birthdate, datetime.date) 
              else datetime.datetime.strptime(birthdate, "%Y-%m-%d").date())
    except Exception as e:
        bd = today

    honmeisei = get_honmeisei(bd.year, bd.month, bd.day)
    dir_year = get_directions(today.year, 0, honmeisei)
    dir_now = get_directions(today.year, today.month, honmeisei)
    next_month_date = today + datetime.timedelta(days=30)
    dir_next = get_directions(next_month_date.year, next_month_date.month, honmeisei)

    good_dir_year = dir_year.get("good", "不明")
    good_dir_now = dir_now.get("good", "不明")
    good_dir_next = dir_next.get("good", "不明")

    return f"{today.year}年の吉方位は{good_dir_year}、今月は{good_dir_now}、来月は{good_dir_next}です。"



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
def generate_lucky_renai_info(nicchu_eto, birthdate, age, shichu_result, kyusei_text):
    prompt = f"""あなたは占いの専門家です。
相談者は現在{age}歳です。以下の2つの鑑定結果を参考にしてください。

【四柱推命】\n{shichu_result}\n
【九星気学の方位】\n{kyusei_text}

この内容を元に、相談者にとって今最も恋愛運を高めるための
ラッキーアイテム・ラッキーカラー・ラッキーナンバー・ラッキーフード・ラッキーデー
をそれぞれ1つずつ、以下の形式で提案してください：

・ラッキーアイテム：〇〇  
・ラッキーカラー：〇〇  
・ラッキーナンバー：〇〇  
・ラッキーフード：〇〇  
・ラッキーデー：〇曜日

自然で前向きな言葉で書いてください。"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"].strip().splitlines()
    except Exception as e:
        print("❌ 恋愛ラッキー情報取得失敗:", e)
        return ["取得できませんでした。"]
