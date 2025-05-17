import openai
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tesou import tesou_names, tesou_descriptions
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from lucky_utils import generate_lucky_info, generate_lucky_direction
from yearly_love_fortune_utils import generate_yearly_love_fortune
from pdf_generator_unified import create_pdf_unified


def get_shichu_fortune(birthdate):
    eto = get_nicchu_eto(birthdate)
    try:
        today = datetime.today()
        this_year = today.year

        # 月の20日以降なら次月・再来月を占う
        target1 = today.replace(day=15)
        if today.day >= 20:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)

        tsuhen_year = get_tsuhensei_for_year(birthdate, this_year)
        tsuhen_month1 = get_tsuhensei_for_date(birthdate, target1.year, target1.month)
        tsuhen_month2 = get_tsuhensei_for_date(birthdate, target2.year, target2.month)

        prompt = f"""あなたは四柱推命の専門家です。
- 日柱: {eto}
- 年の通変星: {tsuhen_year}
- {target1.year}年{target1.month}月の通変星: {tsuhen_month1}
- {target2.year}年{target2.month}月の通変星: {tsuhen_month2}

以下の3つの項目について、それぞれ300文字以内で現実的に鑑定してください。
本文中に干支名や通変星の名前は書かず、内容に反映させてください。

■ 性格
■ {this_year}年の運勢
■ {target1.year}年{target1.month}月の運勢
■ {target2.year}年{target2.month}月の運勢

・優しい語り口で自然な文章にしてください。
・各項目はタイトルと本文を明確に区切ってください。
・読んでいて前向きになれるような文面にしてください。
"""

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.8
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print("❌ 四柱推命取得失敗:", e)
        return f"""■ 性格\n取得できませんでした\n■ {this_year}年の運勢\n取得できませんでした\n■ {target1.year}年{target1.month}月の運勢\n取得できませんでした\n■ {target2.year}年{target2.month}月の運勢\n取得できませんでした"""




def analyze_palm(image_data):
    try:
        # Data URL形式 or base64のみの両方に対応
        if "," in image_data:
            base64data = image_data.split(",", 1)[1]
        else:
            base64data = image_data

        # 除外線（基本3本＋感情線・頭脳線）
        excluded = {"生命線", "運命線", "金運線", "頭脳線", "感情線"}
        special_line_candidates = [name for name in tesou_names if name not in excluded]
        special_lines_text = "、".join(special_line_candidates)

        # 線の意味説明文を整形
        description_text = "\n".join(
            f"{name}：{tesou_descriptions[name]}"
            for name in tesou_names
            if name in tesou_descriptions
        )

        # システムプロンプト（AIの注意点）
        system_prompt = (
            "あなたはプロの手相鑑定士です。以下の条件に従って、手相画像から5つの線・相を選び、"
            "それぞれ意味と印象をわかりやすく説明してください。\n\n"
            "【出力構成】\n"
            "・1. 生命線、2. 運命線、3. 金運線は必ず含める\n"
            "・4. 特殊線1、5. 特殊線2は以下の中から目立つものを優先：\n"
            f"{special_lines_text}\n"
            "・目立つ特殊線が無ければ感情線や頭脳線で自然に補完してください\n\n"
            "【各線の意味ガイド】\n"
            f"{description_text}\n\n"
            "全体として、読み手が安心し前向きになれるよう、柔らかく肯定的な語り口でまとめてください。"
        )

        # ユーザープロンプト（出力フォーマット）
        user_prompt = (
            "以下の形式で出力してください：\n"
            "### 1. 生命線\n（説明文）\n\n"
            "### 2. 運命線\n（説明文）\n\n"
            "### 3. 金運線\n（説明文）\n\n"
            "### 4. 特殊線1\n（説明文）\n\n"
            "### 5. 特殊線2\n（説明文）\n\n"
            "### 総合的なアドバイス\n（全体のバランスを見たまとめ）\n\n"
            "・各項目は200文字前後で自然な文体に\n"
            "・“無い”と明記せず、手相全体の印象から前向きに解釈してください\n"
            "・読んだ人が『占ってよかった』と思えるような締めくくりを心がけてください"
        )

        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
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
            temperature=0.8,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print("❌ Vision APIエラー:", e)
        return "手相診断中にエラーが発生しました。"


def get_iching_advice():
    try:
        prompt = "あなたは易占いの専門家です。今の相談者に必要なメッセージを、200文字で優しく前向きに教えてください。"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 易占い取得失敗:", e)
        return "現在、易占いの結果が取得できませんでした。"


def get_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result, kyusei_text):
    prompt = f"""あなたは占いの専門家です。
相談者は現在{age}歳です。以下の鑑定結果を参考にしてください。

【手相】\n{palm_result}\n
【四柱推命】\n{shichu_result}\n
【九星気学の方位】\n{kyusei_text}

以下5つの項目を、すべて1行にまとめて簡潔に出力してください：

◆ アイテム：〇〇　　◆ カラー：〇〇　　◆ ナンバー：〇〇　　◆ フード：〇〇　　◆ デー：〇曜日

- 補足、理由、改行は一切禁止
- 各項目は短く（単語～数語）
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return [response["choices"][0]["message"]["content"].strip()]
    except Exception as e:
        print("❌ ラッキー情報取得失敗:", e)
        return ["◆ アイテム：ー　　◆ カラー：ー　　◆ ナンバー：ー　　◆ フード：ー　　◆ デー：ー"]



def generate_fortune(image_data, birthdate, kyusei_text):
    palm_result = analyze_palm(image_data)
    shichu_result_raw = get_shichu_fortune(birthdate)
    iching_result = get_iching_advice()
    age = datetime.today().year - int(birthdate[:4])
    nicchu_eto = get_nicchu_eto(birthdate)
    raw_lucky_info = generate_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result_raw, kyusei_text)

    # ✅ ラッキー情報整形（1行目から ◆で最大6項目）
    lucky_lines = []
    if isinstance(raw_lucky_info, list):
        raw_line = raw_lucky_info[0]
    elif isinstance(raw_lucky_info, str):
        raw_line = raw_lucky_info.strip().splitlines()[0]
    else:
        raw_line = ""
    if "◆" in raw_line:
        items = [item.strip() for item in raw_line.split("◆") if item.strip()]
        lucky_lines = [f"◆ {item}" for item in items]

    # ✅ 四柱推命の構造化（文字列から dict texts に変換）
    shichu_texts = {"personality": "", "year_fortune": "", "month_fortune": "", "next_month_fortune": ""}
    if isinstance(shichu_result_raw, dict) and "texts" in shichu_result_raw:
        shichu_texts = shichu_result_raw["texts"]
    else:
        parts = [p for p in str(shichu_result_raw).split("■ ") if p.strip()]
        for part in parts:
            if "\n" in part:
                title, body = part.split("\n", 1)
                title = title.strip()
                if "性格" in title:
                    shichu_texts["personality"] = body.strip()
                elif "今年" in title:
                    shichu_texts["year_fortune"] = body.strip()
                elif "今月" in title:
                    shichu_texts["month_fortune"] = body.strip()
                elif "来月" in title:
                    shichu_texts["next_month_fortune"] = body.strip()

    # ✅ palm_result を構造化
    palm_titles = []
    palm_texts = []
    for part in palm_result.split("### "):
        if part.strip():
            title, *body = part.strip().split("\n", 1)
            palm_titles.append(title.strip())
            palm_texts.append(body[0].strip() if body else "")

    return palm_titles, palm_texts, shichu_texts, iching_result, lucky_lines



def generate_renai_fortune(user_birth: str, partner_birth: str = None, include_yearly: bool = False, size: str = 'a4') -> dict:
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    import openai
    from lucky_utils import generate_lucky_renai_info, generate_lucky_direction
    from nicchu_utils import get_nicchu_eto
    from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
    from yearly_love_fortune_utils import generate_yearly_love_fortune

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
    iching_result = get_iching_advice()

    for topic in ["恋愛の障害と乗り越え方", "相手との距離感・深め方", "結婚"]:
        try:
            topic_prompt = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}"""
            if partner_eto:
                topic_prompt += f"\n- お相手の日柱: {partner_eto}"
            topic_prompt += f"""
- 易占いからの示唆：{iching_result}

以下の条件で「{topic}」についてアドバイスしてください：

・相談者の傾向（日柱）と、易の示唆を元にした、個別性の高い具体的な鑑定にする  
・200文字以内  
・現実的で誠実だが希望が持てる言葉で  
・一般論や抽象的な助言ではなく、読み手に刺さるような内容にする
"""

            topic_text = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": topic_prompt}],
                max_tokens=600,
                temperature=0.9
            ).choices[0].message.content.strip()

            topic_sections.append({"title": topic, "content": topic_text})
        except Exception as e:
            topic_sections.append({"title": topic, "content": f"（この項目の取得エラー: {e}）"})

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

    # 年齢・方位計算して恋愛用ラッキー情報生成
    try:
        birth_date_obj = datetime.strptime(user_birth, "%Y-%m-%d")
        age = datetime.today().year - birth_date_obj.year - ((datetime.today().month, datetime.today().day) < (birth_date_obj.month, birth_date_obj.day))
        kyusei_text = generate_lucky_direction(user_birth, datetime.today().date())
        lucky_info = generate_lucky_renai_info(user_eto, user_birth, age, year_love, kyusei_text)
    except Exception as e:
        print("❌ 恋愛ラッキー情報取得失敗:", e)
        lucky_info = []
        kyusei_text = ""

    return {
        "texts": {
            "compatibility": comp_text,
            "overall_love_fortune": "" if partner_birth else future_text,
            "year_love": year_love,
            "month_love": month_love,
            "next_month_love": next_month_love,
        },
        "titles": {
            "compatibility": "相性診断",
            "overall_love_fortune": "相手の気持ちと今後の展開" if partner_birth else "理想の相手像と出会いのチャンス",
            "year_love": f"{this_year}年の恋愛運",
            "month_love": f"{this_month}月の恋愛運",
            "next_month_love": f"{next_month}月の恋愛運",
        },
        "themes": topic_sections,
        "lucky_info": lucky_info,
        "lucky_direction": kyusei_text,
        "yearly_love_fortunes": yearly_love_fortunes
    }
