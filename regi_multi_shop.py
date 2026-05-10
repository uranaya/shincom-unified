# -*- coding: utf-8 -*-
"""
店舗別レジ拡張モジュール

目的:
- 既存 sales テーブルに shop_key を追加し、売上を店舗別に分離する。
- おのだサンパーク店 / バジリスク店の入力・管理画面を分ける。
- バジリスク店はキャンペーンとして、対面・コンピューター占いともに売上の20%で出店料計算する。

app_unified.py の末尾付近で以下を呼び出してください。

    from regi_multi_shop import init_regi_multi_shop_tables, register_regi_multi_shop_routes

    init_regi_multi_shop_tables(DATABASE_URL)
    register_regi_multi_shop_routes(
        app,
        DATABASE_URL,
        globals().get("STAFF_LIST"),
        globals().get("METHOD_LIST"),
    )
"""

from __future__ import annotations

import csv
import io
import os
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from flask import Response, abort, make_response, redirect, request, render_template_string


SHOP_CONFIGS: Dict[str, Dict[str, Any]] = {
    "onosun": {
        "name": "おのだサンパーク店",
        "short_name": "おのだ",
        "invoice_note": "通常出店料：対面30％・コンピューター50％。特別出店料は対面20％・コンピューター40％。",
        "normal_rates": {"taimen": Decimal("0.30"), "pc": Decimal("0.50")},
        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.40")},
        "force_campaign": False,
    },
    "basilisk": {
        "name": "バジリスク店",
        "short_name": "バジリスク",
        "invoice_note": "キャンペーン出店料：対面・コンピューター占いともに売上の20％。",
        "normal_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20")},
        "special_rates": {"taimen": Decimal("0.20"), "pc": Decimal("0.20")},
        "force_campaign": True,
    },
}

DEFAULT_STAFF_LIST = ["新保", "二見", "スタッフ"]
DEFAULT_METHOD_LIST = ["対面", "コンピューター", "現金外"]
CASHLESS_KEYWORDS = ("現金外", "クレジット", "カード", "PayPay", "ペイペイ", "電子", "QR")


def _conn(database_url: Optional[str]):
    if not database_url:
        raise RuntimeError("DATABASE_URL が未設定です。Render の Environment に DATABASE_URL が必要です。")
    return psycopg2.connect(database_url)


def _money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _yen(value: Any) -> int:
    return int(_money(value))


def _is_cashless(method: str) -> bool:
    text = method or ""
    return any(keyword in text for keyword in CASHLESS_KEYWORDS)


def _is_taimen(method: str) -> bool:
    text = method or ""
    return ("対面" in text) and not _is_cashless(text)


def _is_pc(method: str) -> bool:
    text = method or ""
    return (("コンピューター" in text) or ("PC" in text.upper())) and not _is_cashless(text)


def _shop_or_404(shop_key: str) -> Dict[str, Any]:
    if shop_key not in SHOP_CONFIGS:
        abort(404)
    return SHOP_CONFIGS[shop_key]


def _normalize_staff_list(staff_list: Optional[Iterable[str]]) -> List[str]:
    items = [str(x) for x in (staff_list or []) if str(x).strip()]
    return items or DEFAULT_STAFF_LIST


def _normalize_method_list(method_list: Optional[Iterable[str]]) -> List[str]:
    items = [str(x) for x in (method_list or []) if str(x).strip()]
    for required in DEFAULT_METHOD_LIST:
        if required not in items:
            items.append(required)
    return items or DEFAULT_METHOD_LIST


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
                        date DATE NOT NULL DEFAULT CURRENT_DATE,
                        staff_name TEXT NOT NULL,
                        method TEXT NOT NULL,
                        amount INTEGER NOT NULL DEFAULT 0
                    );
                    """
                )
                cur.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS shop_key TEXT;")
                cur.execute("UPDATE sales SET shop_key = 'onosun' WHERE shop_key IS NULL OR shop_key = '';")
                cur.execute("ALTER TABLE sales ALTER COLUMN shop_key SET DEFAULT 'onosun';")
                cur.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_shop_date ON sales (shop_key, date);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_shop_staff_date ON sales (shop_key, staff_name, date);")
        print("✅ [REGI-MULTI-SHOP] sales テーブル店舗別拡張 OK", flush=True)
    finally:
        conn.close()


def _fetch_sales(
    database_url: Optional[str],
    shop_key: str,
    *,
    month: Optional[str] = None,
    day: Optional[str] = None,
    staff: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params: List[Any] = [shop_key]
    where = ["COALESCE(shop_key, 'onosun') = %s"]

    if month:
        where.append("date::text LIKE %s")
        params.append(f"{month}%")
    if day:
        where.append("date::text = %s")
        params.append(day)
    if staff:
        where.append("staff_name = %s")
        params.append(staff)

    sql = f"""
        SELECT id, date::text AS date, staff_name, method, amount, COALESCE(shop_key, 'onosun') AS shop_key
        FROM sales
        WHERE {' AND '.join(where)}
        ORDER BY date DESC, id DESC
    """

    conn = _conn(database_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _calc_totals(rows: Iterable[Dict[str, Any]], shop_key: str, *, force_special: bool = False) -> Dict[str, Any]:
    shop = SHOP_CONFIGS[shop_key]
    rates = shop["special_rates"] if (force_special or shop.get("force_campaign")) else shop["normal_rates"]

    total_taimen = Decimal("0")
    total_pc = Decimal("0")
    total_cashless = Decimal("0")
    total_other = Decimal("0")
    methods: Dict[str, int] = defaultdict(int)
    dates = set()

    for row in rows:
        amount = _money(row.get("amount"))
        method = str(row.get("method") or "")
        methods[method] += int(amount)
        if row.get("date"):
            dates.add(str(row.get("date")))

        if _is_cashless(method):
            total_cashless += amount
        elif _is_taimen(method):
            total_taimen += amount
        elif _is_pc(method):
            total_pc += amount
        else:
            total_other += amount

    store_fee = (total_taimen * rates["taimen"] + total_pc * rates["pc"]).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    store_fee_tax = (store_fee * Decimal("1.10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    final_invoice = store_fee_tax - total_cashless
    sales_total = total_taimen + total_pc + total_other
    visit_days = len(dates)
    avg_sales = (sales_total / visit_days).quantize(Decimal("1"), rounding=ROUND_HALF_UP) if visit_days else Decimal("0")

    return {
        "total_taimen": int(total_taimen),
        "total_pc": int(total_pc),
        "total_cashless": int(total_cashless),
        "total_other": int(total_other),
        "sales_total": int(sales_total),
        "store_fee": int(store_fee),
        "store_fee_tax": int(store_fee_tax),
        "final_invoice": int(final_invoice),
        "visit_days": visit_days,
        "avg_sales": int(avg_sales),
        "methods": dict(methods),
        "rate_taimen": int(rates["taimen"] * Decimal("100")),
        "rate_pc": int(rates["pc"] * Decimal("100")),
        "is_special": bool(force_special or shop.get("force_campaign")),
    }


def _monthly_group(rows: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str], int]:
    grouped: Dict[Tuple[str, str], int] = defaultdict(int)
    for row in rows:
        grouped[(str(row.get("staff_name") or ""), str(row.get("method") or ""))] += int(row.get("amount") or 0)
    return dict(sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])))


def _staff_details(rows: Iterable[Dict[str, Any]], shop_key: str, *, force_special: bool = False) -> Dict[str, Dict[str, Any]]:
    by_staff: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_staff[str(row.get("staff_name") or "未設定")].append(row)
    return {staff: _calc_totals(sales, shop_key, force_special=force_special) for staff, sales in sorted(by_staff.items())}


def _fmt_yen(value: Any) -> str:
    return f"{int(value):,}"


def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def _current_day() -> str:
    return date.today().isoformat()


PORTAL_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>店舗別レジ</title>
<style>
body{font-family:sans-serif;margin:0;padding:20px;background:#f6f6f6}.wrap{max-width:760px;margin:auto}.card{background:#fff;border-radius:12px;padding:18px;margin:12px 0;box-shadow:0 2px 8px rgba(0,0,0,.08)}
a.btn{display:block;text-align:center;padding:14px;margin:10px 0;border-radius:8px;text-decoration:none;color:#fff;background:#1976d2;font-weight:bold}.btn.sub{background:#555}.note{color:#555;font-size:14px;line-height:1.7}
</style></head><body><div class="wrap">
<h1>店舗別レジ</h1>
{% for key, shop in shops.items() %}
<div class="card">
  <h2>{{ shop.name }}</h2>
  <p class="note">{{ shop.invoice_note }}</p>
  <a class="btn" href="/regi/{{ key }}">売上入力</a>
  <a class="btn sub" href="/admin/regi/{{ key }}">管理画面</a>
</div>
{% endfor %}
</div></body></html>
"""

INPUT_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ shop.name }} 売上入力</title>
<style>
body{font-family:sans-serif;font-size:16px;padding:20px;margin:0;max-width:560px;margin:auto;background:#fafafa}label,select,input,button{display:block;width:100%;margin-bottom:15px;font-size:17px;padding:12px;box-sizing:border-box}button{background:#2e7d32;color:#fff;border:0;border-radius:6px;font-weight:bold}.top{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}.top a{background:#1976d2;color:white;text-decoration:none;padding:8px 10px;border-radius:5px;font-size:14px}.shop{background:#fff;border-left:6px solid #2e7d32;padding:12px;margin-bottom:16px}.success{background:#e8f5e9;border:1px solid #81c784;padding:12px;border-radius:6px;margin-bottom:15px}.note{font-size:13px;color:#555;line-height:1.6}
</style></head><body>
<div class="top"><a href="/regi-shops">店舗選択</a><a href="/admin/regi/{{ shop_key }}">管理画面</a></div>
<div class="shop"><h2>{{ shop.name }} 売上入力</h2><div class="note">{{ shop.invoice_note }}</div></div>
{% if success %}<div class="success">✅ 登録が完了しました</div>{% endif %}
<form method="post">
  <label>日付:</label>
  <input type="date" name="date" value="{{ selected_date }}" required>
  <label>店員名:</label>
  <select name="staff" required>{% for s in staff_list %}<option value="{{ s }}">{{ s }}</option>{% endfor %}</select>
  <label>鑑定方法:</label>
  <select name="method" required>{% for m in method_list %}<option value="{{ m }}">{{ m }}</option>{% endfor %}</select>
  <label>金額:</label>
  <input type="number" name="amount" min="0" inputmode="numeric" required>
  <button type="submit">{{ shop.short_name }}の売上として登録</button>
</form>
</body></html>
"""

ADMIN_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ shop.name }} 本日の売上</title>
<style>
body{font-family:sans-serif;font-size:16px;padding:20px;margin:0}.btn{display:inline-block;margin:4px 4px 12px 0;padding:8px 12px;background:#1976d2;color:white;text-decoration:none;border-radius:5px}.btn.gray{background:#555}.summary{font-size:20px;font-weight:bold;margin:16px 0}table{width:100%;border-collapse:collapse;display:block;overflow-x:auto}th,td{border:1px solid #bbb;padding:8px;text-align:center;white-space:nowrap}th{background:#f0f0f0}.danger{background:#c62828;color:white;border:0;padding:5px 8px;border-radius:4px}.edit{background:#2e7d32;color:white;text-decoration:none;padding:5px 8px;border-radius:4px}
</style></head><body>
<h2>{{ shop.name }} 本日の売上</h2>
<a class="btn gray" href="/regi-shops">店舗選択</a><a class="btn" href="/regi/{{ shop_key }}">売上入力</a><a class="btn" href="/admin/regi/{{ shop_key }}/daily?date={{ current_date }}">日別売上</a><a class="btn" href="/admin/regi/{{ shop_key }}/monthly">月別集計</a>
<div class="summary">{{ current_date }} 合計：{{ total|yen }}円</div>
<table><tr><th>日付</th><th>店員</th><th>方法</th><th>金額</th><th>修正</th></tr>
{% for s in sales %}
<tr><td>{{ s.date }}</td><td>{{ s.staff_name }}</td><td>{{ s.method }}</td><td>{{ s.amount|yen }}</td><td><a class="edit" href="/admin/regi/{{ shop_key }}/edit/{{ s.id }}">修正</a></td></tr>
{% endfor %}
</table>
<form method="post" action="/admin/regi/{{ shop_key }}/export" style="margin-top:20px"><button type="submit">CSV出力（{{ shop.short_name }}）</button></form>
</body></html>
"""

DAILY_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ shop.name }} 日別売上</title><style>
body{font-family:sans-serif;font-size:16px;padding:20px;margin:0}input,button{font-size:16px;padding:8px}.btn{display:inline-block;margin:4px 4px 12px 0;padding:8px 12px;background:#1976d2;color:white;text-decoration:none;border-radius:5px}table{width:100%;border-collapse:collapse;display:block;overflow-x:auto}th,td{border:1px solid #bbb;padding:8px;text-align:center;white-space:nowrap}th{background:#f0f0f0}.edit{background:#2e7d32;color:white;text-decoration:none;padding:5px 8px;border-radius:4px}.danger{background:#c62828;color:white;border:0;padding:5px 8px;border-radius:4px}
</style></head><body>
<h2>{{ shop.name }} 日別売上</h2>
<a class="btn" href="/admin/regi/{{ shop_key }}">管理画面</a><a class="btn" href="/regi/{{ shop_key }}">売上入力</a>
<form method="get"><input type="date" name="date" value="{{ selected_date }}"><button type="submit">表示</button></form>
<p><b>{{ selected_date }} 合計：{{ total|yen }}円</b></p>
<table><tr><th>ID</th><th>日付</th><th>店員</th><th>方法</th><th>金額</th><th>操作</th></tr>
{% for s in sales %}
<tr><td>{{ s.id }}</td><td>{{ s.date }}</td><td>{{ s.staff_name }}</td><td>{{ s.method }}</td><td>{{ s.amount|yen }}</td><td><a class="edit" href="/admin/regi/{{ shop_key }}/edit/{{ s.id }}">修正</a> <form method="post" action="/admin/regi/{{ shop_key }}/delete/{{ s.id }}" style="display:inline" onsubmit="return confirm('削除しますか？')"><button class="danger" type="submit">削除</button></form></td></tr>
{% endfor %}</table>
</body></html>
"""

MONTHLY_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ shop.name }} 月別集計</title><style>
body{font-family:sans-serif;font-size:16px;padding:20px;margin:0}.btn{display:inline-block;margin:4px 4px 12px 0;padding:8px 12px;background:#1976d2;color:white;text-decoration:none;border-radius:5px}.btn.gray{background:#555}input,button{font-size:16px;padding:8px}table{width:100%;border-collapse:collapse;display:block;overflow-x:auto;margin-top:12px}th,td{border:1px solid #bbb;padding:8px;text-align:center;white-space:nowrap}th{background:#f0f0f0}.note{background:#fff8e1;border:1px solid #ffe082;padding:10px;margin:12px 0;line-height:1.6}
</style></head><body>
<h2>{{ shop.name }} 月別売上集計</h2>
<a class="btn gray" href="/regi-shops">店舗選択</a><a class="btn" href="/admin/regi/{{ shop_key }}">管理画面</a><a class="btn" href="/regi/{{ shop_key }}">売上入力</a>
<div class="note">{{ shop.invoice_note }}</div>
<form method="get"><input type="month" name="month" value="{{ month }}"><button type="submit">表示</button></form>
<h3>{{ month }} <a class="btn" href="/admin/regi/{{ shop_key }}/invoice?month={{ month }}" target="_blank">請求書作成</a></h3>
<table><tr><th>店員</th><th>方法</th><th>合計金額</th></tr>
{% for key, total in grouped.items() %}<tr><td>{{ key[0] }}</td><td>{{ key[1] }}</td><td>{{ total|yen }}</td></tr>{% endfor %}
</table>
<h3>占い師ごとの請求書</h3>
{% for staff in staff_list %}<a class="btn" href="/admin/regi/{{ shop_key }}/invoice_staff?month={{ month }}&staff={{ staff|urlencode }}" target="_blank">{{ staff }}</a>{% endfor %}
</body></html>
"""

INVOICE_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ month }} {{ shop.name }} 請求書</title><style>
body{font-family:sans-serif;padding:20px;max-width:900px;margin:auto;font-size:16px;line-height:1.6}h2{text-align:center}table{width:100%;border-collapse:collapse;margin-bottom:20px}th,td{border:1px solid #ccc;padding:8px;text-align:right}th{text-align:center;background:#f0f0f0}.left{text-align:left}.total-row td{font-weight:bold;font-size:18px;background:#f9f9f9}.btn{display:inline-block;margin:4px 4px 12px 0;padding:9px 14px;background:#1976d2;color:white;text-decoration:none;border-radius:5px}button{padding:9px 14px;font-size:16px}@media print{.noprint{display:none}}
</style></head><body>
<h2>{{ month }} {{ shop.name }} 請求書</h2>
<p>{{ shop.invoice_note }}</p>
<div class="noprint"><button onclick="window.print()">印刷</button> <a class="btn" href="/admin/regi/{{ shop_key }}/invoice_pdf?month={{ month }}">PDF出力</a></div>
<table><tr><th>占い師</th><th>対面売上</th><th>コンピューター売上</th><th>現金外</th><th>出店料率</th><th>出店料 税抜</th><th>税込10%</th><th>請求額</th><th class="noprint">個別</th></tr>
{% for staff, d in details.items() %}
<tr><td class="left">{{ staff }}</td><td>{{ d.total_taimen|yen }}</td><td>{{ d.total_pc|yen }}</td><td>{{ d.total_cashless|yen }}</td><td>対面{{ d.rate_taimen }}% / PC{{ d.rate_pc }}%</td><td>{{ d.store_fee|yen }}</td><td>{{ d.store_fee_tax|yen }}</td><td>{{ d.final_invoice|yen }}</td><td class="noprint"><a href="/admin/regi/{{ shop_key }}/invoice_staff?month={{ month }}&staff={{ staff|urlencode }}">表示</a></td></tr>
{% endfor %}
<tr class="total-row"><td class="left">合計</td><td>{{ totals.total_taimen|yen }}</td><td>{{ totals.total_pc|yen }}</td><td>{{ totals.total_cashless|yen }}</td><td>—</td><td>{{ totals.store_fee|yen }}</td><td>{{ totals.store_fee_tax|yen }}</td><td>{{ totals.final_invoice|yen }}</td><td class="noprint"></td></tr>
</table>
</body></html>
"""

STAFF_INVOICE_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ month }} {{ shop.name }} {{ staff }} 請求書</title><style>
body{font-family:sans-serif;padding:20px;max-width:760px;margin:auto;font-size:16px;line-height:1.6}h2{text-align:center}table{width:100%;border-collapse:collapse;margin-bottom:20px}th,td{border:1px solid #ccc;padding:8px;text-align:right}th{text-align:center;background:#f0f0f0}.left{text-align:left}.total-row td{font-weight:bold;font-size:18px;background:#f9f9f9}.btn{display:inline-block;margin:4px 4px 12px 0;padding:9px 14px;background:#1976d2;color:white;text-decoration:none;border-radius:5px}button{padding:9px 14px;font-size:16px}@media print{.noprint{display:none}}
</style></head><body>
<h2>{{ month }} {{ shop.name }}<br>{{ staff }} 請求書</h2>
<p>{{ shop.invoice_note }}</p>
<div class="noprint"><button onclick="window.print()">印刷</button> <a class="btn" href="/admin/regi/{{ shop_key }}/invoice_staff_pdf?month={{ month }}&staff={{ staff|urlencode }}">PDF出力</a></div>
<table>
<tr><th>項目</th><th>金額</th></tr>
<tr><td class="left">対面売上合計</td><td>{{ d.total_taimen|yen }}円</td></tr>
<tr><td class="left">コンピューター売上合計</td><td>{{ d.total_pc|yen }}円</td></tr>
<tr><td class="left">現金外合計</td><td>{{ d.total_cashless|yen }}円</td></tr>
<tr><td class="left">出店料率</td><td>対面{{ d.rate_taimen }}% / コンピューター{{ d.rate_pc }}%</td></tr>
<tr><td class="left">出店料（税抜）</td><td>{{ d.store_fee|yen }}円</td></tr>
<tr><td class="left">出店料（税込10％）</td><td>{{ d.store_fee_tax|yen }}円</td></tr>
<tr class="total-row"><td class="left">請求額（現金外差引後）</td><td>{{ d.final_invoice|yen }}円</td></tr>
</table>
</body></html>
"""

EDIT_TEMPLATE = """
<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ shop.name }} 取引修正</title><style>body{font-family:sans-serif;font-size:16px;padding:20px;margin:0;max-width:560px;margin:auto}label,select,input,button{display:block;width:100%;margin-bottom:15px;font-size:17px;padding:12px;box-sizing:border-box}button{background:#1976d2;color:#fff;border:0;border-radius:6px}.back{display:inline-block;margin-bottom:16px}</style></head><body>
<a class="back" href="/admin/regi/{{ shop_key }}/daily?date={{ sale.date }}">← 日別一覧へ戻る</a>
<h2>{{ shop.name }} 取引修正</h2>
<form method="post">
<label>日付:</label><input type="date" name="date" value="{{ sale.date }}" required>
<label>占い師:</label><select name="staff" required>{% for s in staff_list %}<option value="{{ s }}" {% if s == sale.staff_name %}selected{% endif %}>{{ s }}</option>{% endfor %}</select>
<label>鑑定方法:</label><select name="method" required>{% for m in method_list %}<option value="{{ m }}" {% if m == sale.method %}selected{% endif %}>{{ m }}</option>{% endfor %}</select>
<label>金額:</label><input type="number" name="amount" min="0" value="{{ sale.amount }}" required>
<button type="submit">修正する</button>
</form></body></html>
"""


def _register_pdf_font() -> str:
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        candidates = [
            "ipaexg.ttf",
            os.path.join(os.getcwd(), "ipaexg.ttf"),
            os.path.join(os.getcwd(), "fonts", "ipaexg.ttf"),
            "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in candidates:
            if path and os.path.exists(path):
                name = "RegiJapaneseFont"
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                except Exception:
                    pass
                return name
    except Exception:
        pass
    return "Helvetica"


def _pdf_response(title: str, lines: List[Tuple[str, str]]) -> Response:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = _register_pdf_font()

    y = height - 45
    c.setFont(font_name, 16)
    c.drawCentredString(width / 2, y, title)
    y -= 35
    c.setFont(font_name, 11)
    for label, value in lines:
        if y < 60:
            c.showPage()
            c.setFont(font_name, 11)
            y = height - 45
        c.drawString(55, y, str(label))
        c.drawRightString(width - 55, y, str(value))
        y -= 22
    c.save()
    buffer.seek(0)
    filename = f"invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename={filename}"
    return response


def register_regi_multi_shop_routes(
    app,
    database_url: Optional[str],
    staff_list: Optional[Iterable[str]] = None,
    method_list: Optional[Iterable[str]] = None,
) -> None:
    """Flask app に店舗別レジのルートを追加する。"""
    staffs = _normalize_staff_list(staff_list)
    methods = _normalize_method_list(method_list)

    app.jinja_env.filters["yen"] = _fmt_yen

    def portal():
        return render_template_string(PORTAL_TEMPLATE, shops=SHOP_CONFIGS)

    def input_sales(shop_key: str):
        shop = _shop_or_404(shop_key)
        selected_date = request.values.get("date") or _current_day()
        success = request.args.get("success") == "1"
        if request.method == "POST":
            sale_date = request.form.get("date") or _current_day()
            staff = request.form.get("staff") or ""
            method = request.form.get("method") or ""
            amount = int(request.form.get("amount") or 0)
            conn = _conn(database_url)
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO sales (date, staff_name, method, amount, shop_key)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (sale_date, staff, method, amount, shop_key),
                        )
            finally:
                conn.close()
            return redirect(f"/regi/{shop_key}?success=1")
        return render_template_string(
            INPUT_TEMPLATE,
            shop_key=shop_key,
            shop=shop,
            staff_list=staffs,
            method_list=methods,
            selected_date=selected_date,
            success=success,
        )

    def admin_top(shop_key: str):
        shop = _shop_or_404(shop_key)
        today = _current_day()
        rows = _fetch_sales(database_url, shop_key, day=today)
        total = sum(int(r.get("amount") or 0) for r in rows if not _is_cashless(str(r.get("method") or "")))
        return render_template_string(ADMIN_TEMPLATE, shop_key=shop_key, shop=shop, sales=rows, total=total, current_date=today)

    def daily(shop_key: str):
        shop = _shop_or_404(shop_key)
        selected_date = request.args.get("date") or _current_day()
        rows = _fetch_sales(database_url, shop_key, day=selected_date)
        total = sum(int(r.get("amount") or 0) for r in rows if not _is_cashless(str(r.get("method") or "")))
        return render_template_string(DAILY_TEMPLATE, shop_key=shop_key, shop=shop, sales=rows, total=total, selected_date=selected_date)

    def monthly(shop_key: str):
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        rows = _fetch_sales(database_url, shop_key, month=month)
        grouped = _monthly_group(rows)
        staff_names = sorted({str(r.get("staff_name") or "") for r in rows} | set(staffs))
        return render_template_string(MONTHLY_TEMPLATE, shop_key=shop_key, shop=shop, month=month, grouped=grouped, staff_list=staff_names)

    def invoice(shop_key: str):
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        rows = _fetch_sales(database_url, shop_key, month=month)
        force_special = bool(shop.get("force_campaign")) or request.args.get("special") == "1"
        totals = _calc_totals(rows, shop_key, force_special=force_special)
        details = _staff_details(rows, shop_key, force_special=force_special)
        return render_template_string(INVOICE_TEMPLATE, shop_key=shop_key, shop=shop, month=month, totals=totals, details=details)

    def invoice_pdf(shop_key: str):
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        rows = _fetch_sales(database_url, shop_key, month=month)
        d = _calc_totals(rows, shop_key, force_special=bool(shop.get("force_campaign")))
        title = f"{month} {shop['name']} 請求書"
        lines = [
            ("計算条件", shop["invoice_note"]),
            ("対面売上合計", f"{_fmt_yen(d['total_taimen'])} 円"),
            ("コンピューター売上合計", f"{_fmt_yen(d['total_pc'])} 円"),
            ("現金外合計", f"{_fmt_yen(d['total_cashless'])} 円"),
            ("出店料率", f"対面 {d['rate_taimen']}% / コンピューター {d['rate_pc']}%"),
            ("出店料（税抜）", f"{_fmt_yen(d['store_fee'])} 円"),
            ("出店料（税込10％）", f"{_fmt_yen(d['store_fee_tax'])} 円"),
            ("請求額（現金外差引後）", f"{_fmt_yen(d['final_invoice'])} 円"),
        ]
        return _pdf_response(title, lines)

    def invoice_staff(shop_key: str):
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        staff = request.args.get("staff") or ""
        rows = _fetch_sales(database_url, shop_key, month=month, staff=staff)
        force_special = bool(shop.get("force_campaign")) or request.args.get("special") == "1"
        d = _calc_totals(rows, shop_key, force_special=force_special)
        return render_template_string(STAFF_INVOICE_TEMPLATE, shop_key=shop_key, shop=shop, month=month, staff=staff, d=d)

    def invoice_staff_pdf(shop_key: str):
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        staff = request.args.get("staff") or ""
        rows = _fetch_sales(database_url, shop_key, month=month, staff=staff)
        d = _calc_totals(rows, shop_key, force_special=bool(shop.get("force_campaign")))
        title = f"{month} {shop['name']} {staff} 請求書"
        lines = [
            ("計算条件", shop["invoice_note"]),
            ("対面売上合計", f"{_fmt_yen(d['total_taimen'])} 円"),
            ("コンピューター売上合計", f"{_fmt_yen(d['total_pc'])} 円"),
            ("現金外合計", f"{_fmt_yen(d['total_cashless'])} 円"),
            ("出店料率", f"対面 {d['rate_taimen']}% / コンピューター {d['rate_pc']}%"),
            ("出店料（税抜）", f"{_fmt_yen(d['store_fee'])} 円"),
            ("出店料（税込10％）", f"{_fmt_yen(d['store_fee_tax'])} 円"),
            ("請求額（現金外差引後）", f"{_fmt_yen(d['final_invoice'])} 円"),
        ]
        return _pdf_response(title, lines)

    def edit_sale(shop_key: str, sale_id: int):
        shop = _shop_or_404(shop_key)
        conn = _conn(database_url)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, date::text AS date, staff_name, method, amount FROM sales WHERE id = %s AND COALESCE(shop_key, 'onosun') = %s",
                    (sale_id, shop_key),
                )
                sale = cur.fetchone()
                if not sale:
                    abort(404)
            if request.method == "POST":
                sale_date = request.form.get("date") or _current_day()
                staff = request.form.get("staff") or ""
                method = request.form.get("method") or ""
                amount = int(request.form.get("amount") or 0)
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE sales SET date=%s, staff_name=%s, method=%s, amount=%s, shop_key=%s WHERE id=%s",
                            (sale_date, staff, method, amount, shop_key, sale_id),
                        )
                return redirect(f"/admin/regi/{shop_key}/daily?date={sale_date}")
        finally:
            conn.close()
        return render_template_string(EDIT_TEMPLATE, shop_key=shop_key, shop=shop, sale=sale, staff_list=staffs, method_list=methods)

    def delete_sale(shop_key: str, sale_id: int):
        _shop_or_404(shop_key)
        conn = _conn(database_url)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT date::text FROM sales WHERE id=%s AND COALESCE(shop_key, 'onosun')=%s", (sale_id, shop_key))
                    row = cur.fetchone()
                    selected_date = row[0] if row else _current_day()
                    cur.execute("DELETE FROM sales WHERE id=%s AND COALESCE(shop_key, 'onosun')=%s", (sale_id, shop_key))
        finally:
            conn.close()
        return redirect(f"/admin/regi/{shop_key}/daily?date={selected_date}")

    def export_csv(shop_key: str):
        shop = _shop_or_404(shop_key)
        month = request.values.get("month") or None
        rows = _fetch_sales(database_url, shop_key, month=month)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["店舗", "ID", "日付", "店員", "方法", "金額"])
        for row in rows:
            writer.writerow([shop["name"], row.get("id"), row.get("date"), row.get("staff_name"), row.get("method"), row.get("amount")])
        data = output.getvalue().encode("utf-8-sig")
        filename_month = month or "all"
        return Response(
            data,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=regi_{shop_key}_{filename_month}.csv"},
        )

    # 新規URLだけを追加し、既存 /input /admin/monthly などは壊さない。
    app.add_url_rule("/regi-shops", endpoint="regi_multi_shop_portal", view_func=portal, methods=["GET"])
    app.add_url_rule("/regi/<shop_key>", endpoint="regi_multi_shop_input", view_func=input_sales, methods=["GET", "POST"])
    app.add_url_rule("/admin/regi/<shop_key>", endpoint="regi_multi_shop_admin", view_func=admin_top, methods=["GET"])
    app.add_url_rule("/admin/regi/<shop_key>/daily", endpoint="regi_multi_shop_daily", view_func=daily, methods=["GET"])
    app.add_url_rule("/admin/regi/<shop_key>/monthly", endpoint="regi_multi_shop_monthly", view_func=monthly, methods=["GET"])
    app.add_url_rule("/admin/regi/<shop_key>/invoice", endpoint="regi_multi_shop_invoice", view_func=invoice, methods=["GET"])
    app.add_url_rule("/admin/regi/<shop_key>/invoice_pdf", endpoint="regi_multi_shop_invoice_pdf", view_func=invoice_pdf, methods=["GET"])
    app.add_url_rule("/admin/regi/<shop_key>/invoice_staff", endpoint="regi_multi_shop_invoice_staff", view_func=invoice_staff, methods=["GET"])
    app.add_url_rule("/admin/regi/<shop_key>/invoice_staff_pdf", endpoint="regi_multi_shop_invoice_staff_pdf", view_func=invoice_staff_pdf, methods=["GET"])
    app.add_url_rule("/admin/regi/<shop_key>/edit/<int:sale_id>", endpoint="regi_multi_shop_edit", view_func=edit_sale, methods=["GET", "POST"])
    app.add_url_rule("/admin/regi/<shop_key>/delete/<int:sale_id>", endpoint="regi_multi_shop_delete", view_func=delete_sale, methods=["POST"])
    app.add_url_rule("/admin/regi/<shop_key>/export", endpoint="regi_multi_shop_export", view_func=export_csv, methods=["GET", "POST"])

    print("✅ [REGI-MULTI-SHOP] 店舗別レジルート登録 OK", flush=True)
