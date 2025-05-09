import openai
import os
from datetime import datetime
from hayami_table_full_complete import hayami_table
from dateutil.relativedelta import relativedelta
from lucky_utils import generate_lucky_info, generate_lucky_direction
from yearly_love_fortune_utils import generate_yearly_love_fortune
from pdf_generator_unified import create_pdf_unified

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
                           selected_topics: list[str] = None, include_yearly: bool = False,
                           size: str = 'a4') -> str:
    """恋愛占い結果を生成し、PDFファイルとして保存する。保存先パスを返す。"""
    if selected_topics is None:
        selected_topics = []

    # 生年月日から日柱干支を取得
    user_eto = get_nicchu_eto(user_birth)
    partner_eto = get_nicchu_eto(partner_birth) if partner_birth else None

    # 1ページ目メイン占いテキスト生成
    try:
        if partner_eto:
            # お相手あり：相性・（お相手の気持ち＋今後）の2セクション生成
            prompt_comp = (
                "あなたは四柱推命に基づく恋愛占いの専門家です。\n"
                f"- あなたの日柱: {user_eto}\n"
                f"- お相手の日柱: {partner_eto}\n\n"
                "この2人の恋愛相性や関係性の特徴、注意点について、" 
                "現実的で温かい口調で400文字程度で教えてください。主語は「あなた」で記述してください。"
            )
            prompt_future = (
                "あなたは四柱推命に基づく恋愛占いの専門家です。\n"
                f"- あなたの日柱: {user_eto}\n"
                f"- お相手の日柱: {partner_eto}\n\n"
                "お相手の気持ちと今後の展開について、"
                "現実的で温かい口調で400文字程度で教えてください。主語は「あなた」で記述してください。"
            )
            # OpenAI API呼び出し（GPT-3.5-Turbo）
            comp_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_comp}],
                max_tokens=600,
                temperature=0.9
            )
            future_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_future}],
                max_tokens=600,
                temperature=0.9
            )
            comp_text = comp_response.choices[0].message.content.strip()
            future_text = future_response.choices[0].message.content.strip()
        else:
            # お相手なし：性格・恋愛傾向と理想の相手・出会いのチャンスの2セクション生成
            prompt_personality = (
                "あなたは四柱推命に基づく恋愛占いの専門家です。\n"
                f"- あなたの日柱: {user_eto}\n\n"
                "あなたの性格や恋愛傾向について、"
                "現実的で温かい口調で400文字程度で教えてください。主語は「あなた」で記述してください。"
            )
            prompt_ideal = (
                "あなたは四柱推命に基づく恋愛占いの専門家です。\n"
                f"- あなたの日柱: {user_eto}\n\n"
                "あなたにとっての理想の相手像と出会いのチャンスについて、"
                "現実的で温かい口調で400文字程度で教えてください。主語は「あなた」で記述してください。"
            )
            personality_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_personality}],
                max_tokens=600,
                temperature=0.9
            )
            ideal_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_ideal}],
                max_tokens=600,
                temperature=0.9
            )
            comp_text = personality_response.choices[0].message.content.strip()
            future_text = ideal_response.choices[0].message.content.strip()
    except Exception as e:
        # 万一APIエラーが発生した場合、エラーメッセージをテキストに設定
        error_msg = f"（エラーにより占い結果を取得できませんでした: {e}）"
        comp_text = error_msg
        future_text = ""

    # トピック別占い結果生成（選択された最大3項目）
    topic_sections = []  # [{ "title": タイトル, "content": テキスト }, ...]
    for topic in selected_topics[:3]:
        try:
            if topic == "相性":
                if partner_eto:
                    # お相手ありの相性（詳細解説やアドバイス）
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n"
                        f"- お相手の日柱: {partner_eto}\n\n"
                        "二人の相性についてさらに深く教えてください。"
                        "今後の付き合い方のアドバイスも含め、400文字程度でお願いします。"
                    )
                    title = "相性"
                else:
                    # お相手なしの相性（どんな人と相性が良いかなど）
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n\n"
                        "あなたに合う異性のタイプや、恋愛における相性の傾向について、"
                        "400文字程度で教えてください。"
                    )
                    title = "相性"
            elif topic == "進展":
                if partner_eto:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n"
                        f"- お相手の日柱: {partner_eto}\n\n"
                        "この二人の関係が今後進展する可能性について、"
                        "400文字程度で詳しく教えてください。"
                    )
                else:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n\n"
                        "今後あなたに訪れる恋愛の進展（新たな出会いや関係の深まり）の可能性について、"
                        "400文字程度で教えてください。"
                    )
                title = "今後の進展"
            elif topic == "復縁":
                if partner_eto:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n"
                        f"- お相手の日柱: {partner_eto}\n\n"
                        "一度離れたこの二人が復縁する可能性について、"
                        "現実的に占ってください。400文字程度でお願いします。"
                    )
                else:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n\n"
                        "過去の恋人との復縁の可能性について、"
                        "400文字程度で現実的に教えてください。"
                    )
                title = "復縁の可能性"
            elif topic == "出会い":
                if partner_eto:
                    # お相手がいる場合でも選択されたら一般論として回答
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n"
                        f"- お相手の日柱: {partner_eto}\n\n"
                        "今後新たな出会いが訪れるか、またそのタイミングについて、"
                        "400文字程度で教えてください。"
                    )
                else:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n\n"
                        "運命の人との出会いのタイミングや機会について、"
                        "400文字程度で具体的に教えてください。"
                    )
                title = "出会いのタイミング"
            elif topic == "結婚":
                if partner_eto:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n"
                        f"- お相手の日柱: {partner_eto}\n\n"
                        "この二人が将来結婚に至る可能性について、"
                        "400文字程度で教えてください。"
                    )
                else:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n\n"
                        "あなたの結婚運や将来結婚できる可能性について、"
                        "400文字程度で教えてください。"
                    )
                title = "結婚の可能性"
            elif topic == "注意点":
                if partner_eto:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n"
                        f"- お相手の日柱: {partner_eto}\n\n"
                        "二人の関係において注意すべき点や乗り越える課題について、"
                        "400文字程度でアドバイスしてください。"
                    )
                else:
                    prompt_topic = (
                        "あなたは恋愛占いの専門家です。\n"
                        f"- あなたの日柱: {user_eto}\n\n"
                        "あなたの恋愛において注意すべきポイントや気をつけるべきことを、"
                        "400文字程度で教えてください。"
                    )
                title = "注意すべき点"
            else:
                # 未知のトピックは無視
                continue

            topic_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_topic}],
                max_tokens=600,
                temperature=0.9
            )
            topic_text = topic_response.choices[0].message.content.strip()
        except Exception as e:
            topic_text = f"（この項目の占い結果を取得できませんでした: {e}）"
            title = topic  # そのまま

        topic_sections.append({"title": title, "content": topic_text})

    # 年運・月運（恋愛）データ生成
    yearly_fortunes = None
    if include_yearly:
        try:
            now = datetime.now()
            yearly_fortunes = generate_yearly_love_fortune(user_birth, now)
        except Exception as e:
            print(f"❌ 年運占いの取得に失敗しました: {e}")
            include_yearly = False  # エラー時は年運出力を無効化

    # ラッキー情報・吉方位取得
    try:
        lucky_info = generate_lucky_info(user_eto, user_birth)  # 5項目のリスト
    except Exception as e:
        lucky_info = []
        print(f"❌ ラッキー情報取得エラー: {e}")
    try:
        lucky_direction = generate_lucky_direction(user_birth, datetime.now().date())
    except Exception as e:
        lucky_direction = ""
        print(f"❌ 吉方位取得エラー: {e}")

    # PDF用データ組み立て
    data = {
        "palm_image": None,  # 恋愛占いでは手相画像は使用しない
        "titles": {},
        "texts": {},
        "lucky_info": lucky_info,
        "lucky_direction": lucky_direction,
        "themes": topic_sections,
        "yearly_fortunes": yearly_fortunes
    }
    if partner_eto:
        data["titles"]["compatibility"] = "お二人の相性"
        data["texts"]["compatibility"] = comp_text
        data["titles"]["feelings"] = "お相手の気持ち"
        data["texts"]["feelings"] = future_text.split("。", 1)[0] + "。" if future_text else ""
        data["titles"]["future"] = "今後の展開"
        # お相手の気持ちと今後の展開が一続きで出力された場合、2つに分割
        if "。" in future_text:
            data["texts"]["future"] = future_text.split("。", 1)[1].strip()
        else:
            data["texts"]["future"] = future_text
    else:
        data["titles"]["compatibility"] = "性格・恋愛傾向"
        data["texts"]["compatibility"] = comp_text
        data["titles"]["love_summary"] = "理想の相手と出会いのチャンス"
        data["texts"]["love_summary"] = future_text

    # PDF生成（A4/B4, レイアウトはshincom準拠）
    output_file = f"renai_fortune_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    create_pdf_unified(output_file, data, mode="renai", size=size, include_yearly=include_yearly)
    return output_file
