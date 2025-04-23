import openai
from datetime import datetime

def get_lucky_info(birthdate, palm_result, shichu_result, kyusei_fortune):
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
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ ラッキー情報取得エラー:", e)
        return "取得できませんでした。"

def generate_fortune(image_data, birthdate):
    from vision_palm import analyze_palm
    from shichu_utils import get_shichu_fortune
    from kyusei_utils import get_kyusei_fortune_openai

    palm_result = analyze_palm(image_data)
    shichu_result = get_shichu_fortune(birthdate)

    year, month, day = map(int, birthdate.split("-"))
    kyusei_fortune = get_kyusei_fortune_openai(year, month, day)

    lucky_info = get_lucky_info(birthdate, palm_result, shichu_result, kyusei_fortune)

    return palm_result, shichu_result, kyusei_fortune, lucky_info