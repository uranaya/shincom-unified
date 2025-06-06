import openai

def generate_tarot_fortune(question: str) -> dict:
    prompt = f"""
以下はお客様のご相談内容です：
「{question}」

この相談に対して、ケルト十字スプレッド（10枚）を使用し、タロット占いを行ってください。

【ルール】
- 大アルカナ・小アルカナ両方を使用
- 各カードは正位置／逆位置をランダムに指定
- 各カードについて以下の情報を出力してください：
    ・ポジション名（例：現在、障害、過去など）
    ・カード名と正逆（例：カップの3（逆位置））
    ・簡単な意味（1文）
    ・相談者に対する具体的な解釈（2〜3文）

最後に、10枚すべての読みを踏まえた「総合的なまとめと今後へのアドバイス」を明確に示してください。
全体で1,200文字以内に収めてください。
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "あなたはベテランのタロット占い師です。文章は商業占い誌に掲載できるような文体で、誠実でわかりやすく書いてください。"},
            {"role": "user", "content": prompt}
        ]
    )
    result_text = response.choices[0].message.content.strip()
    return {
        "question": question,
        "result_text": result_text
    }
