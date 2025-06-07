import openai
import re

def generate_tarot_fortune(question: str) -> dict:
    prompt = f"""
以下はお客様からのご相談内容です：
「{question}」

この相談内容をもとに、以下の構成でタロット占いを行ってください：

＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
🔮【1. 全体リーディング（ケルト十字スプレッド）】
- 大アルカナ・小アルカナを使用
- 正位置・逆位置を含めて、各カードの意味をポジションに合わせて解釈
- 以下の形式で10枚を出力：

【ポジション名】（カード名・正/逆位置）
簡易解釈：
相談者への解釈：

＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
🃏【2. 個別質問カード（3問）】
以下のような相談者が気にしていそうな疑問を3つ挙げ、それぞれに1枚カードを引いて回答してください。
例：
- 相手は今どう思っているか？
- これからどう動くべきか？
- 自分の気持ちをどう伝えるべきか？

形式：
【Q1】（質問文）
▶︎（カード名・正/逆位置）：解釈と助言（200字以内）

＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
💬【3. 総合読み解きとアドバイス】
- 1〜10のケルト十字および個別質問カードの流れを一つのストーリーとしてまとめる。
- 状況の本質や原因、相手の心情、自分にできること、可能性などをつなげて具体的に解説。
- 最後に行動のための一言アドバイスで締める。
- カウンセラー的な安心感あるトーンで、心に届く文章を600〜800字程度で。
＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝

出力は以下のように構造化して、JSON形式の辞書で返してください：

{
  "spread_result": "（ケルト十字の結果）",
  "extra_questions": [
    {"question": "質問文1", "card": "カード名（正/逆）", "answer": "解釈文"},
    {"question": "質問文2", "card": "カード名（正/逆）", "answer": "解釈文"},
    {"question": "質問文3", "card": "カード名（正/逆）", "answer": "解釈文"}
  ],
  "summary_advice": "（総合読み解きとアドバイス）"
}
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        temperature=0.9,
        messages=[{"role": "user", "content": prompt}]
    )

    reply = response["choices"][0]["message"]["content"]
    return parse_tarot_reply_to_dict(reply)  # ←これでテキストを辞書に変換（別途定義が必要）




def parse_tarot_reply_to_dict(reply_text: str) -> dict:
    # 1. ケルト十字全体リーディング
    spread_match = re.search(r"🔮【1\. 全体リーディング.*?】\n(.*?)\n\n🃏【2\.", reply_text, re.DOTALL)
    spread_result = spread_match.group(1).strip() if spread_match else ""

    # 2. 個別質問（3問）
    question_blocks = re.findall(r"【Q\d+】\s*（(.*?)）\n▶︎（(.*?)）：(.*?)\n", reply_text, re.DOTALL)
    extra_questions = [
        {"question": q.strip(), "card": c.strip(), "answer": a.strip()}
        for q, c, a in question_blocks
    ]

    # 3. 総合読み解きとアドバイス
    summary_match = re.search(r"💬【3\. 総合読み解きとアドバイス】\n(.*)", reply_text, re.DOTALL)
    summary_advice = summary_match.group(1).strip() if summary_match else ""

    return {
        "spread_result": spread_result,
        "extra_questions": extra_questions,
        "summary_advice": summary_advice
    }

