import openai
import os
import re
import hashlib, random
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tesou import tesou_names, tesou_descriptions
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from lucky_utils import generate_lucky_info, generate_lucky_direction
from yearly_love_fortune_utils import generate_yearly_love_fortune
from pdf_generator_unified import create_pdf_unified




def get_shichu_fortune(birthdate, now=None, force_next_month: bool = False):
    import json
    eto = get_nicchu_eto(birthdate)
    try:
        today = now or datetime.today()

        # ★ 20日境の基準月ロジック
        target1 = today.replace(day=15)
        if today.day >= 20 or force_next_month:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)

        # 「今年」は基準月の年に合わせる
        this_year = target1.year

        tsuhen_year = get_tsuhensei_for_year(birthdate, this_year)
        tsuhen_month1 = get_tsuhensei_for_date(birthdate, target1.year, target1.month)
        tsuhen_month2 = get_tsuhensei_for_date(birthdate, target2.year, target2.month)

        prompt = f"""あなたは四柱推命の専門家です。
- 日柱: {eto}
- 年の通変星: {tsuhen_year}
- {target1.year}年{target1.month}月の通変星: {tsuhen_month1}
- {target2.year}年{target2.month}月の通変星: {tsuhen_month2}

以下の4項目について、次のJSON形式で返答してください（出力はJSONのみ）：

{{
  "personality": "性格について300文字以内で自然な本文",
  "year_fortune": "{this_year}年の運勢（300文字以内）",
  "month_fortune": "{target1.year}年{target1.month}月の運勢（300文字以内）",
  "next_month_fortune": "{target2.year}年{target2.month}月の運勢（300文字以内）"
}}

出力は日本語で、本文中に干支・通変星名を含めず、前向きで柔らかい口調にしてください。
"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.8
        )

        raw = response.choices[0].message.content.strip()
        print("=== GPT四柱推命 JSONレスポンス ===")
        print(raw)

        try:
            result = json.loads(raw)
            # 月表記のズレ対策（GPTが本文先頭で別月を出すことがあるため矯正）
            import re
            def _fix_month_prefix(s, y, m):
                if not isinstance(s, str):
                    return s
                s = s.strip()
                s = re.sub(r"^\s*(?:\d{4}年\s*\d{1,2}月|今月|来月)\s*は\s*[、,]?\s*", "", s)
                if not s:
                    return f"{y}年{m}月は"
                return f"{y}年{m}月は、" + s

            if isinstance(result, dict):
                result["month_fortune"] = _fix_month_prefix(result.get("month_fortune", ""), target1.year, target1.month)
                result["next_month_fortune"] = _fix_month_prefix(result.get("next_month_fortune", ""), target2.year, target2.month)

            print("=== 四柱推命内容 ===")
            for k, v in result.items():
                print(f"{k}: {v[:50]}{'...' if len(v) > 50 else ''}")
            return result
        except json.JSONDecodeError:
            print("❌ GPTが正しいJSONを返しませんでした")
            return {
                "personality": "取得できませんでした",
                "year_fortune": f"{this_year}年の運勢は取得できませんでした",
                "month_fortune": f"{target1.year}年{target1.month}月の運勢は取得できませんでした",
                "next_month_fortune": f"{target2.year}年{target2.month}月の運勢は取得できませんでした"
            }
    except Exception as e:
        print("❌ get_shichu_fortune エラー:", e)
        return {
            "personality": "取得できませんでした",
            "year_fortune": "今年の運勢は取得できませんでした",
            "month_fortune": "今月の運勢は取得できませんでした",
            "next_month_fortune": "来月の運勢は取得できませんでした"
        }


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

        # 特殊線をより魅力的に出すようにした system_prompt（語り口・優先順位調整版）
        system_prompt = (
            "あなたはプロの手相鑑定士です。以下の条件に従って、手相画像から5つの線・相を選び、"
            "それぞれの意味と印象を、聞いた人が『ほう…！』と唸るような語り口で魅力的に解説してください。\n\n"
            "【出力構成】\n"
            "・1. 生命線、2. 運命線、3. 金運線は必ず含める\n"
            "・4. 特殊線1、5. 特殊線2は以下の中から“あると嬉しいもの”を優先して選ぶ：\n"
            f"{special_lines_text}\n"
            "・特殊線は、兆し・傾向レベルでもポジティブに採用して構いません\n"
            "・特に幸運・守護・才能・使命を感じさせる線を優先して選んでください\n"
            "・2つの特殊線がどうしても見つからない場合のみ、感情線や頭脳線などで自然に補ってください\n\n"
            "【各線の意味ガイド】\n"
            f"{description_text}\n\n"
            "全体を通して、読み手が安心し前向きになれるような、優しく包み込むような文体でまとめてください。"
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
            "・各項目は200文字前後で、やわらかく詩的で心に残る表現にしてください\n"
            "・“無い”や“不足”という否定的な表現は避け、可能性や伸びしろとして前向きに表現してください\n"
            "・心に灯をともすような、やさしく前向きな締めくくりで終えてください"
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




def generate_lucky_info_mixed(
    nicchu_eto: str,
    birthdate: str,
    age: int,
    palm_result: str,
    shichu_result: str,
    kyusei_text: str,
    now=None,
    lang: str = "ja",
):
    """
    GPT非依存の「ラッキー情報」を生成します。

    方針:
    - 日本語 / 英語の両対応（lang: 'ja' or 'en'）
    - PDFに収めやすいよう **最大2行** で返す（list[str]）
      * 1行目: Item / Color / Number
      * 2行目: Food / Day
    - 九星の文章(kyusei_text)は、日本語混入の主因になりやすいので
      lucky_info には含めず、別枠(lucky_direction 等)で表示する前提。
    """
    from datetime import datetime
    import hashlib

    today = now or datetime.today()
    seed_base = f"{birthdate}-{today.year}-{today.month}"
    seed = int(hashlib.sha256(seed_base.encode("utf-8")).hexdigest(), 16)

    def pick(arr):
        return arr[seed % len(arr)]

    items_ja = ["浄化用の小さな水晶", "アロマオイル（ラベンダー）", "白いハンカチ", "金色のチャーム", "小さなノート", "シンプルなリング"]
    items_en = ["a small cleansing crystal", "lavender aroma oil", "a white handkerchief", "a gold charm", "a small notebook", "a simple ring"]

    colors_ja = ["白", "金", "深い青", "若草色", "薄紫", "黒"]
    colors_en = ["white", "gold", "deep blue", "fresh green", "soft purple", "black"]

    foods_ja = ["ハーブティー", "柑橘", "温かいスープ", "ナッツ", "魚料理", "チョコレート（少量）"]
    foods_en = ["herbal tea", "citrus", "warm soup", "nuts", "fish dish", "a small piece of chocolate"]

    days_ja = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
    days_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    item = pick(items_en if lang == "en" else items_ja)
    color = pick(colors_en if lang == "en" else colors_ja)
    number = (seed % 9) + 1
    food = pick(foods_en if lang == "en" else foods_ja)
    day = (days_en if lang == "en" else days_ja)[seed % 7]

    if lang == "en":
        line1 = f"Item: {item}   Color: {color}   Number: {number}"
        line2 = f"Food: {food}   Day: {day}"
    else:
        line1 = f"◆ アイテム：{item}　◆ カラー：{color}　◆ ナンバー：{number}"
        line2 = f"◆ フード：{food}　◆ デー：{day}"

    return [line1, line2]


def generate_fortune(image_data, birthdate, kyusei_text, now=None, force_next_month: bool = False, lang: str = 'ja'):
    import re
    palm_result = analyze_palm(image_data)
    shichu_result_raw = get_shichu_fortune(birthdate, now=now, force_next_month=force_next_month)
    iching_result = get_iching_advice()
    age = datetime.today().year - int(birthdate[:4])
    nicchu_eto = get_nicchu_eto(birthdate)
    raw_lucky_info = generate_lucky_info_mixed(nicchu_eto, birthdate, age, palm_result, str(shichu_result_raw), kyusei_text, now=now, lang=lang)


    lucky_lines = []
    try:
        if isinstance(raw_lucky_info, list):
            raw_line = raw_lucky_info[0]
        elif isinstance(raw_lucky_info, str):
            raw_line = raw_lucky_info.strip().splitlines()[0]
        else:
            raw_line = ""
        if "◆" in raw_line:
            items = [item.strip() for item in raw_line.split("◆") if item.strip()]
            lucky_lines = [f"◆ {item}" for item in items]
    except Exception as e:
        print("❌ lucky_info 整形失敗:", e)
        lucky_lines = []

    today = now or datetime.today()
    target1 = today.replace(day=15)
    if today.day >= 20 or force_next_month:
        target1 += relativedelta(months=1)
    target2 = target1 + relativedelta(months=1)
    month_label = f"{target1.year}年{target1.month}月の運勢"
    next_month_label = f"{target2.year}年{target2.month}月の運勢"

    shichu_texts = {"personality": "", "year_fortune": "", "month_fortune": "", "next_month_fortune": ""}
    pattern = r"[■◆]\s*(性格|[0-9]{4}年の運勢|[0-9]{4}年[0-9]{1,2}月の運勢)(.*?)(?=[■◆]|$)"
    matches = re.findall(pattern, str(shichu_result_raw), flags=re.DOTALL)
    for title, body in matches:
        title = title.strip()
        body = body.strip()
        if "性格" in title:
            shichu_texts["personality"] = body
        elif title == month_label:
            shichu_texts["month_fortune"] = body
        elif title == next_month_label:
            shichu_texts["next_month_fortune"] = body
        elif "年" in title and "運勢" in title:
            shichu_texts["year_fortune"] = body

    palm_titles = []
    palm_texts = []
    for part in palm_result.split("### "):
        if part.strip():
            title, *body = part.strip().split("\n", 1)
            palm_titles.append(title.strip())
            palm_texts.append(body[0].strip() if body else "")

    return palm_titles, palm_texts, shichu_result_raw, iching_result, lucky_lines




def generate_renai_fortune(user_birth: str, partner_birth: str = None, include_yearly: bool = False, size: str = 'a4') -> dict:
    """
    恋愛版：相性・今年/今月/来月の恋愛運・テーマ別アドバイス・ラッキー情報・年運12ヶ月をまとめて生成する。
    ・20日境で「今月/来月」「今年」を決定
    ・通変星は tsuhensei_utils の get_tsuhensei_for_year / get_tsuhensei_for_date を使用
    ・年運12ヶ月は base（月盤基準）から12ヶ月分
    """
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    import openai
    from lucky_utils import generate_lucky_renai_info, generate_lucky_direction
    from nicchu_utils import get_nicchu_eto
    from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
    from yearly_love_fortune_utils import generate_yearly_love_fortune

    # 日柱
    user_eto = get_nicchu_eto(user_birth)

    # partner_birth が未入力や不正な場合に備える
    partner_eto = None
    if partner_birth:
        try:
            partner_eto = get_nicchu_eto(partner_birth)
        except Exception as e:
            print("⚠ partner_eto 計算エラー:", e)
            partner_eto = None

    # =========================
    # 1. 相性／総合恋愛運テキスト
    # =========================
    try:
        if partner_eto:
            # お相手がいる場合：相性 ＋ 相手の気持ちと今後の展開
            prompt_comp = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}
- お相手の日柱: {partner_eto}

二人の性格的な相性と、関係を良くするためのポイントを、
200文字でやさしく、具体的に教えてください。"""

            prompt_future = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}
- お相手の日柱: {partner_eto}

お相手の今の気持ちと、この先3か月ほどの関係の流れについて、
200文字で具体的に教えてください。"""
        else:
            # お相手がいない場合：あなたの恋愛傾向 ＋ 理想の相手像と出会いのチャンス
            prompt_comp = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}

あなたの恋愛傾向・魅力・パートナーシップの癖について、
200文字でやさしく、前向きに教えてください。"""

            prompt_future = f"""あなたは恋愛占いの専門家です。
- あなたの日柱: {user_eto}

理想の相手像と、今後1年の出会いのチャンスについて、
200文字で具体的に教えてください。"""

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
        print("❌ 相性・総合恋愛運取得エラー:", e)
        comp_text = f"（相性・性格占い取得エラー: {e}）"
        future_text = ""

    # =========================
    # 2. テーマ別アドバイス（3項目：注意点・復縁・結婚）
    # =========================
    from_section_topics = ["恋愛の注意点", "復縁のヒント", "結婚について"]

    topic_sections = []
    try:
        iching_result = get_iching_advice()
    except Exception as e:
        print("⚠ 易占い取得エラー（テーマ用）:", e)
        iching_result = "（易占い結果取得エラー）"

    for topic in from_section_topics:
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
            topic_sections.append(
                {"title": topic, "content": f"（この項目の取得エラー: {e}）"}
            )

    # =========================
    # 3. 今年／今月／来月（20日境で base を決定）
    # =========================
    try:
        today = datetime.today()

        # 20日境で基準月 base を決める
        base = today.replace(day=15)
        if today.day >= 20:
            base += relativedelta(months=1)

        this_year = base.year      # 「今年」は base の年
        this_month = base.month    # 「今月」は base の月

        # 来月（基準月の翌月）
        next_base = base + relativedelta(months=1)
        next_year = next_base.year
        next_month = next_base.month

        # 通変星
        tsuhen_year = get_tsuhensei_for_year(user_birth, this_year)
        tsuhen_month = get_tsuhensei_for_date(user_birth, this_year, this_month)
        tsuhen_next_month = get_tsuhensei_for_date(user_birth, next_year, next_month)

        # 今年の恋愛運
        prompt_year = f"""あなたは四柱推命の専門家です。
- 日柱: {user_eto}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_month}
今年（{this_year}年）の恋愛運について、出会いや進展、距離の縮まり方などに触れて
200文字でやさしく教えてください。主語は「あなた」。"""

        # 今月の恋愛運
        prompt_month = f"""あなたは四柱推命の専門家です。
- 日柱: {user_eto}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_month}
今月（{this_month}月）の恋愛運を150文字でやさしく教えてください。"""

        # 来月の恋愛運
        prompt_next = f"""あなたは四柱推命の専門家です。
- 日柱: {user_eto}
- 年の通変星: {tsuhen_year}
- 月の通変星: {tsuhen_next_month}
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
        print("❌ 恋愛運（今年・今月・来月）取得エラー:", e)
        year_love = month_love = next_month_love = f"（恋愛運取得エラー: {e}）"
        # タイトル生成用に最低限 base を再計算
        today = datetime.today()
        base = today.replace(day=15)
        if today.day >= 20:
            base += relativedelta(months=1)
        this_year = base.year
        this_month = base.month
        next_base = base + relativedelta(months=1)
        next_year = next_base.year
        next_month = next_base.month

    # =========================
    # 4. 年運 12 ヶ月（include_yearly=True のとき）
    # =========================
    yearly_love_fortunes = {}
    if include_yearly:
        try:
            # 今年／今月と同じ基準 base から 12 ヶ月分を生成
            yearly_love_fortunes = generate_yearly_love_fortune(user_birth, base)
            print("✅ 年運データ取得:", yearly_love_fortunes)
        except Exception as e:
            print(f"❌ 年運取得失敗: {e}")
            yearly_love_fortunes = {}

    # =========================
    # 5. 恋愛版ラッキー情報＆吉方位
    # =========================
    try:
        birth_date_obj = datetime.strptime(user_birth, "%Y-%m-%d")
        # 年齢も base 時点で計算（誕生日を迎えているかどうか）
        age = base.year - birth_date_obj.year - (
            (base.month, base.day) < (birth_date_obj.month, birth_date_obj.day)
        )

        # 吉方位テキスト（九星気学ベース）
        kyusei_text = generate_lucky_direction(user_birth, base.date())

        # ラッキー情報（恋愛版）
        lucky_info = generate_lucky_renai_info(
            user_eto, user_birth, age, year_love, kyusei_text
        )
    except Exception as e:
        print("❌ 恋愛ラッキー情報取得失敗:", e)
        lucky_info = []
        kyusei_text = ""

    # =========================
    # 6. まとめて返却
    # =========================
    return {
        "texts": {
            "compatibility": comp_text,
            # partner_eto の有無でタイトルだけ変える。中身は future_text を常に返す。
            "overall_love_fortune": future_text,
            "year_love": year_love,
            "month_love": month_love,
            "next_month_love": next_month_love,
        },
        "titles": {
            "compatibility": "相性診断",
            "overall_love_fortune": (
                "相手の気持ちと今後の展開"
                if partner_eto
                else "理想の相手像と出会いのチャンス"
            ),
            "year_love": f"{this_year}年の恋愛運",
            "month_love": f"{this_month}月の恋愛運",
            "next_month_love": f"{next_month}月の恋愛運",
        },
        "themes": topic_sections,
        "lucky_info": lucky_info,
        "lucky_direction": kyusei_text,
        "yearly_love_fortunes": yearly_love_fortunes,
    }
