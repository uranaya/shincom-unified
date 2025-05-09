
from datetime import datetime
from hayami_table_full_complete import hayami_table

stems = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
branches = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

def get_nicchu_eto(birthdate: str) -> str:
    """
    生年月日（YYYY-MM-DD）から干支（日柱）を返す。
    """
    try:
        date_obj = datetime.strptime(birthdate, "%Y-%m-%d")
        year, month, day = date_obj.year, date_obj.month, date_obj.day
        if year in hayami_table and 1 <= month <= 12:
            base = hayami_table[year][month - 1]
            index = base + day - 1
            while index >= 60:
                index -= 60
            return stems[index % 10] + branches[index % 12]
        return "不明"
    except Exception as e:
        print("❌ 日柱計算エラー:", e)
        return "不明"
