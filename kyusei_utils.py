from __future__ import annotations

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import json
import os
from typing import Dict, List, Tuple, Optional, Set


# =========================
# 九星（本命星の名称）
# =========================
NINE_STARS: List[str] = [
    "一白水星", "二黒土星", "三碧木星",
    "四緑木星", "五黄土星", "六白金星",
    "七赤金星", "八白土星", "九紫火星",
]

STAR_TO_NUM: Dict[str, int] = {name: i + 1 for i, name in enumerate(NINE_STARS)}
NUM_TO_STAR: Dict[int, str] = {i + 1: name for i, name in enumerate(NINE_STARS)}

# 8方位（出力用の順序）
DIRECTIONS_8: List[str] = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]
OPPOSITE_DIR: Dict[str, str] = {
    "北": "南",
    "南": "北",
    "東": "西",
    "西": "東",
    "北東": "南西",
    "南西": "北東",
    "南東": "北西",
    "北西": "南東",
}

# =========================
# 年別・固定テーブルの読み込み
# =========================
# このファイルと同じディレクトリに kyusei_year_table_1950_2026.json を配置しておくこと
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KYUSEI_TABLE_PATH = os.path.join(BASE_DIR, "kyusei_year_table_1950_2026.json")

with open(KYUSEI_TABLE_PATH, "r", encoding="utf-8") as f:
    KYUSEI_YEAR_TABLE: Dict[str, str] = json.load(f)


# =========================
# 節分（このテーブルにない年は 2/3 扱い）
# =========================
SETSUBUN_BY_YEAR: Dict[int, Tuple[int, int]] = {
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
    1978: (2, 4),
    1979: (2, 4),
    1980: (2, 4),
    1981: (2, 4),
    1982: (2, 4),
    1983: (2, 4),
    1984: (2, 4),
    1985: (2, 4),
    1986: (2, 4),
    1987: (2, 4),
    1988: (2, 4),
    1989: (2, 4),
    1990: (2, 4),
    1991: (2, 4),
    1992: (2, 4),
    1993: (2, 4),
    1994: (2, 4),
    1995: (2, 4),
    1996: (2, 4),
    1997: (2, 4),
    1998: (2, 4),
    1999: (2, 4),
    2000: (2, 4),
    2001: (2, 4),
    2002: (2, 4),
    2003: (2, 4),
    2004: (2, 4),
    2005: (2, 4),
    2006: (2, 4),
    2007: (2, 4),
    2008: (2, 4),
    2009: (2, 4),
    2010: (2, 4),
    2011: (2, 4),
    2012: (2, 4),
    2013: (2, 4),
    2014: (2, 4),
    2015: (2, 4),
    2016: (2, 4),
    2017: (2, 3),
    2018: (2, 4),
    2019: (2, 4),
    2020: (2, 4),
    2021: (2, 3),
    2022: (2, 4),
    2023: (2, 4),
    2024: (2, 4),
    2025: (2, 3),
    2026: (2, 3),
}


def get_setsubun_date(year: int) -> date:
    """節分日を返す（テーブルに無い年は 2/3）。"""
    m, d = SETSUBUN_BY_YEAR.get(year, (2, 3))
    return date(year, m, d)


def get_kyusei_year_from_birth(year: int, month: int, day: int) -> int:
    """生年月日から「九星年（本命星を決める年）」を求める。"""
    birth = date(year, month, day)
    setsu = get_setsubun_date(year)
    return year - 1 if birth < setsu else year


def get_honmeisei(year: int, month: int, day: int) -> str:
    """生年月日から本命星名（例: '四緑木星'）を取得する。"""
    kyusei_year = get_kyusei_year_from_birth(year, month, day)
    key = str(kyusei_year)
    if key not in KYUSEI_YEAR_TABLE:
        raise ValueError(f"kyusei_year_table に {key} 年のデータがありません。")
    return KYUSEI_YEAR_TABLE[key]


# =========================================================
# 中宮（年盤・月盤）の算出ロジック（AI不使用）
# =========================================================
# 盤面は「洛書（九宮）」の基準配置（中宮=五黄）の数を採用し、
# 中宮が変わる場合は「全数を同じだけシフト」して盤を作る。
#
# 〔基準配置：中宮=5（北が上）〕
#   北西=6, 北=1, 北東=8,
#   西  =7, 中=5, 東  =3,
#   南西=2, 南=9, 南東=4
#
# 任意の中宮 c に対し、delta = c - 5 を各マスに加算（1..9で循環）すると盤が得られる。
# これにより「五黄殺（=5がいる方位）」等も機械的に求められる。


BASE_LOSHU: Dict[str, int] = {
    "北西": 6,
    "北": 1,
    "北東": 8,
    "西": 7,
    "中": 5,
    "東": 3,
    "南西": 2,
    "南": 9,
    "南東": 4,
}


def _wrap_star_num(n: int) -> int:
    """1..9 に丸める。"""
    return ((n - 1) % 9) + 1


def _board_from_center(center: int) -> Dict[str, int]:
    """中宮（1..9）から、8方位+中の星番号配置を返す。"""
    delta = center - 5
    return {pos: _wrap_star_num(v + delta) for pos, v in BASE_LOSHU.items()}


def _get_year_center_star(kyusei_year: int) -> int:
    """年盤の中宮（=その年の九星）を返す。"""
    key = str(kyusei_year)
    if key not in KYUSEI_YEAR_TABLE:
        raise ValueError(f"kyusei_year_table に {key} 年のデータがありません。")
    name = KYUSEI_YEAR_TABLE[key]
    if name not in STAR_TO_NUM:
        raise ValueError(f"不正な九星名: {name}")
    return STAR_TO_NUM[name]


# 十二支の年（1984=甲子）を基準に「子=1..亥=12」へ
# 参考：1984年=子、1985年=丑 ... 1995年=亥
def _eto_index_for_year(year: int) -> int:
    """十二支のインデックス（子=1..亥=12）を返す。"""
    return ((year - 1984) % 12) + 1


def _eto_direction_8(eto_index: int) -> str:
    """
    十二支（子=1..亥=12）を 8方位に丸める。
    （歳破・月破の算出用：本実装では8方位出力に合わせて簡略化）
    """
    # 子(北)→丑(北東)→寅(東)→卯(東)→辰(南東)→巳(南東)→午(南)→未(南西)→申(西)→酉(西)→戌(北西)→亥(北西)
    if eto_index == 1:
        return "北"
    if eto_index == 2:
        return "北東"
    if eto_index in (3, 4):
        return "東"
    if eto_index in (5, 6):
        return "南東"
    if eto_index == 7:
        return "南"
    if eto_index == 8:
        return "南西"
    if eto_index in (9, 10):
        return "西"
    # 11,12
    return "北西"


def _tiger_month_center_star_for_kyusei_year(kyusei_year: int) -> int:
    """
    寅月（概ね2月：節入り～）の月盤中宮を返す。
    観測される規則（年の十二支を3グループに分け、寅月中宮は 2/8/5 のいずれか）：
      - 年支インデックス % 3 == 0 → 二黒(2)
      - 年支インデックス % 3 == 1 → 八白(8)
      - 年支インデックス % 3 == 2 → 五黄(5)
    """
    eto_idx = _eto_index_for_year(kyusei_year)
    mod = eto_idx % 3
    if mod == 0:
        return 2
    if mod == 1:
        return 8
    return 5


def _month_branch_index(ki_month_index: int) -> int:
    """
    九星気学の月支（節入り基準）を返す。寅=3 から始まり、丑=2 が最後。
    ki_month_index: 寅月=1 ... 丑月=12
    戻り値: 十二支インデックス（子=1..亥=12）
    """
    # 寅(3) を起点に + (ki_month_index-1)
    return ((3 - 1 + (ki_month_index - 1)) % 12) + 1


def _month_center_star(year: int, month: int) -> int:
    """
    月盤の中宮（1..9）を返す。
    - 節入りの年始（立春）を概ね「2月」起点として扱うため、1月は前年の九星年に属する。
    - 寅月（2月相当）の中宮を年支から決定し、その後は月ごとに 1 ずつ減衰（1→9循環）させる。
    """
    if not (1 <= month <= 12):
        raise ValueError("month must be 1..12")

    kyusei_year = year if month >= 2 else year - 1

    # 寅月=1, 卯月=2, ... 丑月=12
    ki_month_index = month - 1 if month >= 2 else 12

    tiger_center = _tiger_month_center_star_for_kyusei_year(kyusei_year)
    # 寅月から (ki_month_index-1) ヶ月進むと 1ずつ減る
    return _wrap_star_num(tiger_center - (ki_month_index - 1))


def _five_kill_direction(board: Dict[str, int]) -> str:
    """五黄殺（=星5がいる方位）を返す。"""
    for d in DIRECTIONS_8:
        if board.get(d) == 5:
            return d
    # あり得ないが保険
    return "不明"


def _honmei_kill_direction(board: Dict[str, int], honmeisei_num: int) -> str:
    """本命殺（=本命星が入っている方位）を返す。"""
    for d in DIRECTIONS_8:
        if board.get(d) == honmeisei_num:
            return d
    return "不明"


def _format_dir_list(dirs: List[str]) -> str:
    """['北','南東'] -> '北、南東' / 空なら 'なし' """
    return "、".join(dirs) if dirs else "なし"


def get_directions(year: int, month: int, honmeisei: str) -> dict:
    """
    九星気学に基づき、吉方位・凶方位を「計算」で返す（AI不使用）。

    出力：
      {"good": "南東、西", "bad": "北、北西"} のように、8方位のうち該当するものを列挙。

    判定（簡略・固定ルール）：
      - 三大凶殺：五黄殺・暗剣殺・（歳破 or 月破）
      - 本命殺・本命的殺（本命星の位置とその反対）
      - 月の場合は「年盤」と「月盤」の両方で上記を評価し、どちらかで凶なら凶扱い
    """
    if honmeisei not in STAR_TO_NUM:
        # 例外にせず、既存実装の「取得失敗」相当で返す
        return {"good": "取得失敗", "bad": "取得失敗"}

    hon_num = STAR_TO_NUM[honmeisei]

    # 年盤：月が1月なら前年の年盤扱いに寄せる（節入り年始の簡略）
    kyusei_year_for_board = year if (month == 0 or month >= 2) else year - 1
    year_center = _get_year_center_star(kyusei_year_for_board)
    year_board = _board_from_center(year_center)

    bad: Set[str] = set()

    # ---- 年盤由来の凶方位 ----
    five_dir_year = _five_kill_direction(year_board)
    bad.add(five_dir_year)                      # 五黄殺
    bad.add(OPPOSITE_DIR[five_dir_year])        # 暗剣殺（反対）
    # 歳破（年支の反対）
    eto_dir_year = _eto_direction_8(_eto_index_for_year(kyusei_year_for_board))
    bad.add(OPPOSITE_DIR[eto_dir_year])

    # 本命殺・本命的殺（年盤）
    hon_dir_year = _honmei_kill_direction(year_board, hon_num)
    if hon_dir_year in OPPOSITE_DIR:
        bad.add(hon_dir_year)
        bad.add(OPPOSITE_DIR[hon_dir_year])

    # ---- 月盤（month != 0）の場合 ----
    if month != 0:
        month_center = _month_center_star(year, month)
        month_board = _board_from_center(month_center)

        five_dir_month = _five_kill_direction(month_board)
        bad.add(five_dir_month)
        bad.add(OPPOSITE_DIR[five_dir_month])

        # 月破（＝月支の反対）
        ki_month_index = month - 1 if month >= 2 else 12
        month_branch_idx = _month_branch_index(ki_month_index)
        eto_dir_month = _eto_direction_8(month_branch_idx)
        bad.add(OPPOSITE_DIR[eto_dir_month])

        # 本命殺・本命的殺（月盤）
        hon_dir_month = _honmei_kill_direction(month_board, hon_num)
        if hon_dir_month in OPPOSITE_DIR:
            bad.add(hon_dir_month)
            bad.add(OPPOSITE_DIR[hon_dir_month])

    bad_list = [d for d in DIRECTIONS_8 if d in bad]
    good_list = [d for d in DIRECTIONS_8 if d not in bad]

    return {"good": _format_dir_list(good_list), "bad": _format_dir_list(bad_list)}


def get_kyusei_fortune(
    year: int,
    month: int,
    day: int,
    now: Optional[datetime] = None,
    force_next_month: bool = False
) -> str:
    """九星気学の2行テキストを生成する。

    - 通常は「20日以降は翌月ベース」で年・月を判定
    - force_next_month=True の場合は、日付に関係なく「翌月起点」で判定
    """
    try:
        honmeisei = get_honmeisei(year, month, day)

        base_now = now if now is not None else datetime.now()

        base = base_now
        if force_next_month or base.day >= 20:
            base = base + relativedelta(months=1)

        next_month = base + relativedelta(months=1)

        directions_year = get_directions(base.year, 0, honmeisei)
        directions_this_month = get_directions(base.year, base.month, honmeisei)
        directions_next_month = get_directions(next_month.year, next_month.month, honmeisei)

        return (
            f"あなたの本命星は「{honmeisei}」です。\n"
            f"{base.year}年の吉方位：{directions_year['good']}　"
            f"今月：{directions_this_month['good']}　"
            f"来月：{directions_next_month['good']} です。"
        )
    except Exception as e:
        print("❌ get_kyusei_fortune エラー:", e)
        return "吉方位を取得できませんでした"
