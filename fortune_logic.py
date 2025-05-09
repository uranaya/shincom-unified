import openai
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from nicchu_utils import get_nicchu_eto
from lucky_utils import generate_lucky_info, generate_lucky_direction
from yearly_love_fortune_utils import generate_yearly_love_fortune
from pdf_generator_unified import create_pdf_unified


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
        response = openai.ChatCompletion.create(
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
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 易占い取得エラー:", e)
        return "取得できませんでした。"

def get_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result, kyusei_text):
    prompt = f"""あなたは占いの専門家です。
相談者は現在{age}歳です。以下の3つの鑑定結果を参考にしてください。

【手相】\n{palm_result}\n
【四柱推命】\n{shichu_result}\n
【九星気学の方位】\n{kyusei_text}

この内容を元に、相談者にとって今最も運気を高めるための
ラッキーアイテム・ラッキーカラー・ラッキーナンバー・ラッキーフード・ラッキーデー
をそれぞれ1つずつ、以下の形式で提案してください：

・ラッキーアイテム：〇〇
・ラッキーカラー：〇〇
・ラッキーナンバー：〇〇
・ラッキーフード：〇〇
・ラッキーデー：〇曜日

自然で前向きな言葉で書いてください。"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response["choices"][0]["message"]["content"].splitlines()
    except Exception as e:
        print("❌ ラッキー情報取得失敗:", e)
        return ["取得できませんでした。"]

def analyze_palm(image_data):
    try:
        base64data = image_data.split(",", 1)[1]
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはプロの手相鑑定士です。以下の条件に従い、特殊線を優先的にピックアップし、金運に関する要素があれば優先的に言及し、なければ無理に言及しないようにしてください。全体として相談者の魅力を引き出す自然な文章で出力してください。"
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
                                "・各項目は200文字前後で\n"
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

def generate_fortune(image_data, birthdate, kyusei_text):
    palm_result = analyze_palm(image_data)
    shichu_result = get_shichu_fortune(birthdate)
    iching_result = get_iching_advice()
    age = datetime.today().year - int(birthdate[:4])
    nicchu_eto = get_nicchu_eto(birthdate)
    lucky_info = get_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result, kyusei_text)
    return palm_result, shichu_result, iching_result, lucky_info


def generate_renai_fortune(user_birth: str, partner_birth: str = None,
                           include_yearly: bool = False, size: str = 'a4') -> dict:
    from datetime import datetime
    from lucky_utils import generate_lucky_info, generate_lucky_direction
    from yearly_love_fortune_utils import generate_yearly_love_fortune

    user_eto = get_nicchu_eto(user_birth)
    partner_eto = get_nicchu_eto(partner_birth) if partner_birth else None

    try:
        if partner_eto:
            prompt_comp = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}
- お相手の日柱: {partner_eto}

この2人の恋愛相性や関係性の特徴、注意点について、現実的で温かい口調で200文字程度で教えてください。主語は「あなた」で記述してください。"""
            prompt_future = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}
- お相手の日柱: {partner_eto}

お相手の気持ちと今後の展開について、現実的で温かい口調で100文字程度で教えてください。主語は「あなた」で記述してください。"""
        else:
            prompt_comp = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}

あなたの性格や恋愛傾向について、現実的で温かい口調で100文字程度で教えてください。主語は「あなた」で記述してください。"""
            prompt_future = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}

あなたにとっての理想の相手像と出会いのチャンスについて、現実的で温かい口調で400文字程度で教えてください。主語は「あなた」で記述してください。"""

        comp_text = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_comp}],
            max_tokens=600,
            temperature=0.9
        ).choices[0].message.content.strip()

        future_text = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_future}],
            max_tokens=600,
            temperature=0.9
        ).choices[0].message.content.strip()
    except Exception as e:
        comp_text = f"（相性・性格占い取得エラー: {e}）"
        future_text = ""

    # トピック固定3項目：「注意点」「復縁」「結婚」
    fixed_topics = ["注意点", "復縁", "結婚"]
    topic_sections = []

    for topic in fixed_topics:
        try:
            if topic == "注意点":
                prompt_topic = (
                    f"あなたは恋愛占いの専門家です。\n"
                    f"- あなたの日柱: {user_eto}\n" +
                    (f"- お相手の日柱: {partner_eto}\n" if partner_eto else "") +
                    "恋愛において注意すべき点や気をつけるべきことについて、200文字程度で優しくアドバイスしてください。"
                )
            elif topic == "復縁":
                prompt_topic = (
                    f"あなたは恋愛占いの専門家です。\n"
                    f"- あなたの日柱: {user_eto}\n" +
                    (f"- お相手の日柱: {partner_eto}\n" if partner_eto else "") +
                    "復縁の可能性やそのために必要なことについて、200文字程度で教えてください。"
                )
            elif topic == "結婚":
                prompt_topic = (
                    f"あなたは恋愛占いの専門家です。\n"
                    f"- あなたの日柱: {user_eto}\n" +
                    (f"- お相手の日柱: {partner_eto}\n" if partner_eto else "") +
                    "将来の結婚の可能性や良いタイミングについて、200文字程度で教えてください。"
                )
            else:
                continue

            topic_text = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_topic}],
                max_tokens=600,
                temperature=0.9
            ).choices[0].message.content.strip()

            topic_sections.append({"title": topic, "content": topic_text})

        except Exception as e:
            topic_sections.append({"title": topic, "content": f"（この項目の取得エラー: {e}）"})

    # 年運
    yearly_fortunes = {}
    if include_yearly:
        try:
            yearly_fortunes = generate_yearly_love_fortune(user_birth, datetime.now())
        except Exception as e:
            print(f"年運取得失敗: {e}")

    # ラッキー情報・吉方位
    try:
        lucky_info = generate_lucky_info(user_eto, user_birth)
    except:
        lucky_info = []
    try:
        lucky_direction = generate_lucky_direction(user_birth, datetime.now().date())
    except:
        lucky_direction = ""

    return {
        "compatibility_text": comp_text,
        "overall_love_fortune": "" if partner_birth else future_text,
        "topic_fortunes": topic_sections,
        "lucky_info": lucky_info,
        "lucky_direction": lucky_direction,
        "yearly_love_fortunes": yearly_fortunes
    }
