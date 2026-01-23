import datetime
from dateutil.relativedelta import relativedelta   # ★ この行を追加
from kyusei_utils import get_honmeisei, get_directions
import openai
import os
from reportlab.lib.units import mm


# ✅ APIキーの指定（必須）
openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result, kyusei_text):
    prompt = f"""あなたは占いの専門家です。
相談者は現在{age}歳です。以下の鑑定結果を参考にしてください。

【手相】\n{palm_result}\n
【四柱推命】\n{shichu_result}\n
【九星気学の方位】\n{kyusei_text}

以下5つの項目を、すべて1行にまとめて簡潔に出力してください：

◆ アイテム：〇〇　　◆ カラー：〇〇　　◆ ナンバー：〇〇　　◆ フード：〇〇　　◆ デー：〇曜日

- 「◆」で始める
- 出力は1行だけにする
- 各項目は短く（単語～数語）
- 補足説明・理由・語り・改行は一切禁止
- 他の文や文章は禁止（この形式のみで返答すること）
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )
        return [response["choices"][0]["message"]["content"].strip()]
    except Exception as e:
        print("❌ ラッキー情報取得失敗:", e)
        return ["◆ アイテム：ー　　◆ カラー：ー　　◆ ナンバー：ー　　◆ フード：ー　　◆ デー：ー"]


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



def draw_lucky_section(c, width, margin, y, lucky_info, lucky_direction, font_name="IPAexGothic", lang="ja", page_height=None):
    """
    Draw Lucky Info + Lucky Directions.

    - Backward compatible: lucky_info can be list[str] or str or dict.
    - lang: 'ja' or 'en' (any value starting with 'en' treated as English)
    - page_height: optional for future page-fit logic (currently used for compact layout)
    """
    lang = (lang or "ja").strip().lower()
    lang = "en" if lang.startswith("en") else "ja"

    def _t(ja, en):
        return en if lang == "en" else ja

    # --- parse lucky_info into fields ---
    fields = {"item": "", "color": "", "number": "", "food": "", "day": ""}
    if isinstance(lucky_info, dict):
        for k in list(fields.keys()):
            if k in lucky_info and isinstance(lucky_info[k], str):
                fields[k] = lucky_info[k].strip()
    else:
        if isinstance(lucky_info, str):
            items = [x.strip() for x in lucky_info.splitlines() if x.strip()]
        elif isinstance(lucky_info, (list, tuple)):
            items = [str(x).strip() for x in lucky_info if str(x).strip()]
        else:
            items = []
        for it in items:
            s = str(it).replace("◆", "").replace("・", "").strip()
            if "：" in s:
                label, value = s.split("：", 1)
            elif ":" in s:
                label, value = s.split(":", 1)
            else:
                continue
            label = label.strip().lower()
            value = value.strip()
            if "アイテム" in label or "item" in label:
                fields["item"] = value
            elif "カラー" in label or "color" in label:
                fields["color"] = value
            elif "ナンバー" in label or "number" in label:
                fields["number"] = value
            elif "フード" in label or "food" in label:
                fields["food"] = value
            elif "デー" in label or "day" in label or "曜日" in label:
                fields["day"] = value

    # --- simple translations (JA -> EN) ---
    COLOR_MAP = {
        "チャコール": "Charcoal", "桃": "Peach", "ピンク": "Pink", "赤": "Red", "青": "Blue",
        "紺": "Navy", "白": "White", "黒": "Black", "金": "Gold", "銀": "Silver", "緑": "Green",
        "黄": "Yellow", "紫": "Purple", "オレンジ": "Orange", "ベージュ": "Beige", "茶": "Brown",
        "グレー": "Gray",
    }
    FOOD_MAP = {
        "桃": "Peach", "りんご": "Apple", "みかん": "Mandarin orange", "チョコ": "Chocolate",
        "抹茶": "Matcha", "納豆": "Natto", "寿司": "Sushi", "うどん": "Udon", "ラーメン": "Ramen",
        "カレー": "Curry", "パン": "Bread", "コーヒー": "Coffee", "紅茶": "Tea",
    }
    DAY_MAP = {
        "月曜日": "Monday", "火曜日": "Tuesday", "水曜日": "Wednesday",
        "木曜日": "Thursday", "金曜日": "Friday", "土曜日": "Saturday", "日曜日": "Sunday",
        "月": "Monday", "火": "Tuesday", "水": "Wednesday", "木": "Thursday", "金": "Friday", "土": "Saturday", "日": "Sunday",
    }
    def _map(v, mp):
        if not v:
            return v
        vv = v.strip()
        return mp.get(vv, vv)

    if lang == "en":
        fields["color"] = _map(fields["color"], COLOR_MAP)
        fields["food"] = _map(fields["food"], FOOD_MAP)
        fields["day"] = _map(fields["day"], DAY_MAP)

    # --- section header ---
    c.setFont(font_name, 12)
    c.drawString(margin, y, "■ " + _t("ラッキー情報（生年月日より）", "Lucky Info (based on birthdate)"))
    y -= 7 * mm

    # --- body ---
    if lang == "en":
        # Compact two-line layout to keep within page 2
        c.setFont(font_name, 9)
        line1 = f"Item: {fields['item']}   Color: {fields['color']}   Number: {fields['number']}".strip()
        line2 = f"Food: {fields['food']}   Day: {fields['day']}".strip()
        c.drawString(margin + 10, y, line1)
        y -= 5 * mm
        c.drawString(margin + 10, y, line2)
        y -= 6 * mm
    else:
        # Existing two-column JA layout
        c.setFont(font_name, 10)
        items = []
        if fields["item"]: items.append(f"アイテム：{fields['item']}")
        if fields["color"]: items.append(f"カラー：{fields['color']}")
        if fields["number"]: items.append(f"ナンバー：{fields['number']}")
        if fields["food"]: items.append(f"フード：{fields['food']}")
        if fields["day"]: items.append(f"デー：{fields['day']}")
        if not items:
            if isinstance(lucky_info, (list, tuple)):
                items = [str(x).strip() for x in lucky_info if str(x).strip()]
            elif isinstance(lucky_info, str):
                items = [x.strip() for x in lucky_info.splitlines() if x.strip()]
            else:
                items = []
        col_width = (width - 2 * margin) / 2
        x1 = margin + 10
        x2 = margin + 10 + col_width
        col = 0
        for it in items:
            s = str(it).strip()
            if not s:
                continue
            x = x1 if col == 0 else x2
            c.drawString(x, y, s)
            if col == 1:
                y -= 6 * mm
            col = (col + 1) % 2
        if col == 1:
            y -= 6 * mm

    # --- lucky directions ---
    def _translate_dir(text: str) -> str:
        if not isinstance(text, str):
            return ""
        s = text.strip()
        if not s:
            return ""
        year_dir = month_dir = next_dir = ""
        m = re.search(r"吉方位[:：]\s*([^\s　]+)", s)
        if m:
            year_dir = m.group(1)
        m = re.search(r"今月[:：]\s*([^\s　]+)", s)
        if m:
            month_dir = m.group(1)
        m = re.search(r"来月[:：]\s*([^\s　]+)", s)
        if m:
            next_dir = m.group(1)

        DIR_MAP = {
            "北": "North", "南": "South", "東": "East", "西": "West",
            "北東": "Northeast", "北西": "Northwest", "南東": "Southeast", "南西": "Southwest",
        }
        def map_dir(v):
            if not v:
                return v
            vv = v.strip()
            return DIR_MAP.get(vv, vv)

        year_dir_en = map_dir(year_dir)
        month_dir_en = map_dir(month_dir)
        next_dir_en = map_dir(next_dir)

        STAR_MAP = {
            "一白水星": "One White Water Star",
            "二黒土星": "Two Black Earth Star",
            "三碧木星": "Three Jade Wood Star",
            "四緑木星": "Four Green Wood Star",
            "五黄土星": "Five Yellow Earth Star",
            "六白金星": "Six White Metal Star",
            "七赤金星": "Seven Red Metal Star",
            "八白土星": "Eight White Earth Star",
            "九紫火星": "Nine Purple Fire Star",
        }
        star = ""
        m = re.search(r"本命星は[「『\"]?([^」』\"\s]+)", s)
        if m:
            star = STAR_MAP.get(m.group(1), m.group(1))

        parts = []
        if star:
            parts.append(f"Main Star: {star}")
        dirs = []
        if year_dir_en:
            dirs.append(f"Year: {year_dir_en}")
        if month_dir_en:
            dirs.append(f"This month: {month_dir_en}")
        if next_dir_en:
            dirs.append(f"Next month: {next_dir_en}")
        if dirs:
            parts.append("Lucky Directions: " + " / ".join(dirs))
        return "  ".join(parts) if parts else s

    c.setFont(font_name, 12)
    c.drawString(margin, y, "■ " + _t("吉方位（九星気学より）", "Lucky Directions (Nine-Star Ki)"))
    y -= 6 * mm
    c.setFont(font_name, 9 if lang == "en" else 10)
    if lucky_direction and isinstance(lucky_direction, str) and lucky_direction.strip():
        if lang == "en":
            c.drawString(margin + 10, y, _translate_dir(lucky_direction))
            y -= 6 * mm
        else:
            for line in lucky_direction.strip().splitlines():
                c.drawString(margin + 10, y, line.strip())
                y -= 6 * mm
    else:
        c.drawString(margin + 10, y, _t("情報未取得", "Not available"))
        y -= 6 * mm

    return y - 6 * mm


# 🆕 恋愛専用：手相なしの簡易版ラッキー情報
def generate_lucky_renai_info(nicchu_eto, birthdate, age, shichu_result, kyusei_text):
    prompt = f"""あなたは占いの専門家です。
相談者は現在{age}歳です。以下の2つの鑑定結果を参考にしてください。

【四柱推命】\n{shichu_result}\n
【九星気学の方位】\n{kyusei_text}

この内容を元に、相談者にとって今最も恋愛運を高めるための
ラッキーアイテム・ラッキーカラー・ラッキーナンバー・ラッキーフード・ラッキーデー
をそれぞれ1つずつ、以下の形式で簡潔に提案してください：

・アイテム：〇〇  
・カラー：〇〇  
・ナンバー：〇〇  
・フード：〇〇  
・デー：〇曜日

※以下の条件を厳守してください：
- 各項目は1行で記述
- 解説や補足、象徴、理由付けは禁止
- 装飾語は不要（例：「共感力を象徴する」などはNG）
- 出力は上記5行のみに限定
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        lines = response["choices"][0]["message"]["content"].strip().splitlines()
        lucky_lines = []
        for line in lines:
            if "：" in line:
                label, value = line.split("：", 1)
                label = label.replace("・", "").strip()
                value = value.strip().split("（")[0]
                lucky_lines.append(f"{label}：{value}")  # 「◆」は付けない
            if len(lucky_lines) == 5:
                break
        return lucky_lines
    except Exception as e:
        print("❌ 恋愛ラッキー情報取得失敗:", e)
        return ["アイテム：ー", "カラー：ー", "ナンバー：ー", "フード：ー", "デー：ー"]