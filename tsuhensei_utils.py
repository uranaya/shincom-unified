
# tsuhensei_utils.py -- 通変星ユーティリティ（年支・月支を自動計算対応）

# 十干・十二支の五行・陰陽情報
gogyou_dict = {
    "甲": ("木", "陽"), "乙": ("木", "陰"),
    "丙": ("火", "陽"), "丁": ("火", "陰"),
    "戊": ("土", "陽"), "己": ("土", "陰"),
    "庚": ("金", "陽"), "辛": ("金", "陰"),
    "壬": ("水", "陽"), "癸": ("水", "陰"),
}

# 十二支の本元蔵干（通変星判断用）
shishi_zokan_main = {
    "子": "癸", "丑": "己", "寅": "甲", "卯": "乙", "辰": "戊",
    "巳": "丙", "午": "丁", "未": "己", "申": "庚", "酉": "辛",
    "戌": "戊", "亥": "壬"
}

def get_eto_branch(year: int) -> str:
    branches = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    base_year = 1984  # 子年
    return branches[(year - base_year) % 12]

def get_eto_month_branch(month: int) -> str:
    # 寅月（旧暦2月）を1月として扱う順番
    branches = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]
    return branches[(month - 1) % 12]

def get_tsuhensei(nikkang: str, branch: str) -> str:
    day_elem, day_yin = gogyou_dict.get(nikkang, ("不明", "不明"))
    month_kan = shishi_zokan_main.get(branch)
    if not month_kan:
        return "不明"
    month_elem, month_yin = gogyou_dict.get(month_kan, ("不明", "不明"))

    if day_elem == month_elem:
        return "比肩" if day_yin == month_yin else "劫財"
    elif (day_elem, month_elem) in [("木", "火"), ("火", "土"), ("土", "金"), ("金", "水"), ("水", "木")]:
        return "食神" if day_yin == month_yin else "傷官"
    elif (month_elem, day_elem) in [("木", "火"), ("火", "土"), ("土", "金"), ("金", "水"), ("水", "木")]:
        return "正印" if day_yin == month_yin else "偏印"
    elif (month_elem, day_elem) in [("木", "金"), ("火", "水"), ("土", "木"), ("金", "火"), ("水", "土")]:
        return "正官" if day_yin == month_yin else "偏官"
    elif (day_elem, month_elem) in [("木", "土"), ("火", "金"), ("土", "水"), ("金", "木"), ("水", "火")]:
        return "正財" if day_yin == month_yin else "偏財"
    return "不明"

def get_tsuhensei_for_date(birthdate: str, year: int, month: int) -> str:
    from hayami_table_full_complete import get_nicchu_eto
    nikkanshi = get_nicchu_eto(birthdate)
    nikkang = nikkanshi[0]
    branch = get_eto_month_branch(month)
    return get_tsuhensei(nikkang, branch)

def get_tsuhensei_for_year(birthdate: str, year: int) -> str:
    from hayami_table_full_complete import get_nicchu_eto
    nikkanshi = get_nicchu_eto(birthdate)
    nikkang = nikkanshi[0]
    branch = get_eto_branch(year)
    return get_tsuhensei(nikkang, branch)
