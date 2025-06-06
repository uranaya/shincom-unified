import openai

def generate_tarot_fortune(question: str) -> dict:
    prompt = f"""
お客様の相談内容は以下です：
「{question}」

この内容に基づいて、3枚のタロットカードを引き、過去・現在・未来の順にスプレッドを展開してください。
各カードの：
- カード名
- 簡単な意味（1文）
- 質問内容への具体的解釈（2〜3文）

その後、総合アドバイスを300文字以内で書いてください。
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "あなたはタロット占い師です。"},
            {"role": "user", "content": prompt}
        ]
    )
    result_text = response.choices[0].message.content.strip()
    return {
        "question": question,
        "result_text": result_text
    }
