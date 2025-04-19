import openai
from datetime import datetime
from hayami_table_full_complete import hayami_table

stems = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
branches = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

def get_nicchu_eto(birthdate):
    try:
        date_obj = datetime.strptime(birthdate, "%Y-%m-%d")
        year, month, day = date_obj.year, date_obj.month, date_obj.day
        if year not in hayami_table or month < 1 or month > 12:
            return "不明"
        base = hayami_table[year][month - 1]
        index = base + day - 1
        index %= 60
        eto = stems[index % 10] + branches[index % 12]
        return eto
    except Exception as e:
        print("❌ 日柱計算エラー:", e)
        return "不明"

def get_shichu_fortune(birthdate):
    eto = get_nicchu_eto(birthdate)
    prompt = f"""以下の条件に従って、日柱が『{eto}』の人の四柱推命鑑定結果を作成してください。

■ 性格
■ 今月の運勢
■ 来月の運勢

※文章中に干支の表記は不要です。
※親しみやすい現実的な日本語で、それぞれ300文字程度で簡潔に書いてください。"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content.strip()
        if "■ 今月の運勢" in result and "■ 来月の運勢" in result:
            return result
        else:
            raise ValueError("■ 区切りのあるフォーマットで出力されませんでした")
    except Exception as e:
        print("❌ 四柱推命取得失敗:", e)
        return "■ 性格\n取得できませんでした\n\n■ 今月の運勢\n取得できませんでした\n\n■ 来月の運勢\n取得できませんでした"

def get_iching_advice():
    prompt = "イーチン占いによる現実的なアドバイスを、日本語で300文字程度で、親しみやすく簡潔に書いてください。"
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 易占い取得エラー:", e)
        return "イーチン占いの取得に失敗しました。"

def get_lucky_info(birthdate):
    prompt = f"生年月日が{birthdate}の人にとって、ラッキーカラー、ラッキーアイテム、ラッキーナンバーを1行ずつ日本語で簡潔に教えてください。"
    try:
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ ラッキー情報取得エラー:", e)
        return "ラッキー情報の取得に失敗しました。"


def analyze_palm(image_data):
    try:
        base64data = image_data.split(",", 1)[1]
        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "あなたはプロの手相鑑定士です。以下の条件で手相を鑑定してください。1) 特徴的な線（特殊線含む）を優先的に含めること。2) 各項目400文字程度の解説を5項目書くこと。3) 最後にまとめのアドバイスを加えること。日本語でわかりやすく書いてください。"},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64data}"}}
                ]}
            ],
            max_tokens=3000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Vision APIエラー:", e)
        return "手相診断中にエラーが発生しました。"
