def create_pdf_tarot(filename, question, tarot_result):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    styles = getSampleStyleSheet()

    x_margin = 20 * mm
    y = height - 30 * mm

    c.setFont("HeiseiKakuGo-W5", 14)
    c.drawString(x_margin, y, f"📍 質問内容：{question}")
    y -= 20

    # --- ケルト十字スプレッド結果 ---
    c.setFont("HeiseiKakuGo-W5", 12)
    for i in range(1, 11):
        card_info = tarot_result["celtic_cross"].get(str(i), {})
        if not card_info:
            continue
        card = card_info.get("card", "未知のカード")
        meaning = card_info.get("answer", "")
        para = Paragraph(f"【{i}】{card}：{meaning}", styles["Normal"])
        w, h = para.wrap(width - 2 * x_margin, y)
        if y - h < 30 * mm:
            c.showPage()
            y = height - 30 * mm
        para.drawOn(c, x_margin, y - h)
        y -= h + 5

    # --- 総合読み解きとアドバイス ---
    c.showPage()
    y = height - 30 * mm
    c.setFont("HeiseiKakuGo-W5", 14)
    c.drawString(x_margin, y, "🌟 総合読み解きとアドバイス")
    y -= 20

    advice_para = Paragraph(tarot_result.get("summary_advice", "（未記入）"), styles["Normal"])
    w, h = advice_para.wrap(width - 2 * x_margin, y)
    advice_para.drawOn(c, x_margin, y - h)
    y -= h + 10

    # --- 追加の質問とカードリーディング ---
    extras = tarot_result.get("extra_questions", [])
    if extras:
        c.showPage()
        y = height - 30 * mm
        c.setFont("HeiseiKakuGo-W5", 14)
        c.drawString(x_margin, y, "🔍 補足質問とカードの答え")
        y -= 20
        for item in extras:
            q = item.get("question", "")
            card = item.get("card", "")
            ans = item.get("answer", "")
            para = Paragraph(f"Q. {q}<br/>→ {card}：{ans}", styles["Normal"])
            w, h = para.wrap(width - 2 * x_margin, y)
            if y - h < 30 * mm:
                c.showPage()
                y = height - 30 * mm
            para.drawOn(c, x_margin, y - h)
            y -= h + 10

    c.save()
