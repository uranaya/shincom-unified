import openai
import re

def generate_tarot_fortune(question: str) -> dict:
    prompt = f"""
以下はお客様からのご相談内容です：
「{question}」

この相談内容をもとに、相談者が気にしていると思われる「質問」を3～5個に分解してください。
（例：相手は自分をどう思っているか？／行動すべきか？／障害や注意点は？／未来の可能性は？など）

それぞれの質問に対して、1枚のタロットカードを引き、以下の形式で回答してください。

🔸占いルール：
- スプレッド形式は使わず、一問一答の形式とする
- 大アルカナ・小アルカナどちらも使用可能
- 正位置・逆位置を明記し、それに応じた意味を使用する

🔸出力形式（JSON風）：
[
  {{ "question": "質問文1", "card": "カード名（正/逆）", "answer": "そのカードからの丁寧な解釈" }},
  ...
]

🔸最後に以下を追加してください（アドバイス）：
- 全体の流れを読み取り、カード結果を統合して「総合的な読み解きとアドバイス」（400～500文字）を誠実で親身なカウンセリング調で記述する
- 占いに詳しくない方にもわかりやすく
- 商用利用できる鑑定文として、自然で信頼感のある日本語で

🔸出力形式の順序：
1. 質問ごとのカードと回答（3～5件）
2. 「【総合読み解きとアドバイス】」というラベルのあとに全体まとめ

🔸注意点：
- JSON構造に近いがPythonで読み取れる辞書に整形しやすい形にしてください
- 不要な飾り枠や表現（絵文字など）は使わず、あくまで丁寧で自然な文体で
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたはタロット占いの専門家で、優れた文章表現力も持つAI占い師です。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
        )
        result_text = response["choices"][0]["message"]["content"].strip()
        parsed = parse_tarot_reply_to_dict(result_text)
        return parsed

    except Exception as e:
        return {"error": f"OpenAI診断エラー: {e}"}

def parse_tarot_reply_to_dict(reply_text: str) -> dict:
    question_blocks = re.findall(r'{\s*"question":\s*"(.+?)",\s*"card":\s*"(.+?)",\s*"answer":\s*"(.+?)"\s*}', reply_text, re.DOTALL)
    extra_questions = [
        {"question": q.strip(), "card": c.strip(), "answer": a.strip()}
        for q, c, a in question_blocks
    ]

    summary_match = re.search(r"【総合読み解きとアドバイス】\s*(.*)", reply_text, re.DOTALL)
    summary_advice = summary_match.group(1).strip() if summary_match else ""

    return {
        "extra_questions": extra_questions,
        "summary_advice": summary_advice
    }
