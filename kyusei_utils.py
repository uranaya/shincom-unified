from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import json
import openai
import os

# Nine Star Ki star names (本命星の名称)
NINE_STARS = [
    "一白水星", "二黒土星", "三碧木星",
    "四緑木星", "五黄土星", "六白金星",
    "七赤金星", "八白土星", "九紫火星",
]

# English names for Nine Star Ki (簡易英訳)
NINE_STARS_EN = [
    "One White Water",
    "Two Black Earth",
    "Three Jade Wood",
    "Four Green Wood",
    "Five Yellow Earth",
    "Six White Metal",
    "Seven Red Metal",
    "Eight White Earth",
    "Nine Purple Fire",
]


# =========================
# 年別・固定テーブルの読み込み
# =========================

# このファイルと同じディレクトリに
# kyusei_year_table_1950_2026.json を配置しておくこと
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KYUSEI_TABLE_PATH = os.path.join(BASE_DIR, "kyusei_year_table_1950_2026.json")

with open(KYUSEI_TABLE_PATH, "r", encoding="utf-8") as f:
    KYUSEI_YEAR_TABLE = json.load(f)

# =========================
# 節分日データ（1950〜2026）
# =========================
# ユーザー提供の早見表に合わせた節分日。
# ここに載っていない年は 2月3日 とみなす。
SETSUBUN_BY_YEAR = {
    1950: (2, 3),
    1951: (2, 4),
    1952: (2, 4),
    1953: (2, 3),
    1954: (2, 3),
    1955: (2, 3),
    1956: (2, 4),
    1957: (2, 3),
    1958: (2, 3),
    1959: (2, 3),
    1960: (2, 4),
    1961: (2, 3),
    1962: (2, 3),
    1963: (2, 3),
    1964: (2, 4),
    1965: (2, 3),
    1966: (2, 3),
    1967: (2, 3),
    1968: (2, 4),
    1969: (2, 3),
    1970: (2, 3),
    1971: (2, 3),
    1972: (2, 4),
    1973: (2, 3),
    1974: (2, 3),
    1975: (2, 3),
    1976: (2, 4),
    1977: (2, 3),
    1978: (2, 3),
    1979: (2, 3),
    1980: (2, 4),
    1981: (2, 3),
    1982: (2, 3),
    1983: (2, 3),
    1984: (2, 4),
    1985: (2, 3),
    1986: (2, 3),
    1987: (2, 3),
    1988: (2, 3),
    1989: (2, 3),
    1990: (2, 3),
    1991: (2, 3),
    1992: (2, 3),
    1993: (2, 3),
    1994: (2, 3),
    1995: (2, 3),
    1996: (2, 3),
    1997: (2, 3),
    1998: (2, 3),
    1999: (2, 3),
    2000: (2, 3),
    2001: (2, 3),
    2002: (2, 3),
    2003: (2, 3),
    2004: (2, 3),
    2005: (2, 3),
    2006: (2, 3),
    2007: (2, 3),
    2008: (2, 3),
    2009: (2, 3),
    2010: (2, 3),
    2011: (2, 3),
    2012: (2, 3),
    2013: (2, 3),
    2014: (2, 3),
    2015: (2, 3),
    2016: (2, 3),
    2017: (2, 3),
    2018: (2, 3),
    2019: (2, 3),
    2020: (2, 3),
    2021: (2, 2),
    2022: (2, 3),
    2023: (2, 3),
    2024: (2, 3),
    2025: (2, 2),
    2026: (2, 3),
}

DEFAULT_SETSUBUN = (2, 3)


def get_setsubun_date(year: int) -> date:
    """指定年の節分日を返す。1950〜2026年は表どおり、それ以外は 2月3日。"""
    month, day = SETSUBUN_BY_YEAR.get(year, DEFAULT_SETSUBUN)
    return date(year, month, day)


def get_kyusei_year_from_birth(year: int, month: int, day: int) -> int:
    """生年月日から「九星年（本命星を決める年）」を求める。"""
    birth = date(year, month, day)
    setsu = get_setsubun_date(year)
    return year - 1 if birth < setsu else year



# ---- i18n helpers (EN) ----
import re as _re

DIRECTION_JA_TO_EN = {
    "北": "North",
    "北東": "Northeast",
    "東": "East",
    "南東": "Southeast",
    "南": "South",
    "南西": "Southwest",
    "西": "West",
    "北西": "Northwest",
}

HONMEISEI_JA_TO_EN = {
    "一白水星": "One White Water Star",
    "二黒土星": "Two Black Earth Star",
    "三碧木星": "Three Jade Wood Star",
    "四緑木星": "Four Green Wood Star",
    "五黄土星": "Five Yellow Earth Star",
    "六白金星": "Six White Metal Star",
    "七赤金星": "Seven Red Metal Star",
    "八白土星": "Eight White Earth Star",
    "九紫火星": "Nine Purple Fire Star",
}

def _dir_to_en(direction_text: str) -> str:
    if not direction_text:
        return ""
    parts = _re.split(r"[／/・,、\s]+", direction_text.strip())
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        out.append(DIRECTION_JA_TO_EN.get(part, part))
    return "/".join(out)

def _star_to_en(star_ja: str) -> str:
    return HONMEISEI_JA_TO_EN.get(star_ja, star_ja)

def get_honmeisei(year: int, month: int, day: int) -> str:
    """生年月日から本命星名（例: '四緑木星'）を取得する。"""
    kyusei_year = get_kyusei_year_from_birth(year, month, day)
    key = str(kyusei_year)
    if key not in KYUSEI_YEAR_TABLE:
        raise ValueError(f"kyusei_year_table に {key} 年のデータがありません。")
    return KYUSEI_YEAR_TABLE[key]


def get_directions(year: int, month: int, honmeisei: str, lang: str = "ja") -> dict:
    """九星気学に基づき、吉方位・凶方位を OpenAI に問い合わせる。"""
    if month == 0:
        period = f"{year}年の年間"
        explanation = "年盤を元に判断してください。"
    else:
        period = f"{year}年{month}月"
        explanation = "年盤と月盤を重ねて、総合的に吉方位・凶方位を判断してください。"

    if lang == "en":
        prompt = f"""You are an expert in Nine Star Ki (Kyusei Kigaku).
For the period: {period}
Main star: {honmeisei}

Return ONE lucky direction and ONE unlucky direction.
Output must be JSON in English only, exactly in this format:
{{"good": "Southeast", "bad": "Northwest"}}

Directions must be chosen from:
North, Northeast, East, Southeast, South, Southwest, West, Northwest

No extra text, JSON only.""".strip()
    else:
        prompt = f"""あなたは九星気学の専門家です。
{period}において、本命星「{honmeisei}」の人の
吉方位と凶方位を、{explanation}
次の形式で日本語のJSONのみを出力してください：

{{"good": "南東", "bad": "北西"}}

※ 方位は次の8方位からそれぞれ1つずつ選んでください：
北, 北東, 東, 南東, 南, 南西, 西, 北西

※説明文・注釈は一切不要。JSONのみを返答してください。""".strip()

    try:
        res = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.3,
        )
        txt = res.choices[0].message.content.strip()
        return json.loads(txt)
    except Exception as e:
        print("❌ get_directions エラー:", e)
        return {"good": "取得失敗", "bad": "取得失敗"}



def get_kyusei_fortune(year: int, month: int, day: int, now=None, force_next_month: bool = False, lang: str = "ja") -> str:
    """九星気学の短文（PDF末尾用）を生成する。

    - lang="ja": 日本語
    - lang="en": 英語
    - force_next_month=True: 「今月/来月」を1ヶ月先送り（来月起点）
    """
    try:
        honmeisei = get_honmeisei(year, month, day)

        honmeisei_disp = honmeisei
        if lang == "en":
            try:
                idx = NINE_STARS.index(honmeisei)
                honmeisei_disp = NINE_STARS_EN[idx]
            except Exception:
                honmeisei_disp = honmeisei

        base = now or datetime.now()
        if force_next_month:
            base = base + relativedelta(months=1)
        next_month = base + relativedelta(months=1)

        # get_directions requires (year, month, honmeisei). For yearly, use month=0.
        directions_year = get_directions(base.year, 0, honmeisei, lang=lang)
        directions_this_month = get_directions(base.year, base.month, honmeisei, lang=lang)
        directions_next_month = get_directions(next_month.year, next_month.month, honmeisei, lang=lang)

        if lang == "en":
            return (
                f"Your main star is '{honmeisei_disp}'.\n"
                f"Lucky direction for {base.year}: {directions_year.get('good', 'N/A')}  "
                f"This month: {directions_this_month.get('good', 'N/A')}  "
                f"Next month: {directions_next_month.get('good', 'N/A')}."
            )

        return (
            f"あなたの本命星は「{honmeisei_disp}」です。\n"
            f"{base.year}年の吉方位：{directions_year.get('good', '取得失敗')}　"
            f"今月：{directions_this_month.get('good', '取得失敗')}　"
            f"来月：{directions_next_month.get('good', '取得失敗')} です。"
        )

    except Exception as e:
        print("❌ get_kyusei_fortune エラー:", e)
        if lang == "en":
            return "Lucky direction: unavailable."
        return "吉方位：取得失敗"
