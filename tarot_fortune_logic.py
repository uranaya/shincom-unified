import openai
import re

def generate_tarot_fortune(question: str) -> dict:
    prompt = f"""
以下はお客様からのご相談内容です：
「{question}」

この相談内容をもとに、相談者が気にしていると思われる「質問」を3～5個に分解してください。
...（省略: 占いルールと出力形式の指示）...
🔸出力形式（JSON風）：
[
  {{ "question": "質問文1", "card": "カード名（正/逆）", "answer": "そのカードからの解釈" }},
  ...
]

🔸最後に「総合読み解きとアドバイス」の文章（400～500文字程度）を付けてください。
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたはタロット占いの専門家です。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
        )
        result_text = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return {"error": f"OpenAI API エラー: {e}"}

    # 生成されたテキスト（JSON風）を解析して辞書化
    # 質問・カード・回答を抽出
    question_blocks = re.findall(
        r'{\s*"question"\s*:\s*"(.*?)"\s*,\s*"card"\s*:\s*"(.*?)"\s*,\s*"answer"\s*:\s*"(.*?)"\s*}',
        result_text, re.DOTALL
    )
    questions = []
    for q, c, a in question_blocks:
        questions.append({
            "question": q.strip(),
            "card": c.strip(),
            "answer": a.strip()
        })
    # 「総合読み解きとアドバイス」を抽出
    summary_match = re.search(r'総合読み解きとアドバイス\s*[:：]?\s*(.*)', result_text, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else ""
    
    return {
        "questions": questions,
        "summary_advice": summary
    }
