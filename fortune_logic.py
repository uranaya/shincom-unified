import openai
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tesou import tesou_names, tesou_descriptions
from nicchu_utils import get_nicchu_eto
from tsuhensei_utils import get_tsuhensei_for_year, get_tsuhensei_for_date
from lucky_utils import generate_lucky_info, generate_lucky_direction
from yearly_love_fortune_utils import generate_yearly_love_fortune

# Four Pillars (Shichu) fortune via GPT
def get_shichu_fortune(birthdate):
    eto = get_nicchu_eto(birthdate)
    try:
        today = datetime.today()
        this_year = today.year
        # Determine target months for fortune (20th cutoff for switching to next month)
        target1 = today.replace(day=15)
        if today.day >= 20:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)
        # Compute Tsuhensei (element) for year and the two target months
        tsuhen_year = get_tsuhensei_for_year(birthdate, this_year)
        tsuhen_month1 = get_tsuhensei_for_date(birthdate, target1.year, target1.month)
        tsuhen_month2 = get_tsuhensei_for_date(birthdate, target2.year, target2.month)

        prompt = f"""あなたは四柱推命の専門家です。
- 日柱: {eto}
- 年の通変星: {tsuhen_year}
- {target1.year}年{target1.month}月の通変星: {tsuhen_month1}
- {target2.year}年{target2.month}月の通変星: {tsuhen_month2}

以下の4つの項目について、それぞれ300文字以内で鑑定してください。
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
        # Return placeholder text for each section if error
        return (f"■ 性格\n取得できませんでした\n"
                f"■ {today.year}年の運勢\n取得できませんでした\n"
                f"■ {target1.year}年{target1.month}月の運勢\n取得できませんでした\n"
                f"■ {target2.year}年{target2.month}月の運勢\n取得できませんでした")

# Analyze palm lines via rules/lookup (no AI needed for palm reading text)
def analyze_palm(image_data):
    # For simplicity, use a rule-based interpretation from tesou module
    # (tesou_names and tesou_descriptions are lists of palm line names and meanings)
    results = []
    for name, desc in zip(tesou_names, tesou_descriptions):
        results.append(f"◆ {name}\n{desc}")
    # Combine results and mark end of sections with separator "###"
    return "### ".join(results)

# I Ching advice via GPT
def get_iching_advice():
    try:
        prompt = ("あなたは易経の専門家です。易占の結果に基づき、"
                  "相談者へのアドバイスを100文字で教えてください。")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ 易経アドバイス取得失敗:", e)
        return "（易経からのアドバイス取得に失敗しました）"

# Generate full fortune (normal mode)
def generate_fortune(image_data, birthdate, kyusei_text):
    # Palm reading (rule-based)
    palm_result = analyze_palm(image_data)
    # Four Pillars fortune (AI)
    shichu_result = get_shichu_fortune(birthdate)
    # I Ching advice (AI)
    iching_result = get_iching_advice()
    # Age for lucky info prompt
    age = datetime.today().year - int(birthdate[:4])
    # Day-pillar zodiac (日柱干支)
    nicchu_eto = get_nicchu_eto(birthdate)
    # Lucky items (AI)
    lucky_info = generate_lucky_info(nicchu_eto, birthdate, age, palm_result, shichu_result, kyusei_text)
    return palm_result, shichu_result, iching_result, lucky_info

# Generate full love fortune (compatibility and love luck)
def generate_renai_fortune(user_birth: str, partner_birth: str = None, include_yearly: bool = False) -> dict:
    from dateutil.relativedelta import relativedelta
    user_eto = get_nicchu_eto(user_birth)
    partner_eto = get_nicchu_eto(partner_birth) if partner_birth else None

    # Prepare prompts for compatibility and future (or personality if no partner)
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
        comp_text = f"（相性診断エラー: {e}）"
        future_text = ""

    # Love-specific I Ching insight for themes
    iching_result = get_iching_advice()
    themes = []
    for topic in ["恋愛の障害と乗り越え方", "相手との距離感・深め方", "結婚"]:
        try:
            topic_prompt = (f"あなたは恋愛占いの専門家です。\n- あなたの日柱: {user_eto}")
            if partner_eto:
                topic_prompt += f"\n- お相手の日柱: {partner_eto}"
            topic_prompt += (f"\n- 易占いからの示唆：{iching_result}\n\n"
                             f"以下の条件で「{topic}」についてアドバイスしてください：\n\n"
                             "・相談者の傾向（日柱）と、易の示唆を元にした、個別性の高い具体的な鑑定にする\n"
                             "・200文字以内\n"
                             "・現実的で誠実だが希望が持てる言葉で\n"
                             "・一般論や抽象的な助言ではなく、読み手に刺さるような内容にする\n")
            topic_text = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": topic_prompt}],
                max_tokens=600,
                temperature=0.9
            ).choices[0].message.content.strip()
            themes.append({"title": topic, "content": topic_text})
        except Exception as e:
            themes.append({"title": topic, "content": f"（この項目の取得エラー: {e}）"})

    # Current year and month love fortunes
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

    # Retrieve yearly love fortunes if requested
    yearly_love_fortunes = {}
    if include_yearly:
        try:
            yearly_love_fortunes = generate_yearly_love_fortune(user_birth, datetime.now())
            print("✅ 年運データ取得:", yearly_love_fortunes)
        except Exception as e:
            print(f"❌ 年運取得失敗: {e}")

    # Lucky items and direction for love (using current year fortune text as context)
    try:
        birth_date_obj = datetime.strptime(user_birth, "%Y-%m-%d")
        age = datetime.today().year - birth_date_obj.year - ((datetime.today().month, datetime.today().day) < (birth_date_obj.month, birth_date_obj.day))
        # Lucky direction text (Nine-Star Ki) for love - uses same generate_lucky_direction function
        kyusei_text = generate_lucky_direction(user_birth, datetime.today().date())
        lucky_info = generate_lucky_info(user_eto, user_birth, age, year_love, year_love, kyusei_text)  # Reuse generate_lucky_info for love context
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
            "next_month_love": next_month_love
        },
        "titles": {
            "compatibility": "相性診断",
            "overall_love_fortune": "相手の気持ちと今後の展開" if partner_birth else "理想の相手像と出会いのチャンス",
            "year_love": f"{datetime.today().year}年の恋愛運",
            "month_love": f"{datetime.today().month}月の恋愛運",
            "next_month_love": f"{(datetime.today() + relativedelta(months=1)).month}月の恋愛運"
        },
        "themes": themes,
        "lucky_info": lucky_info,
        "lucky_direction": kyusei_text,
        "yearly_love_fortunes": yearly_love_fortunes
    }
