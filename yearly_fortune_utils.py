from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from kyusei_utils import get_honmeisei, get_directions
from datetime import datetime
from dateutil.relativedelta import relativedelta
import openai
import os
import time
import re

# 日本語は従来通り短め（120〜160字目安）。
MAX_CHAR_JA = 120

# 英語は「文字数」で制限すると極端に短くなりやすいため、
# 1か月あたりの文章量を増やしてページがスカスカにならないようにする。
# （厳密な words 制限ではなく、過剰に長くなりすぎないための上限）
MAX_CHAR_EN = 420
MAX_CHAR_EN_YEAR = 520
MAX_CHAR_EN_MONTH = 380


def _build_monthly_prompt(month_label: str, eto: str, tsuhensei_year: str, tsuhensei_month: str, lang: str) -> str:
    if lang == "en":
        return "\n".join([
            "You are a professional fortune teller.",
            "Write in natural, friendly English for customers.",
            "Do NOT mention stems/branches or technical terms; do not show raw astrology tables.",
            f"Month: {month_label}",
            f"Day pillar: {eto}",
            f"Year star (Tsuhensei): {tsuhensei_year}",
            f"Month star (Tsuhensei): {tsuhensei_month}",
            "Output: 3-5 sentences (roughly 70-110 words).",
            "Keep it practical and positive. Include at least one actionable tip.",
            f"Upper limit: about {MAX_CHAR_EN_YEAR} characters.",
        ])
    return "\n".join([
        "あなたはプロの占い師です。",
        "干支や専門用語を出さず、現実に即した前向きな文章にしてください。",
        f"対象月: {month_label}",
        f"日柱: {eto}",
        f"年の通変星: {tsuhensei_year}",
        f"月の通変星: {tsuhensei_month}",
        "出力は2〜3文で、実用的でやさしい語り口にしてください。",
        f"文字数上限: {MAX_CHAR_JA}字。",
    ])



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



def generate_yearly_fortune(user_birth: str, now: datetime, force_next_month: bool = False, lang: str = 'ja'):
    """Generate yearly + 12-month fortunes (text only)."""
    lang = (lang or 'ja').lower()
    lang_instruction = "\n\nWrite in English. Do NOT include eto names or Ten-God terms." if lang.startswith('en') else ""
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)

    # 20日境の基準月
    base = now.replace(day=15)
    if now.day >= 20 or force_next_month:
        base += relativedelta(months=1)

    target_year = base.year

    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)

    if lang.startswith('en'):
        prompt_year = f"""You are a fortune-telling advisor.
Using the information below, write a {target_year} overview for the customer in natural English.

Length:
- 4–7 sentences
- Aim for ~80–110 words (keep within about {MAX_CHAR_EN_YEAR} characters)

- Day pillar (reference only): {nicchu}
- Year influence (reference only): {tsuhen_year}

Rules:
- Do NOT mention eto names or Ten-God terms; translate meanings into plain English
- Positive, practical, and customer-friendly
- Avoid generic filler; give concrete, usable guidance
""" + lang_instruction
    else:
        prompt_year = f"""あなたは開運アドバイザーです。
以下の情報をもとに、{target_year}年における「あなた」の全体運を自然な日本語で表現してください。

- 日柱: {nicchu}
- 通変星: {tsuhen_year}

条件：
- 占い用語（例：比肩、印綬など）や干支名は使わず、意味に沿ってやさしい言葉に置き換えてください
- 約{MAX_CHAR_JA}文字以内
- 前向きで、行動や考え方の指針になるように
""" + lang_instruction

    year_fortune = _trim_to_max_chars(_ask_openai(prompt_year), MAX_CHAR_EN_YEAR if lang.startswith('en') else MAX_CHAR_JA)

    month_fortunes = []
    for i in range(12):
        target = base + relativedelta(months=i)
        y, m = target.year, target.month
        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)
        # directions are computed elsewhere for PDF; keep text clean
        if lang.startswith('en'):
            prompt_month = f"""You are a fortune-telling advisor.
Write the customer's fortune for {y}-{m:02d} in natural English.

Length:
- 3–6 sentences
- Aim for ~45–70 words (keep within about {MAX_CHAR_EN_MONTH} characters)

Reference info:
- Day pillar (reference only): {nicchu}
- Month influence (reference only): {tsuhen_month}

Rules:
- Do NOT mention eto names or Ten-God terms; translate meanings into plain English
- Keep it practical and positive
- Make each month feel different (actions, mood, relationships, work, money, health, etc.)
- Avoid repeating the same phrasing month to month
""" + lang_instruction
            label = f"Fortune for {y}-{m:02d}"
        else:
            prompt_month = f"""あなたは占いの専門家です。
以下の情報をもとに、{y}年{m}月の運気を自然な日本語で約{MAX_CHAR_JA}〜160文字程度にまとめてください。

- 日柱: {nicchu}
- 月の通変星: {tsuhen_month}

条件：
- 占い専門用語は使わず意味をやさしく表現
- 主語は「あなた」
- 月ごとに変化を出す（行動・感情・周囲との関係など）
- 現実的でポジティブな内容
""" + lang_instruction
            label = f"{y}年{m}月の運勢"

        # OpenAIで生成（英語/日本語とも共通）
        text = _trim_to_max_chars(_ask_openai(prompt_month), MAX_CHAR_EN_MONTH if lang.startswith('en') else MAX_CHAR_JA)
        month_fortunes.append({"label": label, "text": text})

    return {
        "year_label": (f"Overall fortune for {target_year}" if lang.startswith('en') else f"{target_year}年の総合運"),
        "year_text": year_fortune,
        "months": month_fortunes
    }


