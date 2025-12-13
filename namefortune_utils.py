"""
namefortune_utils.py
--------------------
姓名判断用のユーティリティモジュール。

・漢字の画数カウント
・五運（天格・人格・地格・外格・総格）の算出
・OpenAI へのプロンプト生成 ＆ レスポンス取得

shincom-unified への組み込みを想定していますが、
このファイル単体でも動作するように実装してあります。
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

# OpenAI公式Pythonライブラリ（2024以降版）
# pip install openai
from openai import OpenAI


# =========================
# データクラス定義
# =========================

@dataclass
class NameFortuneInput:
    full_name: str
    reading: str = ""
    kanji_candidates: List[str] = None
    gender: Optional[str] = None  # "male" / "female" / None

    # 五運（後で自動計算）
    tenkaku: int = 0
    jinkaku: int = 0
    chikaku: int = 0
    gaikaku: int = 0
    soukaku: int = 0

    family_name: str = ""
    given_name: str = ""


# =========================
# 画数辞書（サンプル）
# 実運用では「常用漢字＋人名用漢字」を追加してください。
# =========================

def get_kanji_strokes_dict() -> Dict[str, int]:
    """
    漢字 -> 画数 の辞書。
    ここではサンプルのみ定義しています。
    実運用では CSV 等からの読み込みや、
    より完全な辞書に差し替えてください。
    """
    base_dict = {
        # よくある苗字・名前の漢字から一部サンプル
        "山": 3,
        "田": 5,
        "太": 4,
        "郎": 9,
        "中": 4,
        "川": 3,
        "本": 5,
        "木": 4,
        "林": 8,
        "小": 3,
        "野": 11,
        "高": 10,
        "橋": 16,
        "村": 7,
        "岡": 8,
        "安": 6,
        "美": 9,
        "香": 9,
        "花": 7,
        "愛": 13,
        "翔": 12,
        "結": 12,
        "悠": 11,
        "子": 3,
        "菜": 11,
        "陽": 12,
        "希": 7,
        "海": 9,
        "空": 8,
        # ひらがな・カタカナは1画として扱う or 別ルールにしてもOK
    }

    # ひらがな・カタカナを一律1画として扱う（簡易ルール）
    hira_kata = [
        *(chr(c) for c in range(ord("ぁ"), ord("ゖ") + 1)),
        *(chr(c) for c in range(ord("ァ"), ord("ヺ") + 1)),
    ]
    for ch in hira_kata:
        base_dict.setdefault(ch, 1)

    return base_dict


# =========================
# 画数計算＆五運計算
# =========================

def split_name(full_name: str) -> (str, str):
    """
    フルネームを「姓」「名」に分割する簡易関数。
    ・スペース（全角・半角）があればそこで分割
    ・なければ前半を姓、後半を名にするが、ここでは
      「2文字以上の場合、最初の1文字を姓、それ以降を名」
      というシンプルルールにします。
    """
    full_name = full_name.strip()
    if " " in full_name:
        family, given = full_name.split(" ", 1)
        return family.strip(), given.strip()
    if "　" in full_name:
        family, given = full_name.split("　", 1)
        return family.strip(), given.strip()

    # スペースが無い場合の簡易分割
    if len(full_name) <= 1:
        return full_name, ""
    return full_name[0], full_name[1:]


def count_strokes(text: str, strokes_dict: Dict[str, int]) -> int:
    """
    文字列中の各文字の画数を合計する。
    未定義の文字は 1画 として計上しつつ、
    必要なら後でログ出力などで確認できるようにしています。
    """
    total = 0
    for ch in text:
        if ch.strip() == "":
            continue
        total += strokes_dict.get(ch, 1)
    return total


def calculate_goun(nfi: NameFortuneInput, strokes_dict: Dict[str, int]) -> NameFortuneInput:
    """
    姓名から五運を計算して NameFortuneInput に埋め込んで返す。
    五運のルール（代表的な流派に基づく簡易版）：
      天格：姓の合計画数
      地格：名の合計画数
      人格：姓の最後の一字 + 名の最初の一字
      総格：姓＋名の合計
      外格：総格 − 人格
    """
    family = nfi.family_name
    given = nfi.given_name

    # 天格・地格・総格
    ten = count_strokes(family, strokes_dict)
    chi = count_strokes(given, strokes_dict)
    sou = ten + chi

    # 人格
    if family and given:
        jin_str = family[-1] + given[0]
    else:
        # 片方だけの場合の簡易対応
        jin_str = family or given
    jin = count_strokes(jin_str, strokes_dict)

    # 外格
    gai = sou - jin

    nfi.tenkaku = ten
    nfi.chikaku = chi
    nfi.soukaku = sou
    nfi.jinkaku = jin
    nfi.gaikaku = gai

    return nfi


# =========================
# OpenAI プロンプト生成
# =========================

def build_user_prompt(nfi: NameFortuneInput) -> str:
    """
    OpenAI に渡す user 用プロンプトを生成。
    """
    kanji_str = "、".join(nfi.kanji_candidates) if nfi.kanji_candidates else "（特になし）"

    if nfi.gender == "male":
        gender_text = "男性"
    elif nfi.gender == "female":
        gender_text = "女性"
    else:
        gender_text = "未回答"

    prompt = f"""以下の情報をもとに、姓名判断のレポート文章を作成してください。

【氏名】
{nfi.full_name}（よみ：{nfi.reading or "（よみ未入力）"}）

【五運と画数】
天格：{nfi.tenkaku}画
人格：{nfi.jinkaku}画
地格：{nfi.chikaku}画
外格：{nfi.gaikaku}画
総格：{nfi.soukaku}画

【入れたい漢字（任意）】
{kanji_str}

【依頼者の性別】
{gender_text}

【出力形式と順番】
以下の4つのセクションを、この順番で出力してください。
それぞれの見出しを「### 見出し名」の形式で付けてください。

1. 「### 五運の総合鑑定」
  ・五運のバランスから、性格傾向・仕事運・人間関係・健康面などを総合的に解説してください。
  ・良い点と課題の両方を書き、課題については「どう気をつければうまくいくか」まで書いてください。
  ・600〜800文字程度に収めてください。

2. 「### 改名するなら」
  ・今の名前の傾向を踏まえて、「どのような画数・雰囲気の名前にすると運が整いやすいか」を説明してください。
  ・【入れたい漢字】があれば、できる範囲で活かした方針を述べてください。
  ・そのうえで、改名候補を3つ挙げてください。
    例）「山田翔太（やまだ しょうた）：●●な運勢になりやすく、～～な場面で力を発揮しやすい名前です。」
  ・全体で300〜500文字程度にしてください。

3. 「### 子どもにオススメの名前」
  ・依頼者の名前の傾向から見て、子どもに受け継がせたい運勢のポイントを説明してください。
  ・男の子の名前候補を3つ、女の子の名前候補を3つ挙げ、それぞれに一言コメントをつけてください。
  ・【入れたい漢字】があれば、可能な範囲で候補に含めてください。
  ・全体で600〜800文字程度にしてください。

4. 「### 結婚相手の名前の傾向」
  ・人格や地格などの相性の観点から、「どういう画数・雰囲気の名前の人と相性が良くなりやすいか」を説明してください。
  ・そのイメージに近い「例の名前」を3つ挙げてください（実在の特定個人を指すものではなく、あくまで傾向の例として）。
  ・「こういう雰囲気の名前の人は、●●なタイプが多く、あなたにとって△△な存在になりやすい」など、イメージが湧くように説明してください。
  ・全体で400〜600文字程度にしてください。

【注意事項】
・出力はプレーンテキストのみとし、JSON形式にはしないでください。
・絵文字は使わないでください。
・強い不安をあおる表現や、「離婚する」「不幸になる」など断定的な不幸の宣告は避けてください。
・最終的に名前を決めるのは本人の自由である、というスタンスを保ってください。
"""
    return prompt


SYSTEM_PROMPT = """あなたは姓名判断のプロフェッショナルです。

・五運（天格・人格・地格・外格・総格）の意味を踏まえて、現実的で前向きな鑑定を行ってください。
・霊感やスピリチュアルな表現、「絶対」「必ず」などの断定は避けてください。
・実生活で役立つアドバイスを中心に、やさしく、丁寧な日本語で書いてください。
・依頼者を不安にさせる言い方ではなく、「改善方法」や「活かし方」を必ずセットで伝えてください。
・改名や子どもの名前、結婚相手の名前の候補は、あくまで例示であり、最終的な決定は自由であることを前提に書いてください。
"""


def generate_name_fortune_text(
    nfi: NameFortuneInput,
    api_key: Optional[str] = None,
    model: str = "gpt-4.1-mini",
) -> str:
    """
    OpenAI API を使って姓名判断レポートの本文（プレーンテキスト）を生成する。
    shincom-unified 側で OpenAI の API キーがすでに環境変数などで
    設定されている前提。
    """
    client = OpenAI(api_key=api_key)

    user_prompt = build_user_prompt(nfi)

    # 新しい responses API を使用
    response = client.responses.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_output_tokens=2000,
    )

    # content[0].text から本文を取得
    content_block = response.output[0].content[0]
    text = content_block.get("text", "") if isinstance(content_block, dict) else str(content_block)
    return text
