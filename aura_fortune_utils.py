# aura_fortune_utils.py

import openai

def generate_aura_fortune(base64_image: str) -> dict:
    """
    OpenAI API を用いて、オーラ・前世・守護霊・メッセージを生成する
    """
    prompt = (
        "以下は、ある人物の顔写真をスピリチュアルな視点で分析した結果です。\n"
        "その人物の持つオーラの色と意味、前世の姿、守護霊のイメージ、"
        "そしてその人物に今必要なスピリチュアルメッセージを含めて、"
        "やさしい口調で、合計800文字以内でまとめてください。\n\n"
        "【形式】\n"
        "オーラの色と意味：○○色。意味は○○です。\n"
        "前世の姿：○○時代の○○。\n"
        "守護霊のタイプ：○○系の存在。\n"
        "スピリチュアルメッセージ：○○○○。\n"
    )

    # APIへのリクエスト
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "あなたはスピリチュアルな視点で人を診断するヒーラーです。"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=800,
        temperature=0.9,
    )

    result_text = response['choices'][0]['message']['content'].strip()

    return {
        "text": result_text
    }
