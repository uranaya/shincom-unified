
import openai
from datetime import datetime
from hayami_table_full_complete import hayami_table

stems = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
branches = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

def get_nicchu_eto(birthdate):
    try:
        date_obj = datetime.strptime(birthdate, "%Y-%m-%d")
        year, month, day = date_obj.year, date_obj.month, date_obj.day
        if year in hayami_table and 1 <= month <= 12:
            base = hayami_table[year][month - 1]
            index = base + day - 1
            while index >= 60:
                index -= 60
            return stems[index % 10] + branches[index % 12]
        return "不明"
    except Exception as e:
        print("❌ 日柱計算エラー:", e)
        return "不明"

def get_shichu_fortune(birthdate):
    eto = get_nicchu_eto(birthdate)
    prompt = f"""あなたはプロの四柱推命鑑定士です。
以下の干支（日柱）が「{eto}」の人に対して、以下の3つの項目で現実的な鑑定をしてください。

■ 性格
■ 今月の運勢
■ 来月の運勢

・それぞれ300文字以内。
・項目ごとに明確に区切ってください。
・干支名は本文に含めないでください。"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 四柱推命取得失敗:", e)
        return "■ 性格\n取得できませんでした\n■ 今月の運勢\n取得できませんでした\n■ 来月の運勢\n取得できませんでした"

def get_iching_advice():
    prompt = "今の相談者にとって最適な易占いのアドバイスを、日本語で300文字以内で現実的に書いてください。"
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 易占い取得エラー:", e)
        return "取得できませんでした。"

def get_lucky_info(birthdate):
    prompt = "10代の人に向けたラッキーカラー・ラッキーアイテム・ラッキーナンバーを、それぞれ1行で日本語で教えてください。"
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ ラッキー情報取得エラー:", e)
        return "取得できませんでした。"

def analyze_palm(image_data):
    try:
        base64data = image_data.split(",", 1)[1]
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはプロの手相鑑定士です。以下の指示に従って、写真から手相を分析し日本語で出力してください。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "手相の写真を見て、以下の形式で出力してください：\n"
                                "### 1. 生命線\n（説明文）\n\n"
                                "### 2. 知能線\n（説明文）\n\n"
                                "### 3. 感情線\n（説明文）\n\n"
                                "### 4. 運命線\n（説明文）\n\n"
                                "### 5. 太陽線\n（説明文）\n\n"
                                "### 総合的なアドバイス\n（全体を踏まえたまとめ）\n\n"
                                "・各項目は400文字前後で\n・丁寧でわかりやすく自然な表現で\n・改行や記号などで項目を明確に区切ってください"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64data}"
                            },
                        },
                    ],
                },
            ],
            max_tokens=3000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Vision APIエラー:", e)
        return "手相診断中にエラーが発生しました。"

def generate_fortune(image_data, birthdate):
    palm_result = analyze_palm(image_data)
    shichu_result = get_shichu_fortune(birthdate)
    iching_result = get_iching_advice()
    lucky_info = get_lucky_info(birthdate)
    return palm_result, shichu_result, iching_result, lucky_info

def generate_renai_fortune(user_birth, partner_birth=None, include_yearly=False):
    result = {
        "compatibility_text": "",
        "overall_love_fortune": "",
        "topic_fortunes": [],
        "yearly_love_fortunes": None
    }

    # 干支（日柱）の計算
    user_eto = get_nicchu_eto(user_birth)
    partner_eto = get_nicchu_eto(partner_birth) if partner_birth else None

    # 相性占いパート
    if partner_eto:
        prompt_compatibility = f"""
あなたは四柱推命に基づく恋愛占いの専門家です。
- あなたの日柱: {user_eto}
- お相手の日柱: {partner_eto}

この2人の恋愛相性や関係性の特徴、注意点などを自然で現実的な文章で解説してください。
"""
    else:
        prompt_compatibility = f"""
あなたは四柱推命に基づく恋愛占いの専門家です。
- あなたの日柱: {user_eto}

あなたの性格、恋愛傾向、理想の相手像、そして出会いのチャンスについて自然で現実的な文章で解説してください。
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_compatibility}],
            temperature=0.9
        )
        result["compatibility_text"] = response.choices[0].message.content.strip()
    except Exception as e:
        result["compatibility_text"] = f"[エラー] 相性占いの生成に失敗しました：{e}"

    # 今後必要ならば、以下にトピック占いや年運の生成処理を追加可能
    return result
