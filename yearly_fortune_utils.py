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


def generate_yearly_fortune(user_birth: str, now: datetime, force_next_month: bool = False, lang: str = 'ja'):
    """
    Returns yearly fortune + 12 monthly fortunes.
    - force_next_month: if True, base month starts from next month even if today < 20th.
    - lang: 'ja' or 'en'
    """
    lang_instruction = "\n\nWrite in English. Do NOT include eto names or Ten-God terms. Avoid fortune-telling jargon. Keep it positive and practical." if lang == 'en' else ""

    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)

    # Base month (20-day rule)
    base = now.replace(day=15)
    if now.day >= 20 or force_next_month:
        base += relativedelta(months=1)

    target_year = base.year

    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)
    prompt_year = f"""
You are an advisor who gives practical, uplifting guidance.
Based on the info below, write a short yearly outlook for {target_year} for the person addressed as "you".

- Day-pillar (internal): {nicchu}
- Ten-God (internal meaning): {tsuhen_year}

Rules:
- Do NOT mention eto names or Ten-God terms.
- About 120 Japanese characters or ~3-5 English sentences.
- Positive, realistic, actionable.
""" + lang_instruction
    year_fortune = _ask_openai(prompt_year)

    month_fortunes = []
    for i in range(12):
        target = base + relativedelta(months=i)
        y, m = target.year, target.month
        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)
        _ = get_directions(y, m, honmeisei)  # kept for future use / consistency

        prompt_month = f"""
You are a professional fortune advisor.
Write an outlook for {y}-{m:02d} for the person addressed as "you", in a practical and positive tone.

- Day-pillar (internal): {nicchu}
- Monthly Ten-God (internal meaning): {tsuhen_month}

Rules:
- Do NOT mention eto names or Ten-God terms.
- Keep it concise (about 120 Japanese characters or ~3-5 English sentences).
- Add month-to-month variation (actions, emotions, relationships, pacing).
""" + lang_instruction

        text = _ask_openai(prompt_month)
        label = f"{y}年{m}月の運勢" if lang != 'en' else f"Fortune for {y}-{m:02d}"
        month_fortunes.append({"label": label, "text": text})

    year_label = f"{target_year}年の総合運" if lang != 'en' else f"Yearly Fortune for {target_year}"
    return {"year_label": year_label, "year_text": year_fortune, "months": month_fortunes}

