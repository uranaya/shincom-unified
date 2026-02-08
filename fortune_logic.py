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
追加ルール：
- 『例えば』は禁止。
- 『かもしれません』『でしょう』『可能性』は多用しない（各項目1回以内）。
- 断定は柔らかく、根拠→具体策1つ→安心の締め、の流れで書く。

- 禁止：『例えば』
- 曖昧語（かもしれません/でしょう/可能性）の多用は禁止（各項目1回以内）
- 各項目は『結論→理由→具体策1つ』で、読み手が動ける形にしてください。
"""
        # ----------------------------
        # Style add-on (JA-only): Yuta-like safe tone
        # ----------------------------
        if (not is_en) and (not is_zh) and (not is_ko):
            s = (style or 'normal').strip().lower()
            if s == 'yuta_safe':
                prompt += (
                    "\n\n【追加スタイル：ユタ調・安全版】\n"
                    "- 目的：内容（意味・事実関係）は変えず、温かい口語の“語り”に整える。\n"
                    "- リズム：短文中心で『結論→理由→具体策1つ→安心の締め』。\n"
                    "- 口調：導入は『うん、今ね、』/『ほら、今はね、』のように話しかける。断定は柔らかく。\n"
                    "- 方言：『〜さ』『〜だよ』は“段落に1回まで”。毎文末に付けない。『さぁ』は使わない。\n"
                    "- 禁止：霊・呪い・祟り・除霊・先祖の断定／病気・死／恐怖を煽る言い方。\n"
                    "- 最後：必ず『大丈夫。』など安心させる一文で締める。\n"
                )
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


def analyze_palm(image_data, lang: str = 'ja', style: str = 'normal'):
    try:
        lang_norm = (lang or 'ja').lower()
        is_en = lang_norm.startswith('en')
        is_zh = lang_norm.startswith('zh') or lang_norm.startswith('cn')
        is_ko = lang_norm.startswith('ko') or lang_norm.startswith('kr')
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
        if is_en:
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
        elif is_zh:
            system_prompt = (
                "你是一位专业的手相解读师。请根据以下约束，从手相图像中解读并用温暖、鼓励的语气写给顾客。\n\n"
                "[输出规则]\n"
                "- 必须包含：1) 生命线 2) 命运线 3) 金钱线\n"
                "- 另外选择两条‘特殊线’，尽量从下面列表中选（即使是细微迹象也可以，但要用积极的方式表达）：\n"
                f"{special_lines_text}\n"
                "- 若确实无法选出两条特殊线，可自然地用感情线/头脑线替代\n\n"
                "[含义参考]\n"
                f"{description_text}\n\n"
                "请用自然的简体中文，不要用‘没有/缺乏’等否定措辞，尽量写成潜力与倾向。"
            )
            user_prompt = (
                "请严格按以下格式输出：\n"
                "### 1. 生命线\n（约 150–220 字）\n\n"
                "### 2. 命运线\n（约 150–220 字）\n\n"
                "### 3. 金钱线\n（约 150–220 字）\n\n"
                "### 4. 特殊线 1\n（约 150–220 字）\n\n"
                "### 5. 特殊线 2\n（约 150–220 字）\n\n"
                "### 总体建议\n（温柔、积极的收尾）\n\n"
                "- 文风可以略带诗意但要清晰\n"
                "- 结尾给出1条可执行的小建议"
            )

        elif is_ko:
            system_prompt = (
                "당신은 프로 손금 감정가입니다. 아래 조건을 지켜 손금 이미지를 해석하고, 따뜻하고 고무적인 톤으로 작성하세요.\n\n"
                "[출력 규칙]\n"
                "- 반드시 포함: 1) 생명선 2) 운명선 3) 금전선\n"
                "- 추가로 '특수선' 2개를 아래 목록에서 가급적 선택 (미묘해도 긍정적으로 표현 가능):\n"
                f"{special_lines_text}\n"
                "- 정말로 특수선을 2개 고르기 어렵다면, 자연스럽게 감정선/두뇌선을 사용해도 됩니다\n\n"
                "[의미 가이드]\n"
                f"{description_text}\n\n"
                "한국어로 자연스럽고 고객 친화적으로 작성하세요. '없다/부족하다' 같은 부정 표현은 피하고 잠재력으로 재구성하세요."
            )
            user_prompt = (
                "아래 형식을 반드시 지켜 출력하세요:\n"
                "### 1. 생명선\n(약 150–220자)\n\n"
                "### 2. 운명선\n(약 150–220자)\n\n"
                "### 3. 금전선\n(약 150–220자)\n\n"
                "### 4. 특수선 1\n(약 150–220자)\n\n"
                "### 5. 특수선 2\n(약 150–220자)\n\n"
                "### 종합 조언\n(부드럽고 긍정적인 마무리)\n\n"
                "- 문체는 약간 시적이어도 좋지만 명확하게\n"
                "- 마지막에 실행 가능한 작은 조언 1개를 포함"
            )
        else:
            system_prompt = (
                "あなたはプロの手相鑑定士です。手相画像を読み取り、鑑定文を日本語で作成してください。\n\n"
                "【最重要ルール】\n"
                "1) 仮定・あいまい表現は禁止：『もし』『〜なら』『かもしれない』『可能性』『〜があれば/あるなら』『例えば』を使わない\n"
                "2) 画像から読み取った事実として描写し、『〜が見えます』『〜が出ています』『〜と読めます』で言い切る\n"
                "3) 同じ内容の言い換え反復は禁止（各項目は一度で言い切る）\n"
                "4) ネガティブ断定は禁止。課題は『整えるコツ』『伸びしろ』として優しく示す\n\n"
                "【出力構成】\n"
                "・1. 生命線、2. 運命線、3. 金運線は必ず含める\n"
                "・4. 特殊線1、5. 特殊線2は以下の候補から優先して選ぶ（候補外は原則選ばない）:\n"
                f"{special_lines_text}\n"
                "・生命線/運命線/金運線は、形状タグを最低1つ入れる（例：長い/短い/濃い/薄い/途切れ/枝分かれ/二重/鎖状）\n\n"
                "【各線の意味ガイド】\n"
                f"{description_text}\n\n"
                "読み手が安心して前向きになれるよう、やさしく詩的だが具体的な文章でまとめてください。"
            )
            # Style add-on (JA-only): Yuta-like safe tone
            s = (style or 'normal').strip().lower()
            if s == 'yuta_safe':
                system_prompt += (
                    "\n\n【追加スタイル：ユタ調・安全版】\n"
                    "- 目的：内容（意味・事実関係）は変えず、温かい口語の“語り”に整える。\n"
                    "- リズム：各項目は『結論→理由→今日からの具体策1つ』。短文中心。\n"
                    "- 口調：段落冒頭の呼びかけは“全体で1〜2回まで”。語尾の連打は禁止。\n"
                    "- 方言：『〜さ』『〜だよ』は“段落に1回まで”。毎文末に付けない。『さぁ』は使わない。\n"
                    "- 禁止：霊・呪い・祟り・除霊・先祖の断定／病気・死／恐怖を煽る言い方。\n"
                    "- 禁止語：『例えば』。曖昧語（かもしれません/でしょう/可能性）の多用も禁止（各項目1回以内）。\n"
                    "- 最後：Overall Advice の最後は必ず『大丈夫。』など安心させる一文で締める。\n"
                )
            response = openai.ChatCompletion.create(
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
        raw = response.choices[0].message.content.strip()
        # Post-process to reduce hedge wording and duplicate lines (especially Japanese)
        def _polish_palm_text(t: str) -> str:
            if not t:
                return t
            # remove common hedge starters
            t = t.replace('もし', '')
            t = t.replace('例えば、', '')
            t = t.replace('例えば', '')
            t = t.replace('かもしれません', 'です')
            t = t.replace('でしょう', 'です')
            t = t.replace('可能性があります', '傾向があります')
            t = t.replace('可能性が高い', '傾向が強い')
            t = t.replace('例えば、', '')
            t = t.replace('例えば', '')
            t = t.replace('かもしれません', 'でしょう')
            t = t.replace('可能性があります', '傾向があります')
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
        print("❌ Vision APIエラー:", e)
        return "手相診断中にエラーが発生しました。"




def get_iching_advice(lang: str = 'ja', style: str = 'normal'):
    try:
        lang_norm = (lang or 'ja').lower()
        if lang_norm.startswith('en'):
            prompt = "You are an I Ching advisor. Give a gentle, positive message the customer needs right now in natural English (about 180–220 characters)."
        elif lang_norm.startswith('zh') or lang_norm.startswith('cn'):
            prompt = "你是一位易经占卜顾问。请用温柔、积极、可执行的语气，给出当下最需要的一段提醒（约150–220字，简体中文）。不要出现任何卦名或术语。"
        elif lang_norm.startswith('ko') or lang_norm.startswith('kr'):
            prompt = "당신은 주역(I Ching) 조언자입니다. 지금 고객에게 필요한 메시지를 따뜻하고 긍정적이며 실행 가능하게 한국어로 150–220자 정도로 전해주세요. 괘명이나 전문 용어는 절대 쓰지 마세요."
        else:
            prompt = "あなたは易占いの専門家です。今の相談者に必要なメッセージを、200文字で優しく前向きに教えてください。
追加ルール：『例えば』は禁止。『かもしれません』『でしょう』『可能性』は多用せず、結論→理由→具体策1つ→安心で締める。
- 禁止：例えば
- 曖昧語（かもしれません/でしょう/可能性）の多用は禁止
- 結論→理由→具体策1つ→安心、で締める"
        # Style add-on (JA-only)
        if (lang_norm.startswith('ja') or lang_norm == ''):
            s = (style or 'normal').strip().lower()
            if s == 'yuta_safe':
                prompt += (
                    "\n\n【追加スタイル：ユタ調・安全版】\n"
                    "- 目的：内容（意味・事実関係）は変えず、温かい口語の“語り”に整える。\n"
                    "- リズム：短文中心で『結論→理由→具体策1つ→安心の締め』。\n"
                    "- 方言：『〜さ』『〜だよ』は“段落に1回まで”。毎文末に付けない。『さぁ』は使わない。\n"
                    "- 禁止：霊・呪い・祟り・除霊・先祖の断定／病気・死／恐怖を煽る言い方。\n"
                    "- 最後：必ず『大丈夫。』など安心させる一文で締める。\n"
                )
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
            t = t.replace('例えば、', '')
            t = t.replace('例えば', '')
            t = t.replace('かもしれません', 'です')
            t = t.replace('でしょう', 'です')
            t = t.replace('可能性があります', '傾向があります')
            t = t.replace('可能性が高い', '傾向が強い')
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
    palm_result = analyze_palm(image_data, lang=lang, style=style)
    shichu_result_raw = get_shichu_fortune(birthdate, now=now, force_next_month=force_next_month, style=style, lang=lang)
    iching_result = get_iching_advice(lang=lang, style=style)
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
	        iching_result = get_iching_advice(lang=lang, style=style)
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