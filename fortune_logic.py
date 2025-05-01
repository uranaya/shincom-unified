import openai
from datetime import datetime
from base64 import b64decode
from hayami_table_full_complete import hayami_table
from dateutil.relativedelta import relativedelta

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

    # 今月と来月を計算（日本時間前提）
    now = datetime.now()
    this_month = f"{now.year}年{now.month}月"
    next_month_dt = now + relativedelta(months=1)
    next_month = f"{next_month_dt.year}年{next_month_dt.month}月"

    prompt = f"""あなたはプロの四柱推命鑑定士です。
以下の干支（日柱）が「{eto}」の人に対して、以下の3つの項目で現実的な鑑定をしてください。

■ 性格
■ {this_month}の運勢
■ {next_month}の運勢

・それぞれ300文字以内。
・項目ごとに明確に区切ってください。
・干支名は本文に含めないでください。"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 四柱推命取得失敗:", e)
        return f"■ 性格\n取得できませんでした\n■ {this_month}の運勢\n取得できませんでした\n■ {next_month}の運勢\n取得できませんでした"


def get_iching_advice():
    prompt = "今の相談者にとって最適な易占いのアドバイスを、日本語で300文字以内で現実的に書いてください。"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 易占い取得エラー:", e)
        return "取得できませんでした。"


def analyze_palm(image_data):
    try:
        base64data = image_data.split(",", 1)[1]
        response = openai.ChatCompletion.create(
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
    "### 5. 特徴的な線\n（説明文）\n\n"
    "### 総合的なアドバイス\n（全体を踏まえたまとめ）\n\n"
    "・各項目は400文字前後で\n"
    "・読み手が楽しく前向きな気持ちになれるような、温かく優しい語り口で\n"
    "・改行や記号などで各項目が明確に区切られるようにしてください\n"
    "・特徴的な線が見られなかった場合でも“無い”とは書かず、全体の印象やバランスからポジティブな要素を自然に伝えてください\n"
    "・読み手に「占ってもらってよかった」と思ってもらえるように、1つでも印象に残るようなコメントを入れてください\n"
    "・もし金運に関連する良い線（財運線、太陽線、スター、覇王線、フィッシュなど）が見られた場合は、優先的に金運についてもポジティブなコメントを入れてください。\n"
    "・金運に関する記述を強調する場合は、他の項目を簡潔にまとめても構いません。\n"
    "・金運に特に特徴が見られない場合でも、そのことには一切触れず、全体の印象から前向きな鑑定結果にまとめてください。"
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

def get_lucky_info(birthdate, palm_result, shichu_result, kyusei_fortune):
    # 年齢を計算
    try:
        birth = datetime.strptime(birthdate, "%Y-%m-%d")
        today = datetime.today()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except:
        birth = None
        age = "不明"

    prompt = f"""以下の鑑定結果と基本情報を参考にして、
この人にとってのラッキーカラー、ラッキーアイテム、ラッキーナンバーを1行ずつ教えてください。

生年月日：{birthdate}
年齢：{age}歳

手相結果：
{palm_result}

四柱推命結果：
{shichu_result}

九星気学：
{kyusei_fortune}

・若者向けではなく、全年齢に自然に響く文体で。
・1項目につき1行、日本語で簡潔に出力してください。
・親しみやすく穏やかな口調で記述してください。
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ ラッキー情報取得エラー:", e)
        return "取得できませんでした。"



def generate_fortune(image_data, birthdate):
    palm_result = analyze_palm(image_data)
    shichu_result = get_shichu_fortune(birthdate)
    iching_result = get_iching_advice()

    # 年・月・日を分解
    year, month, day = map(int, birthdate.split("-"))
    from kyusei_utils import get_kyusei_fortune_openai
    kyusei_fortune = get_kyusei_fortune_openai(year, month, day)

    # すべての結果を元にラッキー情報生成
    lucky_info = get_lucky_info(birthdate, palm_result, shichu_result, kyusei_fortune)

    return palm_result, shichu_result, iching_result, lucky_info

