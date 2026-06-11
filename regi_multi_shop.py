# -*- coding: utf-8 -*-
"""
店舗別レジ拡張モジュール v5

- /regi/onosun       おのだサンパーク店 売上入力
- /regi/basilisk     バジリスク店 売上入力
- /admin/regi/onosun おのだサンパーク店 管理画面（店舗別パスワード）
- /admin/regi/basilisk バジリスク店 管理画面（店舗別パスワード）

重要:
スタッフ・鑑定方法は app_unified.py 側の STAFF_LIST / METHOD_LIST を正とする。
register_regi_multi_shop_routes(app, DATABASE_URL, STAFF_LIST, METHOD_LIST) の形で渡してください。
"""

import os
import io
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import psycopg2
import psycopg2.extras
from flask import (
    abort,
    make_response,
    redirect,
    render_template_string,
    request,
    send_file,
    session,
)

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
try:
    from reportlab.pdfbase.ttfonts import TTFont
except Exception:  # pragma: no cover
    TTFont = None


SHOP_CONFIGS: Dict[str, Dict[str, Any]] = {
    "onosun": {
        "key": "onosun",
        "name": "おのだサンパーク店",
        "short_name": "おのだ",
        "invoice_note": "通常出店料：対面30％・コンピューター50％。特別出店料：対面20％・コンピューター40％。",
        "normal_rates": {"taimen": Decimal("0.30"), "pc": Decimal("0.50"), "food": Decimal("0.00")},
        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.40"), "food": Decimal("0.00")},
        "force_campaign": False,
        "password_env": "REGI_ONOSUN_ADMIN_PASSWORD",
        "fallback_password_env": "REGI_ADMIN_PASSWORD",
        "default_password": "admin123",
    },
    "basilisk": {
        "key": "basilisk",
        "name": "バジリスク店",
        "short_name": "バジリスク",
        "invoice_note": "キャンペーン出店料：対面・コンピューター・飲食ともに売上の20％。",
        "normal_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20"), "food": Decimal("0.20")},
        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20"), "food": Decimal("0.20")},
        "force_campaign": True,
        "password_env": "REGI_BASILISK_ADMIN_PASSWORD",
        "fallback_password_env": None,
        "default_password": "basilisk123",
    },
}

# app_unified.py の既存仕様に合わせた既定値。
# register_regi_multi_shop_routes() へ STAFF_LIST が渡ってこない場合でも、
# 「新保・二見・スタッフ」のような仮リストを出さないための保険です。
DEFAULT_STAFF_LIST: List[str] = [
    "HIROMI", "美帆", "あい", "礼", "あお",
    "月のかけら", "金子美月", "水木杏香", "幽香", "優芳",
    "蛍石", "うらなや", "ふく", "COCORAKU", "リリア",
]

DEFAULT_METHOD_LIST: List[str] = ["対面", "コンピューター", "現金外（クレカQR)"]
CASHLESS_KEYWORDS = ("現金外", "クレジット", "カード", "PayPay", "ペイペイ", "電子", "QR")


def _conn(database_url: Optional[str]):
    if not database_url:
        raise RuntimeError("DATABASE_URL が未設定です。Render の Environment に DATABASE_URL が必要です。")
    return psycopg2.connect(database_url)


def _money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _int_yen(value: Any) -> int:
    return int(_money(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _format_yen(value: Any) -> str:
    return f"{_int_yen(value):,}"


def _normalize_method(method: str) -> str:
    """DBに入っている '現金外（クレカQR）' などをPDF集計用に正規化"""
    if method == "対面":
        return "対面"
    if method == "コンピューター":
        return "コンピューター"
    if method == "飲食":
        return "飲食"
    if "現金外" in (method or ""):
        return "現金外"
    return method or ""


def _normalize_staff_list(staff_list: Optional[Iterable[str]]) -> List[str]:
    names: List[str] = []
    seen = set()
    for raw in staff_list or []:
        name = str(raw or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _normalize_method_list(method_list: Optional[Iterable[str]]) -> List[str]:
    methods: List[str] = []
    seen = set()
    for raw in method_list or []:
        method = str(raw or "").strip()
        if method and method not in seen:
            seen.add(method)
            methods.append(method)
    for required in DEFAULT_METHOD_LIST:
        if required not in seen:
            methods.append(required)
            seen.add(required)
    return methods or DEFAULT_METHOD_LIST[:]


def _month_range(month: Optional[str]) -> Tuple[str, date, date]:
    if not month:
        month = datetime.now().strftime("%Y-%m")
    try:
        start = datetime.strptime(month, "%Y-%m").date()
    except ValueError:
        raise ValueError("month は YYYY-MM 形式で指定してください。")
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return month, start, end


def _date_from_form(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def _shop_or_404(shop_key: str) -> Dict[str, Any]:
    shop = SHOP_CONFIGS.get(shop_key)
    if not shop:
        abort(404)
    return shop


def _shop_admin_password(shop_key: str) -> str:
    shop = _shop_or_404(shop_key)
    password = os.getenv(shop["password_env"], "")
    if not password and shop.get("fallback_password_env"):
        password = os.getenv(shop["fallback_password_env"], "")
    return password or shop["default_password"]


def _admin_session_key(shop_key: str) -> str:
    return f"regi_admin_{shop_key}"


def _is_shop_admin(shop_key: str) -> bool:
    return bool(session.get(_admin_session_key(shop_key)))


def _safe_next_url(shop_key: str, next_url: Optional[str]) -> str:
    if next_url and next_url.startswith(f"/admin/regi/{shop_key}") and not next_url.startswith("//"):
        return next_url
    return f"/admin/regi/{shop_key}"


def _invoice_force_special(shop_key: str) -> bool:
    shop = SHOP_CONFIGS[shop_key]
    return bool(shop.get("force_campaign")) or request.args.get("special") == "1"


def _invoice_label(shop_key: str, force_special: bool) -> str:
    if SHOP_CONFIGS[shop_key].get("force_campaign"):
        return "キャンペーン出店料"
    return "特別出店料" if force_special else "通常出店料"


def _rates_for(shop_key: str, force_special: bool) -> Dict[str, Decimal]:
    shop = SHOP_CONFIGS[shop_key]
    if shop.get("force_campaign") or force_special:
        return shop["special_rates"]
    return shop["normal_rates"]


def _calc_invoice_totals(total_taiken: Decimal, total_pc: Decimal, total_cashless: Decimal,
                         shop_key: str, force_special: bool, total_food: Decimal = Decimal("0")) -> Dict[str, Any]:
    rates = _rates_for(shop_key, force_special)
    store_fee = (
        total_taiken * rates["taimen"]
        + total_pc * rates["pc"]
        + total_food * rates.get("food", Decimal("0"))
    )
    store_fee = store_fee.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    store_fee_tax = (store_fee * Decimal("1.10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    final_invoice = store_fee_tax - total_cashless
    return {
        "rates": rates,
        "store_fee": store_fee,
        "store_fee_tax": store_fee_tax,
        "final_invoice": final_invoice,
    }


def _register_pdf_font() -> str:
    """
    既存仕様では static/ipaexg.ttf を使用。
    見つからない環境でもPDF生成が落ちないよう、CIDフォントにフォールバック。
    """
    font_path_candidates = [
        os.path.join("static", "ipaexg.ttf"),
        "ipaexg.ttf",
    ]
    if TTFont:
        for font_path in font_path_candidates:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont("IPAexGothic", font_path))
                    return "IPAexGothic"
                except Exception:
                    pass
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        return "HeiseiKakuGo-W5"
    except Exception:
        return "Helvetica"


def init_regi_multi_shop_tables(database_url: Optional[str]) -> None:
    """既存 sales テーブルを店舗別管理に拡張する。既存データはおのだサンパーク店扱いにする。"""
    if not database_url:
        print("⚠️ [REGI-MULTI-SHOP] DATABASE_URL 未設定のためDB初期化をスキップ", flush=True)
        return

    conn = _conn(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sales (
                        id SERIAL PRIMARY KEY,
                        date DATE DEFAULT CURRENT_DATE,
                        staff_name TEXT,
                        method TEXT,
                        amount INTEGER
                    );
                    """
                )
                cur.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS shop_key TEXT DEFAULT 'onosun';")
                cur.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                cur.execute("UPDATE sales SET shop_key = 'onosun' WHERE shop_key IS NULL OR shop_key = '';")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_shop_date ON sales (shop_key, date);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_shop_staff_date ON sales (shop_key, staff_name, date);")
        print("✅ [REGI-MULTI-SHOP] sales 店舗別拡張完了", flush=True)
    finally:
        conn.close()


def _fetch_monthly_rows(database_url: str, shop_key: str, month_start: date, month_end: date,
                        staff: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = _conn(database_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            params: List[Any] = [shop_key, month_start, month_end]
            staff_sql = ""
            if staff:
                staff_sql = " AND staff_name = %s "
                params.append(staff)
            cur.execute(
                f"""
                SELECT staff_name, method, SUM(amount)::numeric AS total
                FROM sales
                WHERE shop_key = %s
                  AND date >= %s
                  AND date < %s
                  {staff_sql}
                GROUP BY staff_name, method
                ORDER BY staff_name, method;
                """,
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def _fetch_daily_details(database_url: str, shop_key: str, month_start: date, month_end: date,
                         staff: str) -> Dict[str, Dict[str, Decimal]]:
    conn = _conn(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT date, method, SUM(amount)::numeric AS total
                FROM sales
                WHERE shop_key = %s
                  AND date >= %s
                  AND date < %s
                  AND staff_name = %s
                GROUP BY date, method
                ORDER BY date;
                """,
                (shop_key, month_start, month_end, staff),
            )
            daily: Dict[str, Dict[str, Decimal]] = {}
            for row_date, method, total in cur.fetchall():
                key = row_date.strftime("%Y-%m-%d") if hasattr(row_date, "strftime") else str(row_date)
                cat = _normalize_method(method)
                if key not in daily:
                    daily[key] = {"対面": Decimal("0"), "コンピューター": Decimal("0"), "飲食": Decimal("0"), "現金外": Decimal("0")}
                if cat in daily[key]:
                    daily[key][cat] += _money(total)
            return daily
    finally:
        conn.close()


def _aggregate_invoice(database_url: str, shop_key: str, month: str, staff: str,
                       force_special: bool) -> Dict[str, Any]:
    month, month_start, month_end = _month_range(month)
    rows = _fetch_monthly_rows(database_url, shop_key, month_start, month_end, staff=staff)

    total_taiken = Decimal("0")
    total_pc = Decimal("0")
    total_food = Decimal("0")
    total_cashless = Decimal("0")

    for row in rows:
        cat = _normalize_method(row.get("method"))
        amount = _money(row.get("total"))
        if cat == "対面":
            total_taiken += amount
        elif cat == "コンピューター":
            total_pc += amount
        elif cat == "飲食":
            total_food += amount
        elif cat == "現金外":
            total_cashless += amount

    totals = _calc_invoice_totals(total_taiken, total_pc, total_cashless, shop_key, force_special, total_food)
    daily_details = _fetch_daily_details(database_url, shop_key, month_start, month_end, staff)

    return {
        "month": month,
        "staff": staff,
        "total_taiken": total_taiken,
        "total_pc": total_pc,
        "total_food": total_food,
        "total_cashless": total_cashless,
        "daily_details": daily_details,
        **totals,
    }


def _aggregate_monthly(database_url: str, shop_key: str, month: str) -> Dict[str, Any]:
    month, month_start, month_end = _month_range(month)
    rows = _fetch_monthly_rows(database_url, shop_key, month_start, month_end)

    details: Dict[str, Dict[str, Any]] = {}
    staff_names = set()

    for row in rows:
        staff = (row.get("staff_name") or "").strip()
        method = row.get("method") or ""
        amount = _money(row.get("total"))
        if not staff:
            continue

        staff_names.add(staff)
        if staff not in details:
            details[staff] = {
                "methods": {},
                "total": Decimal("0"),
                "cashless_total": Decimal("0"),
                "visit_days": 0,
                "avg_sales": Decimal("0"),
            }

        cat = _normalize_method(method)
        details[staff]["methods"][cat] = details[staff]["methods"].get(cat, Decimal("0")) + amount
        if cat in ("対面", "コンピューター", "飲食"):
            details[staff]["total"] += amount
        elif cat == "現金外":
            details[staff]["cashless_total"] += amount

    conn = _conn(database_url)
    try:
        with conn.cursor() as cur:
            for staff in list(details.keys()):
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT date)
                    FROM sales
                    WHERE shop_key = %s
                      AND date >= %s
                      AND date < %s
                      AND staff_name = %s;
                    """,
                    (shop_key, month_start, month_end, staff),
                )
                visit_days = cur.fetchone()[0] or 0
                details[staff]["visit_days"] = visit_days
                details[staff]["avg_sales"] = (
                    (details[staff]["total"] / Decimal(visit_days)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                    if visit_days > 0 else Decimal("0")
                )
    finally:
        conn.close()

    total_taiken = sum((d["methods"].get("対面", Decimal("0")) for d in details.values()), Decimal("0"))
    total_pc = sum((d["methods"].get("コンピューター", Decimal("0")) for d in details.values()), Decimal("0"))
    total_food = sum((d["methods"].get("飲食", Decimal("0")) for d in details.values()), Decimal("0"))
    total_cashless = sum((d["cashless_total"] for d in details.values()), Decimal("0"))

    # 月別画面の上部に、旧仕様と同じ「対面合計 / コンピューター合計 / 現金外合計 / 出店料 / 請求額」を表示する。
    # おのだサンパーク店は通常・特別の両方を使うため、通常計算と特別計算の両方を用意する。
    monthly_normal_invoice = _calc_invoice_totals(
        total_taiken, total_pc, total_cashless, shop_key, force_special=False, total_food=total_food
    )
    monthly_special_invoice = _calc_invoice_totals(
        total_taiken, total_pc, total_cashless, shop_key, force_special=True, total_food=total_food
    )

    return {
        "month": month,
        "month_start": month_start,
        "month_end": month_end,
        "details": details,
        "staff_list": sorted(staff_names),
        "total_taiken": total_taiken,
        "total_pc": total_pc,
        "total_food": total_food,
        "total_cashless": total_cashless,
        "monthly_normal_invoice": monthly_normal_invoice,
        "monthly_special_invoice": monthly_special_invoice,
    }


def _create_invoice_pdf(output_path: str, shop_name: str, invoice_label: str, month: str, staff: str,
                        total_taiken: Decimal, total_pc: Decimal, total_food: Decimal, total_cashless: Decimal,
                        store_fee: Decimal, store_fee_tax: Decimal, final_invoice: Decimal,
                        daily_details: Dict[str, Dict[str, Decimal]]) -> None:
    font_name = _register_pdf_font()

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # タイトル
    c.setFont(font_name, 18)
    c.drawString(20 * mm, height - 20 * mm, f"{month} {staff} 請求書")

    # 店舗・出店料区分
    c.setFont(font_name, 10)
    c.drawString(20 * mm, height - 28 * mm, f"店舗：{shop_name}　区分：{invoice_label}")

    # 会社情報（元仕様準拠）
    c.setFont(font_name, 9)
    company_info = [
        "〒756-0817 山口県山陽小野田市大字小野田７３０番地２",
        "合同会社むすび家プランニング",
        "代表社員　新保　保（しんぽ　たもつ）",
        "TEL: 090-7506-2065",
        "Email: musubiya.planning@gmail.com",
    ]
    y_info = height - 38 * mm
    for line in company_info:
        c.drawString(20 * mm, y_info, line)
        y_info -= 5 * mm

    c.drawString(20 * mm, y_info, "適格請求書発行事業者登録番号：＿＿＿＿＿＿＿＿＿＿＿＿")

    # 売上・請求額（元仕様準拠）
    y = height - 75 * mm
    c.setFont(font_name, 10)
    rows = [
        ("対面売上合計", total_taiken),
        ("コンピューター売上合計", total_pc),
        ("飲食売上合計", total_food),
        ("現金外合計", total_cashless),
        ("出店料（税抜）", store_fee),
        ("出店料（税込10％）", store_fee_tax),
        ("請求額（現金外差引後）", final_invoice),
    ]
    for label, value in rows:
        c.drawString(20 * mm, y, label)
        c.drawRightString(180 * mm, y, f"{_format_yen(value)} 円")
        y -= 10 * mm

    # 日別内訳（元仕様準拠）
    y -= 10 * mm
    c.setFont(font_name, 12)
    c.drawString(20 * mm, y, "【日別内訳】")
    y -= 8 * mm

    c.setFont(font_name, 10)
    c.drawString(20 * mm, y, "日付")
    c.drawString(55 * mm, y, "対面")
    c.drawString(90 * mm, y, "コンピューター")
    c.drawString(130 * mm, y, "飲食")
    c.drawString(160 * mm, y, "現金外")
    y -= 6 * mm
    c.line(20 * mm, y, 180 * mm, y)
    y -= 6 * mm

    for date_str, amounts in daily_details.items():
        c.drawString(20 * mm, y, date_str)
        c.drawRightString(75 * mm, y, _format_yen(amounts.get("対面", 0)))
        c.drawRightString(120 * mm, y, _format_yen(amounts.get("コンピューター", 0)))
        c.drawRightString(150 * mm, y, _format_yen(amounts.get("飲食", 0)))
        c.drawRightString(180 * mm, y, _format_yen(amounts.get("現金外", 0)))
        y -= 6 * mm
        if y < 40 * mm:
            c.showPage()
            c.setFont(font_name, 10)
            y = height - 20 * mm

    # 振込先情報（元仕様準拠）
    y -= 10 * mm
    if y < 40 * mm:
        c.showPage()
        c.setFont(font_name, 10)
        y = height - 20 * mm

    c.setFont(font_name, 11)
    c.drawString(20 * mm, y, "【振込先】")
    y -= 6 * mm
    bank_info = [
        "山口銀行　西ノ浜　普通　5016837",
        "ゆうちょ　15580-30544691",
        "PayPay　005-6931827",
        "西京銀行　日の出　普通　2055422",
    ]
    c.setFont(font_name, 10)
    for line in bank_info:
        c.drawString(25 * mm, y, line)
        y -= 6 * mm

    c.save()


PORTAL_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>店舗別レジ</title>
  <style>
    body { font-family: sans-serif; padding: 20px; max-width: 720px; margin: auto; }
    a.btn { display:block; padding:14px; margin:12px 0; border-radius:8px; background:#f3f3f3; color:#111; text-decoration:none; border:1px solid #ddd; }
    small { color:#666; }
  </style>
</head>
<body>
  <h1>店舗別レジ</h1>
  {% for key, shop in shops.items() %}
    <a class="btn" href="/regi/{{ key }}">売上入力：{{ shop.name }}</a>
    <a class="btn" href="/admin/regi/{{ key }}">管理画面：{{ shop.name }}</a>
  {% endfor %}
</body>
</html>
"""

INPUT_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ shop.name }} 売上入力</title>
  <style>
    body { font-family: sans-serif; padding: 16px; max-width: 560px; margin: auto; }
    label { display:block; font-weight: bold; margin-top: 14px; }
    input, select, button { width:100%; box-sizing:border-box; padding:12px; font-size:16px; margin-top:6px; }
    button { background:#2e7d32; color:white; border:0; border-radius:6px; margin-top:20px; }
    .ok { background:#e8f5e9; padding:12px; border-radius:6px; margin:12px 0; }
    .links a { display:inline-block; margin-top:16px; margin-right:12px; }
  </style>
</head>
<body>
  <h1>{{ shop.name }} 売上入力</h1>
  {% if saved %}<div class="ok">保存しました。</div>{% endif %}
  <form method="post">
    <label>日付</label>
    <input type="date" name="date" value="{{ today }}">

    <label>スタッフ</label>
    <select name="staff" required>
      {% for staff in staffs %}
        <option value="{{ staff }}">{{ staff }}</option>
      {% endfor %}
    </select>

    <label>鑑定方法</label>
    <select name="method" required>
      {% for method in methods %}
        <option value="{{ method }}">{{ method }}</option>
      {% endfor %}
    </select>

    <label>金額</label>
    <input type="number" name="amount" inputmode="numeric" min="0" step="1" required>

    <button type="submit">売上を登録</button>
  </form>

  <div class="links">
    <a href="/regi-shops">店舗選択へ</a>
  </div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ shop.name }} 管理ログイン</title>
  <style>
    body { font-family: sans-serif; padding: 20px; max-width: 480px; margin:auto; }
    input, button { width:100%; box-sizing:border-box; padding:12px; font-size:16px; margin-top:8px; }
    button { background:#1565c0; color:white; border:0; border-radius:6px; margin-top:16px; }
    .err { color:#b00020; margin:12px 0; }
  </style>
</head>
<body>
  <h1>{{ shop.name }} 管理ログイン</h1>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="post">
    <input type="hidden" name="next" value="{{ next_url }}">
    <label>管理パスワード</label>
    <input type="password" name="password" autocomplete="current-password" autofocus>
    <button type="submit">ログイン</button>
  </form>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ shop.name }} 管理画面</title>
  <style>
    body { font-family:sans-serif; padding:20px; max-width:800px; margin:auto; }
    a.btn { display:block; padding:14px; margin:12px 0; background:#f3f3f3; border:1px solid #ddd; border-radius:8px; color:#111; text-decoration:none; }
  </style>
</head>
<body>
  <h1>{{ shop.name }} 管理画面</h1>
  <p>{{ shop.invoice_note }}</p>
  <a class="btn" href="/admin/regi/{{ shop.key }}/monthly">月別集計・請求書</a>
  <a class="btn" href="/admin/regi/{{ shop.key }}/daily">日別売上一覧・修正</a>
  <a class="btn" href="/admin/regi/{{ shop.key }}/csv">CSV出力</a>
  <a class="btn" href="/admin/regi/{{ shop.key }}/logout">ログアウト</a>
</body>
</html>
"""

MONTHLY_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ shop.name }} 月別集計</title>
  <style>
    body { font-family:sans-serif; padding:16px; max-width:1100px; margin:auto; }
    table { width:100%; border-collapse:collapse; margin-top:16px; }
    th, td { border:1px solid #ccc; padding:8px; text-align:right; }
    th { background:#f0f0f0; text-align:center; }
    td.name { text-align:left; }
    input, button { padding:8px; font-size:14px; }
    a.btn { display:inline-block; padding:7px 10px; margin:2px; background:#eee; border-radius:4px; text-decoration:none; color:#111; }
    .summary-wrap { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:12px; margin:16px 0 22px; }
    .summary-box { border:1px solid #ccc; border-radius:8px; padding:12px; background:#fafafa; }
    .summary-box h2 { font-size:18px; margin:0 0 8px; }
    .summary-line { display:flex; justify-content:space-between; border-bottom:1px dotted #ddd; padding:5px 0; }
    .summary-line strong { font-size:18px; }
  </style>
</head>
<body>
  <h1>{{ shop.name }} 月別集計</h1>
  <form method="get">
    <input type="month" name="month" value="{{ month }}">
    <button type="submit">表示</button>
  </form>

  <p>{{ shop.invoice_note }}</p>

  <div class="summary-wrap">
    <div class="summary-box">
      <h2>
        {% if shop.key == "onosun" %}
          月全体の請求計算（通常出店料）
        {% elif shop.key == "basilisk" %}
          月全体の請求計算（キャンペーン20％）
        {% else %}
          月全体の請求計算
        {% endif %}
      </h2>
      <div class="summary-line"><span>対面合計</span><strong>{{ yen(total_taiken) }}円</strong></div>
      <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>
      {% if shop.key == "basilisk" %}<div class="summary-line"><span>飲食合計</span><strong>{{ yen(total_food) }}円</strong></div>{% endif %}
      <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>
      <div class="summary-line"><span>出店料（税抜）</span><strong>{{ yen(monthly_normal_invoice.store_fee) }}円</strong></div>
      <div class="summary-line"><span>出店料（税込10％）</span><strong>{{ yen(monthly_normal_invoice.store_fee_tax) }}円</strong></div>
      <div class="summary-line"><span>請求額（現金外差引後）</span><strong>{{ yen(monthly_normal_invoice.final_invoice) }}円</strong></div>
    </div>

    {% if shop.key == "onosun" %}
      <div class="summary-box">
        <h2>月全体の請求計算（特別出店料）</h2>
        <div class="summary-line"><span>対面合計</span><strong>{{ yen(total_taiken) }}円</strong></div>
        <div class="summary-line"><span>コンピューター合計</span><strong>{{ yen(total_pc) }}円</strong></div>
        <div class="summary-line"><span>現金外合計</span><strong>{{ yen(total_cashless) }}円</strong></div>
        <div class="summary-line"><span>出店料（税抜）</span><strong>{{ yen(monthly_special_invoice.store_fee) }}円</strong></div>
        <div class="summary-line"><span>出店料（税込10％）</span><strong>{{ yen(monthly_special_invoice.store_fee_tax) }}円</strong></div>
        <div class="summary-line"><span>請求額（現金外差引後）</span><strong>{{ yen(monthly_special_invoice.final_invoice) }}円</strong></div>
      </div>
    {% endif %}
  </div>

  <table>
    <tr>
      <th>スタッフ</th>
      <th>対面</th>
      <th>コンピューター</th>
      {% if shop.key == "basilisk" %}<th>飲食</th>{% endif %}
      <th>現金外</th>
      <th>{% if shop.key == "basilisk" %}対面+コンピューター+飲食{% else %}対面+コンピューター{% endif %}</th>
      <th>出勤日数</th>
      <th>平均売上</th>
      <th>請求書</th>
    </tr>
    {% for staff, d in details.items() %}
      <tr>
        <td class="name">{{ staff }}</td>
        <td>{{ yen(d.methods.get("対面", 0)) }}</td>
        <td>{{ yen(d.methods.get("コンピューター", 0)) }}</td>
        {% if shop.key == "basilisk" %}<td>{{ yen(d.methods.get("飲食", 0)) }}</td>{% endif %}
        <td>{{ yen(d.cashless_total) }}</td>
        <td>{{ yen(d.total) }}</td>
        <td>{{ d.visit_days }}</td>
        <td>{{ yen(d.avg_sales) }}</td>
        <td>
          {% if shop.key == "onosun" %}
            <a class="btn" href="/admin/regi/{{ shop.key }}/invoice?month={{ month }}&staff={{ staff }}">通常</a>
            <a class="btn" href="/admin/regi/{{ shop.key }}/invoice?month={{ month }}&staff={{ staff }}&special=1">特別</a>
            <a class="btn" href="/admin/regi/{{ shop.key }}/invoice_pdf?month={{ month }}&staff={{ staff }}">通常PDF</a>
            <a class="btn" href="/admin/regi/{{ shop.key }}/invoice_pdf?month={{ month }}&staff={{ staff }}&special=1">特別PDF</a>
          {% else %}
            <a class="btn" href="/admin/regi/{{ shop.key }}/invoice?month={{ month }}&staff={{ staff }}">請求書</a>
            <a class="btn" href="/admin/regi/{{ shop.key }}/invoice_pdf?month={{ month }}&staff={{ staff }}">PDF</a>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
  </table>

  <p>
    <a href="/admin/regi/{{ shop.key }}">管理トップへ</a>
  </p>
</body>
</html>
"""

INVOICE_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ month }} {{ staff }} 請求書</title>
  <style>
    body {
      font-family: sans-serif;
      padding: 20px;
      margin: 0;
      max-width: 700px;
      margin: auto;
      font-size: 16px;
      line-height: 1.6;
    }
    h2 { margin-bottom: 8px; text-align: center; }
    .sub { text-align:center; color:#555; margin-bottom:20px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: right; }
    th { background-color: #f0f0f0; text-align: center; }
    .left { text-align:left; }
    .total-row td { font-weight: bold; font-size: 18px; background-color: #f9f9f9; }
    button, a.btn {
      display:inline-block;
      padding: 10px 20px;
      font-size: 16px;
      margin-top: 12px;
      margin-right: 8px;
      background-color: #4CAF50;
      color: white;
      border: none;
      cursor: pointer;
      text-decoration:none;
    }
    @media print { button, a.btn { display: none; } }
  </style>
</head>
<body>
  <h2>{{ month }} {{ staff }} 請求書</h2>
  <div class="sub">{{ shop.name }} / {{ invoice_label }}</div>

  <table>
    <tr><th>項目</th><th>金額 (円)</th></tr>
    <tr><td class="left">対面売上合計</td><td>{{ yen(total_taiken) }}</td></tr>
    <tr><td class="left">コンピューター売上合計</td><td>{{ yen(total_pc) }}</td></tr>
    {% if shop.key == "basilisk" %}<tr><td class="left">飲食売上合計</td><td>{{ yen(total_food) }}</td></tr>{% endif %}
    <tr><td class="left">現金外合計</td><td>{{ yen(total_cashless) }}</td></tr>
    <tr><td class="left">出店料（税抜）</td><td>{{ yen(store_fee) }}</td></tr>
    <tr><td class="left">出店料（税込10％）</td><td>{{ yen(store_fee_tax) }}</td></tr>
    <tr class="total-row"><td class="left">請求額（現金外差引後）</td><td>{{ yen(final_invoice) }}</td></tr>
  </table>

  <a class="btn" href="/admin/regi/{{ shop.key }}/invoice_pdf?month={{ month }}&staff={{ staff }}{% if force_special %}&special=1{% endif %}">
    PDF出力
  </a>

  {% if shop.key == "onosun" %}
    {% if force_special %}
      <a class="btn" href="/admin/regi/{{ shop.key }}/invoice?month={{ month }}&staff={{ staff }}">通常出店料へ</a>
    {% else %}
      <a class="btn" href="/admin/regi/{{ shop.key }}/invoice?month={{ month }}&staff={{ staff }}&special=1">特別出店料へ</a>
    {% endif %}
  {% endif %}

  <a class="btn" href="/admin/regi/{{ shop.key }}/monthly?month={{ month }}">月別集計へ</a>
</body>
</html>
"""

DAILY_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ shop.name }} 日別売上一覧</title>
  <style>
    body { font-family:sans-serif; padding:16px; max-width:1000px; margin:auto; }
    table { width:100%; border-collapse:collapse; margin-top:16px; }
    th, td { border:1px solid #ccc; padding:8px; }
    th { background:#f0f0f0; }
    td.num { text-align:right; }
    input, select, button { padding:8px; }
    a.btn, button.btn { display:inline-block; padding:6px 10px; background:#eee; border:1px solid #ccc; border-radius:4px; color:#111; text-decoration:none; }
    form.inline { display:inline; }
  </style>
</head>
<body>
  <h1>{{ shop.name }} 日別売上一覧</h1>
  <form method="get">
    <input type="date" name="date" value="{{ target_date }}">
    <button type="submit">表示</button>
  </form>
  <table>
    <tr>
      <th>ID</th><th>日付</th><th>スタッフ</th><th>方法</th><th>金額</th><th>操作</th>
    </tr>
    {% for row in rows %}
      <tr>
        <td>{{ row.id }}</td>
        <td>{{ row.date }}</td>
        <td>{{ row.staff_name }}</td>
        <td>{{ row.method }}</td>
        <td class="num">{{ yen(row.amount) }}</td>
        <td>
          <a class="btn" href="/admin/regi/{{ shop.key }}/sale/{{ row.id }}/edit">修正</a>
          <form class="inline" method="post" action="/admin/regi/{{ shop.key }}/sale/{{ row.id }}/delete" onsubmit="return confirm('削除してよろしいですか？');">
            <button class="btn" type="submit">削除</button>
          </form>
        </td>
      </tr>
    {% endfor %}
  </table>
  <p><a href="/admin/regi/{{ shop.key }}">管理トップへ</a></p>
</body>
</html>
"""

EDIT_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>売上修正</title>
  <style>
    body { font-family:sans-serif; padding:16px; max-width:560px; margin:auto; }
    label { display:block; font-weight:bold; margin-top:14px; }
    input, select, button { width:100%; box-sizing:border-box; padding:12px; font-size:16px; margin-top:6px; }
    button { background:#1565c0; color:white; border:0; border-radius:6px; margin-top:20px; }
  </style>
</head>
<body>
  <h1>{{ shop.name }} 売上修正</h1>
  <form method="post">
    <label>日付</label>
    <input type="date" name="date" value="{{ row.date }}">

    <label>スタッフ</label>
    <select name="staff" required>
      {% for staff in staffs %}
        <option value="{{ staff }}" {% if staff == row.staff_name %}selected{% endif %}>{{ staff }}</option>
      {% endfor %}
    </select>

    <label>鑑定方法</label>
    <select name="method" required>
      {% for method in methods %}
        <option value="{{ method }}" {% if method == row.method %}selected{% endif %}>{{ method }}</option>
      {% endfor %}
    </select>

    <label>金額</label>
    <input type="number" name="amount" value="{{ row.amount }}" min="0" step="1" required>

    <button type="submit">更新</button>
  </form>
  <p><a href="/admin/regi/{{ shop.key }}/daily?date={{ row.date }}">戻る</a></p>
</body>
</html>
"""


def register_regi_multi_shop_routes(
    app,
    database_url: Optional[str],
    staff_list: Optional[Iterable[str]] = None,
    method_list: Optional[Iterable[str]] = None,
) -> None:
    """
    店舗別レジルートを Flask app に登録する。

    staff_list / method_list は app_unified.py の STAFF_LIST / METHOD_LIST を渡してください。
    ここでは固定の仮スタッフを使わず、渡された一覧を最優先します。
    """
    fallback_staffs = _normalize_staff_list(staff_list) or DEFAULT_STAFF_LIST[:]
    methods = _normalize_method_list(method_list)

    def current_methods(shop_key: str) -> List[str]:
        result = methods[:]
        if shop_key == "basilisk" and "飲食" not in result:
            if "コンピューター" in result:
                result.insert(result.index("コンピューター") + 1, "飲食")
            else:
                result.append("飲食")
        return result

    def yen(value: Any) -> str:
        return _format_yen(value)

    def current_staffs() -> List[str]:
        return fallback_staffs

    def require_shop_admin(shop_key: str):
        _shop_or_404(shop_key)
        if _is_shop_admin(shop_key):
            return None
        next_url = quote(request.full_path if request.query_string else request.path, safe="/:?=&%")
        return redirect(f"/admin/regi/{shop_key}/login?next={next_url}")

    def portal():
        return render_template_string(PORTAL_TEMPLATE, shops=SHOP_CONFIGS)

    def input_sales(shop_key: str):
        shop = _shop_or_404(shop_key)
        if request.method == "POST":
            if not database_url:
                return "DATABASE_URL が未設定です。", 500

            staff = (request.form.get("staff") or request.form.get("staff_name") or "").strip()
            method = (request.form.get("method") or "").strip()
            amount_raw = request.form.get("amount") or "0"
            sale_date = _date_from_form(request.form.get("date"))

            if not staff or not method:
                return "スタッフ名と鑑定方法を入力してください。", 400

            try:
                amount = int(str(amount_raw).replace(",", "").strip())
            except ValueError:
                return "金額は数値で入力してください。", 400

            conn = _conn(database_url)
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO sales (date, staff_name, method, amount, shop_key)
                            VALUES (%s, %s, %s, %s, %s);
                            """,
                            (sale_date, staff, method, amount, shop_key),
                        )
            finally:
                conn.close()

            return redirect(f"/regi/{shop_key}?saved=1")

        return render_template_string(
            INPUT_TEMPLATE,
            shop=shop,
            staffs=current_staffs(),
            methods=current_methods(shop_key),
            today=date.today().strftime("%Y-%m-%d"),
            saved=request.args.get("saved") == "1",
        )

    def admin_login(shop_key: str):
        shop = _shop_or_404(shop_key)
        next_url = _safe_next_url(shop_key, request.values.get("next"))
        error = ""

        if request.method == "POST":
            password = request.form.get("password", "")
            if password == _shop_admin_password(shop_key):
                session[_admin_session_key(shop_key)] = True
                return redirect(next_url)
            error = "パスワードが違います。"

        return render_template_string(LOGIN_TEMPLATE, shop=shop, error=error, next_url=next_url)

    def admin_logout(shop_key: str):
        _shop_or_404(shop_key)
        session.pop(_admin_session_key(shop_key), None)
        return redirect(f"/admin/regi/{shop_key}/login")

    def admin_top(shop_key: str):
        guard = require_shop_admin(shop_key)
        if guard:
            return guard
        shop = _shop_or_404(shop_key)
        return render_template_string(ADMIN_TEMPLATE, shop=shop)

    def monthly(shop_key: str):
        guard = require_shop_admin(shop_key)
        if guard:
            return guard
        shop = _shop_or_404(shop_key)
        if not database_url:
            return "DATABASE_URL が未設定です。", 500

        try:
            month, _, _ = _month_range(request.args.get("month"))
            data = _aggregate_monthly(database_url, shop_key, month)
        except Exception as e:
            return f"❌ 集計エラー: {e}", 500

        return render_template_string(
            MONTHLY_TEMPLATE,
            shop=shop,
            month=data["month"],
            details=data["details"],
            staff_list=data["staff_list"],
            total_taiken=data["total_taiken"],
            total_pc=data["total_pc"],
            total_food=data["total_food"],
            total_cashless=data["total_cashless"],
            monthly_normal_invoice=data["monthly_normal_invoice"],
            monthly_special_invoice=data["monthly_special_invoice"],
            yen=yen,
        )

    def invoice(shop_key: str):
        guard = require_shop_admin(shop_key)
        if guard:
            return guard
        shop = _shop_or_404(shop_key)
        staff = (request.args.get("staff") or "").strip()
        if not staff:
            return "staff が指定されていません。", 400
        if not database_url:
            return "DATABASE_URL が未設定です。", 500

        force_special = _invoice_force_special(shop_key)
        try:
            month, _, _ = _month_range(request.args.get("month"))
            data = _aggregate_invoice(database_url, shop_key, month, staff, force_special)
        except Exception as e:
            return f"❌ 集計エラー: {e}", 500

        return render_template_string(
            INVOICE_TEMPLATE,
            shop=shop,
            invoice_label=_invoice_label(shop_key, force_special),
            force_special=force_special,
            yen=yen,
            **data,
        )

    def invoice_pdf(shop_key: str):
        guard = require_shop_admin(shop_key)
        if guard:
            return guard
        shop = _shop_or_404(shop_key)
        staff = (request.args.get("staff") or "").strip()
        if not staff:
            return "staff が指定されていません。", 400
        if not database_url:
            return "DATABASE_URL が未設定です。", 500

        force_special = _invoice_force_special(shop_key)
        try:
            month, _, _ = _month_range(request.args.get("month"))
            data = _aggregate_invoice(database_url, shop_key, month, staff, force_special)
            label = _invoice_label(shop_key, force_special)

            safe_staff = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in staff)
            filename = f"invoice_{shop_key}_{safe_staff}_{month}_{'special' if force_special else 'normal'}.pdf"
            output_dir = os.getenv("UPLOAD_FOLDER", ".")
            os.makedirs(output_dir, exist_ok=True)
            pdf_path = os.path.join(output_dir, filename)

            _create_invoice_pdf(
                pdf_path,
                shop_name=shop["name"],
                invoice_label=label,
                month=data["month"],
                staff=data["staff"],
                total_taiken=data["total_taiken"],
                total_pc=data["total_pc"],
                total_food=data["total_food"],
                total_cashless=data["total_cashless"],
                store_fee=data["store_fee"],
                store_fee_tax=data["store_fee_tax"],
                final_invoice=data["final_invoice"],
                daily_details=data["daily_details"],
            )
            return send_file(pdf_path, as_attachment=True, mimetype="application/pdf")
        except Exception as e:
            return f"❌ PDF生成エラー: {e}", 500

    def daily(shop_key: str):
        guard = require_shop_admin(shop_key)
        if guard:
            return guard
        shop = _shop_or_404(shop_key)
        if not database_url:
            return "DATABASE_URL が未設定です。", 500

        target_date = request.args.get("date") or date.today().strftime("%Y-%m-%d")
        conn = _conn(database_url)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, date, staff_name, method, amount
                    FROM sales
                    WHERE shop_key = %s AND date = %s
                    ORDER BY id DESC;
                    """,
                    (shop_key, target_date),
                )
                rows = list(cur.fetchall())
        finally:
            conn.close()

        return render_template_string(
            DAILY_TEMPLATE,
            shop=shop,
            target_date=target_date,
            rows=rows,
            yen=yen,
        )

    def edit_sale(shop_key: str, sale_id: int):
        guard = require_shop_admin(shop_key)
        if guard:
            return guard
        shop = _shop_or_404(shop_key)
        if not database_url:
            return "DATABASE_URL が未設定です。", 500

        conn = _conn(database_url)
        try:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT id, date, staff_name, method, amount
                        FROM sales
                        WHERE id = %s AND shop_key = %s;
                        """,
                        (sale_id, shop_key),
                    )
                    row = cur.fetchone()
                    if not row:
                        abort(404)

                    if request.method == "POST":
                        staff = (request.form.get("staff") or "").strip()
                        method = (request.form.get("method") or "").strip()
                        sale_date = _date_from_form(request.form.get("date"))
                        try:
                            amount = int(str(request.form.get("amount") or "0").replace(",", "").strip())
                        except ValueError:
                            return "金額は数値で入力してください。", 400

                        cur.execute(
                            """
                            UPDATE sales
                            SET date = %s, staff_name = %s, method = %s, amount = %s
                            WHERE id = %s AND shop_key = %s;
                            """,
                            (sale_date, staff, method, amount, sale_id, shop_key),
                        )
                        return redirect(f"/admin/regi/{shop_key}/daily?date={sale_date}")

                    row["date"] = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])
                    return render_template_string(
                        EDIT_TEMPLATE,
                        shop=shop,
                        row=row,
                        staffs=current_staffs(),
                        methods=current_methods(shop_key),
                    )
        finally:
            conn.close()

    def delete_sale(shop_key: str, sale_id: int):
        guard = require_shop_admin(shop_key)
        if guard:
            return guard
        _shop_or_404(shop_key)
        if not database_url:
            return "DATABASE_URL が未設定です。", 500

        back_date = request.form.get("date") or request.args.get("date") or date.today().strftime("%Y-%m-%d")
        conn = _conn(database_url)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT date FROM sales WHERE id = %s AND shop_key = %s;", (sale_id, shop_key))
                    row = cur.fetchone()
                    if row and row[0]:
                        back_date = row[0].strftime("%Y-%m-%d") if hasattr(row[0], "strftime") else str(row[0])
                    cur.execute("DELETE FROM sales WHERE id = %s AND shop_key = %s;", (sale_id, shop_key))
        finally:
            conn.close()

        return redirect(f"/admin/regi/{shop_key}/daily?date={back_date}")

    def csv_export(shop_key: str):
        guard = require_shop_admin(shop_key)
        if guard:
            return guard
        shop = _shop_or_404(shop_key)
        if not database_url:
            return "DATABASE_URL が未設定です。", 500

        month, month_start, month_end = _month_range(request.args.get("month"))
        conn = _conn(database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT date, staff_name, method, amount
                    FROM sales
                    WHERE shop_key = %s
                      AND date >= %s
                      AND date < %s
                    ORDER BY date, id;
                    """,
                    (shop_key, month_start, month_end),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        sio = io.StringIO()
        writer = csv.writer(sio)
        writer.writerow(["date", "shop", "staff_name", "method", "amount"])
        for row in rows:
            writer.writerow([row[0], shop["name"], row[1], row[2], row[3]])

        data = sio.getvalue().encode("utf-8-sig")
        resp = make_response(data)
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"
        resp.headers["Content-Disposition"] = f'attachment; filename="sales_{shop_key}_{month}.csv"'
        return resp

    # 二重登録対策：同名endpointが既にあれば登録をスキップ
    def safe_add(rule: str, endpoint: str, view_func, methods: List[str]) -> None:
        if endpoint in app.view_functions:
            print(f"⚠️ [REGI-MULTI-SHOP] endpoint already exists, skipped: {endpoint}", flush=True)
            return
        app.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=methods)

    safe_add("/regi-shops", "regi_multi_shop_portal", portal, ["GET"])
    safe_add("/regi/<shop_key>", "regi_multi_shop_input", input_sales, ["GET", "POST"])

    safe_add("/admin/regi/<shop_key>/login", "regi_multi_shop_login", admin_login, ["GET", "POST"])
    safe_add("/admin/regi/<shop_key>/logout", "regi_multi_shop_logout", admin_logout, ["GET"])

    safe_add("/admin/regi/<shop_key>", "regi_multi_shop_admin", admin_top, ["GET"])
    safe_add("/admin/regi/<shop_key>/daily", "regi_multi_shop_daily", daily, ["GET"])
    safe_add("/admin/regi/<shop_key>/monthly", "regi_multi_shop_monthly", monthly, ["GET"])
    safe_add("/admin/regi/<shop_key>/invoice", "regi_multi_shop_invoice", invoice, ["GET"])
    safe_add("/admin/regi/<shop_key>/invoice_pdf", "regi_multi_shop_invoice_pdf", invoice_pdf, ["GET"])
    safe_add("/admin/regi/<shop_key>/sale/<int:sale_id>/edit", "regi_multi_shop_sale_edit", edit_sale, ["GET", "POST"])
    safe_add("/admin/regi/<shop_key>/sale/<int:sale_id>/delete", "regi_multi_shop_sale_delete", delete_sale, ["POST"])
    safe_add("/admin/regi/<shop_key>/csv", "regi_multi_shop_csv", csv_export, ["GET"])
