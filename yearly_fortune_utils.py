import openai
from datetime import datetime
from kyusei_utils import get_honmeisei, get_directions
from sxtwl_utils import get_nicchu_eto  # 早見表 or sxtwl ラッパー

MAX_CHAR = 300  # 月運 300 文字以内

def _ask_openai(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        max_tokens=850,
        temperature=0.7,
        messages=[{"role": "system", "content": "あなたは…（略）"},
                  {"role": "user",   "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def generate_yearly_fortune(user_birth: str, now: datetime):
    """干支（日柱）と九星の本命星を求め、年運＋12 か月分を返す"""
    nicchu = get_nicchu_eto(user_birth)
    honmeisei = get_honmeisei(user_birth)

    # 今年の運勢
    prompt_year = f"""あなたは四柱推命のプロ…（略）:
- 相談者の日柱: {nicchu}
- 今年: {now.year} 年
- 300 文字以内、主語を『あなた』で統一、ポジティブ寄り
"""
    year_fortune = _ask_openai(prompt_year)

    # 月運
    month_fortunes = []
    for i in range(12):
        target = (now.replace(day=15)  # 安全に
                  + relativedelta(months=i))
        y, m = target.year, target.month
        dirs = get_directions(y, m, honmeisei)
        prompt_month = f"""あなたは四柱推命のプロ…（略）
- 日柱: {nicchu}
- 対象月: {y} 年 {m} 月
- 290 字以内で月運を述べ、末尾に『吉方位: {dirs['good']} / 凶方位: {dirs['bad']}』を必ず付ける"""
        month_fortunes.append({
            "label": f"{y}年{m}月の運勢",
            "text": _ask_openai(prompt_month)
        })

    return {
        "year_label": f"{now.year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    }
