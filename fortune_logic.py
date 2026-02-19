import openai
import os
import re
import hashlib, random
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tesou import tesou_names, tesou_descriptions, PALM_DETAIL_BY_ID, PALM_DETAIL_INDEX_BY_CATEGORY, find_palm_detail_ids_by_name, get_palm_detail_text_by_id
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from lucky_utils import generate_lucky_info, generate_lucky_direction
from yearly_love_fortune_utils import generate_yearly_love_fortune
from pdf_generator_unified import create_pdf_unified






def get_shichu_fortune(birthdate, now=None, force_next_month: bool = False, lang: str = 'ja'):
    import json
    lang_norm = (lang_norm or 'ja').lower()
    is_en = lang_norm.startswith('en')
    is_zh = lang_norm.startswith('zh') or lang_norm.startswith('cn')
    is_ko = lang_norm.startswith('ko') or lang_norm.startswith('kr')
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

        if is_en:
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
        elif is_zh:
            # 简体中文
            prompt = f"""你是一位四柱推命（八字）解读顾问。
- 日柱（仅供参考）: {eto}
- 年度影响（通变星，仅供参考）: {tsuhen_year}
- {target1.year}-{target1.month:02d} 的影响（通变星，仅供参考）: {tsuhen_month1}
- {target2.year}-{target2.month:02d} 的影响（通变星，仅供参考）: {tsuhen_month2}

请只输出以下结构的 JSON（不要输出任何多余文本）：
{{
  "personality": "用自然、友好的中文写一段性格描述（约 260 字以内）",
  "year_fortune": "{this_year} 年的整体运势（约 260 字以内）",
  "month_fortune": "{target1.year} 年 {target1.month} 月的运势（约 200 字以内）",
  "next_month_fortune": "{target2.year} 年 {target2.month} 月的运势（约 200 字以内）"
}}

规则：
- 绝对不要在正文中提到干支名、通变星名或任何占术术语；请把含义翻译成日常语言
- 积极、具体、可执行（至少给 1 条行动建议）
"""

        elif is_ko:
            prompt = f"""당신은 사주(사주명리) 상담가입니다.
- 일주(참고용): {eto}
- {this_year}년의 영향(통변성/십성, 참고용): {tsuhen_year}
- {target1.year}-{target1.month:02d}의 영향(통변성/십성, 참고용): {tsuhen_month1}
- {target2.year}-{target2.month:02d}의 영향(통변성/십성, 참고용): {tsuhen_month2}

아래 스키마의 JSON만 출력하세요(추가 문장 금지):
{{
  "personality": "자연스러운 한국어 문단(약 260자 이내)",
  "year_fortune": "{this_year}년의 전체 운세(약 260자 이내)",
  "month_fortune": "{target1.year}년 {target1.month}월 운세(약 200자 이내)",
  "next_month_fortune": "{target2.year}년 {target2.month}월 운세(약 200자 이내)"
}}

규칙:
- 본문에 간지명, 통변성/십성명, 전문 용어를 절대 쓰지 말고 일상적인 말로 의미만 풀어주세요
- 긍정적이고 실천 가능한 조언을 최소 1개 포함
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
            def _fix_month_prefix(s, y, m, zh: bool = False, ko: bool = False):
                if not isinstance(s, str):
                    return s
                s = s.strip()
                if zh:
                    s = re.sub(r"^\s*(?:\d{4}年\s*\d{1,2}月|本月|下月|这个月|下个月)\s*[是:,，]?\s*", "", s)
                elif ko:
                    s = re.sub(r"^\s*(?:\d{4}년\s*\d{1,2}월|이번\s*달|다음\s*달)\s*(?:은|는)?\s*[:;,，]?\s*", "", s)
                else:
                    s = re.sub(r"^\s*(?:\d{4}年\s*\d{1,2}月|今月|来月)\s*は\s*[、,]?\s*", "", s)
                if not s:
                    if zh:
                        return f"{y}年{m}月是"
                    if ko:
                        return f"{y}년 {m}월은"
                    return f"{y}年{m}月は"
                if zh:
                    return f"{y}年{m}月是，" + s
                if ko:
                    return f"{y}년 {m}월은, " + s
                return f"{y}年{m}月は、" + s

            if isinstance(result, dict) and (not is_en):
                result["month_fortune"] = _fix_month_prefix(result.get("month_fortune", ""), target1.year, target1.month, zh=is_zh, ko=is_ko)
                result["next_month_fortune"] = _fix_month_prefix(result.get("next_month_fortune", ""), target2.year, target2.month, zh=is_zh, ko=is_ko)

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
            if is_en:
                return {
                "personality": "Could not retrieve the result.",
                "year_fortune": f"Could not retrieve the fortune for {this_year}.",
                "month_fortune": f"Could not retrieve the fortune for {target1.year}-{target1.month:02d}.",
                "next_month_fortune": f"Could not retrieve the fortune for {target2.year}-{target2.month:02d}."
                }
            if is_zh:
                return {
                    "personality": "未能取得结果。",
                    "year_fortune": f"未能取得 {this_year} 年的运势。",
                    "month_fortune": f"未能取得 {target1.year} 年 {target1.month} 月的运势。",
                    "next_month_fortune": f"未能取得 {target2.year} 年 {target2.month} 月的运势。",
                }
            return {
                "personality": "取得できませんでした",
                "year_fortune": f"{this_year}年の運勢は取得できませんでした",
                "month_fortune": f"{target1.year}年{target1.month}月の運勢は取得できませんでした",
                "next_month_fortune": f"{target2.year}年{target2.month}月の運勢は取得できませんでした"
            }
    except Exception as e:
        print("❌ get_shichu_fortune エラー:", e)
        if is_en:
            return {
                "personality": "Could not retrieve the result.",
                "year_fortune": f"Could not retrieve the fortune for {this_year}.",
                "month_fortune": f"Could not retrieve the fortune for {target1.year}-{target1.month:02d}.",
                "next_month_fortune": f"Could not retrieve the fortune for {target2.year}-{target2.month:02d}."
            }
        if is_zh:
            return {
                "personality": "未能取得结果。",
                "year_fortune": f"未能取得 {this_year} 年的运势。",
                "month_fortune": f"未能取得 {target1.year} 年 {target1.month} 月的运势。",
                "next_month_fortune": f"未能取得 {target2.year} 年 {target2.month} 月的运势。",
            }
        return {
                "personality": "取得できませんでした",
                "year_fortune": f"{this_year}年の運勢は取得できませんでした",
                "month_fortune": f"{target1.year}年{target1.month}月の運勢は取得できませんでした",
                "next_month_fortune": f"{target2.year}年{target2.month}月の運勢は取得できませんでした"
            }


def analyze_palm(image_data, output_lang="ja", output_style="normal", output_mode="normal", lang=None, **kwargs):
    """
    画像から手相を分析して、6項目（生命線/運命線/金運線/特殊線①/特殊線②/総合）の鑑定文を返す。

    重要: generate_fortune() 側は "### " 見出しで分割して palm_titles/palm_texts を作るため、
    返却テキストは必ず "### " で始まる見出しを6つ含む形式にする。
    """
    import json

    # -------------------------
    # base64正規化
    # -------------------------
    if isinstance(image_data, str) and image_data.startswith("data:image"):
        base64data = image_data.split(",", 1)[1]
    else:
        base64data = image_data

    # -------------------------
    # Backward-compatible language alias:
    # generate_fortune() passes lang=..., while older callers may pass output_lang=...
    # Prefer explicit output_lang unless it's default/empty.
    # -------------------------
    try:
        if lang is not None and (output_lang is None or str(output_lang).strip() == "" or str(output_lang).lower() == "ja"):
            output_lang = lang
    except Exception:
        if lang is not None:
            output_lang = lang

    lang_norm = (output_lang or "ja").lower()
    is_en = lang_norm.startswith("en")
    is_zh = lang_norm.startswith("zh") or lang_norm.startswith("cn")
    is_ko = lang_norm.startswith("ko") or lang_norm.startswith("kr")

    # -------------------------
    # 既存の基本線と特殊線候補（旧DB）
    # -------------------------
    base_lines = ["生命線", "頭脳線", "感情線", "運命線", "金運線"]

    # Excel由来の詳細DB（存在しない環境でも落ちないように）
    try:
        from tesou import (
            PALM_DETAIL_BY_ID,
            PALM_DETAIL_INDEX_BY_CATEGORY,
            find_palm_detail_ids_by_name,
            get_palm_detail_text_by_id,
        )
    except Exception:
        PALM_DETAIL_BY_ID = {}
        PALM_DETAIL_INDEX_BY_CATEGORY = {}
        def find_palm_detail_ids_by_name(_name):  # type: ignore
            return []
        def get_palm_detail_text_by_id(_id):  # type: ignore
            return ""

    # tesou.py 既存の名称・説明（旧DB）
    # ※ tesou_names / tesou_descriptions は元ファイル側で import 済み
    try:
        special_from_excel = [name for _id, name in PALM_DETAIL_INDEX_BY_CATEGORY.get("特殊な線", [])]
        # 基本線が混ざると「特殊線が基本線になる」不具合になるため除外
        special_from_excel = [n for n in special_from_excel if n and n not in base_lines and n != "太陽線"]
    except Exception:
        special_from_excel = []

    special_line_candidates = sorted(
        set([n for n in tesou_names if n not in base_lines] + special_from_excel)
    )
    special_candidates_set = set(special_line_candidates)

    # -------------------------
    # ユーティリティ：候補一覧文字列（番号: 名称）
    # -------------------------
    def _format_variant_list(category: str) -> str:
        items = PALM_DETAIL_INDEX_BY_CATEGORY.get(category, [])
        if not items:
            return "(データなし)"
        return "\n".join([f"{i}: {name}" for i, name in items])

    life_options = _format_variant_list("生命線")
    fate_options = _format_variant_list("運命線")
    sun_options  = _format_variant_list("太陽線")  # 金運の補助（太陽線が見える場合）

    # -------------------------
    # JSON抽出（モデルが余計な文章を付けた場合の保険）
    # -------------------------
    def _safe_json_load(text: str):
        if not text:
            return None
        text = str(text).strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    # -------------------------
    # 名称の正規化（ゆるい補正）
    # -------------------------
    def _norm_name(s: str) -> str:
        s = str(s or "").strip()
        s = s.replace("\u3000", " ").strip()  # 全角スペース
        s = re.sub(r"\s+", " ", s)
        return s

    # -------------------------
    # ① 画像判定：番号/名称の選択（詳細本文は渡さない）
    # -------------------------
    detect = None
    try:
        detect_system = (
            "あなたは手相画像から『線の形状タイプ（番号）』と『特殊線の名称』を選ぶ判定者です。"
            "必ず提示された候補から選び、出力はJSONのみ。推測で本文を書かない。"
        )

        detect_user = f"""
次の3カテゴリの候補一覧から、画像に最も近いものを1つずつ選んでください。
- 生命線（カテゴリ: 生命線）: 1件必須
- 運命線（カテゴリ: 運命線）: 1件必須
- 金運（カテゴリ: 太陽線）: 見える場合のみ（見えない/判断不可なら 0）

また、特殊線は候補一覧から「最大2つ」選んでください（見当たらなければ空配列）。
※ 生命線/運命線/金運線/頭脳線/感情線 は “基本線” なので special に入れてはいけません。

【生命線 候補（番号: 名称）】
{life_options}

【運命線 候補（番号: 名称）】
{fate_options}

【太陽線 候補（番号: 名称）】
{sun_options}

【特殊線 候補（名称のみ）】
{", ".join(special_line_candidates)}

出力JSONスキーマ（このキー名で、余計なキーは付けない）：
{{
  "life_id": 1,
  "fate_id": 52,
  "money_sun_id": 0,
  "special": ["神秘十字線", "仏眼相"],
  "notes": "画像の事実ベースの所見（2文以内）"
}}

ルール：
- 候補にない番号/名称は絶対に出さない
- special は最大2件。重複禁止
- 見えない場合は無理に選ばず、money_sun_id は 0、special は [] でもよい
- JSON以外の文章は禁止
""".strip()

        resp1 = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": detect_system},
                {"role": "user", "content": [
                    {"type": "text", "text": detect_user},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64data}"}}
                ]}
            ],
            temperature=0.1,
            max_tokens=650,
        )
        raw1 = resp1.choices[0].message["content"]
        detect = _safe_json_load(raw1)
    except Exception:
        detect = None

    # -------------------------
    # 判定が取れない場合はフォールバック（旧DBガイドを渡して直接生成）
    # ※ この場合でも必ず "### " 6見出し形式で返す
    # -------------------------
    if not isinstance(detect, dict):
        description_text = "\n".join([f"{k}: {v}" for k, v in tesou_descriptions.items()])
        special_lines_text = ", ".join(special_line_candidates)

        if is_en:
            system_prompt = """You are a warm, entertaining but practical palm reader.
Use ONLY the provided meaning guide (translate it internally), and base everything on what you see in the image.
Return EXACTLY 6 sections with headings that start with '### ' in this order:
### 1. Life Line
### 2. Fate Line
### 3. Money Line
### 4. Special Line 1
### 5. Special Line 2
### Overall Advice
Length targets (EN): sections 1–5 are ~95–140 words each; Overall Advice is ~170–230 words. If too short, add more.
Style: confident, vivid, a touch mystical but grounded. Avoid hedging words like 'maybe'/'might'.
Never say 'cannot see'/'not visible'. If a line looks faint, reframe positively (e.g., 'subtle now, grows with habit').
Do NOT mention IDs, databases, or references. Do NOT use '###' anywhere else. Write in English only."""
        elif is_zh:
            system_prompt = (
                "你是一位温和、带点娱乐感但务实的手相解读师。只使用提供的含义指南。\n"
                "必须输出6段，并且每个标题都以 '### ' 开头，顺序固定：\n"
                "### 1. 生命线\n### 2. 命运线\n### 3. 金运线\n### 4. 特殊线①\n"
                "### 5. 特殊线②\n### 综合建议\n"
                "每段约130-220个汉字。避免消极措辞如“看不到/无法确认”。不要提及编号/数据库/参考资料。正文不要再出现'###'。"
            )
        elif is_ko:
            system_prompt = (
                "당신은 친절하면서도 엔터테인먼트 감각이 있는 현실적인 손금 해석가입니다. 제공된 의미 가이드만 사용하세요.\n"
                "반드시 6개 섹션을 출력하고 각 제목은 '### '로 시작해야 합니다(순서 고정):\n"
                "### 1. 생명선\n### 2. 운명선\n### 3. 금운선\n### 4. 특수선①\n"
                "### 5. 특수선②\n### 종합 조언\n"
                "각 섹션은 약 130~220자. '보이지 않는다' 같은 부정적 표현은 피하고, 번호/DB/참고자료 언급 금지. 본문에 '###' 재사용 금지."
            )
        else:
            system_prompt = (
                "あなたはプロの手相占い師です。与えられた意味ガイドのみを根拠に、必ず6項目を出力してください。\n"
                "各見出しは必ず '### ' から始め、この順番で固定：\n"
                "### 1. 生命線\n### 2. 運命線\n### 3. 金運線\n### 4. 特殊線①\n"
                "### 5. 特殊線②\n### 手相の総合アドバイス\n"
                "各項目は200〜320文字程度（総合は320〜480文字）。"
                "『確認できない/見えない』などの言い方は禁止。線が薄い場合は『繊細に出ており、これから育つタイプ』のように前向きに言い換える。"
                "用語の羅列は禁止。お客様がワクワクする比喩を1つ入れつつ、現実的な行動提案で締める。"
                "本文中に '###' を再登場させない。"
            )
        if is_en:
            user_prompt = f"""Meaning guide:
{description_text}

Special-line candidates:
{special_lines_text}

Look at the image, identify the relevant lines, and write the reading in the required format. Write in English only."""
        elif is_zh:
            user_prompt = f"""含义指南:
{description_text}

特殊线候选列表:
{special_lines_text}

请看图像并按指定格式写出解读（仅使用简体中文）。"""
        elif is_ko:
            user_prompt = f"""의미 가이드:
{description_text}

특수선 후보 목록:
{special_lines_text}

이미지를 보고 해당 선을 읽어 지정 형식으로 해석을 작성하세요(한국어만)."""
        else:
            user_prompt = f"""意味ガイド:
{description_text}

特殊線候補一覧:
{special_lines_text}

画像を見て該当する線を読み取り、指定形式で鑑定文を作ってください。"""

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64data}"}}
                ]}
            ],
            temperature=0.85,
            presence_penalty=0.3,
            frequency_penalty=0.1,
            max_tokens=1600,
        )
        return response.choices[0].message["content"]

    # -------------------------
    # ② 詳細本文（Excel由来）＋既存の簡易説明（旧DB）を根拠に、鑑定文生成
    # ※ 必ず "### " 6見出し形式で返す
    # -------------------------
    life_id = int(detect.get("life_id", 0) or 0)
    fate_id = int(detect.get("fate_id", 0) or 0)
    money_sun_id = int(detect.get("money_sun_id", 0) or 0)
    notes = str(detect.get("notes", "") or "").strip()

    special = detect.get("special", [])
    if not isinstance(special, list):
        special = []

    # 最大2つ、重複除外、候補外は捨てる（頭脳線/感情線など基本線が混ざる事故防止）
    special_clean = []
    for s in special:
        s = _norm_name(s)
        if not s:
            continue
        if s not in special_candidates_set:
            continue
        if s in special_clean:
            continue
        special_clean.append(s)
        if len(special_clean) >= 2:
            break

    # 足りない分は、候補から “エンタメ性が高い” 特殊線を優先して補完（基本線には絶対にしない）
    def _pick_priority_specials(need: int, already: list) -> list:
        if need <= 0:
            return []
        # よく盛り上がるキーワード（候補名に含まれていれば優先）
        priority_keywords = [
            "金星帯", "神秘十字", "覇王", "太陽", "フィッシュ", "スター", "仏眼", "ますかけ",
            "直感", "火星", "ソロモン", "二重", "結婚", "財運", "成功", "人気"
        ]
        picks = []
        # 1) キーワード一致で拾う
        for kw in priority_keywords:
            for name in special_line_candidates:
                if name in already or name in picks:
                    continue
                if kw in name:
                    picks.append(name)
                    if len(picks) >= need:
                        return picks
        # 2) それでも足りない場合は、候補順で埋める
        for name in special_line_candidates:
            if name in already or name in picks:
                continue
            picks.append(name)
            if len(picks) >= need:
                break
        return picks

    if len(special_clean) < 2:
        special_clean.extend(_pick_priority_specials(2 - len(special_clean), special_clean))

    # 最終保険：万一 still 足りなければ、空文字ではなく候補から埋める
    if len(special_clean) < 2:
        for name in special_line_candidates:
            if name not in special_clean:
                special_clean.append(name)
            if len(special_clean) >= 2:
                break

    sp1_name, sp2_name = special_clean[0], special_clean[1]

    # 生命線詳細
    life_row = PALM_DETAIL_BY_ID.get(life_id, {})
    life_name = life_row.get("name", "（不明）")
    life_detail = life_row.get("detail", "")

    # 運命線詳細
    fate_row = PALM_DETAIL_BY_ID.get(fate_id, {})
    fate_name = fate_row.get("name", "（不明）")
    fate_detail = fate_row.get("detail", "")

    # 金運：太陽線の詳細が取れればそれを優先。なければ旧DBの金運線説明。
    money_detail = ""
    money_name = ""
    if money_sun_id and money_sun_id in PALM_DETAIL_BY_ID:
        sun_row = PALM_DETAIL_BY_ID.get(money_sun_id, {})
        money_name = sun_row.get("name", "") or "太陽線"
        money_detail = sun_row.get("detail", "")
    else:
        money_name = "金運線（基本）"
        money_detail = ""

    # 旧DBのベース説明（合併用）
    base_life = tesou_descriptions.get("生命線", "")
    base_fate = tesou_descriptions.get("運命線", "")
    base_money = tesou_descriptions.get("金運線", "")

    # 特殊線の詳細（Excel側にもあれば拾う）
    def _special_detail(name: str):
        base = tesou_descriptions.get(name, "")
        detail_text = ""
        try:
            ids = find_palm_detail_ids_by_name(name)
            if ids:
                detail_text = get_palm_detail_text_by_id(ids[0])
        except Exception:
            detail_text = ""
        return {"name": name, "base": base, "detail": detail_text}

    sp1 = _special_detail(sp1_name)
    sp2 = _special_detail(sp2_name)

    # -------------------------
    # 出力スタイル（ゆるい切替）
    # -------------------------
    style_hint = ""
    try:
        if str(output_style).lower() in ("yuta", "mystic") or str(output_mode).lower() in ("yuta", "mystic"):
            # ユタ調：少し神秘寄り。ただし煽りすぎない
            style_hint = "語り口は少し神秘的で断定的。ただし不安を煽らず、最後は安心させる。"
    except Exception:
        style_hint = ""

    # -------------------------
    # 生成プロンプト（6見出し）
    # -------------------------
    if is_en:
        system_prompt = """You are a professional palm reader with an entertaining, cinematic voice — but always practical.
Use ONLY the provided [FACTS] and [MEANINGS] (translate Japanese into English internally). Do not invent facts.
Return EXACTLY 6 sections with headings that start with '### ' in this order:
### 1. Life Line
### 2. Fate Line
### 3. Money Line
### 4. Special Line 1
### 5. Special Line 2
### Overall Advice
In 'Special Line 1' interpret Special1 from [FACTS]. In 'Special Line 2' interpret Special2 from [FACTS].
Length targets (EN): sections 1–5 are ~110–170 words each; Overall Advice is ~190–260 words. If too short, add more.
Style: confident, warm, a touch mystical but grounded. Avoid hedging ('maybe', 'might').
Never say 'cannot see'/'not visible'. If something looks subtle, reframe positively.
Do NOT mention IDs, databases, prompts, or references. Do NOT use '###' anywhere else.
Write in English only; avoid Japanese characters in the output."""
    elif is_zh:
        system_prompt = (
            "你是一位专业、温和、带一点娱乐感的手相解读师。只能使用提供的“事实”和“含义文本”。\n"
            "必须输出6段，并且每个标题都以 '### ' 开头，顺序固定：\n"
            f"### 1. 生命线\n### 2. 命运线\n### 3. 金运线\n### 4. 特殊线①（{sp1_name}）\n"
            f"### 5. 特殊线②（{sp2_name}）\n### 综合建议\n"
            "每段约160-260个汉字（综合建议更长一些）。避免“看不到/无法确认”等消极措辞。"
            "不要提及编号/数据库/参考资料。正文不要再出现'###'。"
        )
    elif is_ko:
        system_prompt = (
            "당신은 전문적이고 따뜻하며 약간의 엔터테인먼트 감각이 있는 손금 해석가입니다. 제공된 '사실'과 '의미 텍스트'만 사용하세요.\n"
            "반드시 6개 섹션을 출력하고 각 제목은 '### '로 시작해야 합니다(순서 고정):\n"
            f"### 1. 생명선\n### 2. 운명선\n### 3. 금운선\n### 4. 특수선①({sp1_name})\n"
            f"### 5. 특수선②({sp2_name})\n### 종합 조언\n"
            "각 섹션은 약 160~260자(종합은 더 길게). '보이지 않는다' 같은 부정적 표현은 피하세요. 번호/DB/참고자료 언급 금지. 본문에 '###' 재사용 금지."
        )
    else:
        system_prompt = (
            "あなたはプロの手相占い師です。以下に与えた『事実（判定結果）』と『意味テキスト』のみを根拠に、"
            "お客様が“占ってよかった”と思えるエンタメ性と、今日から動ける実用性を両立した文章を書いてください。\n"
            f"{style_hint}\n"
            "必ず6項目を出力し、各見出しは必ず '### ' から始め、この順番で固定：\n"
            "### 1. 生命線\n### 2. 運命線\n### 3. 金運線\n"
            f"### 4. 特殊線①（{sp1_name}）\n"
            f"### 5. 特殊線②（{sp2_name}）\n"
            "### 手相の総合アドバイス\n"
            "文字量の目安：1〜5は各200〜320文字、総合は320〜520文字。短すぎる場合は必ず増やす。\n"
            "禁止事項：『確認できない/見えない/不明』などの否定表現、ID/番号/DB/参照、箇条書きの羅列、過度な脅し。\n"
            "書き方：断定口調（あなたは〜です）を基本に、比喩を1つ入れてワクワクさせる。"
            "ただし根拠は意味テキストから逸脱しすぎない。線が弱い場合は『繊細に出ており、これから育つ』のように前向きに言い換える。"
            "総合アドバイスの最後は、具体的な行動提案（1〜2個）と、背中を押す一言で締める。\n"
            "本文中に '###' を再登場させない。"
        )

    meaning_block = f"""
[FACTS]
- Life: {life_name}
- Fate: {fate_name}
- Money: {money_name}
- Special1: {sp1_name}
- Special2: {sp2_name}
- Notes: {notes}

[MEANINGS]
(Life detail)
{life_detail}

(Life base)
{base_life}

(Fate detail)
{fate_detail}

(Fate base)
{base_fate}

(Money detail - if any)
{money_detail}

(Money base)
{base_money}

(Special1)
{json.dumps(sp1, ensure_ascii=False)}

(Special2)
{json.dumps(sp2, ensure_ascii=False)}
""".strip()
    if is_en:
        user_prompt = f"""{meaning_block}

Using ONLY the above [FACTS] and [MEANINGS], write the final reading in the required 6-section format.
Keep it upbeat, vivid, and practical. Structure each section as: short conclusion → reason → how to use.
Translate any Japanese line names into natural English. Write in English only and avoid Japanese characters in the output."""
    elif is_zh:
        user_prompt = f"""{meaning_block}

只根据以上[FACTS]与[MEANINGS]，按要求的6段标题格式写出最终解读。
语气积极、生动但务实；每段遵循：结论→理由→如何运用。仅使用简体中文。"""
    elif is_ko:
        user_prompt = f"""{meaning_block}

위의 [FACTS] 와 [MEANINGS] 만을 근거로, 지정된 6개 제목 형식으로 최종 해석을 작성하세요.
톤은 긍정적이고 생동감 있게, 그러나 실용적으로. 각 섹션은: 결론→이유→활용법 순서. 한국어만 사용."""
    else:
        user_prompt = f"""{meaning_block}

上の内容だけを根拠に、指定の6見出し形式で最終鑑定文を書いてください。
前向きで、情景が浮かぶ言葉を使い、各項目は“短い結論→理由→活かし方”の流れにしてください。"""

    response2 = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
        presence_penalty=0.35,
        frequency_penalty=0.12,
        max_tokens=1800,
    )
    return response2.choices[0].message["content"]

def get_iching_advice(lang: str = 'ja'):
    try:
        lang_norm = (lang_norm or 'ja').lower()
        if lang_norm.startswith('en'):
            prompt = "You are an I Ching advisor. Give a gentle, positive message the customer needs right now in natural English (about 180–220 characters)."
        elif lang_norm.startswith('zh') or lang_norm.startswith('cn'):
            prompt = "你是一位易经占卜顾问。请用温柔、积极、可执行的语气，给出当下最需要的一段提醒（约150–220字，简体中文）。不要出现任何卦名或术语。"
        elif lang_norm.startswith('ko') or lang_norm.startswith('kr'):
            prompt = "당신은 주역(I Ching) 조언자입니다. 지금 고객에게 필요한 메시지를 따뜻하고 긍정적이며 실행 가능하게 한국어로 150–220자 정도로 전해주세요. 괘명이나 전문 용어는 절대 쓰지 마세요."
        else:
            prompt = "あなたは易占いの専門家です。今の相談者に必要なメッセージを、200文字で優しく前向きに教えてください。"
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        raw = response.choices[0].message.content.strip()
        # Post-process to reduce hedge wording and duplicate lines (especially Japanese)
        def _polish_palm_text(t: str) -> str:
            if not t:
                return t
            t = t.replace('もし', '')
            # Convert common '〜なら' hedges into assertive phrasing
            t = re.sub(r'この線が([^。\n]{0,30}?)なら、', r'この線は\1ので、', t)
            t = re.sub(r'([一-龥ぁ-んァ-ンA-Za-z0-9_]+)が([^。\n]{0,30}?)なら、', r'\1は\2ので、', t)
            t = re.sub(r'([一-龥ぁ-んァ-ンA-Za-z0-9_]+)が([^。\n]{0,30}?)なら。', r'\1は\2です。', t)
            t = t.replace('あるなら、', 'あり、')
            t = t.replace('現れているなら、', '現れており、')
            t = t.replace('見えるなら、', '見えており、')
            t = t.replace('なら、', 'ので、')
            t = t.replace('なら。', 'です。')
            # De-duplicate identical lines within each section
            lines = [ln.rstrip() for ln in t.split('\n')]
            out = []
            prev = None
            seen_in_section = set()
            for ln in lines:
                key = re.sub(r'\s+', '', ln)
                if key.startswith('###') or key.startswith('◆'):
                    seen_in_section = set()
                if not key:
                    out.append(ln)
                    prev = key
                    continue
                if key == prev:
                    continue
                if key in seen_in_section:
                    continue
                seen_in_section.add(key)
                out.append(ln)
                prev = key
            return '\n'.join(out).strip()

        try:
            if (lang_norm or 'ja').lower().startswith('ja'):
                raw = _polish_palm_text(raw)
        except Exception:
            pass
        return raw
    except Exception as e:
        print("❌ 易占い取得失敗:", e)
        if (lang or 'ja').lower().startswith('en'):
            return "Could not retrieve the I Ching message right now."
        if (lang or 'ja').lower().startswith(('zh', 'cn')):
            return "目前无法取得易经信息。"
        if (lang or 'ja').lower().startswith(('ko', 'kr')):
            return "현재 주역 메시지를 가져올 수 없습니다."
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

    lang_norm = (lang_norm or 'ja').lower()

    # 英語化（ラベル + 主要値）
    if lang_norm.startswith("en"):
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

    # 中文化（ラベル + 主要値）
    if lang_norm.startswith(("zh", "cn")):
        item_zh = {
            "スマホ充電器": "手机充电器",
            "小さなノート": "随身小本",
            "ハンドクリーム": "护手霜",
            "ミントガム": "薄荷口香糖",
            "折りたたみ傘": "折叠伞",
            "白いハンカチ": "白色手帕",
            "イヤホン": "耳机",
            "水筒": "水壶",
            "目薬": "眼药水",
            "入浴剤": "浴盐",
            "エコバッグ": "环保袋",
            "観葉植物": "室内绿植",
            "腕時計": "手表",
            "小さな鏡": "小镜子",
        }
        color_zh = {
            "ネイビー": "海军蓝",
            "スカイブルー": "天蓝",
            "モスグリーン": "苔藓绿",
            "ミントグリーン": "薄荷绿",
            "ワインレッド": "酒红",
            "ローズピンク": "玫瑰粉",
            "ゴールド": "金色",
            "シルバー": "银色",
            "アイボリー": "象牙白",
            "ホワイト": "白色",
            "ブラック": "黑色",
        }
        day_zh = {
            "月曜日": "周一",
            "火曜日": "周二",
            "水曜日": "周三",
            "木曜日": "周四",
            "金曜日": "周五",
            "土曜日": "周六",
            "日曜日": "周日",
        }
        food_zh = {
            "小松菜": "小松菜",
            "ブロッコリー": "西兰花",
            "枝豆": "毛豆",
            "抹茶": "抹茶",
            "緑茶": "绿茶",
            "トマト": "番茄",
            "唐辛子": "辣椒",
            "赤身肉": "瘦肉",
            "いちご": "草莓",
            "カカオ": "可可",
            "さつまいも": "红薯",
            "かぼちゃ": "南瓜",
            "味噌汁": "味噌汤",
            "玄米": "糙米",
            "きなこ": "黄豆粉",
            "大根": "白萝卜",
            "白ねぎ": "大葱",
            "豆腐": "豆腐",
            "梨": "梨",
            "白ごま": "白芝麻",
            "わかめ": "裙带菜",
            "しじみ汁": "蜆汤",
            "寒天": "琼脂",
            "ところてん": "心太",
            "昆布だし": "昆布高汤",
        }

        item = item_zh.get(item_ja, item_ja)
        color = color_zh.get(color_ja, color_ja)
        day = day_zh.get(day_ja, day_ja)
        food = food_zh.get(food_ja, food_ja)

        return [
            f"◆ 物品: {item}",
            f"◆ 数字: {number}",
            f"◆ 星期: {day}",
            f"◆ 颜色: {color}",
            f"◆ 食物: {food}",
        ]


    # 한국어화（라벨 + 주요 값）
    if lang_norm.startswith(("ko", "kr")):
        item_ko = {
            "スマホ充電器": "휴대폰 충전기",
            "小さなノート": "작은 노트",
            "ハンドクリーム": "핸드크림",
            "ミントガム": "민트껌",
            "折りたたみ傘": "접이식 우산",
            "白いハンカチ": "흰 손수건",
            "イヤホン": "이어폰",
            "水筒": "물병",
            "目薬": "안약",
            "入浴剤": "입욕제",
            "エコバッグ": "에코백",
            "観葉植物": "실내 식물",
            "腕時計": "손목시계",
            "小さな鏡": "작은 거울",
        }
        color_ko = {
            "アイアンブルー": "아이언 블루",
            "ネイビー": "네이비",
            "スカイブルー": "스카이 블루",
            "モスグリーン": "모스 그린",
            "オリーブ": "올리브",
            "ミントグリーン": "민트 그린",
            "ワインレッド": "와인 레드",
            "ボルドー": "보르도",
            "ローズピンク": "로즈 핑크",
            "ゴールド": "골드",
            "シルバー": "실버",
            "アイボリー": "아이보리",
            "ホワイト": "화이트",
            "ブラック": "블랙",
        }
        day_ko = {
            "月曜日": "월요일",
            "火曜日": "화요일",
            "水曜日": "수요일",
            "木曜日": "목요일",
            "金曜日": "금요일",
            "土曜日": "토요일",
            "日曜日": "일요일",
        }
        food_ko = {
            "小松菜": "코마츠나",
            "ブロッコリー": "브로콜리",
            "枝豆": "에다마메",
            "抹茶": "말차",
            "緑茶": "녹차",
            "トマト": "토마토",
            "唐辛子": "고추",
            "赤身肉": "살코기",
            "いちご": "딸기",
            "カカオ": "카카오",
            "さつまいも": "고구마",
            "かぼちゃ": "호박",
            "味噌汁": "된장국",
            "玄米": "현미",
            "きなこ": "콩가루",
            "大根": "무",
            "白ねぎ": "대파",
            "豆腐": "두부",
            "梨": "배",
            "白ごま": "흰깨",
            "わかめ": "미역",
            "しじみ汁": "재첩국",
            "寒天": "한천",
            "ところてん": "도코로텐",
            "昆布だし": "다시마 육수",
        }

        item = item_ko.get(item_ja, item_ja)
        color = color_ko.get(color_ja, color_ja)
        day = day_ko.get(day_ja, day_ja)
        food = food_ko.get(food_ja, food_ja)

        return [
            f"◆ 아이템: {item}",
            f"◆ 숫자: {number}",
            f"◆ 요일: {day}",
            f"◆ 컬러: {color}",
            f"◆ 푸드: {food}",
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
    lang_norm = (lang_norm or 'ja').lower()
    if lang_norm.startswith('en'):
        system = "You are a professional fortune teller. Write clear, natural English for customers. Do not mention Japanese astrology jargon, eto names, or Ten-God terms; translate meanings into plain English."
        note = "\n\nWrite in English. Do NOT include eto names or Ten-God terms. Keep it friendly, practical, and positive."
        return system, note
    if lang_norm.startswith(('zh', 'cn')):
        system = "你是一位专业的占卜师。请用自然的简体中文写给顾客：积极、具体、可执行。不要出现干支名、通变星名或任何占术术语；请把含义翻译成日常语言。"
        note = "\n\n请用简体中文输出。不要出现干支名、通变星名或任何占术术语。语气友好、具体、正向。"
        return system, note
    if lang_norm.startswith(('ko', 'kr')):
        system = "당신은 전문 점술가입니다. 고객이 편안해지고 희망을 얻을 수 있도록 자연스러운 한국어로, 긍정적이고 구체적인 조언을 작성하세요. 간지명/통변성/점술 용어는 쓰지 말고 의미를 일상어로 풀어주세요."
        note = "\n\n한국어로 출력하세요. 간지명, 통변성/십성, 전문 용어는 절대 쓰지 마세요. 친절하고 실천 가능한 조언으로 작성하세요."
        return system, note

    system = "あなたは占いのプロです。お客様に寄り添い、前向きで具体的なアドバイスを自然な日本語で書いてください。占い用語や干支名は出さず、意味をやさしい言葉に置き換えてください。"
    note = ""
    return system, note

def generate_fortune(image_data, birthdate, kyusei_text, now=None, force_next_month: bool=False, style: str='normal', lang: str='ja', **kwargs):
    import re

    # --- Normalize output language (UI may send output_lang, or english_output flag) ---
    def _normalize_lang(lang_value: str, kw: dict) -> str:
        out = kw.get("output_lang") or lang_value
        # Some UIs toggle English via a boolean flag instead of output_lang
        eng_flag = kw.get("english_output")
        if isinstance(eng_flag, str):
            eng_flag = eng_flag.strip().lower() in ("1", "true", "yes", "on")
        if eng_flag:
            out = "en"

        mode = (kw.get("output_mode") or "").strip().lower()
        if mode in ("en", "english", "eng"):
            out = "en"

        out = (out or "ja")
        out = str(out).strip().lower()
        if out.startswith(("zh", "cn")):
            return "zh"
        if out.startswith(("ko", "kr")):
            return "ko"
        if out.startswith("en"):
            return "en"
        return "ja"

    lang_norm = _normalize_lang(lang, kwargs)
    output_style = kwargs.get("output_style", style)
    output_mode = kwargs.get("output_mode", "normal")

    palm_result = analyze_palm(
        image_data,
        output_lang=lang_norm,
        output_style=output_style,
        output_mode=output_mode,
        lang=lang_norm,  # backward compatibility
    )
    shichu_result_raw = get_shichu_fortune(
        birthdate, now=now, force_next_month=force_next_month, lang=lang_norm
    )
    iching_result = get_iching_advice(lang=lang_norm)
    age = datetime.today().year - int(birthdate[:4])
    nicchu_eto = get_nicchu_eto(birthdate)
    raw_lucky_info = generate_lucky_info_mixed(
        nicchu_eto, birthdate, age, palm_result, shichu_result_raw, kyusei_text, lang=lang_norm
    )


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
            labels_zh = {"item": "物品", "number": "数字", "color": "颜色", "day": "星期", "food": "食物"}
            lang_norm = str(lang).lower()
            if lang_norm.startswith("en"):
                labels = labels_en
            elif lang_norm.startswith(("zh", "cn")):
                labels = labels_zh
            else:
                labels = labels_ja
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
    lang_norm = (lang_norm or 'ja').lower()
    if lang_norm.startswith("en"):
        fallback_titles = [
            "Life Line",
            "Fate Line",
            "Money Line",
            "Special Line 1",
            "Special Line 2",
            "Overall Advice",
        ]
        fallback_text = (
            "This part couldn't be clearly identified from the photo. "
            "If you can, please retake the photo with better lighting and focus."
        )
    elif lang_norm.startswith(("zh", "cn")):
        fallback_titles = [
            "生命线",
            "命运线",
            "金运线",
            "特殊线①",
            "特殊线②",
            "综合建议",
        ]
        fallback_text = "※从图片中无法清晰判断该项目。建议在更明亮、对焦清晰的环境重新拍摄。"
    elif lang_norm.startswith(("ko", "kr")):
        fallback_titles = [
            "생명선",
            "운명선",
            "금운선",
            "특수선①",
            "특수선②",
            "종합 조언",
        ]
        fallback_text = "※사진에서 이 항목을 명확히 판정하기 어려웠습니다. 가능하면 더 밝은 곳에서 초점을 맞춰 다시 촬영해 주세요."
    else:
        fallback_titles = [
            "生命線",
            "運命線",
            "金運線",
            "特殊線①",
            "特殊線②",
            "手相の総合アドバイス",
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