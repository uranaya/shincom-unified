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
    # 2. テーマ別アドバイス（3項目）
    # =========================
    from .fortune_logic import get_iching_advice if False else None  # ダミー（実際にはファイル先頭の get_iching_advice を使用）

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
            topic_sections.append(
                {"title": topic, "content": f"（この項目の取得エラー: {e}）"}
            )

    # =========================
    # 3. 今年／今月／来月（20日境）
    # =========================
    try:
        today = datetime.today()

        # 20日境で基準月 base を決める
        base = today.replace(day=15)
        if today.day >= 20:
            base += relativedelta(months=1)

        this_year = base.year      # 今年 → 基準月の属する年
        this_month = base.month    # 今月 → 基準月の月

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
        # 年・月情報が titles で必要になるので、fallback の場合も base を元に一応セット
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
        # 仕様に合わせて: nicchu_eto, birthdate, age, shichu_result(=year_love), kyusei_text
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
