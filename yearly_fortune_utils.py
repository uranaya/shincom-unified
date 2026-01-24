from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from kyusei_utils import get_honmeisei, get_directions
from datetime import datetime
from dateutil.relativedelta import relativedelta
import openai
import time

MAX_CHAR = 120  # Max characters for monthly fortune (JA). English is treated as a soft guideline.


def _ask_openai(prompt: str, system: str, retries: int = 3, delay: int = 2) -> str:
    """Simple retry wrapper (compatible with the legacy openai python package)."""
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                max_tokens=900,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"❌ OpenAI API error ({attempt+1}/{retries}): {e}")
            time.sleep(delay)
    return "取得に失敗しました（OpenAI APIエラー）" if system.startswith("あなた") else "Failed to generate (OpenAI API error)."


def generate_yearly_fortune(user_birth: str, now: datetime, force_next_month: bool = False, lang: str = "ja"):
    """
    Generate:
      - year_label, year_text
      - months: list of {label, text} for 12 months
    Notes:
      - base month uses the 20th-boundary rule (day>=20 -> next month), or force_next_month.
      - lang: 'ja' or 'en'
    """
    lang = (lang or "ja").lower()
    is_en = lang.startswith("en")

    # Important: define BEFORE use
    if is_en:
        lang_instruction = "\n\nWrite in English. Do NOT include eto (sexagenary cycle) names or Ten-God terms. Do NOT use Japanese."
        system_msg = "You are a professional Four Pillars of Destiny (Shichu Suimei) consultant. Provide practical, uplifting advice."
    else:
        lang_instruction = ""
        system_msg = "あなたは四柱推命のプロの占い師です。占い用語は使わず、現実的で前向きな助言に翻訳してください。"

    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)

    # 20日境の基準月 base
    base = now.replace(day=15)
    if now.day >= 20 or force_next_month:
        base += relativedelta(months=1)

    target_year = base.year

    # Year fortune
    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)

    if is_en:
        prompt_year = f"""You are a luck and life coach.
Using the following info, write the overall fortune for the year {target_year} for the person described.

- Day pillar (for reference only): {nicchu}
- Ten-God (meaning only): {tsuhen_year}

Requirements:
- Do NOT use any fortune-telling jargon (including Ten-God names) or eto names.
- Use plain, practical English.
- About 2–4 sentences, concise.
- Positive, actionable guidance.
""" + lang_instruction
    else:
        prompt_year = f"""あなたは開運アドバイザーです。
以下の情報をもとに、{target_year}年における「あなた」の全体運を自然な日本語で表現してください。

- 日柱（参照用）: {nicchu}
- 通変星（意味のみ）: {tsuhen_year}

条件：
- 占い用語（例：比肩、印綬など）や干支名は使わず、意味に沿ってやさしい言葉に置き換える
- 約{MAX_CHAR}文字以内
- 前向きで、行動や考え方の指針になるように
""" + lang_instruction

    year_fortune = _ask_openai(prompt_year, system_msg)

    # 12 months from base
    month_fortunes = []
    for i in range(12):
        target = base + relativedelta(months=i)
        y, m = target.year, target.month

        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)
        _ = get_directions(y, m, honmeisei)  # keep calculation for consistency (even if not shown here)

        if is_en:
            prompt_month = f"""You are a professional fortune-telling consultant.
Write the monthly fortune for {y}-{m:02d} in plain English.

- Day pillar (for reference only): {nicchu}
- Month Ten-God (meaning only): {tsuhen_month}

Requirements:
- Do NOT use any fortune-telling jargon (including Ten-God names) or eto names.
- 2–4 sentences, concise.
- Include a concrete focus (actions / mindset / relationships / timing).
""" + lang_instruction
            label = f"{y}-{m:02d} Monthly Fortune"
        else:
            prompt_month = f"""あなたは占いの専門家です。
以下の情報をもとに、{y}年{m}月の運気を自然な日本語で約{MAX_CHAR}文字以内にまとめてください。

- 日柱（参照用）: {nicchu}
- 月の通変星（意味のみ）: {tsuhen_month}

条件：
- 占い専門用語は使わず意味をやさしく表現
- 主語は「あなた」
- 月ごとに変化を出す（行動・感情・周囲との関係など）
- 現実的でポジティブな内容
""" + lang_instruction
            label = f"{y}年{m}月の運勢"

        text = _ask_openai(prompt_month, system_msg)
        month_fortunes.append({"label": label, "text": text})

    if is_en:
        year_label = f"{target_year} Overall Fortune"
    else:
        year_label = f"{target_year}年の総合運"

    return {
        "year_label": year_label,
        "year_text": year_fortune,
        "months": month_fortunes,
        "lang": "en" if is_en else "ja",
    }
