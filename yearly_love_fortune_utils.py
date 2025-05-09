import openai
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from kyusei_utils import get_honmeisei, get_directions


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

    from nicchu_utils import get_nicchu_eto

    """干支（日柱）と九星の本命星を求め、年運＋12 か月分を返す"""
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)

    # 今年の運勢
    prompt_year = f"""あなたは恋愛占いのプロの占い師です。以下の情報をもとに、恋愛運について150文字以内で現実的かつ温かいアドバイスをください。
- 相談者の日柱: {nicchu}
- 今年: {now.year} 年
- 120 文字以内、主語を『あなた』で統一、ポジティブ寄り
"""
    year_fortune = _ask_openai(prompt_year)

    # 月運
    month_fortunes = []
    for i in range(12):
        target = (now.replace(day=15) + relativedelta(months=i))
        y, m = target.year, target.month
        dirs = get_directions(y, m, honmeisei)
        prompt_month = f"""あなたは恋愛占いのプロの占い師です。相談者の日柱と対象月から、その月の恋愛運を占ってください。

- 日柱: {nicchu}
- 年月: {y}年{m}月

条件:
- 恋愛面に焦点を当てて、150文字程度で自然な日本語で書いてください
- 運気の流れに加え、出会い、進展、気持ちの変化、相性の傾向、距離の縮まり方などを中心に書いてください
- 具体的な恋愛シーンを想像できるように、現実味あるアドバイスを含めてください
- 主語は「あなた」で統一し、肯定的でやや温かみのある口調で語ってください
"""

        month_fortunes.append({
            "label": f"{y}年{m}月の恋愛運",
            "text": _ask_openai(prompt_month)
        })


    print("📦 年運生成結果（内部）:", {
        "year_label": f"{now.year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    })


    return {
        "year_label": f"{now.year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    }
