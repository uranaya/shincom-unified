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




def get_shichu_fortune(birthdate, now=None, force_next_month: bool = False, style: str = 'normal', lang: str = 'ja'):
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

        # Build prompt by language / style
        style_note = ""
        if style == "tokyo":
            style_note = ("\nStyle: Use a bright, uplifting tone suitable for Tokyo/Asakusa visitors. "
                          "You may add one short, natural Asakusa-flavored phrase at most, and avoid excessive tourism talk.\n"
                          if lang == "en" else
                          "\n【スタイル】東京（浅草）向け：明るく前向きで、観光客にも自然に馴染む言葉選び。浅草要素は一言程度に留め、旅ガイド化しない。\n")

        if lang == "en":
            prompt = f"""You are a professional Four Pillars of Destiny (Shichu Suimei) consultant.
        Return ONLY valid JSON with exactly these keys:
        - personality
        - year_fortune
        - month_fortune
        - next_month_fortune

        Rules:
        - Write natural, customer-friendly English.
        - Do NOT mention the zodiac stem/branch name directly.
        - Avoid overly deterministic or scary wording; keep it constructive and actionable.
        - Keep each field to about 3-6 sentences.

        Birthdate: {birthdate}
        Target year/month: {target1.strftime('%Y-%m')} (month_fortune), next month is {target2.strftime('%Y-%m')}

        {style_note}
        """
        else:
            prompt = f"""あなたは四柱推命の専門家です。以下の情報をもとに、鑑定結果を **JSON形式のみ** で出力してください。
        キーは必ず次の4つのみ：
        - personality
        - year_fortune
        - month_fortune
        - next_month_fortune

        ルール：
        - 干支名（例：甲子など）を本文に表示しない
        - 脅す表現や断定的すぎる表現は避け、前向きで実用的に
        - 各項目は3〜6文程度で、読みやすく

        生年月日: {birthdate}
        対象年月: {target1.strftime('%Y-%m')}（今月運勢）, 来月: {target2.strftime('%Y-%m')}

        {style_note}
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




def generate_lucky_info_mixed(nicchu_eto: str, birthdate: str, age: int, palm_result: str, shichu_result: str, kyusei_text: str, now=None, lang: str = 'ja'):
    """
    九星の直接連想（紫/9/火曜…）を避け、数秘 + タロット + 易(八卦) + 色彩心理を混ぜて
    「◆ アイテム／カラー／ナンバー／フード／デー」を1行で返す（リスト1要素）。
    - GPT非依存
    - 誕生日 × 当年月で擬似ランダム
    - タロット/八卦の配列長差異（3/4/5要素）に強い
    """
    from datetime import datetime

    # ---- 1) 擬似ランダム seed（誕生日×当年当月で月替わり）----
    today = now or datetime.today()
    seed_base = f"{birthdate}-{today.year}-{today.month}"
    seed = int(hashlib.sha256(seed_base.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    # ---- 2) 数秘：ライフパス（1〜9）----
    def lifepath(date_str: str) -> int:
        digits = [int(ch) for ch in date_str if ch.isdigit()]
        s = sum(digits)
        while s > 9:
            s = sum(int(d) for d in str(s))
        return max(1, min(9, s))
    lp = lifepath(birthdate)  # 1..9

    # ---- 3) タロット（大アルカナ）一枚引き + 惑星/曜日 + 色ヒント ----
    # 惑星→曜日：Sun=日, Moon=月, Mars=火, Mercury=水, Jupiter=木, Venus=金, Saturn=土
    tarot_deck = [
        ("The Fool", "Uranus", "自由/風", ["白", "ライム", "ターコイズ"]),
        ("The Magician", "Mercury", "創造/知", ["黄", "ライトグレー", "シルバー"]),
        ("The High Priestess", "Moon", "直感/内省", ["群青", "オフホワイト", "パール"]),
        ("The Empress", "Venus", "実り/美", ["ピンク", "オリーブ", "アプリコット"]),
        ("The Emperor", "Mars", "意志/統率", ["赤", "黒", "ボルドー"]),
        ("The Hierophant", "Venus", "価値/伝統", ["ベージュ", "グリーン", "ココア"]),
        ("The Lovers", "Mercury", "選択/調和", ["ライトピンク", "ミント", "コーラル"]),
        ("The Chariot", "Moon", "前進/勝利", ["ネイビー", "ホワイト", "メタリック"]),
        ("Strength", "Sun", "勇気/自己肯定", ["ゴールド", "サンイエロー", "キャメル"]),
        ("The Hermit", "Mercury", "洞察/学び", ["チャコール", "カーキ", "ティール"]),
        ("Wheel of Fortune", "Jupiter", "転機/拡大", ["ロイヤルブルー", "サファイア", "群青"]),
        ("Justice", "Venus", "均衡/公正", ["エメラルド", "グレージュ", "ホワイト"]),
        ("The Hanged Man", "Neptune", "視点転換/献身", ["アクア", "ラベンダー", "スモーキーブルー"]),
        ("Death", "Mars", "刷新/再生", ["バーガンディ", "スレートグレー", "ダークグリーン"]),
        ("Temperance", "Jupiter", "調整/中庸", ["スカイブルー", "ペールオレンジ", "セージ"]),
        ("The Devil", "Saturn", "執着/制御", ["ダークブラウン", "グラファイト", "モスグリーン"]),
        ("The Tower", "Mars", "突破/再構成", ["クリムゾン", "チャコール", "アイアンブルー"]),
        ("The Star", "Saturn", "希望/透明感", ["アイスブルー", "シルバー", "パステル"]),
        ("The Moon", "Moon", "感受性/夢", ["パールホワイト", "ブルーグレー", "ミッドナイトブルー"]),
        ("The Sun", "Sun", "祝福/活力", ["サンフラワー", "オレンジ", "アンバー"]),
        ("Judgement", "Pluto", "覚醒/再起", ["ホワイト", "スカーレット", "スカイグレー"]),
        ("The World", "Saturn", "完成/統合", ["ピーコックグリーン", "ディープブルー", "サンド"])
    ]
    card = rng.choice(tarot_deck)
    # 3要素/4要素 どちらでも受ける
    if len(card) == 4:
        card_name, planet, _theme, card_color_candidates = card
    elif len(card) == 3:
        card_name, planet, card_color_candidates = card
    else:
        # フォールバック
        card_name, planet, card_color_candidates = ("The Sun", "Sun", ["サンフラワー", "オレンジ", "アンバー"])

    weekday_map = {
        "Sun": "日曜日", "Moon": "月曜日", "Mars": "火曜日",
        "Mercury": "水曜日", "Jupiter": "木曜日",
        "Venus": "金曜日", "Saturn": "土曜日",
        "Neptune": "木曜日", "Pluto": "土曜日", "Uranus": "水曜日"
    }
    tarot_weekday = weekday_map.get(planet, "金曜日")

    # ---- 4) 易（八卦）→ 色/食の傾向（4要素 or 5要素を許容）----
    # 4要素: (卦名, 性質, 五行, [色])
    # 5要素: (卦名, 性質, 五行, [色], [食])
    trigrams = [
        ("乾", "天", "金", ["白", "シルバー"], ["ナッツ", "白身魚", "大根"]),
        ("兌", "沢", "金", ["ミルキー", "ピンク"], ["乳製品", "ヨーグルト", "桃"]),
        ("離", "火", "火", ["オレンジ", "朱"], ["スパイス", "トマト", "唐辛子"]),
        ("震", "雷", "木", ["ライム", "若草"], ["香草", "枝豆", "青菜"]),
        ("巽", "風", "木", ["ミント", "ターコイズ"], ["ハーブティー", "緑茶", "きのこ"]),
        ("坎", "水", "水", ["青", "ネイビー"], ["海藻", "貝類", "寒天"]),
        ("艮", "山", "土", ["ベージュ", "オークル"], ["根菜", "芋", "味噌"]),
        ("坤", "地", "土", ["アース", "モカ"], ["穀類", "きなこ", "パン"])
    ]
    trig = rng.choice(trigrams)
    trig_foods_from_tuple = None
    if len(trig) >= 5:
        trig_name, trig_nature, wu_xing, trig_colors, trig_foods_from_tuple = trig[:5]
    elif len(trig) == 4:
        trig_name, trig_nature, wu_xing, trig_colors = trig
    else:
        trig_name, trig_nature, wu_xing, trig_colors = ("坤", "地", "土", ["アース", "モカ"])

    # ---- 5) アイテム候補（タロット傾向に応じた雑貨）----
    item_pool = {
        "The Magician": ["高機能ペン", "小型ガジェット", "カードケース"],
        "The High Priestess": ["ノート", "アロマストーン", "読書用しおり"],
        "The Empress": ["フラワー雑貨", "リップバーム", "ハンドクリーム"],
        "The Emperor": ["手帳カバー", "革財布", "名刺入れ"],
        "The Hierophant": ["万年筆", "御守り", "レザーしおり"],
        "The Lovers": ["ペアマグ", "ハートチャーム", "香水"],
        "The Chariot": ["スニーカー", "トラベルポーチ", "スポーツタオル"],
        "Strength": ["トレーニングバンド", "蜂蜜飴", "カフェタンブラー"],
        "The Hermit": ["読書灯", "ルーペ", "上質ノート"],
        "Wheel of Fortune": ["腕時計", "キーホルダー", "ラッキーチャーム"],
        "Justice": ["バランスボード", "スクエアトート", "スケール柄グッズ"],
        "The Hanged Man": ["アイピロー", "ストレッチポール", "アロマオイル"],
        "Death": ["断捨離ボックス", "新品タオル", "新しい歯ブラシ"],
        "Temperance": ["ブレンドティー", "保温ボトル", "整う入浴剤"],
        "The Devil": ["カカオ高配チョコ", "アロマキャンドル", "レザーブレス"],
        "The Tower": ["スマホ充電器", "耐衝撃ケース", "貼るカイロ"],
        "The Star": ["星座チャーム", "ミスト化粧水", "クリアポーチ"],
        "The Moon": ["アロマディフューザー", "ムーン雑貨", "柔軟剤"],
        "The Sun": ["サングラス", "ビタミンCタブレット", "明るいマグ"],
        "Judgement": ["ホイッスル", "目覚まし時計", "ホワイトノート"],
        "The World": ["地球柄ノート", "パスポートケース", "トラベルタグ"],
        "The Fool": ["小さなバックパック", "ピンバッジ", "スカーフ"]
    }
    item_candidates = item_pool.get(card_name, ["キーホルダー", "ノート", "トートバッグ"])
    item = rng.choice(item_candidates)

    # ---- 6) カラー：タロット候補 × 八卦候補 → 紫系を抑制して1つ ----
    color_candidates = list({*card_color_candidates, *trig_colors})
    filtered = [c for c in color_candidates if "紫" not in c and "パープル" not in c]
    color = rng.choice(filtered if filtered else color_candidates)

    # ---- 7) ナンバー：数秘ライフパス優先、9偏重回避 ----
    number = lp
    if number == 9 and rng.random() < 0.5:
        number = rng.choice([1,2,3,4,5,6,7,8])

    # ---- 8) フード：八卦タプルに食候補があれば優先、無ければ五行マップ ----
    if trig_foods_from_tuple:
        food = rng.choice(trig_foods_from_tuple)
    else:
        food_map = {
            "木": ["バジル", "ほうれん草", "枝豆", "抹茶", "グリーンスムージー"],
            "火": ["カレー", "トマトスープ", "唐辛子せんべい", "チリビーンズ", "生姜湯"],
            "土": ["さつまいも", "かぼちゃ", "雑穀ごはん", "味噌汁", "おにぎり"],
            "金": ["白身魚", "ヨーグルト", "梨", "ナッツ", "豆腐"],
            "水": ["わかめ", "しじみ汁", "寒天", "ところてん", "昆布だし"]
        }
        food = rng.choice(food_map.get(wu_xing, ["季節の果物", "ナッツ", "スープ"]))

    # ---- 9) デー（曜日）：タロットの惑星由来 ----
    day = tarot_weekday

    # ---- 10) 最終1行フォーマット ----
    line = f"◆ アイテム：{item}　　◆ カラー：{color}　　◆ ナンバー：{number}　　◆ フード：{food}　　◆ デー：{day}"
    return [line]





def generate_fortune(image_data, birthdate, kyusei_text, now=None, force_next_month: bool = False, style: str = 'normal', lang: str = 'ja'):
    import re
    palm_result = analyze_palm(image_data)
    shichu_result_raw = get_shichu_fortune(birthdate, now=now, force_next_month=force_next_month, style=style, lang=lang)
    iching_result = get_iching_advice()
    age = datetime.today().year - int(birthdate[:4])
    nicchu_eto = get_nicchu_eto(birthdate)
    raw_lucky_info = generate_lucky_info_mixed(nicchu_eto, birthdate, age, palm_result, str(shichu_result_raw), kyusei_text, now=now)


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
