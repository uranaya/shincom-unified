from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from kyusei_utils import get_honmeisei, get_directions
from datetime import datetime
from dateutil.relativedelta import relativedelta
import openai
import os
import time
import re

# 日本語は「途中で切れる」と尻切れトンボになりやすく体験が悪い。
# そこで、プロンプト側の目安（年: 140〜220 / 月: 120〜160）に合わせつつ、
# 末尾が文として自然に閉じるようにトリム処理も改善する。
MAX_CHAR_JA_YEAR = 220
MAX_CHAR_JA_MONTH = 160

# 英語は「文字数」で制限すると極端に短くなりやすいため、
# 1か月あたりの文章量を増やしてページがスカスカにならないようにする。
# （厳密な words 制限ではなく、過剰に長くなりすぎないための上限）
MAX_CHAR_EN = 900
MAX_CHAR_EN_YEAR = 2000
MAX_CHAR_EN_MONTH = 900

# 中国語（簡体字）は「文字数」ベースで日本語に近い密度になるため、
# 日本語より少しだけ余裕を持たせる。
MAX_CHAR_ZH_YEAR = 260
MAX_CHAR_ZH_MONTH = 180

# 韓国語（ko）は英語より文字密度が高く、日本語よりはスペースが入るため、
# 日本語より少し余裕を持たせつつ、PDFの見切れを起こしにくい上限にする。
MAX_CHAR_KO_YEAR = 260
MAX_CHAR_KO_MONTH = 180

# --- text helpers ---

def _trim_to_max_chars(text: str, max_chars: int) -> str:
    """Trim text to a safe maximum length without breaking rendering.

    - Collapses excessive whitespace (spaces/newlines).
    - If over max_chars, truncates *cleanly*.

    IMPORTANT:
    The PDF layer already wraps and paginates. Adding "..."/"…" here makes
    month blocks look "cut off" even when we still have room to wrap.
    """
    if not text:
        return ""
    # Normalize whitespace so the PDF layout is predictable
    t = re.sub(r"\s+", " ", str(text)).strip()
    if max_chars and len(t) > max_chars:
        # できるだけ「文の区切り」で自然に終わらせる（日本語優先）
        cut = t[:max_chars]
        # 句点/終端記号を優先
        for punct in ["。", "！", "？", ".", "!", "?"]:
            idx = cut.rfind(punct)
            if idx >= int(max_chars * 0.55):
                return cut[: idx + 1]
        # それでも見つからなければ、読点/スペースで切る
        for punct in ["、", "，", ",", " "]:
            idx = cut.rfind(punct)
            if idx >= int(max_chars * 0.55):
                return cut[: idx].rstrip() + "。"
        # 最終手段：そのまま切る（省略記号は付けない）
        cut2 = cut.rstrip()
        if not cut2:
            return ""
        if cut2[-1] not in ["。", "！", "？", ".", "!", "?"]:
            # なるべく自然な終端にする（英語っぽいなら "."、それ以外は "。"）
            if re.search(r"[A-Za-z0-9]$", cut2):
                cut2 += "."
            else:
                cut2 += "。"
        return cut2
    return t


def _build_monthly_prompt(month_label: str, eto: str, tsuhensei_year: str, tsuhensei_month: str, lang: str) -> str:
    lang_norm = (lang or "ja").lower()
    if lang_norm.startswith("en"):
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
        f"Upper limit: about {MAX_CHAR_EN_MONTH} characters.",
        ])
    if lang_norm.startswith(("zh", "cn")):
        return "\n".join([
            "你是一位专业的占卜师。",
            "请使用简体中文，语气温柔、积极、具象，并给出可执行的建议。",
            "不要出现干支名、通变星等术语（只可用于理解，不要写出来）。",
            f"月份: {month_label}",
            f"日柱(仅参考): {eto}",
            f"年影响(仅参考): {tsuhensei_year}",
            f"月影响(仅参考): {tsuhensei_month}",
            "输出：3-5句话，避免空话，至少给出一个行动建议。",
            f"字符上限：约 {MAX_CHAR_ZH_MONTH} 字。",
        ])
    return "\n".join([
        "あなたはプロの占い師です。",
        "干支や専門用語を出さず、現実に即した前向きな文章にしてください。",
        f"対象月: {month_label}",
        f"日柱: {eto}",
        f"年の通変星: {tsuhensei_year}",
        f"月の通変星: {tsuhensei_month}",
        "出力は2〜3文で、実用的でやさしい語り口にしてください。",
        f"文字数上限: {MAX_CHAR_JA_MONTH}字。",
    ])



def _ask_openai(prompt: str, lang: str = "ja", retries: int = 3, delay: int = 2) -> str:
    lang_norm = (lang or "ja").lower()
    if lang_norm.startswith("en"):
        system_text = "You are a professional fortune teller. Write clear, natural English for customers."
    elif lang_norm.startswith(("zh", "cn")):
        system_text = "你是一位专业的占卜师。请用简体中文，为顾客写出清晰、自然、积极的建议。"
    else:
        system_text = "あなたは四柱推命のプロの占い師です。"
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                max_tokens=2000,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": system_text},
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
    lang_norm = (lang or 'ja').lower()
    if lang_norm.startswith('en'):
        lang_instruction = "\n\nWrite in English. Do NOT include eto names or Ten-God terms."
    elif lang_norm.startswith(('zh', 'cn')):
        lang_instruction = "\n\n请用简体中文。不要出现干支名、通变星等术语（只可用于理解，不要写出来）。"
    else:
        lang_instruction = ""
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")
    honmeisei = get_honmeisei(born.year, born.month, born.day)

    # 20日境の基準月
    base = now.replace(day=15)
    if now.day >= 20 or force_next_month:
        base += relativedelta(months=1)

    target_year = base.year

    tsuhen_year = get_tsuhensei_for_year(user_birth, target_year)

    if lang_norm.startswith('en'):
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
    elif lang_norm.startswith(('zh', 'cn')):
        prompt_year = f"""你是开运建议的顾问。
请根据下面的信息，用简体中文为顾客写出 {target_year} 年的整体运势概览。

长度：
- 4～7句话
- 控制在约 {MAX_CHAR_ZH_YEAR} 字以内（不要写得过长）

参考信息：
- 日柱（仅参考）：{nicchu}
- 年影响（仅参考）：{tsuhen_year}

规则：
- 不要出现干支名、通变星等术语；把含义翻译成日常表达
- 积极、实用、可执行
- 避免空话，给出具体建议（工作、人际、金钱、健康等）
""" + lang_instruction
    elif lang_norm.startswith(("ko", "kr")):
        prompt_year = f"""당신은 개운 상담가(운세 어드바이저)입니다.
아래 정보를 참고하여 고객의 {target_year}년 전체 운세를 자연스러운 한국어로 작성하세요.

길이:
- 4~7문장
- 약 {MAX_CHAR_KO_YEAR}자 이내(너무 길게 쓰지 마세요)

참고 정보:
- 일주(참고용): {nicchu}
- 연의 영향(참고용): {tsuhen_year}

규칙:
- 간지명, 통변성 등 전문 용어는 절대 쓰지 말고, 의미를 일상적인 표현으로 풀어주세요
- 긍정적이고 실용적이며 실행 가능한 조언 중심
- 공허한 말은 피하고(일, 인간관계, 금전, 건강 등) 구체적으로
""" + lang_instruction

    else:
        prompt_year = f"""あなたは開運アドバイザーです。
以下の情報をもとに、{target_year}年における「あなた」の全体運を自然な日本語で表現してください。

- 日柱: {nicchu}
- 通変星: {tsuhen_year}

条件：
- 占い用語（例：比肩、印綬など）や干支名は使わず、意味に沿ってやさしい言葉に置き換えてください
- 約{MAX_CHAR_JA_YEAR}文字以内
- 前向きで、行動や考え方の指針になるように
""" + lang_instruction

    max_year = (MAX_CHAR_EN_YEAR if lang_norm.startswith('en') else (MAX_CHAR_ZH_YEAR if lang_norm.startswith(('zh', 'cn')) else (MAX_CHAR_KO_YEAR if lang_norm.startswith(('ko', 'kr')) else MAX_CHAR_JA_YEAR)))
    year_fortune = _trim_to_max_chars(
        _ask_openai(prompt_year, lang=lang_norm),
        max_year,
    )

    month_fortunes = []
    for i in range(12):
        target = base + relativedelta(months=i)
        y, m = target.year, target.month
        tsuhen_month = get_tsuhensei_for_date(user_birth, y, m)
        # directions are computed elsewhere for PDF; keep text clean
        if lang_norm.startswith('en'):
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
        elif lang_norm.startswith(('zh', 'cn')):
            prompt_month = f"""你是占卜顾问。
请用简体中文写出顾客在 {y}年{m}月 的运势。

长度：
- 3～6句话
- 控制在约 {MAX_CHAR_ZH_MONTH} 字以内

参考信息：
- 日柱（仅参考）：{nicchu}
- 月影响（仅参考）：{tsuhen_month}

规则：
- 不要出现干支名、通变星等术语；用日常语言表达含义
- 积极、实用、有行动建议
- 每个月要有变化（行动、情绪、人际、工作、金钱、健康等）
- 避免每个月都用同样的句式
""" + lang_instruction
            label = f"{y}年{m}月的运势"
        elif lang_norm.startswith(("ko", "kr")):
            prompt_month = f"""당신은 운세 상담가입니다.
아래 정보를 참고하여 고객의 {y}년 {m}월 운세를 자연스러운 한국어로 작성하세요.

길이:
- 3~6문장
- 약 {MAX_CHAR_KO_MONTH}자 이내

참고 정보:
- 일주(참고용): {nicchu}
- 월의 영향(참고용): {tsuhen_month}

규칙:
- 간지명, 통변성 등 전문 용어는 절대 쓰지 말고, 의미를 일상적인 표현으로 풀어주세요
- 실용적이고 긍정적으로, 행동 제안 포함
- 월마다 분위기/초점이 달라지도록(행동, 기분, 인간관계, 일, 금전, 건강 등)
- 매달 같은 문장 패턴 반복 금지
""" + lang_instruction
            label = f"{y}년 {m}월 운세"

        else:
            prompt_month = f"""あなたは占いの専門家です。
以下の情報をもとに、{y}年{m}月の運気を自然な日本語で約{MAX_CHAR_JA_MONTH}字以内にまとめてください。

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
        max_month = (MAX_CHAR_EN_MONTH if lang_norm.startswith('en') else (MAX_CHAR_ZH_MONTH if lang_norm.startswith(('zh', 'cn')) else (MAX_CHAR_KO_MONTH if lang_norm.startswith(('ko', 'kr')) else MAX_CHAR_JA_MONTH)))
        text = _trim_to_max_chars(
            _ask_openai(prompt_month, lang=lang_norm),
            max_month,
        )
        month_fortunes.append({"label": label, "text": text})

    if lang_norm.startswith('en'):
        year_label = f"Overall fortune for {target_year}"
    elif lang_norm.startswith(('zh', 'cn')):
        year_label = f"{target_year}年的整体运势"
    elif lang_norm.startswith(('ko', 'kr')):
        year_label = f"{target_year}년 종합운"
    else:
        year_label = f"{target_year}年の総合運"

    return {
        "year_label": year_label,
        "year_text": year_fortune,
        "months": month_fortunes
    }


