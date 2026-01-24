from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from kyusei_utils import get_honmeisei, get_directions
from datetime import datetime
from dateutil.relativedelta import relativedelta
import openai
import os
import time

MAX_CHAR = 120  # Max characters for monthly fortune


def _ask_openai(prompt: str, retries=3, delay=2) -> str:
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                max_tokens=2000,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": "あなたは四柱推命のプロの占い師です。"},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()
        except openai.error.APIError as e:
            print(f"❌ OpenAI APIエラー（{attempt+1}回目）:", e)
            time.sleep(delay)
    return "取得に失敗しました（OpenAI APIエラー）"


def generate_yearly_fortune(birthdate: str, now=None, lang: str = 'ja', style: str = 'normal'):
    """Generate 12-month fortunes. Returns list[str] of length 12."""
    if now is None:
        now = datetime.datetime.now()

    year = now.year
    months = [f"{year}-{m:02d}" for m in range(1, 13)]

    style_note = ""
    if style == "tokyo":
        style_note = ("Use a bright, uplifting tone suitable for Tokyo/Asakusa visitors. "
                      "At most one short Asakusa-flavored phrase in the entire output."
                      if (lang or 'ja').lower().startswith('en') else
                      "東京（浅草）向け：明るく前向き。浅草要素は全体で一言程度に留める。")

    if (lang or 'ja').lower().startswith('en'):
        prompt = """You create a 12-month fortune for a customer.
Return ONLY valid JSON with key 'months' whose value is an array of 12 strings.
Each string must be 2-4 sentences, practical and encouraging, no scary wording.
Do NOT mention zodiac stem/branch names.

Input:
- Birthdate: {birthdate}
- Target year: {year}
- Months: {months}
Style note: {style_note}
""".format(birthdate=birthdate, year=year, months=", ".join(months), style_note=style_note)
    else:
        prompt = """あなたは占い文章の作成者です。
次の条件で「1年分（12か月）」の運勢を作ってください。

【出力】JSONのみ。キーは months。値は12個の文字列配列。
各月は2〜4文で、前向きで実用的に。脅す表現や断定は避ける。
干支名（例：甲子など）は本文に出さない。

【入力】
生年月日: {birthdate}
対象年: {year}
月: {months}

スタイル: {style_note}
""".format(birthdate=birthdate, year=year, months=", ".join(months), style_note=style_note)

    data = _ask_openai(prompt)
    result = data.get("months") if isinstance(data, dict) else None
    if not isinstance(result, list):
        # Fallback: return empty list with 12 slots to keep PDF stable
        return ["" for _ in range(12)]
    # normalize to 12
    out = [(str(x) if x is not None else "").strip() for x in result]
    if len(out) < 12:
        out += [""] * (12 - len(out))
    elif len(out) > 12:
        out = out[:12]
    return out
