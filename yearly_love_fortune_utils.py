import openai
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from kyusei_utils import get_honmeisei, get_directions
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date

# 月運テキストの最大文字数（全角換算）。PDF が 2 ページに収まるように抑制する目的。
MAX_CHAR = 120


def _ask_openai(prompt: str, max_tokens: int = 200, temperature: float = 0.7) -> str:
    """OpenAI ChatCompletion をラップした共通関数。"""
    response = openai.ChatCompletion.create(
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "あなたは四柱推命と恋愛心理に詳しいプロの占い師です。"},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def _truncate(text: str, limit: int) -> str:
    """PDF のレイアウト崩れを防ぐため、指定文字数でテキストを丸める。"""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    # 行頭・行末の空白を削りつつ、文の途中であっても強制的に丸める
    return text[:limit].rstrip()


def generate_yearly_love_fortune(user_birth: str, now: datetime):
    """恋愛版の年運＋12 ヶ月分の月運を生成する。

    戻り値の形式:
    {
        'year_label': '2026年の総合運',
        'year_text': '...',
        'months': [
            {'label': '2026年1月の恋愛運', 'text': '...'},
            ...
        ]
    }
    """
    # 日柱・本命星などの基礎情報
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)

    # 「12 月なら翌年」を対象にする既存仕様を踏襲
    target_year = now.year + 1 if now.month == 12 else now.year
    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)

    # --- 年運テキスト ---
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

    year_raw = _ask_openai(prompt_year, max_tokens=150, temperature=0.8)
    year_fortune = _truncate(year_raw, MAX_CHAR)

    # --- 月運（今月から 12 ヶ月） ---
    month_fortunes = []
    for i in range(12):
        target = now.replace(day=15) + relativedelta(months=i)
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

        month_raw = _ask_openai(prompt_month, max_tokens=150, temperature=0.9)
        month_text = _truncate(month_raw, MAX_CHAR)

        month_fortunes.append(
            {
                "label": f"{y}年{m}月の恋愛運",
                "text": month_text,
            }
        )

    return {
        "year_label": f"{target_year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes,
    }
