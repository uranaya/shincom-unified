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


def _fallback_shichu_result(this_year: int, target1, target2, lang: str = 'ja') -> dict:
    """OpenAIの一時失敗・JSON不正時でも、お客様向けPDFに失敗文を出さないための保険。"""
    lang_norm = (lang or 'ja').lower()
    if lang_norm.startswith('en'):
        return {
            "personality": "You are steady, observant, and capable of growing through responsibility. Small daily actions strengthen your confidence and open better opportunities.",
            "year_fortune": f"In {this_year}, your luck improves when you choose steady progress over rushing. Trust, learning, and practical action will become your strongest support.",
            "month_fortune": f"{target1.year}-{target1.month:02d} brings chances to show leadership through calm decisions. Listen well, organize priorities, and move one step at a time.",
            "next_month_fortune": f"{target2.year}-{target2.month:02d} favors flexible thinking and honest communication. A positive response to change will lead to better results.",
        }
    if lang_norm.startswith(('zh', 'cn')):
        return {
            "personality": "你稳重、有观察力，越是在责任中越能成长。每天累积一点行动，信心和机会都会逐渐增强。",
            "year_fortune": f"{this_year}年，选择稳步前进会比急于求成更有利。信任、学习与实际行动，会成为你的好运基础。",
            "month_fortune": f"{target1.year}年{target1.month}月，适合用冷静判断展现领导力。多倾听、整理重点，一步一步推进会有好结果。",
            "next_month_fortune": f"{target2.year}年{target2.month}月，灵活思考与真诚沟通会带来好运。积极面对变化，结果会更顺利。",
        }
    if lang_norm.startswith(('ko', 'kr')):
        return {
            "personality": "당신은 차분하고 관찰력이 있으며, 책임 속에서 더 크게 성장하는 사람입니다. 작은 실천이 쌓일수록 자신감과 기회가 커집니다.",
            "year_fortune": f"{this_year}년은 서두르기보다 꾸준히 나아갈 때 운이 열립니다. 신뢰, 배움, 현실적인 행동이 좋은 흐름을 만듭니다.",
            "month_fortune": f"{target1.year}년 {target1.month}월은 침착한 판단으로 리더십을 보이기 좋은 시기입니다. 잘 듣고 우선순위를 정하면 좋은 결과가 따릅니다.",
            "next_month_fortune": f"{target2.year}년 {target2.month}월은 유연한 생각과 솔직한 소통이 운을 돕습니다. 변화를 긍정적으로 받아들이면 길이 열립니다.",
        }
    return {
        "personality": "あなたは観察力と粘り強さを持ち、責任ある場面ほど力を発揮できる人です。日々の小さな積み重ねが自信となり、良い流れを引き寄せます。",
        "year_fortune": f"{this_year}年は、急がず着実に進むことで運が開きます。信頼を積み、学びを行動に変えるほど、周囲からの評価とチャンスが高まります。",
        "month_fortune": f"{target1.year}年{target1.month}月は、落ち着いた判断と丁寧な対話が運を押し上げます。優先順位を整え、一つずつ進めることで良い結果につながります。",
        "next_month_fortune": f"{target2.year}年{target2.month}月は、柔軟さと理解力を活かすほど運が開きます。変化を前向きに受け止めることで、次の成長につながります。",
    }


def _sanitize_fortune_uncertainty(text: str, fallback: str = "") -> str:
    """「確認できませんが」「分かりませんが」等をPDF本文に残さない。"""
    if not isinstance(text, str):
        text = str(text or "")
    s = text.strip()
    if not s:
        return fallback

    patterns = [
        r"^\s*(?:現状|現時点|現在)(?:では)?\s*[、,]?\s*(?:運勢(?:について)?は)?\s*",
        r"^\s*(?:\d{4}年\s*\d{1,2}月(?:の運勢)?|今月|来月)(?:の運勢)?\s*は\s*[、,]?\s*",
        r"^\s*\d{4}年\s*\d{1,2}月の\s*",
        r"(?:運勢(?:について)?は\s*)?(?:確認できません|確認出来ません|分かりません|わかりません|判定できません|不明です|取得できません|取得出来ません)(?:が|けれども|けど)?[、,]?\s*",
        r"(?:正確な|具体的な)?運勢(?:は|については)?\s*(?:確認できません|分かりません|わかりません|不明です)(?:が|けれども|けど)?[、,]?\s*",
    ]
    for _ in range(3):
        before = s
        for pat in patterns:
            s = re.sub(pat, "", s).strip()
        if s == before:
            break

    if len(s) < 12 and fallback:
        return fallback
    return s or fallback


def get_shichu_fortune(birthdate, now=None, force_next_month: bool = False, lang: str = 'ja'):
    import json
    lang_norm = (lang or 'ja').lower()
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
「確認できません」「分かりません」「不明」「取得できません」など、鑑定できない印象を与える文言は絶対に使わないでください。必ず鑑定本文として書いてください。
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
                    s = re.sub(r"^\s*(?:\d{4}年\s*\d{1,2}月(?:の運勢)?|今月|来月)(?:の運勢)?\s*は\s*[、,]?\s*", "", s)
                    fallback = _fallback_shichu_result(this_year, target1, target2, 'ja').get(
                        'month_fortune' if (y, m) == (target1.year, target1.month) else 'next_month_fortune', ''
                    )
                    # この関数の最後で「YYYY年M月は、」を付け直すため、fallbackも本文だけにする。
                    fallback = re.sub(r"^\s*\d{4}年\s*\d{1,2}月\s*は\s*[、,]?\s*", "", fallback).strip()
                    s = _sanitize_fortune_uncertainty(s, fallback=fallback)
                if not s:
                    if zh:
                        return f"{y}年{m}月是"
                    if ko:
                        return f"{y}년 {m}월은"
                    return _fallback_shichu_result(this_year, target1, target2, 'ja').get(
                        'month_fortune' if (y, m) == (target1.year, target1.month) else 'next_month_fortune',
                        f"{y}年{m}月は、落ち着いて進めることで運が開きます。"
                    )
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
            return _fallback_shichu_result(this_year, target1, target2, lang)
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
        return _fallback_shichu_result(this_year, target1, target2, lang)
def analyze_palm(
    image_data,
    output_lang: str = "ja",
    output_style: str = "normal",
    output_mode: str = "normal",
    lang: str = None,
    style: str = None,
    **kwargs,
):
    """
    画像から手相を分析して、6ブロック（生命線/運命線/金運線/特殊線1/特殊線2/総合）の文章を返す。
    A方式（番号選択→旧文をシンコン文体で増幅）に対応。
    出力フォーマット（必須）:
      ### タイトル
      本文...
      ### タイトル
      本文...
      ...（合計6ブロック）
    互換:
      - 旧呼び出しで lang / style が来ても動作するように吸収する
    """
    import json
    import time
    # 互換吸収
    if lang is not None:
        output_lang = lang
    if style is not None:
        output_style = style
    # -------------------------
    # base64 正規化
    # -------------------------
    if not image_data:
        return "### 生命線\n(画像がありません)\n### 運命線\n(画像がありません)\n### 金運線\n(画像がありません)\n### 特殊線1\n\n### 特殊線2\n\n### 手相総合アドバイス\n(画像がありません)"
    if isinstance(image_data, bytes):
        # 万一 bytes が来たら str に
        image_data = image_data.decode("utf-8", errors="ignore")
    if image_data.startswith("data:image"):
        base64data = image_data.split(",", 1)[1]
    else:
        base64data = image_data
    lang_norm = (output_lang or "ja").lower()
    is_en = lang_norm.startswith("en")
    is_zh = lang_norm.startswith(("zh", "cn"))
    is_ko = lang_norm.startswith(("ko", "kr"))
    # -------------------------
    # DB 取得
    # -------------------------
    try:
        from tesou import (
            PALM_DETAIL_BY_ID,
            PALM_DETAIL_INDEX_BY_CATEGORY,
        )
        # 旧追加分の文章も拾えるようにする（存在しない環境でも落ちない）
        try:
            from tesou import tesou_descriptions  # type: ignore
        except Exception:
            tesou_descriptions = {}
    except Exception:
        PALM_DETAIL_BY_ID = {}
        PALM_DETAIL_INDEX_BY_CATEGORY = {}
        tesou_descriptions = {}
    # -------------------------
    # ユーティリティ
    # -------------------------
    def _safe_json_load(text: str):
        if not text:
            return None
        text = text.strip()
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
    def _format_id_name_list(category: str, max_items: int = None) -> str:
        items = PALM_DETAIL_INDEX_BY_CATEGORY.get(category, []) or []
        if max_items is not None and max_items > 0:
            items = items[:max_items]
        if not items:
            return "(no data)"
        return "\n".join([f"{i}: {name}" for i, name in items])
    def _openai_chat_with_retry(**params):
        last_err = None
        for attempt in range(3):
            try:
                return openai.ChatCompletion.create(**params)
            except Exception as e:
                last_err = e
                time.sleep(0.8 * (2 ** attempt))
        raise last_err
    # -------------------------
    # 候補リスト（番号: 名称）
    # -------------------------
    life_list = _format_id_name_list("生命線")
    fate_list = _format_id_name_list("運命線")
    sun_list  = _format_id_name_list("太陽線")   # 金運
    # 特殊線は「特殊な線」カテゴリを基本にする（tesou.py で旧追加分もここへ寄せる）
    special_items = PALM_DETAIL_INDEX_BY_CATEGORY.get("特殊な線", []) or []
    # プロンプト肥大を防ぐため、まずは全件ID+名称のみ。必要なら後で調整。
    special_list = "\n".join([f"{i}: {name}" for i, name in special_items]) if special_items else "(no data)"
    # -------------------------
    # ① 画像判定（番号選択のみ。本文は書かせない）
    # -------------------------
    detect = None
    try:
        detect_system = (
            "You are a strict classifier for palmistry line variants. "
            "You MUST choose IDs from the provided lists only. Output JSON only."
        )
        # ※候補は日本語でもOK。出力は数値IDのみで統一。
        detect_user = f"""
From the following candidate lists, choose:
- life_id: exactly 1 from Life Line list (if subtle/uncertain, prefer a generic life-line variant such as a 兆し/型 variant rather than an iconic exact line like 二重生命線)
- fate_id: exactly 1 from Fate Line list (if subtle/uncertain, prefer a generic fate-line variant such as a 兆し/型 variant rather than a dramatic exact subtype)
- money_sun_id: exactly 1 from Sun Line list (if subtle/uncertain, choose a '兆し' variant rather than 0)
- special_ids: choose exactly 2 IDs from Special list (if subtle/uncertain, choose '兆し' variants; never return empty)
Return JSON ONLY with this schema:
{{
  "life_id": 1,
  "fate_id": 1,
  "money_sun_id": 1,
  "special_ids": [1, 2],
  "notes": "brief visual notes (<= 2 sentences, in the target language)"
}}
Rules:
- IDs must exist in the lists. Never invent.
- special_ids must be unique; length must be 2
- If subtle/uncertain, choose the closest '兆し' (sign) or generic 型 variants from the lists; NEVER output 0 or empty.
- Do NOT overcall iconic exact lines unless the visual evidence is unmistakable.
- Do NOT choose 二重生命線 / 副生命線 unless a clearly parallel support line can be followed for a meaningful span.
- Do NOT choose a dramatic upward/downward subtype of 運命線 unless the directionality is visually clear.
[Life Line candidates]
{life_list}
[Fate Line candidates]
{fate_list}
[Sun Line candidates]
{sun_list}
[Special line candidates]
{special_list}
""".strip()
        resp1 = _openai_chat_with_retry(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": detect_system},
                {"role": "user", "content": [
                    {"type": "text", "text": detect_user},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64data}"}}
                ]}
            ],
            temperature=0.05,
            max_tokens=650,
        )
        raw1 = resp1.choices[0].message["content"]
        detect = _safe_json_load(raw1)
    except Exception:
        detect = None
    # フォールバック（判定が取れない場合は、旧DBガイド方式で6ブロックを作る）
    if not isinstance(detect, dict):
        # 旧ガイド（なるべく長めに、シンコン寄り）
        guide = "\n".join([f"{k}: {v}" for k, v in (tesou_descriptions or {}).items()])
        if is_en:
            sys = (
                "You are a charismatic palm reader. Write vivid, entertaining, and practical English. "
                "Output EXACTLY 6 blocks using the required '###' headings format. "
                "Do not include any Japanese characters."
            )
            user = (
                "Meaning guide (Japanese):\n" + guide + "\n\n"
                "Look at the photo and write a reading in English."
            )
        elif is_zh:
            sys = (
                "你是一位风格鲜明、很会讲故事的手相解读师。语气积极、具体、有娱乐感。"
                "必须按6个区块输出，使用'### 标题'格式。"
            )
            user = "含义指南（日文）:\n" + guide + "\n\n请看图，用简体中文写。"
        elif is_ko:
            sys = (
                "당신은 스토리텔링이 강한 손금 해석가입니다. 긍정적이고 구체적이며 엔터테인먼트 감이 있도록. "
                "반드시 6개 블록을 '### 제목' 형식으로 출력하세요."
            )
            user = "의미 가이드(일본어):\n" + guide + "\n\n사진을 보고 한국어로 작성."
        else:
            sys = (
                "あなたは“シンコン文体”の手相鑑定師です。詩的で断定的、しかし前向きで具体的。"
                "必ず6ブロックを'### タイトル'形式で出力。"
            )
            user = "意味ガイド:\n" + guide + "\n\n画像を見て鑑定。"
        resp = _openai_chat_with_retry(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64data}"}}
                ]}
            ],
            temperature=0.75,
            max_tokens=1400,
        )
        txt = resp.choices[0].message["content"]
        return _ensure_6_blocks(txt, lang_norm)
    # -------------------------
    # ② 旧文を根拠に“シンコン文体で増幅”
    # -------------------------
    def _get_detail(_id: int) -> str:
        try:
            _id = int(_id)
        except Exception:
            return ""
        row = PALM_DETAIL_BY_ID.get(_id, {})
        d = str(row.get("detail", "") or "")
        if not d:
            # 旧追加分（tesou_descriptions）から拾う
            n = str(row.get("name", "") or "")
            if n and n in (tesou_descriptions or {}):
                d = str(tesou_descriptions.get(n, "") or "")
        return d.strip()
    def _get_name(_id: int) -> str:
        try:
            _id = int(_id)
        except Exception:
            return ""
        row = PALM_DETAIL_BY_ID.get(_id, {})
        return str(row.get("name", "") or "").strip()
    life_id = int(detect.get("life_id", 0) or 0)
    fate_id = int(detect.get("fate_id", 0) or 0)
    money_sun_id = int(detect.get("money_sun_id", 0) or 0)
    # Prefer non-zero IDs: if classifier returned 0/invalid, use "兆し" fallback IDs
    # NOTE:
    #  - Fixed single-ID fallbacks cause visible bias (98001/98011/98012). To add entertainment variability,
    #    we choose from a pool of "兆し" variants deterministically based on the image hash.
    FALLBACK_LIFE_IDS = [98101, 98102, 98103, 98104, 98105, 98106, 98107, 98108, 98109, 98110, 98111, 98112]
    FALLBACK_FATE_IDS = [98201, 98202, 98203, 98204, 98205, 98206, 98207, 98208, 98209, 98210, 98211, 98212]
    FALLBACK_SUN_IDS = [98001, 98002, 98003, 98004, 98005, 98006, 98007, 98008, 98009]
    FALLBACK_SPECIAL_IDS = [
        98011, 98012, 98013, 98014, 98015, 98016, 98017, 98018, 98019, 98020,
        98021, 98022, 98023, 98024, 98025,
        98301, 98302, 98303, 98304, 98305, 98306, 98307, 98308, 98309, 98310,
    ]
    # Optional hints to add thematic variety without changing the stable external interface.
    # We will NOT mention I Ching / hexagrams explicitly in the final text; it is used as a subtle "theme".
    iching_hint = kwargs.get("iching_hint") or kwargs.get("iching_result") or ""
    if isinstance(iching_hint, (dict, list)):
        try:
            iching_hint = json.dumps(iching_hint, ensure_ascii=False)
        except Exception:
            iching_hint = str(iching_hint)
    iching_hint = str(iching_hint or "").strip()
    shichu_hint = kwargs.get("shichu_hint") or kwargs.get("shichu_result") or ""
    if isinstance(shichu_hint, (dict, list)):
        try:
            shichu_hint = json.dumps(shichu_hint, ensure_ascii=False)
        except Exception:
            shichu_hint = str(shichu_hint)
    shichu_hint = str(shichu_hint or "").strip()
    kyusei_hint = kwargs.get("kyusei_text") or ""
    if isinstance(kyusei_hint, (dict, list)):
        try:
            kyusei_hint = json.dumps(kyusei_hint, ensure_ascii=False)
        except Exception:
            kyusei_hint = str(kyusei_hint)
    kyusei_hint = str(kyusei_hint or "").strip()
    def _stable_seed(tag: str) -> int:
        """Stable seed derived from the image (base64) + tag. Same photo -> same fallback choice."""
        try:
            prefix = (base64data or "")[:20000]
        except Exception:
            prefix = ""
        theme_bits = "|".join([
            (iching_hint or "")[:300],
            (shichu_hint or "")[:300],
            (kyusei_hint or "")[:200],
        ])
        h = hashlib.sha256((prefix + "|" + (tag or "") + "|" + theme_bits).encode("utf-8", errors="ignore")).hexdigest()
        return int(h[:12], 16)
    def _stable_choice(pool, tag: str, default_id: int):
        pool2 = []
        for i in (pool or []):
            try:
                ii = int(i)
            except Exception:
                continue
            if ii > 0 and ii in PALM_DETAIL_BY_ID:
                pool2.append(ii)
        if not pool2:
            return default_id if default_id in PALM_DETAIL_BY_ID else (pool[0] if pool else 0)
        rnd = random.Random(_stable_seed(tag))
        return rnd.choice(pool2)
    def _stable_sample(pool, k: int, tag: str, exclude=None):
        exclude = set(exclude or [])
        pool2 = []
        for i in (pool or []):
            try:
                ii = int(i)
            except Exception:
                continue
            if ii <= 0:
                continue
            if ii in exclude:
                continue
            if ii not in PALM_DETAIL_BY_ID:
                continue
            pool2.append(ii)
        if not pool2:
            return []
        rnd = random.Random(_stable_seed(tag))
        if len(pool2) <= k:
            # shuffle for variety but keep deterministic
            rnd.shuffle(pool2)
            return pool2[:k]
        return rnd.sample(pool2, k)
    theme_text = "\n".join([
        str(detect.get("notes", "") or "").strip(),
        iching_hint,
        shichu_hint,
        kyusei_hint,
    ])
    def _theme_scores(text: str):
        base = str(text or "")
        groups = {
            "health": ["健康", "体", "回復", "休", "整", "睡眠", "疲", "基盤", "守", "温", "care", "rest", "health"],
            "work": ["仕事", "評価", "目標", "挑戦", "前進", "転機", "責任", "収入", "金運", "career", "work", "success"],
            "social": ["恋", "愛", "人気", "魅力", "縁", "出会", "人間関係", "紹介", "口コミ", "relationship", "love", "people"],
            "creative": ["直感", "感性", "表現", "芸術", "創作", "ひらめき", "spirit", "creative", "intuition"],
            "move": ["移動", "変化", "再出発", "旅行", "海外", "新しい", "change", "move", "travel"],
        }
        scores = {k: 0 for k in groups}
        for tag, keywords in groups.items():
            for kw in keywords:
                try:
                    scores[tag] += base.lower().count(str(kw).lower())
                except Exception:
                    pass
        return scores
    def _ranked_tags(text: str):
        scores = _theme_scores(text)
        ranked = [k for k, v in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if v > 0]
        return ranked or ["work", "health", "social"]
    THEME_POOLS = {
        "life": {
            "health": [98101, 98102, 98105, 98106, 98109, 98111, 98112],
            "work": [98104, 98107, 98109, 98110],
            "social": [98106, 98108, 98110],
            "creative": [98103, 98108, 98111],
            "move": [98104, 98108, 98111],
        },
        "fate": {
            "health": [98201, 98207, 98210],
            "work": [98201, 98202, 98205, 98207, 98209, 98212],
            "social": [98203, 98206, 98211, 98212],
            "creative": [98208, 98209, 98212],
            "move": [98204, 98208, 98210],
        },
        "sun": {
            "health": [98005, 98006],
            "work": [98001, 98002, 98004, 98005, 98006, 98008],
            "social": [98004, 98007, 98009],
            "creative": [98003, 98008, 98009],
            "move": [98007, 98008],
        },
        "special": {
            "health": [98011, 98014, 98019, 98025, 98304, 98306],
            "work": [98015, 98018, 98022, 98024, 98301, 98302, 98305],
            "social": [98013, 98021, 98023, 98303, 98306, 98308, 98310],
            "creative": [98012, 98016, 98017, 98021, 98025, 98309],
            "move": [98020, 98022, 98303, 98307],
        },
    }
    def _themed_pool(kind: str, base_pool):
        ordered = []
        seen = set()
        for tag in _ranked_tags(theme_text):
            for ii in THEME_POOLS.get(kind, {}).get(tag, []):
                if ii in base_pool and ii not in seen and ii in PALM_DETAIL_BY_ID:
                    ordered.append(ii)
                    seen.add(ii)
        for ii in base_pool:
            if ii not in seen and ii in PALM_DETAIL_BY_ID:
                ordered.append(ii)
                seen.add(ii)
        return ordered
    def _family_from_id(_id: int) -> str:
        try:
            _id = int(_id)
        except Exception:
            return "other"
        name = _get_name(_id)
        if any(k in name for k in ["生命", "守護", "仏眼", "健康", "家庭"]):
            return "protect"
        if any(k in name for k in ["人気", "金星", "魅力", "相談", "影響"]):
            return "social"
        if any(k in name for k in ["旅行", "海外", "出発", "引き立て", "発展"]):
            return "move"
        if any(k in name for k in ["ソロモン", "覇王", "努力", "向上", "財運", "ますかけ"]):
            return "power"
        if any(k in name for k in ["直感", "神秘", "スター", "芸術", "フィッシュ"]):
            return "spirit"
        return "other"
    life_pool = _themed_pool("life", FALLBACK_LIFE_IDS)
    fate_pool = _themed_pool("fate", FALLBACK_FATE_IDS)
    sun_pool = _themed_pool("sun", FALLBACK_SUN_IDS)
    special_pool = _themed_pool("special", FALLBACK_SPECIAL_IDS)
    if life_id <= 0 or life_id not in PALM_DETAIL_BY_ID:
        life_id = _stable_choice(life_pool, "life", default_id=98101)
    elif life_id in FALLBACK_LIFE_IDS:
        life_id = _stable_choice(life_pool, "life_remap", default_id=life_id)
    if fate_id <= 0 or fate_id not in PALM_DETAIL_BY_ID:
        fate_id = _stable_choice(fate_pool, "fate", default_id=98201)
    elif fate_id in FALLBACK_FATE_IDS:
        fate_id = _stable_choice(fate_pool, "fate_remap", default_id=fate_id)
    if money_sun_id <= 0 or money_sun_id not in PALM_DETAIL_BY_ID:
        money_sun_id = _stable_choice(sun_pool, "sun", default_id=98001)
    elif money_sun_id in FALLBACK_SUN_IDS:
        # If the classifier keeps returning the same generic "兆し" ID, diversify within the sign-level pool.
        money_sun_id = _stable_choice(sun_pool, "sun_remap", default_id=money_sun_id)
    notes = str(detect.get("notes", "") or "").strip()
    special_ids = detect.get("special_ids", [])
    if not isinstance(special_ids, list):
        special_ids = []
    # 正規化
    special_clean = []
    for x in special_ids:
        try:
            xi = int(x)
        except Exception:
            continue
        if xi <= 0:
            continue
        if xi not in special_clean:
            special_clean.append(xi)
        if len(special_clean) >= 2:
            break
    # If the classifier keeps returning only the same weak/generic pair, diversify within the broader themed pool.
    if special_clean and all(x in (98011, 98012, 98019) for x in special_clean):
        special_clean = _stable_sample(special_pool, 2, tag="special_remap", exclude=[])
    # Avoid showing two specials from the same family too often (e.g. 守護線 + 二重生命線).
    diversified = []
    used_families = set()
    for sid in special_clean:
        fam = _family_from_id(sid)
        if fam not in used_families or fam == "other":
            diversified.append(sid)
            used_families.add(fam)
    special_clean = diversified[:]
    # Ensure we always have 2 special IDs (avoid 0/empty): fill from themed pool, preferring a different family.
    for sid in special_pool:
        if len(special_clean) >= 2:
            break
        fam = _family_from_id(sid)
        if sid in special_clean:
            continue
        if fam in used_families and fam != "other":
            continue
        if sid in PALM_DETAIL_BY_ID:
            special_clean.append(sid)
            used_families.add(fam)
    # If still short, fill deterministically ignoring family.
    need = 2 - len(special_clean)
    if need > 0:
        fill = _stable_sample(special_pool, need, tag="special", exclude=special_clean)
        special_clean.extend(fill)
    # Last-resort safety
    for _fid in (98011, 98012, 98301):
        if len(special_clean) >= 2:
            break
        if _fid in PALM_DETAIL_BY_ID and _fid not in special_clean:
            special_clean.append(_fid)
# legacy payload
    legacy = {
        "life": {"id": life_id, "name": _get_name(life_id), "text": _get_detail(life_id)},
        "fate": {"id": fate_id, "name": _get_name(fate_id), "text": _get_detail(fate_id)},
        "money": {"id": money_sun_id, "name": _get_name(money_sun_id), "text": _get_detail(money_sun_id)},
        "special1": {"id": special_clean[0] if len(special_clean) >= 1 else 0,
                     "name": _get_name(special_clean[0]) if len(special_clean) >= 1 else "",
                     "text": _get_detail(special_clean[0]) if len(special_clean) >= 1 else ""},
        "special2": {"id": special_clean[1] if len(special_clean) >= 2 else 0,
                     "name": _get_name(special_clean[1]) if len(special_clean) >= 2 else "",
                     "text": _get_detail(special_clean[1]) if len(special_clean) >= 2 else ""},
    }
    # 目標文字量（PDFに収まる“中〜やや多め”）
    if is_en:
        length_rule = (
            "- Each of the 5 line sections: 90-130 words.\n"
            "- Overall: 120-170 words.\n"
            "- Use ONLY English characters (no Japanese/Chinese/Korean characters).\n"
        )
    elif is_zh:
        length_rule = (
            "- 生命线/命运线/金运线/特殊线1/特殊线2：每段约140-220个汉字。\n"
            "- 综合：约180-280个汉字。\n"
        )
    elif is_ko:
        length_rule = (
            "- 각 항목(5개): 160~240자.\n"
            "- 종합: 200~320자.\n"
        )
    else:
        length_rule = (
            "- 生命線/運命線/金運線/特殊線1/特殊線2：各200〜300文字。\n"
            "- 総合：240〜360文字。\n"
        )
    # 見出し（PDFにIDを残す：B方式）
    if is_en:
        heading_spec = (
            "Use these 6 headings exactly, and keep [ID:..] in the heading:\n"
            "### Life Line [ID:..]\n"
            "### Fate Line [ID:..]\n"
            "### Money Line [ID:..]\n"
            "### Special Line 1 [ID:..]\n"
            "### Special Line 2 [ID:..]\n"
            "### Overall Palm Reading\n"
        )
    elif is_zh:
        heading_spec = (
            "必须使用以下6个标题（保留ID）：\n"
            "### 生命线 [ID:..]\n"
            "### 命运线 [ID:..]\n"
            "### 金运线 [ID:..]\n"
            "### 特殊线1 [ID:..]\n"
            "### 特殊线2 [ID:..]\n"
            "### 手相总体建议\n"
        )
    elif is_ko:
        heading_spec = (
            "반드시 아래 6개 제목을 사용(ID 유지):\n"
            "### 생명선 [ID:..]\n"
            "### 운명선 [ID:..]\n"
            "### 금운선 [ID:..]\n"
            "### 특수선 1 [ID:..]\n"
            "### 특수선 2 [ID:..]\n"
            "### 손금 종합 조언\n"
        )
    else:
        heading_spec = (
            "必ず以下の6見出し（IDを残す）で出力してください：\n"
            "### 生命線 [ID:..]\n"
            "### 運命線 [ID:..]\n"
            "### 金運線 [ID:..]\n"
            "### 特殊線1 [ID:..]\n"
            "### 特殊線2 [ID:..]\n"
            "### 手相総合アドバイス\n"
        )
    # Shincom tone
    if is_en:
        sys = (
            "You are 'Shincom' palmistry: vivid, confident, poetic, and customer-friendly. "
            "Use ONLY the provided legacy texts as factual basis, then expand in a captivating style. "
            "Never mention databases, lists, IDs in the body (IDs are allowed only inside headings). "
            "Do not fabricate specific events; keep advice actionable. If JSON includes 'iching_hint', use it as a subtle theme to color metaphors and action tips, but do NOT mention I Ching/hexagrams explicitly."
        )
    elif is_zh:
        sys = (
            "你是“シンコン风格”的手相解读师：有画面感、带一点诗意、语气肯定但温和，"
            "同时给出可执行的建议。只能以提供的旧文为根拠进行扩写，不要提编号/数据库/候选列表。若 JSON 中包含 'iching_hint'，将其作为“暗主题”融入比喻与行动建议，但不要在正文中提到易经/卦名等术语。"
        )
    elif is_ko:
        sys = (
            "당신은 '신콘 스타일' 손금 해석가입니다: 시적이고 단정적이지만 따뜻하고 현실적인 조언. "
            "제공된 '레거시 텍스트'를 근거로만 확장하세요. 본문에서 ID/DB/목록 언급 금지. JSON에 'iching_hint'가 있으면 은근한 테마로 비유와 행동 조언에 섞되, 주역/괘 등 용어는 본문에 쓰지 마세요."
        )
    else:
        sys = (
            "あなたは“シンコン文体”の手相鑑定師です。"
            "詩的で断定的（『あなたは〜です』）に語りつつ、必ず前向きで実践的なアドバイスで着地してください。"
            "与えた旧文（レガシー本文）を根拠に増幅し、本文でID/番号/DB/候補一覧の話は一切しないこと。JSONにiching_hintがあれば“裏テーマ”として比喩や行動提案に薄く混ぜ、本文で『易』『イーチン』『卦』などの語は出さない。"
        )
    # special=0 の時は「無い」と言わず、伸ばすための一般的な“魅力”を描く
    none_special_rule = (
        "If a special line ID is 0, write that section as a positive 'hidden potential' message, "
        "without saying it is absent.\n"
        if is_en else
        "特殊線IDが0の場合は、その項目は“隠れた強み・伸びしろ”として前向きに書き、"
        "『ない』『見えない』等の否定表現は書かない。\n"
    )
    user_payload = {
        "lang": output_lang,
        "style": output_style,
        "notes": notes,
        "iching_hint": iching_hint,
        "legacy": legacy,
    }
    user = (
        "You will write a palm reading based on the following JSON.\n"
        if is_en else
        "以下のJSONを根拠に鑑定文を書いてください。\n"
    ) + json.dumps(user_payload, ensure_ascii=False, indent=2)
    instruction = (
        f"\n\n{heading_spec}\n"
        f"Length rules:\n{length_rule}\n"
        f"{none_special_rule}\n"
        "Rules:\n"
        "- Output MUST be exactly 6 blocks, each starting with '### '.\n"
        "- Headings must include the proper [ID:..] where required.\n"
        "- Do NOT include '###' inside the body text.\n"
    )
    # ここは1回で生成（6ブロックまとめて）
    try:
        resp2 = _openai_chat_with_retry(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user + instruction},
            ],
            temperature=0.85 if not is_en else 0.8,
            max_tokens=2200,
        )
        txt = resp2.choices[0].message["content"]
    except Exception:
        # API失敗時: 旧文をそのまま6ブロック化（最低限）
        txt = _fallback_6_blocks_from_legacy(legacy, lang_norm)
    return _ensure_6_blocks(txt, lang_norm)
# -------------------------
# ensure helpers (local-only)
# -------------------------
def _ensure_6_blocks(text: str, lang_norm: str) -> str:
    """Return a safe string with exactly 6 blocks using '### ' headings."""
    if not text:
        return _fallback_6_blocks_from_legacy({}, lang_norm)
    # normalize
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    # If user accidentally used 【】 headings, convert to ### style (best-effort)
    if "### " not in text and "【" in text:
        text = re.sub(r"^【([^】]+)】\s*$", r"### \1", text, flags=re.M)
    blocks = [b for b in text.split("### ") if b.strip()]
    if len(blocks) < 6:
        # try to split by heading-like lines
        # fallback to legacy-style blocks
        return _fallback_6_blocks_from_legacy({}, lang_norm)
    # keep first 6
    blocks = blocks[:6]
    out = []
    for b in blocks:
        b = b.strip("\n")
        lines = b.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        # sanitize
        title = re.sub(r"\s+", " ", title)
        body = body.replace("###", "").strip()
        out.append(f"### {title}\n{body}".strip())
    return "\n\n".join(out)
def _fallback_6_blocks_from_legacy(legacy: dict, lang_norm: str) -> str:
    """Minimal fallback: build 6 blocks from legacy texts."""
    def pick(k, default_title, default_body):
        try:
            v = legacy.get(k, {})
            _id = int(v.get("id", 0) or 0)
            t = (v.get("text", "") or "").strip()
        except Exception:
            _id, t = 0, ""
        title = default_title + (f" [ID:{_id}]" if _id else " [ID:0]")
        body = t if t else default_body
        return f"### {title}\n{body}"
    if lang_norm.startswith("en"):
        return "\n\n".join([
            pick("life", "Life Line", "We couldn't clearly read this from the photo. Please retake with better lighting."),
            pick("fate", "Fate Line", "We couldn't clearly read this from the photo. Please retake with better lighting."),
            pick("money", "Money Line", "We couldn't clearly read this from the photo. Please retake with better lighting."),
            pick("special1", "Special Line 1", "Your hand suggests quiet strengths that grow with consistent habits."),
            pick("special2", "Special Line 2", "Your hand suggests quiet strengths that grow with consistent habits."),
            "### Overall Palm Reading\nFocus on one small habit you can keep daily; that is where your luck compounds.",
        ])
    if lang_norm.startswith(("zh", "cn")):
        return "\n\n".join([
            pick("life", "生命线", "图片无法清晰判断。建议在光线更明亮、对焦更清晰时重新拍摄。"),
            pick("fate", "命运线", "图片无法清晰判断。建议在光线更明亮、对焦更清晰时重新拍摄。"),
            pick("money", "金运线", "图片无法清晰判断。建议在光线更明亮、对焦更清晰时重新拍摄。"),
            pick("special1", "特殊线1", "你的手相更像是“厚积薄发型”，越坚持越走运。"),
            pick("special2", "特殊线2", "你的手相更像是“厚积薄发型”，越坚持越走运。"),
            "### 手相总体建议\n把目标拆成可执行的小步骤，坚持一周，你会明显感觉到运势在上升。",
        ])
    if lang_norm.startswith(("ko", "kr")):
        return "\n\n".join([
            pick("life", "생명선", "사진에서 선이 선명하지 않습니다. 조명/초점을 맞춰 다시 촬영해 주세요."),
            pick("fate", "운명선", "사진에서 선이 선명하지 않습니다. 조명/초점을 맞춰 다시 촬영해 주세요."),
            pick("money", "금운선", "사진에서 선이 선명하지 않습니다. 조명/초점을 맞춰 다시 촬영해 주세요."),
            pick("special1", "특수선 1", "당신은 꾸준함이 쌓일수록 운이 크게 열리는 타입입니다."),
            pick("special2", "특수선 2", "당신은 꾸준함이 쌓일수록 운이 크게 열리는 타입입니다."),
            "### 손금 종합 조언\n작은 습관 하나를 7일만 유지해 보세요. 그 지점에서 운이 ‘증폭’됩니다.",
        ])
    return "\n\n".join([
        pick("life", "生命線", "画像から判定できませんでした。明るい場所で再撮影してください。"),
        pick("fate", "運命線", "画像から判定できませんでした。明るい場所で再撮影してください。"),
        pick("money", "金運線", "画像から判定できませんでした。明るい場所で再撮影してください。"),
        pick("special1", "特殊線1", "あなたは“積み上げた分だけ運が跳ねる”タイプです。"),
        pick("special2", "特殊線2", "あなたは“積み上げた分だけ運が跳ねる”タイプです。"),
        "### 手相総合アドバイス\n今週は『一つだけ』決めて、毎日積む。そこから現実が動きます。",
    ])
def get_iching_advice(lang: str = 'ja'):
    try:
        lang_norm = (lang or 'ja').lower()
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
    lang_norm = (lang or 'ja').lower()
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
    lang_norm = (lang or 'ja').lower()
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
    iching_result = get_iching_advice(lang=lang)
    shichu_result_raw = get_shichu_fortune(birthdate, now=now, force_next_month=force_next_month, lang=lang)
    palm_result = analyze_palm(
        image_data,
        output_lang=lang,
        output_style=style,
        output_mode=kwargs.get('output_mode','normal'),
        iching_hint=iching_result,
        shichu_hint=shichu_result_raw,
        kyusei_text=kyusei_text,
        birthdate=birthdate,
    )
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
        fallback_shichu = _fallback_shichu_result(target1.year, target1, target2, lang)
        shichu_texts = {
            "personality": _sanitize_fortune_uncertainty(shichu_result_raw.get("personality", ""), fallback=fallback_shichu.get("personality", "")),
            "year_fortune": _sanitize_fortune_uncertainty(shichu_result_raw.get("year_fortune", ""), fallback=fallback_shichu.get("year_fortune", "")),
            "month_fortune": _sanitize_fortune_uncertainty(shichu_result_raw.get("month_fortune", ""), fallback=fallback_shichu.get("month_fortune", "")),
            "next_month_fortune": _sanitize_fortune_uncertainty(shichu_result_raw.get("next_month_fortune", ""), fallback=fallback_shichu.get("next_month_fortune", ""))
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
    lang_norm = (lang or 'ja').lower()
    if lang_norm.startswith("en"):
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
    elif lang_norm.startswith(("zh", "cn")):
        fallback_titles = [
            "生命线",
            "头脑线",
            "感情线",
            "特殊线 1",
            "特殊线 2",
            "手相总体建议",
        ]
        fallback_text = "※从图片中无法清晰判断该项目。建议在更明亮、对焦清晰的环境重新拍摄。"
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
