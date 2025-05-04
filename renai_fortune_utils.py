
import openai
import os
from kyusei_utils import get_honmeisei, get_directions, get_kyusei_fortune_openai
from datetime import datetime
import random

def get_shichu_fortune(nicchu, target_year, target_month):
    prompt = f"""
あなたは四柱推命のプロの占い師です。
- 日柱: {nicchu}
- 対象月: {target_year}年{target_month}月

以下の形式でそれぞれ300文字以内で、占い文を生成してください。

【性格】
（生まれ持った性格・強みや注意点）

【{target_month}月の運勢】
（その月に気をつける点、活かせるチャンスなど）

※干支などの専門用語を使わず、誰にでもわかりやすく自然な文章にしてください。
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[エラー] 四柱推命の占い生成に失敗しました：{e}"

def get_iching_advice():
    prompt = "あなたは易の専門家です。おみくじのように今の相談者に向けた300文字程度のアドバイスをください。"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[エラー] 易占い生成に失敗しました：{e}"

def summarize_all_fortunes(parts):
    joined = "\n\n".join(parts)
    prompt = f"以下は占いの結果の断片です。これらをまとめて、最後に一言のアドバイスをつけてください。\n\n{joined}"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[エラー] まとめの生成に失敗しました：{e}"

def generate_fortune(birthdate, partner_birth, selected_topics, include_yearly=False):
    results = []
    today = datetime.today()
    year, month = today.year, today.month

    # 恋愛テーマが含まれる場合
    if selected_topics:
        topics_text = "、".join(selected_topics)
        prompt = f"""
あなたは恋愛専門の占い師です。
- あなたの誕生日: {birthdate}
- お相手の誕生日: {partner_birth}
- 相談内容: {topics_text}

相談内容に応じて、相性や未来の展望、注意点などを占いらしい口調で自然に出力してください。
"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
            )
            results.append("【恋愛鑑定】\n" + response.choices[0].message.content.strip())
        except Exception as e:
            results.append(f"[エラー] 恋愛占い生成に失敗しました：{e}")

    # 総合鑑定要素（ラッキー・四柱推命・方位など）
    birth = datetime.strptime(birthdate, "%Y-%m-%d")
    nicchu = get_nicchu_eto(birth)
    honmeisei = get_honmeisei(birth.year, birth.month, birth.day)
    directions = get_directions(year, month, honmeisei)
    direction_text = f"あなたの本命星は{honmeisei}です。\n" \
                     f"{year}年の吉方位は{directions['year']}、" \
                     f"{month}月は{directions['month']}です。"

    results.append("【四柱推命】\n" + get_shichu_fortune(nicchu, year, month))
    results.append("【九星気学】\n" + get_kyusei_fortune_openai(honmeisei, year, month, month + 1))
    results.append("【ラッキーアドバイス】\n" + get_lucky_items(birthdate))
    results.append("【易占い】\n" + get_iching_advice())

    summary = summarize_all_fortunes(results)
    results.append("【まとめ】\n" + summary)

    return "\n\n".join(results)

def get_nicchu_eto(birthdate):
    # 簡易干支算出（プレースホルダー）
    stems = "甲乙丙丁戊己庚辛壬癸"
    branches = "子丑寅卯辰巳午未申酉戌亥"
    base_date = datetime(1924, 2, 5)
    delta_days = (birthdate - base_date).days
    eto_index = delta_days % 60
    return stems[eto_index % 10] + branches[eto_index % 12]

def get_lucky_items(birthdate_str):
    random.seed(birthdate_str)
    colors = ["赤", "青", "緑", "黄", "紫", "白", "黒", "オレンジ", "ピンク", "水色"]
    items = ["鍵", "ノート", "アクセサリー", "時計", "ハンカチ", "香水", "帽子", "スマホケース", "ペン", "財布"]
    lucky_color = random.choice(colors)
    lucky_item = random.choice(items)
    lucky_number = random.randint(1, 99)
    lucky_day = random.choice(["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"])
    return f"ラッキーカラーは{lucky_color}、ラッキーアイテムは{lucky_item}、ラッキーナンバーは{lucky_number}、ラッキーデーは{lucky_day}です。"
