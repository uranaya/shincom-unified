from datetime import datetime
import openai

NINE_STARS = [
    "一白水星", "二黒土星", "三碧木星",
    "四緑木星", "五黄土星", "六白金星",
    "七赤金星", "八白土星", "九紫火星"
]

def get_honmeisei(year: int, month: int, day: int) -> str:
    if (month < 2) or (month == 2 and day <= 3):
        year -= 1
    kyusei_num = (11 - (year % 9)) % 9
    kyusei_num = 9 if kyusei_num == 0 else kyusei_num
    return NINE_STARS[kyusei_num - 1]

def get_kyusei_fortune_openai(year: int, month: int, day: int) -> str:
    honmei = get_honmeisei(year, month, day)
    now = datetime.now()
    now_str = f"{now.year}年{now.month}月"
    next_month = now.replace(day=1).replace(month=now.month % 12 + 1)
    next_str = f"{next_month.year}年{next_month.month}月"

    prompt = f"""あなたはプロの九星気学占い師です。
以下の条件で、今月と来月の吉方位と凶方位を1文で出力してください。

・「今月は◯が吉、×が凶。来月は◯が吉、×が凶。」という形で1文にまとめてください。
・「今月」「来月」の表現を必ず使ってください。
・具体的な年月（例：2025年4月）や星名（例：一白水星）は使わないでください。
・方位は「北」「北東」「東」「南東」「南」「南西」「西」「北西」の中から記述してください。
・全体を45文字以内にしてください。
・読みやすく自然な日本語で書いてください。
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ OpenAIによる九星方位占断失敗:", e)
        return "吉方位を取得できませんでした。"


# ───────────────────────────────────────────────
#  月ごとの吉方位／凶方位を OpenAI で取得
# ───────────────────────────────────────────────
import json

def get_directions(year: int, month: int, honmeisei: str) -> dict:
    """
    GPT-4 に JSON 形式だけ返させる。
    例） {"good":"南東","bad":"北西"}
    方位は 8 方位のいずれか 1 文字〜2 文字。
    失敗時は {"good":"取得失敗","bad":"取得失敗"}
    """
    prompt = f"""
あなたはプロの九星気学占い師です。
{year}年{month}月、本命星が「{honmeisei}」の人について、
吉方位と凶方位を JSON だけで返してください。
キーは "good" と "bad"、値は必ず以下 8 つのいずれか 1 つ：
北, 北東, 東, 南東, 南, 南西, 西, 北西
説明や改行は書かず、JSON だけで出力してください。
""".strip()

    try:
        res = openai.chat.completions.create(
            model="gpt-4o-mini",          # ← ご契約モデルに合わせて変更可
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.3,
        )
        txt = res.choices[0].message.content.strip()
        return json.loads(txt)
    except Exception as e:
        print("❌ get_directions エラー:", e)
        return {"good": "取得失敗", "bad": "取得失敗"}
