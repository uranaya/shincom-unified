from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from kyusei_utils import get_honmeisei, get_directions
from datetime import datetime
from dateutil.relativedelta import relativedelta
import openai
import os
import time

MAX_CHAR = 120  # Max characters for monthly fortune

def _ask_openai(prompt: str, retries=3, delay=2) -> str:
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                max_tokens=2000,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": "あなたは四柱推命のプロの占い師です。"},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()
        except openai.error.APIError as e:
            print(f"❌ OpenAI APIエラー（{attempt+1}回目）:", e)
            time.sleep(delay)
    return "取得に失敗しました（OpenAI APIエラー）"

def generate_yearly_fortune(user_birth: str, now: datetime):
    """
    Generate a detailed fortune for the year and each month (12 months starting this month) for normal fortune mode.
    Returns a dict with a year fortune and a list of month fortunes.
    """
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)
    # Determine target year (if current month is December, target next year for "year fortune")
    target_year = now.year + 1 if now.month == 12 else now.year

    # Year fortune prompt
    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)
    prompt_year = f"""
あなたは開運アドバイザーです。
以下の情報をもとに、{target_year}年における「あなた」の全体運を自然な日本語で表現してください。

- 日柱: {nicchu}
- 通変星: {tsuhen_year}

条件：
- 占い用語（例：比肩、印綬など）や干支名は使わず、
  意味に沿ってやさしい言葉に置き換えてください
- 約120文字以内
- 前向きで、行動や考え方の指針になるように
- 読んだ人が「なるほど」と感じるように
""".strip()
    year_fortune = _ask_openai(prompt_year)

    # Monthly fortunes for 12 months starting current month
    month_fortunes = []
    for i in range(12):
        target = now.replace(day=15) + relativedelta(months=i)
        y, m = target.year, target.month
        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)
        dirs = get_directions(y, m, honmeisei)
        prompt_month = f"""
あなたは占いの専門家です。
以下の情報をもとに、{y}年{m}月の運気を自然な日本語で約120文字以内にまとめてください。

- 日柱: {nicchu}
- 月の通変星: {tsuhen_month}

条件：
- 占い専門用語は使わず意味をやさしく表現
- 主語は「あなた」
- 月ごとに変化を出す（行動・感情・周囲との関係など）
- 現実的でポジティブな内容
""".strip()
        text = _ask_openai(prompt_month)
        month_fortunes.append({
            "label": f"{y}年{m}月の運勢",
            "text": text
        })

    return {
        "year_label": f"{target_year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    }
