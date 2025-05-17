import openai
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from kyusei_utils import get_honmeisei, get_directions
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date

MAX_CHAR = 120  # Limit for monthly love fortune text

def _ask_openai(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        max_tokens=200,
        temperature=0.7,
        messages=[{"role": "system", "content": "あなたは四柱推命のプロの占い師です。"},
                  {"role": "user",   "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def generate_yearly_love_fortune(user_birth: str, now: datetime):
    """
    Generate a year-long love fortune (year overview + 12 months) for the given birthdate.
    """
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)
    # Use next year if current month is December
    target_year = now.year + 1 if now.month == 12 else now.year
    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)

    # Year love fortune prompt
    prompt_year = f"""
あなたは恋愛占いの専門家です。
以下の情報をもとに、{target_year}年の恋愛傾向を100文字以内で表現してください。

- 日柱: {nicchu}
- 年の通変星: {tsuhen_year}

条件：
- 占い用語（例：比肩、傷官など）や干支名は文章に出さず、
  その意味を自然な日本語に置き換えてください
- 主語は「あなた」
- 現実的かつ印象に残るアドバイスとしてください
""".strip()
    year_fortune = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt_year}],
        max_tokens=150,
        temperature=0.8
    ).choices[0].message.content.strip()

    # Monthly love fortunes for 12 months from now
    month_fortunes = []
    for i in range(12):
        target = now.replace(day=15) + relativedelta(months=i)
        y, m = target.year, target.month
        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)
        # (Using year tsuhensei for all months as context may be a minor oversight, but acceptable)
        prompt_month = f"""
あなたは恋愛占いの専門家です。
以下の情報をもとに、その月の恋愛運を100文字以内で自然な日本語で表現してください。

- 日柱: {nicchu}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_month}

条件：
- 主語は「あなた」
- 占い用語（例：偏印、正官など）や干支名は出さず、
  意味に沿った自然な表現にしてください
- 現実味のある恋愛展開や気持ちの動きを含めてください
- 毎月の変化が感じられるようにしてください
""".strip()
        text = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_month}],
            max_tokens=150,
            temperature=0.9
        ).choices[0].message.content.strip()
        month_fortunes.append({
            "label": f"{y}年{m}月の恋愛運",
            "text": text
        })

    return {
        "year_label": f"{target_year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    }
