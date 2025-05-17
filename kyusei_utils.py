import datetime
from dateutil.relativedelta import relativedelta

# 九星気学 本命星を計算
def get_honmeisei(year: int, month: int, day: int) -> str:
    try:
        # 立春（2月4日）より前は前年生まれとして扱う
        if month < 2 or (month == 2 and day < 4):
            year -= 1
        # 九星は1から9のサイクル。以下は本命星番号を計算する一例
        base = (11 - (year % 9)) % 9
        num = 9 if base == 0 else base
        stars = {
            1: "一白水星",
            2: "二黒土星",
            3: "三碧木星",
            4: "四緑木星",
            5: "五黄土星",
            6: "六白金星",
            7: "七赤金星",
            8: "八白土星",
            9: "九紫火星"
        }
        return stars.get(num, "不明")
    except Exception as e:
        print("❌ 本命星計算エラー:", e)
        return "不明"

# 九星気学 吉方位を取得（yearに対してmonth月の吉方位。month=0の場合は年運の吉方位）
def get_directions(year: int, month: int, honmeisei: str) -> dict:
    try:
        # 実際の吉方位計算ロジックは省略
        return {"good": "不明"}
    except Exception as e:
        print("❌ 方位計算エラー:", e)
        return {"good": "不明"}

# 九星気学の本命星と吉方位の総合メッセージを取得
def get_kyusei_fortune(year: int, month: int, day: int) -> str:
    try:
        honmeisei = get_honmeisei(year, month, day)
        today = datetime.date.today()
        dir_year = get_directions(today.year, 0, honmeisei)
        dir_now = get_directions(today.year, today.month, honmeisei)
        next_month_date = today + relativedelta(months=1)
        dir_next = get_directions(next_month_date.year, next_month_date.month, honmeisei)
        good_dir_year = dir_year.get("good", "不明")
        good_dir_now = dir_now.get("good", "不明")
        good_dir_next = dir_next.get("good", "不明")
        return f"あなたの本命星は{honmeisei}です\n{today.year}年の吉方位は{good_dir_year}、今月は{good_dir_now}、来月は{good_dir_next}です。"
    except Exception as e:
        print("❌ 九星気学取得失敗:", e)
        return ""
