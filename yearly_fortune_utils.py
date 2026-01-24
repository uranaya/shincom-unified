import os
import json
import openai

def generate_yearly_fortune(birthdate: str, now, lang: str = "ja") -> str:
    lang = (lang or "ja").lower()
    year = now.year
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if lang.startswith("en"):
        system = "You are a fortune-telling assistant. Write concise, friendly monthly forecasts."
        user = f"""Create a 12-month forecast for the year {year} in ENGLISH.

Rules:
- Output JSON array of 12 strings only (no markdown).
- Each month: 2 short sentences, max ~240 characters.
- Start each with month label like "Jan:" "Feb:" etc.
- Do NOT include Japanese.

Birthdate: {birthdate}
"""
    else:
        system = "あなたは占い師アシスタントです。月ごとの運勢を短く読みやすく作ります。"
        user = f"""{year}年の12か月運勢を日本語で作成してください。

ルール：
- JSON配列（12要素）だけを出力（markdown禁止）
- 各月は2文程度、長文禁止（目安：全角120文字以内）
- 先頭に「1月：」「2月：」のように月を付ける

生年月日: {birthdate}
"""

    resp = openai.ChatCompletion.create(
        model=model,
        temperature=0.7,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
    )
    txt = resp["choices"][0]["message"]["content"].strip()

    try:
        arr = json.loads(txt)
        if isinstance(arr, list) and len(arr) >= 12:
            return "\n".join([str(x) for x in arr[:12]])
    except Exception:
        pass
    return txt
