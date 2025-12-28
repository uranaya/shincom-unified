import openai
from datetime import datetime
from dateutil.relativedelta import relativedelta
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date

# 月運テキストの最大文字数（全角ベース想定）
MAX_CHAR = 110


def _ask_openai(prompt: str, max_tokens: int = 200, temperature: float = 0.7) -> str:
    """
    OpenAI ChatCompletion の簡易ラッパ。
    """
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return res.choices[0].message.content.strip()


def _truncate(text: str, limit: int = MAX_CHAR) -> str:
    """
    文章が途中で切れて PDF に出ない問題を避けるため、
    指定文字数以内かつ「最後の '。' まで」で丸める。
    """
    if not text:
        return ""

    t = text.strip().replace("\n", "")
    if len(t) <= limit:
        # もとの文章が十分短ければそのまま。
        return t

    # いったん limit で切る
    snippet = t[:limit]
    # 最後の「。」の位置を探す
    last_period = snippet.rfind("。")
    if last_period != -1 and last_period >= int(limit * 0.5):
        # そこまでを採用（文の途中で終わらない）
        return snippet[: last_period + 1]

    # 「。」が見つからない／かなり手前しかない場合は、
    # 末尾に安全の「。」を付けて返す
    return snippet.rstrip("。") + "。"


def generate_yearly_love_fortune(user_birth: str, now: datetime):
    """
    恋愛版の年間運（1年分＋12か月）を生成。

    - 基準月は「20日境」で、now の 20 日以降なら翌月スタート
    - 年運テキスト + 12 ヶ月分の恋愛運テキストを返す
    """
    nicchu = get_nicchu_eto(user_birth)

    # ★ 20日境：基準月 base を決定
    base = now.replace(day=15)
    if now.day >= 20:
        base += relativedelta(months=1)

    target_year = base.year
    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)

    # 年間の恋愛傾向
    prompt_year = f"""
あなたは恋愛占いの専門家です。
以下の情報をもとに、{target_year}年の恋愛傾向を
80〜120文字程度で1段落にまとめてください。

- 日柱: {nicchu}
- 年の通変星: {tsuhen_year}

条件：
- 占い用語（例：比肩、傷官など）や干支名は文章に出さず、
  その意味を自然な日本語に置き換えてください
- 主語は「あなた」
- 現実的かつ前向きで、行動のヒントになる内容にしてください
- 必ず文末は「。」で終わる1段落とし、途中で文を切らないでください
""".strip()

    year_fortune = _ask_openai(
        prompt_year,
        max_tokens=200,
        temperature=0.8,
    ).strip()

    # ★ 基準月 base から 12ヶ月分
    month_fortunes = []
    for i in range(12):
        target = base + relativedelta(months=i)
        y, m = target.year, target.month

        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)

        prompt_month = f"""
あなたは恋愛占いの専門家です。
以下の情報をもとに、{y}年{m}月の恋愛運を
80〜100文字程度で1段落にまとめてください。

- 日柱: {nicchu}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_month}

条件：
- 主語は「あなた」
- 占い用語（例：偏印、正官など）や干支名は出さず、
  意味に沿った自然な表現にしてください
- 現実味のある恋愛展開や気持ちの動きを含めてください
- 毎月の変化（テンション・出会い・進展のしやすさなど）が感じられるようにしてください
- 必ず文末は「。」で終わる1段落とし、途中で文を切らないでください
""".strip()

        raw_text = _ask_openai(
            prompt_month,
            max_tokens=180,
            temperature=0.8,
        )
        text = _truncate(raw_text, MAX_CHAR)

        month_fortunes.append(
            {
                "label": f"{y}年{m}月の恋愛運",
                "text": text,
            }
        )

    return {
        "year_label": f"{target_year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes,
    }
