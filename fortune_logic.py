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
                                "### 2. 運命線\n（説明文）\n\n"
                                "### 3. 金運線\n（説明文）\n\n"
                                "### 4. 特殊線1\n（目立つ個性的な線があれば記載。なければ感情線などで補完）\n\n"
                                "### 5. 特殊線2\n（さらに目立つ個性的な線があれば記載。なければ頭脳線などで補完）\n\n"
                                "### 総合的なアドバイス\n（全体を踏まえたまとめ）\n\n"
                                "・各項目は200文字前後で\n"
                                "・読み手が楽しく前向きな気持ちになれるような、温かく優しい語り口で\n"
                                "・改行や記号などで各項目が明確に区切られるようにしてください\n"
                                "・特徴的な線が見られなかった場合でも“無い”とは書かず、全体の印象やバランスからポジティブな要素を自然に伝えてください\n"
                                "・読み手に「占ってもらってよかった」と思ってもらえるように、1つでも印象に残るようなコメントを入れてください\n"
                                "・もし金運に関連する良い線（財運線、太陽線、スター、覇王線、フィッシュなど）が見られた場合は、優先的に金運についてもポジティブなコメントを入れてください。\n"
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



def generate_renai_fortune(user_birth: str, partner_birth: str = None, include_yearly: bool = False, size: str = 'a4') -> dict:
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    import openai
    from lucky_utils import generate_lucky_info, generate_lucky_direction
    from yearly_love_fortune_utils import generate_yearly_love_fortune
    from nicchu_utils import get_nicchu_eto
    from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date

    user_eto = get_nicchu_eto(user_birth)
    partner_eto = get_nicchu_eto(partner_birth) if partner_birth else None

    try:
        if partner_eto:
            prompt_comp = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}
- お相手の日柱: {partner_eto}

この2人の恋愛相性や関係性の特徴、注意点について、200文字で教えてください。"""
            prompt_future = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}
- お相手の日柱: {partner_eto}

お相手の気持ちと今後の展開について、200文字で教えてください。"""
        else:
            prompt_comp = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}

あなたの性格や恋愛傾向について、200文字で教えてください。"""
            prompt_future = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}

理想の相手像と出会いのチャンスについて、200文字で教えてください。"""

        comp_text = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_comp}],
            max_tokens=400,
            temperature=0.9
        ).choices[0].message.content.strip()

        future_text = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_future}],
            max_tokens=400,
            temperature=0.9
        ).choices[0].message.content.strip()
    except Exception as e:
        comp_text = f"（相性・性格占い取得エラー: {e}）"
        future_text = ""

    topic_sections = []
    for topic in ["注意点", "復縁", "結婚"]:
        try:
            topic_prompt = f"あなたは恋愛占いの専門家です。\n- あなたの日柱: {user_eto}\n"
            if partner_eto:
                topic_prompt += f"- お相手の日柱: {partner_eto}\n"
            topic_prompt += f"{topic}について200文字で教えてください。"

            topic_text = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": topic_prompt}],
                max_tokens=600,
                temperature=0.9
            ).choices[0].message.content.strip()

            topic_sections.append({"title": topic, "content": topic_text})
        except Exception as e:
            topic_sections.append({"title": topic, "content": f"（この項目の取得エラー: {e}）"})

    # 通変星付きの今年・今月・来月の恋愛運
    try:
        today = datetime.today()
        this_year = today.year
        this_month = today.month
        next_month_date = today.replace(day=15) + relativedelta(months=1)
        next_month = next_month_date.month
        next_year = next_month_date.year

        tsuhen_year = get_tsuhensei_for_year(user_birth, this_year)
        tsuhen_month = get_tsuhensei_for_date(user_birth, this_year, this_month)
        tsuhen_next = get_tsuhensei_for_date(user_birth, next_year, next_month)

        # プロンプト構成（四柱推命＋通変星あり）
        prompt_year = f"""あなたは四柱推命の専門家です。
- 日柱: {user_eto}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_month}
今年（{this_year}年）の恋愛運について、出会いや進展、距離の縮まり方などに触れて200文字でやさしく教えてください。主語は「あなた」。"""

        prompt_month = f"""あなたは四柱推命の専門家です。
- 日柱: {user_eto}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_month}
今月（{this_month}月）の恋愛運を150文字でやさしく教えてください。"""

        prompt_next = f"""あなたは四柱推命の専門家です。
- 日柱: {user_eto}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_next}
来月（{next_month}月）の恋愛運を150文字でやさしく教えてください。"""

        year_love = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_year}],
            max_tokens=400
        ).choices[0].message.content.strip()

        month_love = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_month}],
            max_tokens=400
        ).choices[0].message.content.strip()

        next_month_love = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_next}],
            max_tokens=400
        ).choices[0].message.content.strip()
    except Exception as e:
        year_love = month_love = next_month_love = f"（恋愛運取得エラー: {e}）"

    yearly_love_fortunes = {}
    if include_yearly:
        try:
            yearly_love_fortunes = generate_yearly_love_fortune(user_birth, datetime.now())
            print("✅ 年運データ取得:", yearly_love_fortunes)
        except Exception as e:
            print(f"❌ 年運取得失敗: {e}")

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
        "year_love": year_love,
        "month_love": month_love,
        "next_month_love": next_month_love,
        "lucky_info": lucky_info,
        "lucky_direction": lucky_direction,
        "yearly_love_fortunes": yearly_love_fortunes
    }
