from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import openai
import os

# Nine Star Ki star names
NINE_STARS = [
    "一白水星", "二黒土星", "三碧木星",
    "四緑木星", "五黄土星", "六白金星",
    "七赤金星", "八白土星", "九紫火星"
]

def get_honmeisei(year: int, month: int, day: int) -> str:
    """
    Calculate the Nine-Star Ki main star (本命星) for a given birthdate (year, month, day).
    The Nine-Star Ki year starts on February 4; if birthdate is before that, use previous year.
    """
    if (month < 2) or (month == 2 and day <= 3):
        year -= 1
    kyusei_num = (11 - (year % 9)) % 9
    kyusei_num = 9 if kyusei_num == 0 else kyusei_num
    return NINE_STARS[kyusei_num - 1]

def get_directions(year: int, month: int, honmeisei: str) -> dict:
    """
    Query OpenAI for lucky and unlucky directions for a given year/month and honmeisei.
    If month == 0, it queries for the whole year (年盤のみ)。
    月ごとの場合は、年盤と月盤を重ねた吉方位を返す。
    """
    if month == 0:
        period = f"{year}年の年間"
        explanation = "年盤を元に判断してください。"
    else:
        period = f"{year}年{month}月"
        explanation = "年盤と月盤を重ねて、総合的に吉方位・凶方位を判断してください。"

    prompt = f"""
あなたは九星気学の専門家です。
{period}において、本命星「{honmeisei}」の人の
吉方位と凶方位を、{explanation}
次の形式で日本語のJSONのみを出力してください：

{{"good": "南東", "bad": "北西"}}

※ 方位は次の8方位からそれぞれ1つずつ選んでください：
北, 北東, 東, 南東, 南, 南西, 西, 北西

※説明文・注釈は一切不要。JSONのみを返答してください。
""".strip()

    try:
        res = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.3,
        )
        txt = res.choices[0].message.content.strip()
        return json.loads(txt)
    except Exception as e:
        print("❌ get_directions エラー:", e)
        return {"good": "取得失敗", "bad": "取得失敗"}


def get_kyusei_fortune(year: int, month: int, day: int) -> str:
    """
    Generate the two-line Nine-Star Ki fortune text for the given birthdate.
    Line1: "あなたの本命星は「X」です。"
    Line2: "YYYY年の吉方位：... 今月：... 来月：... です。"
    """
    try:
        honmeisei = get_honmeisei(year, month, day)
        now = datetime.now()
        next_month = (now.replace(day=1) + relativedelta(months=1))
        # Get directions for current year, current month, next month
        directions_year = get_directions(now.year, 0, honmeisei)
        directions_this_month = get_directions(now.year, now.month, honmeisei)
        directions_next_month = get_directions(next_month.year, next_month.month, honmeisei)
        return (
            f"あなたの本命星は「{honmeisei}」です。\n"
            f"{now.year}年の吉方位：{directions_year['good']}　今月：{directions_this_month['good']}　来月：{directions_next_month['good']} です。"
        )
    except Exception as e:
        print("❌ get_kyusei_fortune エラー:", e)
        return "吉方位を取得できませんでした"
