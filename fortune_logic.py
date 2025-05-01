import openai
import json

openai.api_key = os.getenv("OPENAI_API_KEY")

def ask_openai(prompt, max_tokens=800):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ OpenAIエラー:", e)
        return "取得できませんでした"

def analyze_palm(image_data):
    prompt = "手相画像から特徴的な線を3つ挙げて、優しくわかりやすく解説してください。"
    return ask_openai(prompt, max_tokens=600)

def get_shichu_fortune(eto):
    prompt = f"""
あなたは四柱推命の専門家です。
日柱が「{eto}」の人の特徴的な性格と、今月・来月の運勢をわかりやすく優しく300文字以内ずつで3項目に分けて解説してください。
結果は以下の形式で出力してください：

■ 性格  
...  
■ 今月の運勢  
...  
■ 来月の運勢  
...
""".strip()
    return ask_openai(prompt, max_tokens=900)

def get_iching_advice():
    prompt = """
あなたは易占いの専門家です。
今の相談者にとって必要なメッセージを、占い結果として優しく300文字程度で伝えてください。
卦名や専門用語の使用は避け、日常に寄り添う表現でお願いします。
""".strip()
    return ask_openai(prompt, max_tokens=600)

def get_lucky_info():
    prompt = """
あなたは開運アドバイザーです。
今日の相談者のラッキーカラー、ラッキーアイテム、ラッキーナンバーを1つずつ提案してください。
理由や前置きは不要です。以下のように箇条書きで出力してください：

ラッキーカラー：●●  
ラッキーアイテム：●●  
ラッキーナンバー：●●
""".strip()
    return ask_openai(prompt, max_tokens=300)

def generate_fortune(image_data, birthdate):
    try:
        eto = os.getenv("NICHUU_ETO", "不明")
        palm_result = analyze_palm(image_data)
        shichu_result = get_shichu_fortune(eto)
        iching_result = get_iching_advice()
        lucky_info = get_lucky_info()
        return palm_result, shichu_result, iching_result, lucky_info
    except Exception as e:
        print("❌ generate_fortune エラー:", e)
        return "", "", "", ""
