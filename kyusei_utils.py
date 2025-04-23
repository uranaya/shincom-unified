from datetime import datetime
import openai

NINE_STARS = [
    "一白水星", "二黒土星", "三碧木星",
    "四緑木星", "五黄土星", "六白金星",
    "七赤金星", "八白土星", "九紫火星"
]

def get_honmeisei(year: int, month: int, day: int) -> str:
    if (month < 2) or (month == 2 and day <= 3):
        year -= 1
    kyusei_num = (11 - (year % 9)) % 9
    kyusei_num = 9 if kyusei_num == 0 else kyusei_num
    return NINE_STARS[kyusei_num - 1]

def get_kyusei_fortune_openai(year: int, month: int, day: int) -> str:
    honmei = get_honmeisei(year, month, day)
    now = datetime.now()
    now_str = f"{now.year}年{now.month}月"
    next_month = now.replace(day=1).replace(month=now.month % 12 + 1)
    next_str = f"{next_month.year}年{next_month.month}月"

    prompt = f"""あなたはプロの九星気学占い師です。
本命星が「{honmei}」の人に対して、以下の項目に答えてください。

■ {now_str}の吉方位と凶方位
■ {next_str}の吉方位と凶方位

・各月ごとに1文ずつで簡潔に述べてください。
・方位は「北」「北東」「東」「南東」「南」「南西」「西」「北西」など、わかりやすく記述してください。
・本文中に「{honmei}」という星名は使っても使わなくても構いませんが、読みやすい自然な口調で書いてください。
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ OpenAIによる九星方位占断失敗:", e)
        return f"{now_str}と{next_str}の吉方位を取得できませんでした。"