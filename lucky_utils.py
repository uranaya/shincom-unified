# lucky_utils.py
# ラッキー情報・ラッキー方位の生成ユーティリティ
# - 既存の通常運用（日本語）に影響を出さない
# - lang='en' のときは英語ラベルで返す（PDF英語版用）

from __future__ import annotations

import os
from typing import List

from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def _prompt_lucky_info(lang: str, nicchu_eto: str, birthdate: str, age: int, palm_result: str, shichu_result_raw: str, kyusei_text: str) -> str:
    if (lang or "ja").lower().startswith("en"):
        return f"""You are an assistant for a fortune-telling shop.
Given the following inputs, generate EXACTLY 5 short lines in English, each starting with the label and a colon.

Labels (in this order):
1) Lucky Item
2) Lucky Color
3) Lucky Number
4) Lucky Food
5) Lucky Day

Constraints:
- Each line should be concise (about 6-14 words).
- Do not add any extra lines or explanations.
- Avoid overly technical terms.

Inputs:
- Day Pillar (nicchu_eto): {nicchu_eto}
- Birthdate: {birthdate}
- Age: {age}
- Palm reading (summary): {palm_result}
- Shichu (raw): {shichu_result_raw}
- Kyusei: {kyusei_text}
"""
    # default: Japanese
    return f"""あなたは占い館のアシスタントです。
以下の入力をもとに、ラッキー情報を「必ず5行」だけ出力してください。各行は「ラベル：内容」の形式にしてください。

ラベル（この順番）：
1) ラッキーアイテム
2) ラッキーカラー
3) ラッキーナンバー
4) ラッキーフード
5) ラッキーデー

制約：
- 各行は短めに（目安10〜20文字程度）
- 余計な説明や前置き、空行を入れない
- ラベルは必ず上記の文言を使う

入力：
- 日柱（nicchu_eto）: {nicchu_eto}
- 生年月日: {birthdate}
- 年齢: {age}
- 手相（要約）: {palm_result}
- 四柱（raw）: {shichu_result_raw}
- 九星: {kyusei_text}
"""

def generate_lucky_info(
    nicchu_eto: str,
    birthdate: str,
    age: int,
    palm_result: str,
    shichu_result_raw: str,
    kyusei_text: str,
    lang: str = "ja",
    model: str = "gpt-4o-mini",
) -> List[str]:
    """ラッキー情報（5行）を返す。"""
    prompt = _prompt_lucky_info(lang, nicchu_eto, birthdate, age, palm_result, shichu_result_raw, kyusei_text)
    res = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
    )
    text = (res.choices[0].message.content or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # 保険：多すぎたら先頭5行、少なければそのまま
    return lines[:5]

def _prompt_lucky_direction(lang: str, kyusei_text: str) -> str:
    if (lang or "ja").lower().startswith("en"):
        return f"""Given the following Kyusei text, output ONE concise line in English:
Format: Lucky Direction: <directions>
- Keep it short.
- No extra lines.

Kyusei text:
{kyusei_text}
"""
    return f"""以下の九星気学テキストをもとに、ラッキー方位を1行で出力してください。
形式：ラッキー方位：〇〇
- 余計な説明や空行は不要
九星テキスト：
{kyusei_text}
"""

def generate_lucky_direction(
    kyusei_text: str,
    lang: str = "ja",
    model: str = "gpt-4o-mini",
) -> str:
    prompt = _prompt_lucky_direction(lang, kyusei_text)
    res = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )
    return (res.choices[0].message.content or "").strip()
