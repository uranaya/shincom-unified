import openai
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from kyusei_utils import get_honmeisei, get_directions
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date

# 月運テキストの最大文字数（全角ベース想定）
MAX_CHAR = 110


def _ask_openai(prompt: str, max_tokens: int = 200, temperature: float = 0.7) -> str:
    """
    OpenAI ChatCompletion のラッパ。
    必要に応じて今後も使えるように残しておく。
    """
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    res = openai.ChatCompletion.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "あなたは四柱推命と恋愛心理に詳しいプロの占い師です。"},
            {"role": "user", "content": prompt},
        ],
    )
    return res.choices[0].message.content.strip()


def _truncate(text: str, limit: int = MAX_CHAR) -> str:
    """
    PDF がページをまたいで切れないよう、文字数で丸める。
    （日本語前提なので、厳密な「文字幅」ではなく単純な len で管理）
    """
    if not text:
        return ""
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[:limit].rstrip()


def generate_yearly_love_fortune(user_birth: str, now: datetime):
    nicchu = get_nicchu_eto(user_birth)

    # ★ 20日境：基準月 base
    base = now.replace(day=15)
    if now.day >= 20:
        base += relativedelta(months=1)

    target_year = base.year
    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)

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

    # ★ 基準月 base から 12ヶ月分
    month_fortunes = []
    for i in range(12):
        target = base + relativedelta(months=i)
        y, m = target.year, target.month
        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)

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
