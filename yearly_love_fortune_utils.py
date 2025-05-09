import openai
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from kyusei_utils import get_honmeisei, get_directions
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date

MAX_CHAR = 120  # 月運 120 文字以内

def _ask_openai(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        max_tokens=850,
        temperature=0.7,
        messages=[{"role": "system", "content": "あなたは四柱推命のプロの占い師です。"},
                  {"role": "user",   "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def generate_yearly_love_fortune(user_birth: str, now: datetime):
    
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)

    tsuhen_year = get_tsuhensei_for_year(user_birth, now.year)

    # 年運プロンプト（改良）
    prompt_year = f"""
あなたは恋愛占いの専門家です。
以下の干支と通変星の情報をもとに、{now.year}年の恋愛傾向を100文字以内で具体的かつ印象的に表現してください。

- 日柱: {nicchu}
- 年の通変星: {tsuhen_year}

条件：
- 主語は「あなた」
- ポジティブだが具体性を重視
- 無難で抽象的な表現を避け、印象に残る言い回しにしてください
- 月運と差別化してください
""".strip()

    year_fortune = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt_year}],
        max_tokens=100,
        temperature=0.8
    ).choices[0].message.content.strip()

    # 月運生成（12ヶ月分）
    month_fortunes = []
    for i in range(12):
        target = (now.replace(day=15) + relativedelta(months=i))
        y, m = target.year, target.month
        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)
        dirs = get_directions(y, m, honmeisei)

        prompt_month = f"""
あなたは恋愛占いの専門家です。
以下の情報をもとに、その月の恋愛運を100文字で簡潔に教えてください。

- 日柱: {nicchu}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_month}

条件：
- 主語は「あなた」
- 「○年○月の恋愛運は〜」のような前置きは不要（タイトルに記載されます）
- 毎月異なる恋愛の展開を描写してください
- 無難な言い回しを避け、印象に残る表現で個性を出してください
- 出会い・進展・揺らぎ・期待・焦りなど変化を感じさせてください
- 実際の恋愛場面を想起させる具体的な内容を含めてください
""".strip()

        text = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_month}],
            max_tokens=100,
            temperature=0.9
        ).choices[0].message.content.strip()

        month_fortunes.append({
            "label": f"{y}年{m}月の恋愛運",
            "text": text
        })

    return {
        "year_label": f"{now.year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    }
