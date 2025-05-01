import openai, os
from datetime import datetime
from base64 import b64decode
from hayami_table_full_complete import hayami_table
from dateutil.relativedelta import relativedelta

openai.api_key = os.getenv("OPENAI_API_KEY")

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
    now = datetime.now()
    this_month = f"{now.year}年{now.month}月"
    next_month = f"{(now + relativedelta(months=1)).year}年{(now + relativedelta(months=1)).month}月"

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
        return "■ 性格\n取得できませんでした\n■ 今月の運勢\n取得できませんでした\n■ 来月の運勢\n取得できませんでした"

def generate_fortune(image_data, birthdate):
    palm_result = analyze_palm(image_data)
    shichu_result = get_shichu_fortune(birthdate)
    iching_result = get_iching_advice()
    year, month, day = map(int, birthdate.split("-"))
    kyusei_fortune = get_kyusei_fortune_openai(year, month, day)
    lucky_info = get_lucky_info(birthdate, palm_result, shichu_result, kyusei_fortune)
    return palm_result, shichu_result, iching_result, lucky_info
