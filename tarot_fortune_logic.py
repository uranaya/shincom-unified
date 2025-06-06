import openai

def generate_tarot_fortune(question: str) -> dict:
    prompt = f"""
以下はお客様からのご相談内容です：
「{question}」

この相談に対して、ケルト十字スプレッド（10枚）を使用し、タロット占いを行ってください。

🔸使用ルール
- 大アルカナ・小アルカナのどちらも使用可
- 正位置・逆位置を明記し、意味に反映させてください
- 各カードは以下の形式で出力してください：

【ポジション名】（カード名・正/逆位置）
簡易解釈：
相談者への解釈：

🔸出力の順序
1. まず全体のカード構成と印象（ざっくりした展望）
2. 次に1枚ずつ丁寧に10枚を上記形式で説明
3. 最後にまとめとアドバイス（300字以内）

🔸文体トーン
- 誠実で客観的。丁寧語。
- 占いに詳しくない方にもわかりやすく。
- 商用の鑑定文として読める品質にしてください。

全体で1,200字以内におさめてください。
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "あなたは商業向けの文章力を持つ、熟練したタロット占い師です。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    result_text = response.choices[0].message.content.strip()

    return {
        "question": question,
        "result_text": result_text
    }
