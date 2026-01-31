# kyusei_utils.py
# -*- coding: utf-8 -*-
"""Nine Star Ki (九星気学) utilities.

This module is intentionally self-contained.

It provides:
- get_honmeisei(...): main star (本命星) number (1..9)
- get_honmeisei_name(...): main star name (Japanese)
- get_directions(...): simple deterministic 'good direction' calculation

IMPORTANT:
- This file must NOT import itself (no 'from kyusei_utils import ...').
- Function signatures are made backward-compatible to avoid breaking older
  lucky_utils variants.

Notes on accuracy:
- 本命星: uses a common approximation with 立春(2/4) boundary.
- 月盤中宮: uses a standard 12-period month cycle starting in February.
  February's 中宮星 repeats with a 3-year cycle (…→五黄→二黒→八白→…).
  This matches published month charts (e.g., 2024/2 五黄, 2025/2 二黒, 2026/2 八白).
- 吉方位: implements a conservative rule:
  * exclude 本命殺 and 本命的殺 for the given盤
  * prefer directions where the 方位の星の五行 is 'same' or 'generates' the user's五行
  This is a simplified rule-set designed to be stable and non-AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Optional, Tuple, Union


# -------------------------
# Star / Element definitions
# -------------------------

STAR_NAMES_JP: Dict[int, str] = {
    1: "一白水星",
    2: "二黒土星",
    3: "三碧木星",
    4: "四緑木星",
    5: "五黄土星",
    6: "六白金星",
    7: "七赤金星",
    8: "八白土星",
    9: "九紫火星",
}

# 五行
ELEMENT_OF_STAR: Dict[int, str] = {
    1: "water",
    2: "earth",
    3: "wood",
    4: "wood",
    5: "earth",
    6: "metal",
    7: "metal",
    8: "earth",
    9: "fire",
}

# Generating cycle: producer[element] -> element
PRODUCER_OF: Dict[str, str] = {
    "water": "metal",
    "wood": "water",
    "fire": "wood",
    "earth": "fire",
    "metal": "earth",
}


# -------------------------
# Direction / chart geometry
# -------------------------

# Base Lo Shu mapping when 中宮=5
# (This is the standard fixed arrangement.)
BASE_DIR_TO_STAR_WHEN_CENTER_5: Dict[str, int] = {
    "center": 5,
    "north": 1,
    "northeast": 8,
    "east": 3,
    "southeast": 4,
    "south": 9,
    "southwest": 2,
    "west": 7,
    "northwest": 6,
}

DIR_JP: Dict[str, str] = {
    "north": "北",
    "northeast": "北東",
    "east": "東",
    "southeast": "南東",
    "south": "南",
    "southwest": "南西",
    "west": "西",
    "northwest": "北西",
}

DIR_EN: Dict[str, str] = {
    "north": "North",
    "northeast": "Northeast",
    "east": "East",
    "southeast": "Southeast",
    "south": "South",
    "southwest": "Southwest",
    "west": "West",
    "northwest": "Northwest",
}

OPPOSITE_DIR: Dict[str, str] = {
    "north": "south",
    "northeast": "southwest",
    "east": "west",
    "southeast": "northwest",
    "south": "north",
    "southwest": "northeast",
    "west": "east",
    "northwest": "southeast",
}


def _normalize_star_number(x: Union[int, str]) -> int:
    from fortune_logic import generate_fortune
    """Accept int 1..9 or JP star name string; return 1..9."""
    if isinstance(x, int):
        if 1 <= x <= 9:
            return x
        raise ValueError(f"Invalid star number: {x}")

    s = (x or "").strip()
    for k, v in STAR_NAMES_JP.items():
        if s == v:
            return k
    raise ValueError(f"Invalid star name: {x}")


def _year_center_star(year: int) -> int:
    """年盤中宮星 (1..9). Common formula for Gregorian year.

    NOTE: 九星の年は立春(2/4頃)で切り替わるが、この関数は '年' のみで計算する。
    呼び出し側で year をどう渡すかで解釈が変わる。
    """
    r = year % 9
    v = 11 - r
    while v > 9:
        v -= 9
    while v < 1:
        v += 9
    return v


def _feb_center_star_for_kyusei_year(kyusei_year: int) -> int:
    """Return the month 中宮星 for February (節入り〜) of the given 九星年.

    Empirically and per published charts, February's center star follows a 3-year cycle:
      2024/2 -> 5, 2025/2 -> 2, 2026/2 -> 8, 2027/2 -> 5 ...
    i.e., by kyusei_year % 3: {0:2, 1:8, 2:5}
    """
    return {0: 2, 1: 8, 2: 5}[kyusei_year % 3]


def _month_center_star(year: int, month: int) -> int:
    """月盤中宮星 (1..9) for a given Gregorian year/month.

    九星の月は通常「節入り」起点で、
      2月(寅)を1番目として 12ヶ月（寅〜丑）で循環します。

    This function maps:
      Gregorian Feb -> 九星月 index 1
      ...
      Gregorian Dec -> index 11
      Gregorian Jan -> index 12 (belongs to previous 九星年)

    Then it computes center star by descending 1 each month from Feb's center star.
    """
    if not (1 <= month <= 12):
        raise ValueError(f"Invalid month: {month}")

    if month == 1:
        kyusei_year = year - 1
        index = 12
    else:
        kyusei_year = year
        index = month - 1  # Feb=1

    feb_star = _feb_center_star_for_kyusei_year(kyusei_year)
    # Descend one star per month (wrap 1..9)
    # index=1 => feb_star
    v = feb_star - (index - 1)
    v %= 9
    if v == 0:
        v = 9
    return v


# Public helpers (useful for debugging / display)

def get_year_center_star(year: int) -> int:
    """Return the year chart center star (年盤中宮)."""
    return _year_center_star(int(year))


def get_month_center_star(year: int, month: int) -> int:
    """Return the month chart center star (月盤中宮) for a Gregorian month."""
    return _month_center_star(int(year), int(month))


def _chart_dir_to_star(center_star: int) -> Dict[str, int]:
    """Given center_star, return mapping direction->star number."""
    shift = center_star - 5
    out: Dict[str, int] = {}
    for d, base in BASE_DIR_TO_STAR_WHEN_CENTER_5.items():
        # shift with wrap 1..9
        v = base + shift
        v = ((v - 1) % 9) + 1
        out[d] = v
    return out


def _direction_of_star(center_star: int, target_star: int) -> Optional[str]:
    m = _chart_dir_to_star(center_star)
    for d, s in m.items():
        if d == "center":
            continue
        if s == target_star:
            return d
    return None


def _is_favorable_by_element(direction_star: int, person_star: int) -> bool:
    de = ELEMENT_OF_STAR[direction_star]
    pe = ELEMENT_OF_STAR[person_star]
    return de == pe or de == PRODUCER_OF[pe]


# -------------------------
# Public API
# -------------------------

DateLike = Union[date, datetime]


def get_honmeisei(*args: Union[int, DateLike]) -> int:
    """Get 本命星 number (1..9).

    Backward-compatible signatures:
      - get_honmeisei(year:int, month:int, day:int)
      - get_honmeisei(birthdate: date|datetime)

    Uses a common approximation: birthdays before 2/4 are treated as previous year.
    """
    if len(args) == 1 and isinstance(args[0], (date, datetime)):
        bd = args[0]
        y, m, d = bd.year, bd.month, bd.day
    elif len(args) == 3 and all(isinstance(x, int) for x in args):
        y, m, d = int(args[0]), int(args[1]), int(args[2])
    else:
        raise TypeError("get_honmeisei expects (year, month, day) or (birthdate)")

    # 立春(概算): 2/4
    if (m == 1) or (m == 2 and d < 4):
        y -= 1

    return _year_center_star(y)


def get_honmeisei_name(*args: Union[int, DateLike]) -> str:
    """Get 本命星 name in Japanese, e.g., '五黄土星'."""
    n = get_honmeisei(*args)
    return STAR_NAMES_JP[n]


def get_directions(*args, lang: str = "ja", **kwargs) -> Dict[str, str]:
    """Compute a simplified 'good direction' for year/month.

    Backward-compatible call styles:
      A) get_directions(year:int, month:int, honmeisei:int|str, lang='ja')
      B) get_directions(honmeisei:int|str, year:int, month:int, lang='ja')

    Args:
      year: target year (Gregorian)
      month: 0 for year盤, 1..12 for month盤
      honmeisei: 1..9 or JP name
      lang: 'ja' or 'en'

    Returns:
      {"good": <direction label>}
    """
    # Support legacy kw usage
    if "year" in kwargs and "month" in kwargs and "honmeisei" in kwargs:
        year = int(kwargs["year"])
        month = int(kwargs["month"])
        hon = kwargs["honmeisei"]
    else:
        if len(args) < 3:
            raise TypeError("get_directions expects 3 positional args")

        a0, a1, a2 = args[0], args[1], args[2]

        # Heuristic: if first arg looks like a year (>= 1800), treat as style A.
        if isinstance(a0, int) and a0 >= 1800:
            year = int(a0)
            month = int(a1)
            hon = a2
        else:
            hon = a0
            year = int(a1)
            month = int(a2)

    person_star = _normalize_star_number(hon)

    if month == 0:
        center = _year_center_star(year)
    else:
        center = _month_center_star(year, month)

    # Exclude 本命殺 & 本命的殺 (based on the given盤)
    hon_dir = _direction_of_star(center, person_star)
    excluded = set()
    if hon_dir:
        excluded.add(hon_dir)
        excluded.add(OPPOSITE_DIR[hon_dir])

    # Evaluate candidate directions
    dir_to_star = _chart_dir_to_star(center)
    candidates = [
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "northwest",
    ]

    good_dir_key: Optional[str] = None

    for d in candidates:
        if d in excluded:
            continue
        if _is_favorable_by_element(dir_to_star[d], person_star):
            good_dir_key = d
            break

    # Fallback: first non-excluded direction
    if good_dir_key is None:
        for d in candidates:
            if d in excluded:
                continue
            good_dir_key = d
            break

    if good_dir_key is None:
        # Extremely unlikely (all excluded) - fall back to north.
        good_dir_key = "north"

    label_map = DIR_JP if (lang or "ja").lower().startswith("ja") else DIR_EN
    return {"good": label_map[good_dir_key]}
# ============================
# Backward-compat helper APIs
# ============================

_DIR_JA_EN = {
    "北": "North",
    "北東": "Northeast",
    "東": "East",
    "南東": "Southeast",
    "南": "South",
    "南西": "Southwest",
    "西": "West",
    "北西": "Northwest",
}

def _dir_ja_to_en(d: str) -> str:
    return _DIR_JA_EN.get((d or "").strip(), (d or "").strip())

def get_kyusei_fortune(birthdate_str: str, now=None, lang: str = "ja") -> str:
    """Return a short Kyusei Kigaku summary text.

    This function exists for backward-compatibility because some parts of the app import
    `get_kyusei_fortune` from this module.

    Args:
        birthdate_str: 'YYYY-MM-DD'
        now: datetime or None (defaults to datetime.now())
        lang: 'ja' or 'en'

    Returns:
        Summary string (Japanese or English). In English mode, the Kyusei star name is kept in Japanese.
    """
    if now is None:
        now = datetime.now()

    honmeisei_num = get_honmeisei(birthdate_str)
    honmeisei_name = KYUSEI_NAMES_JA.get(honmeisei_num, "")

    dirs = get_directions(birthdate_str, now=now)
    y = now.year

    if (lang or "").lower().startswith("en"):
        year_dir = _dir_ja_to_en(dirs.get("year", ""))
        month_dir = _dir_ja_to_en(dirs.get("month", ""))
        next_dir = _dir_ja_to_en(dirs.get("next_month", ""))
        # Keep Kyusei name in Japanese per requirement
        return f"Main Star: {honmeisei_name}. Lucky directions — {y}: {year_dir}; this month: {month_dir}; next month: {next_dir}."
    else:
        year_dir = (dirs.get("year", "") or "").strip()
        month_dir = (dirs.get("month", "") or "").strip()
        next_dir = (dirs.get("next_month", "") or "").strip()
        return f"あなたの本命星は「{honmeisei_name}」です。{y}年の吉方位：{year_dir}　今月：{month_dir}　来月：{next_dir}です。"


STAR_NAMES_JP = ["一白水星", "二黒土星", "三碧木星", "四緑木星", "五黄土星", "六白金星", "七赤金星", "八白土星", "九紫火星"]
STAR_NAMES_EN = ["Ippaku Water", "Jikoku Earth", "Sanpeki Wood", "Shiroku Wood", "Go-Ou Earth", "Roppaku Metal", "Shichiseki Metal", "Happaku Earth", "Kyushi Fire"]

def get_honmeisei_name(birthdate, lang="ja"):
    num = get_honmeisei(birthdate)
    if lang.startswith("en"):
        return STAR_NAMES_EN[num - 1]
    return STAR_NAMES_JP[num - 1]
