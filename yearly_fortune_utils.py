import openai
from datetime import datetime
from dateutil.relativedelta import relativedelta
from kyusei_utils import get_honmeisei, get_directions
from fortune_logic import get_nicchu_eto  # 既存の実装をそのまま利用

MAX_CHAR = 300  # 月運 300 文字以内

def _ask_openai(prompt: str) -> str:
    response = openai.chat.completions.create(
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

    # 総合年運
    prompt_year = f"""あなたは四柱推命のプロの占い師です。
- 日柱: {nicchu}
- 対象年: {now.year}
- 250文字以内、主語は「あなた」、現実的な文体でお願いします。"""

    year_fortune = _ask_openai(prompt_year)

    # 月運リスト（get_directions 削除）
    month_fortunes = []
    for i in range(12):
        target = (now.replace(day=15) + relativedelta(months=i))
        y, m = target.year, target.month

        prompt_month = f"""あなたは四柱推命のプロの占い師です。
- 日柱: {nicchu}
- 年月: {y}年{m}月

以下の条件で月運を作成してください:
- 約180文字
- 仕事・人間関係・感情面・健康などを含めて具体的に
- 主語「あなた」、温かみある語り口で"""

        month_fortunes.append({
            "label": f"{y}年{m}月の運勢",
            "text": _ask_openai(prompt_month)
        })

    return {
        "year_label": f"{now.year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    }
