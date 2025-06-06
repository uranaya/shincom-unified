# prompt_utils.py

import openai
import re

def extract_prompts_from_result(result_text):
    """
    鑑定文から「オーラ色」「前世」「守護霊」を抽出し、DALL·E用のプロンプトを生成
    """

    # --- 1. 日本語部分の抽出 ---
    aura_match = re.search(r"オーラの色と意味：(.+?)。", result_text)
    past_match = re.search(r"前世の姿：(.+?)。", result_text)
    spirit_match = re.search(r"守護霊のタイプ：(.+?)。", result_text)

    aura_ja = aura_match.group(1) if aura_match else "ラベンダー色"
    past_ja = past_match.group(1) if past_match else "中世の癒し手"
    spirit_ja = spirit_match.group(1) if spirit_match else "自然の精霊"

    # --- 2. 翻訳リクエスト（DALL·E向け） ---
    prompt = (
        f"以下の日本語をDALL·E用の英語プロンプトに翻訳してください：\n"
        f"オーラ色：{aura_ja}\n前世：{past_ja}\n守護霊：{spirit_ja}\n\n"
        f"それぞれ、色を含めた幻想的なプロンプトにしてください。\n"
        f"形式:\nAuraColor: ...\nPastLife: ...\nGuardianSpirit: ..."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You generate creative image prompts for DALL·E."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=400
        )

        content = response['choices'][0]['message']['content']

        aura_prompt = re.search(r"AuraColor:\s*(.+)", content)
        past_prompt = re.search(r"PastLife:\s*(.+)", content)
        spirit_prompt = re.search(r"GuardianSpirit:\s*(.+)", content)

        aura_color_prompt = aura_prompt.group(1).strip() if aura_prompt else "a glowing lavender aura"
        past_prompt = past_prompt.group(1).strip() if past_prompt else "A medieval healer with soft light"
        spirit_prompt = spirit_prompt.group(1).strip() if spirit_prompt else "A guardian spirit of the wind with ethereal glow"

    except Exception:
        aura_color_prompt = "a glowing lavender aura"
        past_prompt = "A medieval healer with soft light"
        spirit_prompt = "A guardian spirit of the wind with ethereal glow"

    return aura_color_prompt, past_prompt, spirit_prompt
