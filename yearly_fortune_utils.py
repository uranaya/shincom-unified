from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date  # ← 修正
from kyusei_utils import get_honmeisei, get_directions
from datetime import datetime
from dateutil.relativedelta import relativedelta
import openai
import os

MAX_CHAR = 120

def _ask_openai(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        max_tokens=850,
        temperature=0.7,
        messages=[
            {"role": "system", "content": "あなたは四柱推命のプロの占い師です。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()


def generate_yearly_fortune(user_birth: str, now: datetime):
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)

    # 年運（通変星あり）
    tsuhen_year = get_tsuhensei_for_year(user_birth, now.year)  # ← 修正
    prompt_year = f"""あなたは占いの専門家です。以下の情報をもとに、性格や考え方を踏まえた現実的な開運アドバイスをください。

- 日柱: {nicchu}
- 今年の通変星: {tsuhen_year}
- 対象年: {now.year} 年

120文字以内で、運気の流れや注意点、やると良いことなど前向きにまとめてください。"""
    year_fortune = _ask_openai(prompt_year)

    # 月運
    month_fortunes = []
    for i in range(12):
        target = (now.replace(day=15) + relativedelta(months=i))
        y, m = target.year, target.month
        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)  # ← 修正
        dirs = get_directions(y, m, honmeisei)
        prompt_month = f"""あなたは占いの専門家です。以下の条件で対象月の総合運を占ってください。

- 日柱: {nicchu}
- 通変星: {tsuhen_month}
- 年月: {y}年{m}月

条件:
- 約120文字以内
- 運気の流れや心がけ、やると良いことを具体的に
- 前向きな語り口で、親しみやすく
"""
        month_fortunes.append({
            "label": f"{y}年{m}月の運勢",
            "text": _ask_openai(prompt_month)
        })

    return {
        "year_label": f"{now.year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    }
