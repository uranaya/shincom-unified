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






def get_shichu_fortune(birthdate, now=None, force_next_month: bool = False, lang: str = 'ja'):
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

        if (lang or 'ja').lower().startswith('en'):
            prompt = f"""You are a Four Pillars (BaZi) reading advisor.
- Day pillar (eto): {eto}
- Ten-God for the year: {tsuhen_year}
- Ten-God for {target1.year}-{target1.month:02d}: {tsuhen_month1}
- Ten-God for {target2.year}-{target2.month:02d}: {tsuhen_month2}

Return ONLY JSON in the following schema:
{{
  "personality": "A natural English paragraph (max ~900 characters, not words)",
  "year_fortune": "Fortune overview for {this_year} (max ~900 characters)",
  "month_fortune": "Fortune for {target1.year}-{target1.month:02d} (max ~900 characters)",
  "next_month_fortune": "Fortune for {target2.year}-{target2.month:02d} (max ~900 characters)"
}}

Rules:
- Do NOT mention eto names or Ten-God terms; translate meanings into plain English
- Positive, practical, and customer-friendly
"""
        else:
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
        # OpenAI呼び出し（たまに502等が出るためリトライ）
        import time
        last_err = None
        response = None
        for attempt in range(3):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1500,
                    temperature=0.8
                )
                last_err = None
                break
            except Exception as e:
                last_err = e
                wait = 1.0 * (2 ** attempt)
                print(f"❌ get_shichu_fortune OpenAIエラー(try={attempt+1}/3): {e}")
                time.sleep(wait)

        if response is None:
            raise RuntimeError(f"OpenAI call failed: {last_err}")

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

            if isinstance(result, dict) and not (lang or "ja").lower().startswith("en"):
                result["month_fortune"] = _fix_month_prefix(result.get("month_fortune", ""), target1.year, target1.month)
                result["next_month_fortune"] = _fix_month_prefix(result.get("next_month_fortune", ""), target2.year, target2.month)

                # 文章が尻切れトンボに見えないよう、末尾が句点等で終わっていなければ補完
                def _ensure_sentence_end(s: str) -> str:
                    s = (s or "").strip()
                    if not s:
                        return s
                    if s.endswith(("。", "！", "？", "!", "?", "…", "。」", "！」", "？」")):
                        return s
                    return s + "。"

                for key in ("personality", "year_fortune", "month_fortune", "next_month_fortune"):
                    if key in result:
                        result[key] = _ensure_sentence_end(str(result.get(key, "")))
            return result
        except json.JSONDecodeError:
            print("❌ GPTが正しいJSONを返しませんでした")
            return ({
                "personality": "Could not retrieve the result.",
                "year_fortune": f"Could not retrieve the fortune for {this_year}.",
                "month_fortune": f"Could not retrieve the fortune for {target1.year}-{target1.month:02d}.",
                "next_month_fortune": f"Could not retrieve the fortune for {target2.year}-{target2.month:02d}."
            } if (lang or 'ja').lower().startswith('en') else {
                "personality": "取得できませんでした",
                "year_fortune": f"{this_year}年の運勢は取得できませんでした",
                "month_fortune": f"{target1.year}年{target1.month}月の運勢は取得できませんでした",
                "next_month_fortune": f"{target2.year}年{target2.month}月の運勢は取得できませんでした"
            })
    except Exception as e:
        print("❌ get_shichu_fortune エラー:", e)
        return ({
                "personality": "Could not retrieve the result.",
                "year_fortune": f"Could not retrieve the fortune for {this_year}.",
                "month_fortune": f"Could not retrieve the fortune for {target1.year}-{target1.month:02d}.",
                "next_month_fortune": f"Could not retrieve the fortune for {target2.year}-{target2.month:02d}."
            } if (lang or 'ja').lower().startswith('en') else {
                "personality": "取得できませんでした",
                "year_fortune": f"{this_year}年の運勢は取得できませんでした",
                "month_fortune": f"{target1.year}年{target1.month}月の運勢は取得できませんでした",
                "next_month_fortune": f"{target2.year}年{target2.month}月の運勢は取得できませんでした"
            })


def analyze_palm(image_data, lang: str = 'ja'):
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
        if (lang or 'ja').lower().startswith('en'):
            system_prompt = (
                "You are a professional palm reader. Follow the constraints and interpret the palm image in a warm, inspiring tone.\n\n"
                "[Output rules]\n"
                "- Always include: 1) Life line, 2) Fate line, 3) Money line\n"
                "- Choose two additional 'special lines' preferably from this list (even subtle signs are OK if described positively):\n"
                f"{special_lines_text}\n"
                "- If you truly cannot pick two special lines, you may naturally use Heart line or Head line instead\n\n"
                "[Meaning guide]\n"
                f"{description_text}\n\n"
                "Write in natural, customer-friendly English. Avoid negative wording like 'none' or 'lacking'; reframe as potential."
            )
            user_prompt = (
                "Output in the following format:\n"
                "### 1. Life Line\n(about 180–220 characters)\n\n"
                "### 2. Fate Line\n(about 180–220 characters)\n\n"
                "### 3. Money Line\n(about 180–220 characters)\n\n"
                "### 4. Special Line 1\n(about 180–220 characters)\n\n"
                "### 5. Special Line 2\n(about 180–220 characters)\n\n"
                "### Overall Advice\n(A gentle, uplifting wrap-up)\n\n"
                "- Keep it poetic but clear\n"
                "- End with a hopeful, action-oriented closing"
            )
        else:
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
            model="gpt-4o-mini",
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




def get_iching_advice(lang: str = 'ja'):
    try:
        prompt = ("You are an I Ching advisor. Give a gentle, positive message the customer needs right now in natural English (about 180–220 characters)." if (lang or "ja").lower().startswith("en") else "あなたは易占いの専門家です。今の相談者に必要なメッセージを、200文字で優しく前向きに教えてください。")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 易占い取得失敗:", e)
        return ("Could not retrieve the I Ching message right now." if (lang or "ja").lower().startswith("en") else "現在、易占いの結果が取得できませんでした。")


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
    shichu_result_raw: dict,
    kyusei_text: str,
    lang: str = "ja",
) -> list[str]:
    """誕生日などから「ラッキー情報」を生成して返す（shincom/renai共通ユーティリティ）。

    返り値はPDF側でそのまま描画できる「◆ key: value」形式の行リスト。
    lang='en' のときはラベルと主要な値を英訳する（未知語は原文のまま）。
    """
    import random
    from datetime import datetime

    # 安定した結果にするため birthdate をシードにする
    try:
        seed_key = int(birthdate.replace("-", ""))
    except Exception:
        seed_key = random.randint(1, 99999999)
    rng = random.Random(seed_key)

    # 1) ラッキーアイテム（九星を軽く反映）
    item_pool = {
        "default": ["スマホ充電器", "小さなノート", "ハンドクリーム", "ミントガム", "折りたたみ傘", "白いハンカチ"],
        "五黄土星": ["革の手帳", "小さな財布", "金色の小物", "方位磁石", "土の香りのアロマ"],
        "一白水星": ["イヤホン", "水筒", "青いボールペン", "目薬", "入浴剤"],
        "二黒土星": ["エコバッグ", "湯のみ", "木のスプーン", "お守り袋", "観葉植物"],
        "三碧木星": ["運動靴", "ストップウォッチ", "栄養ドリンク", "青緑の小物", "スポーツタオル"],
        "四緑木星": ["名刺入れ", "香りの良いハンドソープ", "緑の小物", "交通系ICカードケース"],
        "六白金星": ["腕時計", "銀色の小物", "名刺ケース", "シンプルなペン"],
        "七赤金星": ["リップクリーム", "小さな鏡", "赤い小物", "鍵のキーホルダー"],
        "八白土星": ["小さなライト", "黒い小物", "防寒グッズ", "歩きやすい靴下"],
        "九紫火星": ["赤いペン", "香水（控えめ）", "カメラ", "ビタミンサプリ"],
    }
    key = (kyusei_text or "").strip()
    item_ja = rng.choice(item_pool.get(key, item_pool["default"]))

    # 2) ラッキーカラー
    color_pool_ja = [
        "アイアンブルー", "ネイビー", "スカイブルー",
        "モスグリーン", "オリーブ", "ミントグリーン",
        "ワインレッド", "ボルドー", "ローズピンク",
        "ゴールド", "シルバー", "アイボリー", "ホワイト", "ブラック",
    ]
    color_ja = rng.choice(color_pool_ja)

    # 3) ラッキーナンバー（ライフパス優先）
    try:
        number = int(calculate_life_path_number(birthdate))
    except Exception:
        number = rng.randint(1, 9)

    # 4) ラッキーデー（曜日）
    weekday_ja = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
    try:
        weekday_idx = datetime.strptime(birthdate, "%Y-%m-%d").weekday()
    except Exception:
        weekday_idx = rng.randint(0, 6)
    day_ja = weekday_ja[weekday_idx]

    # 5) ラッキーフード（五行→食）
    try:
        wu_xing = (shichu_result_raw or {}).get("gogyou") or (shichu_result_raw or {}).get("five_elements") or ""
    except Exception:
        wu_xing = ""
    wu_xing = str(wu_xing).strip()

    food_map_ja = {
        "木": ["小松菜", "ブロッコリー", "枝豆", "抹茶", "緑茶"],
        "火": ["トマト", "唐辛子", "赤身肉", "いちご", "カカオ"],
        "土": ["さつまいも", "かぼちゃ", "味噌汁", "玄米", "きなこ"],
        "金": ["大根", "白ねぎ", "豆腐", "梨", "白ごま"],
        "水": ["わかめ", "しじみ汁", "寒天", "ところてん", "昆布だし"],
    }
    if wu_xing in food_map_ja:
        food_ja = rng.choice(food_map_ja[wu_xing])
    else:
        food_ja = rng.choice(sum(food_map_ja.values(), []))

    # 英語化（ラベル + 主要値）
    if (lang or "ja").lower().startswith("en"):
        item_en = {
            "スマホ充電器": "Phone charger",
            "小さなノート": "Pocket notebook",
            "ハンドクリーム": "Hand cream",
            "ミントガム": "Mint gum",
            "折りたたみ傘": "Folding umbrella",
            "白いハンカチ": "White handkerchief",
            "革の手帳": "Leather planner",
            "小さな財布": "Small wallet",
            "金色の小物": "Gold accessory",
            "方位磁石": "Compass",
            "土の香りのアロマ": "Earthy aroma oil",
            "イヤホン": "Earphones",
            "水筒": "Water bottle",
            "青いボールペン": "Blue pen",
            "目薬": "Eye drops",
            "入浴剤": "Bath salts",
            "エコバッグ": "Eco bag",
            "湯のみ": "Tea cup",
            "木のスプーン": "Wooden spoon",
            "お守り袋": "Charm pouch",
            "観葉植物": "Houseplant",
            "運動靴": "Sneakers",
            "ストップウォッチ": "Stopwatch",
            "栄養ドリンク": "Energy drink",
            "青緑の小物": "Teal accessory",
            "スポーツタオル": "Sports towel",
            "名刺入れ": "Business card case",
            "香りの良いハンドソープ": "Scented hand soap",
            "緑の小物": "Green accessory",
            "交通系ICカードケース": "Transit card holder",
            "腕時計": "Wristwatch",
            "銀色の小物": "Silver accessory",
            "名刺ケース": "Card case",
            "シンプルなペン": "Simple pen",
            "リップクリーム": "Lip balm",
            "小さな鏡": "Small mirror",
            "赤い小物": "Red accessory",
            "鍵のキーホルダー": "Keychain",
            "小さなライト": "Mini flashlight",
            "黒い小物": "Black accessory",
            "防寒グッズ": "Warm accessory",
            "歩きやすい靴下": "Comfort socks",
            "赤いペン": "Red pen",
            "香水（控えめ）": "Light perfume",
            "カメラ": "Camera",
            "ビタミンサプリ": "Vitamin supplement",
        }
        color_en = {
            "アイアンブルー": "Iron blue",
            "ネイビー": "Navy",
            "スカイブルー": "Sky blue",
            "モスグリーン": "Moss green",
            "オリーブ": "Olive",
            "ミントグリーン": "Mint green",
            "ワインレッド": "Wine red",
            "ボルドー": "Bordeaux",
            "ローズピンク": "Rose pink",
            "ゴールド": "Gold",
            "シルバー": "Silver",
            "アイボリー": "Ivory",
            "ホワイト": "White",
            "ブラック": "Black",
        }
        day_en = {
            "月曜日": "Monday",
            "火曜日": "Tuesday",
            "水曜日": "Wednesday",
            "木曜日": "Thursday",
            "金曜日": "Friday",
            "土曜日": "Saturday",
            "日曜日": "Sunday",
        }
        food_en = {
            "小松菜": "Komatsuna greens",
            "ブロッコリー": "Broccoli",
            "枝豆": "Edamame",
            "抹茶": "Matcha",
            "緑茶": "Green tea",
            "トマト": "Tomatoes",
            "唐辛子": "Chili pepper",
            "赤身肉": "Lean meat",
            "いちご": "Strawberries",
            "カカオ": "Cacao",
            "さつまいも": "Sweet potato",
            "かぼちゃ": "Pumpkin",
            "味噌汁": "Miso soup",
            "玄米": "Brown rice",
            "きなこ": "Roasted soybean flour",
            "大根": "Daikon radish",
            "白ねぎ": "Leek",
            "豆腐": "Tofu",
            "梨": "Pear",
            "白ごま": "White sesame",
            "わかめ": "Wakame seaweed",
            "しじみ汁": "Clam soup",
            "寒天": "Agar jelly",
            "ところてん": "Tokoroten",
            "昆布だし": "Kombu broth",
        }

        item = item_en.get(item_ja, item_ja)
        color = color_en.get(color_ja, color_ja)
        day = day_en.get(day_ja, day_ja)
        food = food_en.get(food_ja, food_ja)

        return [
            f"◆ Item: {item}",
            f"◆ Number: {number}",
            f"◆ Day: {day}",
            f"◆ Color: {color}",
            f"◆ Food: {food}",
        ]

    return [
        f"◆ アイテム: {item_ja}",
        f"◆ 数字: {number}",
        f"◆ 曜日: {day_ja}",
        f"◆ 色: {color_ja}",
        f"◆ 食べ物: {food_ja}",
    ]

def _lang_pack(lang: str):
    """Return (system_prompt, lang_note) for OpenAI calls."""
    if (lang or 'ja').lower().startswith('en'):
        system = "You are a professional fortune teller. Write clear, natural English for customers. Do not mention Japanese astrology jargon, eto names, or Ten-God terms; translate meanings into plain English."
        note = "\n\nWrite in English. Do NOT include eto names or Ten-God terms. Keep it friendly, practical, and positive."
        return system, note
    system = "あなたは占いのプロです。お客様に寄り添い、前向きで具体的なアドバイスを自然な日本語で書いてください。占い用語や干支名は出さず、意味をやさしい言葉に置き換えてください。"
    note = ""
    return system, note

def generate_fortune(image_data, birthdate, kyusei_text, now=None, force_next_month: bool=False, style: str='normal', lang: str='ja', **kwargs):
    import re
    palm_result = analyze_palm(image_data, lang=lang)
    shichu_result_raw = get_shichu_fortune(birthdate, now=now, force_next_month=force_next_month, lang=lang)
    iching_result = get_iching_advice(lang=lang)
    age = datetime.today().year - int(birthdate[:4])
    nicchu_eto = get_nicchu_eto(birthdate)
    raw_lucky_info = generate_lucky_info_mixed(nicchu_eto, birthdate, age, palm_result, shichu_result_raw, kyusei_text, lang=lang)


    # Lucky info is used as a small 2-column block in the PDF.
    # IMPORTANT: Do not collapse it to a single line (regression that made only "Item" appear).
    lucky_lines: list[str] = []
    try:
        if isinstance(raw_lucky_info, list):
            # Expected shape: ["◆ Item: ...", "◆ Number: ...", "◆ Color: ...", "◆ Day: ...", "◆ Food: ..."]
            lucky_lines = [str(x).strip() for x in raw_lucky_info if str(x).strip()]

        elif isinstance(raw_lucky_info, dict):
            # Defensive: accept dict-style lucky info
            order = ["item", "number", "color", "day", "food"]
            labels_ja = {"item": "アイテム", "number": "番号", "color": "色", "day": "曜日", "food": "食べ物"}
            labels_en = {"item": "Item", "number": "Number", "color": "Color", "day": "Day", "food": "Food"}
            labels = labels_en if str(lang).lower().startswith("en") else labels_ja
            for k in order:
                v = raw_lucky_info.get(k)
                if v is not None and str(v).strip():
                    lucky_lines.append(f"◆ {labels[k]}: {str(v).strip()}")

        else:
            # String: keep each bullet line if present, otherwise split by newlines.
            s = str(raw_lucky_info or "").strip()
            lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
            # If a single line contains multiple '◆', split them into multiple lines.
            if len(lines) == 1 and "◆" in lines[0]:
                parts = [p.strip() for p in lines[0].split("◆") if p.strip()]
                lucky_lines = [f"◆ {p}" for p in parts]
            else:
                lucky_lines = lines

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

    if isinstance(shichu_result_raw, dict):
        shichu_texts = {
            "personality": shichu_result_raw.get("personality", ""),
            "year_fortune": shichu_result_raw.get("year_fortune", ""),
            "month_fortune": shichu_result_raw.get("month_fortune", ""),
            "next_month_fortune": shichu_result_raw.get("next_month_fortune", "")
        }
    else:
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

    
    # --- Safety: ensure we always have 5 palm sections + 1 overall comment (so PDF never crashes) ---
    min_blocks = 6  # 5 lines + overall
    if lang == "en":
        fallback_titles = [
            "Life Line",
            "Head Line",
            "Heart Line",
            "Special Line 1",
            "Special Line 2",
            "Overall Palm Reading",
        ]
        fallback_text = (
            "This part couldn't be clearly identified from the photo. "
            "If you can, please retake the photo with better lighting and focus."
        )
    else:
        fallback_titles = [
            "生命線",
            "頭脳線",
            "感情線",
            "特殊線①",
            "特殊線②",
            "手相総合アドバイス",
        ]
        fallback_text = "※画像からこの項目を明確に判定できませんでした。可能なら明るい場所で撮り直してください。"

    # Normalize list lengths
    while len(palm_titles) < min_blocks:
        palm_titles.append(fallback_titles[min(len(palm_titles), len(fallback_titles) - 1)])
    while len(palm_texts) < min_blocks:
        palm_texts.append(fallback_text)

    # Trim excessive blocks (keep first 5 + overall)
    if len(palm_titles) > min_blocks:
        palm_titles = palm_titles[:min_blocks]
    if len(palm_texts) > min_blocks:
        palm_texts = palm_texts[:min_blocks]

    # Ensure non-empty titles/texts for the first 5 blocks
    for i in range(5):
        if not (palm_titles[i] or "").strip():
            palm_titles[i] = fallback_titles[i]
        if not (palm_texts[i] or "").strip():
            palm_texts[i] = fallback_text
    # Ensure the overall comment exists
    if not (palm_texts[5] or "").strip():
        palm_texts[5] = fallback_text


    return palm_titles, palm_texts, shichu_texts, iching_result, lucky_lines




def generate_renai_fortune(user_birth: str, partner_birth: str = None, include_yearly: bool = False, size: str = 'a4', lang: str = 'ja') -> dict:
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
        kyusei_text = generate_lucky_direction(user_birth, base.date(), lang=lang)

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