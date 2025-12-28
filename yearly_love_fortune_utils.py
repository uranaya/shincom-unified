import openai
from datetime import datetime
from dateutil.relativedelta import relativedelta
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date

# 月運テキストの最大文字数（将来使うかもしれないので残しておく）
MAX_CHAR = 110


def _ask_openai(prompt: str, max_tokens: int = 400, temperature: float = 0.7) -> str:
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
    ★仕様変更：
    恋愛年運の月ごとの文章は「全文を PDF に出力する」方針。
    長さによるカットは行わず、改行除去と末尾の句点整形のみ行う。
    """
    if not text:
        return ""

    # 改行を取り除き、前後の空白をトリム
    t = str(text).strip().replace("\r\n", "").replace("\r", "").replace("\n", "")

    # 末尾が「。」で終わるようにだけ整える
    t = t.rstrip()
    if not t.endswith("。"):
        t = t.rstrip("。") + "。"

    return t


def generate_yearly_love_fortune(user_birth: str, now: datetime):
    """
    恋愛版の年間運（1年分＋12か月）を生成。

    - 基準月は「20日境」で、now の 20 日以降なら翌月スタート
    - 年運テキスト + 12 ヶ月分の恋愛運テキストを返す
    - 2025-12-28 時点なら、基準月は 2026-01、12ヶ月は
      2026年1月〜12月 までが出力される
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
- 前向きでやさしいトーン
- ネガティブなことに触れる場合も、最後は希望が持てる締めくくりにしてください
""".strip()

    year_fortune_raw = _ask_openai(prompt_year, max_tokens=260)
    year_fortune = _truncate(year_fortune_raw)

    # 12ヶ月分の月別恋愛運
    month_fortunes = []

    for i in range(12):
        target = base + relativedelta(months=i)
        y = target.year
        m = target.month

        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)

        prompt_month = f"""
あなたは恋愛占いの専門家です。
以下の情報をもとに、{y}年{m}月の恋愛運を
150〜220文字程度で1段落で教えてください。

- 日柱: {nicchu}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_month}

条件：
- 占い用語（例：比肩、傷官など）や干支名は文章に出さず、
  その意味を現実的な日本語に置き換えてください
- 主語は「あなた」
- 出会い・進展・距離感・気をつけるポイントなどに触れてください
- 前向きでやさしいトーン
- 文末は「〜でしょう。」「〜していきましょう。」など、日本語として自然に完結させてください
""".strip()

        raw_text = _ask_openai(prompt_month, max_tokens=260)
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
