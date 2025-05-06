def generate_yearly_fortune(user_birth: str, now: datetime):
    nicchu = get_nicchu_eto(user_birth)
    born = datetime.strptime(user_birth, "%Y-%m-%d")

    # 総合年運
    prompt_year = f"""あなたは四柱推命のプロの占い師です。
- 日柱: {nicchu}
- 対象年: {now.year}
- 300文字以内、主語は「あなた」、現実的な文体でお願いします。"""

    year_fortune = _ask_openai(prompt_year)

    # 月運リスト（get_directions 削除）
    month_fortunes = []
    for i in range(12):
        target = (now.replace(day=15) + relativedelta(months=i))
        y, m = target.year, target.month

        prompt_month = f"""あなたは四柱推命のプロの占い師です。
- 日柱: {nicchu}
- 年月: {y}年{m}月

以下の条件で月運を作成してください:
- 約200文字
- 仕事・人間関係・感情面・健康などを含めて具体的に
- 主語「あなた」、温かみある語り口で"""

        month_fortunes.append({
            "label": f"{y}年{m}月の運勢",
            "text": _ask_openai(prompt_month)
        })

    return {
        "year_label": f"{now.year}年の総合運",
        "year_text": year_fortune,
        "months": month_fortunes
    }
