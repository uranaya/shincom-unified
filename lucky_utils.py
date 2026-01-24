import os
import json
from typing import List

import openai


def _call_chat(system: str, user: str, model: str = None, temperature: float = 0.7) -> str:
    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    resp = openai.ChatCompletion.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp["choices"][0]["message"]["content"].strip()


def generate_lucky_info(nicchu_eto: str, birthdate: str, age: int, palm_result: str, shichu_result_raw: str, kyusei_text: str, lang: str = "ja") -> List[str]:
    lang = (lang or "ja").lower()

    if lang.startswith("en"):
        system = "You are a helpful fortune-telling assistant. Produce concise, friendly, practical suggestions."
        user = f"""Create 5 short 'Lucky Info' lines in ENGLISH.

Rules:
- Output JSON array only (no markdown).
- Keep each line short (ideally <= 40 characters).
- Topics (in order): lucky item, lucky color, lucky number, lucky food/drink, lucky action.
- Do NOT include Japanese.

Inputs:
Birthdate: {birthdate} (age {age})
Palm summary: {palm_result}
Shichu summary: {shichu_result_raw}
Kyusei: {kyusei_text}
"""
    else:
        system = "あなたは占い師アシスタントです。短く読みやすい開運情報を作ります。"
        user = f"""次の入力を参考に「ラッキー情報」を5行、日本語で作ってください。

ルール：
- JSON配列のみ（markdown禁止）
- 1行は短く（目安：全角18〜22文字程度）
- テーマ（順番）：ラッキーアイテム、ラッキーカラー、ラッキーナンバー、ラッキーフード/ドリンク、ラッキーアクション

入力：
生年月日: {birthdate}（{age}歳）
手相要約: {palm_result}
四柱推命要約: {shichu_result_raw}
九星: {kyusei_text}
"""

    txt = _call_chat(system, user, temperature=0.6)
    try:
        arr = json.loads(txt)
        if isinstance(arr, list):
            return [str(x) for x in arr][:5]
    except Exception:
        pass

    # fallback
    lines = [x.strip(" -•　") for x in txt.splitlines() if x.strip()]
    return lines[:5]


def generate_lucky_direction(birthdate: str, kyusei_text: str, now_ym: str, lang: str = "ja") -> str:
    lang = (lang or "ja").lower()

    if lang.startswith("en"):
        system = "You are a helpful fortune-telling assistant."
        user = f"""Write ONE short 'Lucky Direction' sentence in ENGLISH (max ~120 chars).

Inputs:
Birthdate: {birthdate}
Kyusei: {kyusei_text}
Period: {now_ym}
"""
    else:
        system = "あなたは占い師アシスタントです。吉方位を短くまとめます。"
        user = f"""次の入力を参考に、吉方位を短く1〜2文で日本語出力してください（長文禁止）。

生年月日: {birthdate}
九星: {kyusei_text}
対象: {now_ym}
"""

    return _call_chat(system, user, temperature=0.5)
