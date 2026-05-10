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
import hmac
from urllib.parse import quote
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from psycopg2 import sql
from flask import Response, abort, make_response, redirect, request, render_template_string, session


SHOP_CONFIGS: Dict[str, Dict[str, Any]] = {
    "onosun": {
        "name": "おのだサンパーク店",
        "short_name": "おのだ",
        "invoice_note": "通常出店料：対面30％・コンピューター50％。必要に応じて特別出店料（対面20％・コンピューター40％）も選択できます。",
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

DEFAULT_STAFF_LIST: List[str] = []
DEFAULT_METHOD_LIST = ["対面", "コンピューター", "現金外（クレカQR)"]
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
    """引数で渡された候補を整形する。固定の仮スタッフ名は使わない。"""
    seen = set()
    items: List[str] = []
    for raw in (staff_list or []):
        name = str(raw or "").strip()
        if name and name not in seen:
            seen.add(name)
            items.append(name)
    return items


def _normalize_method_list(method_list: Optional[Iterable[str]]) -> List[str]:
    items = [str(x) for x in (method_list or []) if str(x).strip()]
    for required in DEFAULT_METHOD_LIST:
        if required not in items:
            items.append(required)
    return items or DEFAULT_METHOD_LIST


def _table_columns(cur, table_name: str) -> List[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return [str(row[0]) for row in cur.fetchall()]


def _fetch_staff_list(database_url: Optional[str], fallback_staffs: Optional[Iterable[str]] = None) -> List[str]:
    """
    スタッフ名はDBマスタを優先する。
    想定: tellers テーブル / staffs テーブル等。
    DBマスタが取れない場合のみ、app_unified.py 側から渡された既存 STAFF_LIST を使う。
    """
    fallback = _normalize_staff_list(fallback_staffs)
    if not database_url:
        return fallback or DEFAULT_STAFF_LIST

    table_candidates = ["tellers", "staffs", "staff"]
    name_candidates = [
        "display_name",
        "name",
        "staff_name",
        "teller_name",
        "nickname",
        "full_name",
    ]
    order_candidates = ["display_order", "sort_order", "order_no", "id"]

    conn = None
    try:
        conn = _conn(database_url)
        with conn.cursor() as cur:
            for table in table_candidates:
                cols = _table_columns(cur, table)
                if not cols:
                    continue

                name_col = next((c for c in name_candidates if c in cols), None)
                if not name_col:
                    continue

                order_col = next((c for c in order_candidates if c in cols), None)

                query = sql.SQL("SELECT DISTINCT {name_col}::text AS staff_name FROM {table} WHERE {name_col} IS NOT NULL AND TRIM({name_col}::text) <> ''").format(
                    name_col=sql.Identifier(name_col),
                    table=sql.Identifier(table),
                )
                if order_col:
                    # DISTINCT と任意の並び順を安全に両立させるため、Python側で重複除去する。
                    query = sql.SQL("SELECT {name_col}::text AS staff_name FROM {table} WHERE {name_col} IS NOT NULL AND TRIM({name_col}::text) <> '' ORDER BY {order_col} NULLS LAST, {name_col}").format(
                        name_col=sql.Identifier(name_col),
                        table=sql.Identifier(table),
                        order_col=sql.Identifier(order_col),
                    )

                cur.execute(query)
                names: List[str] = []
                seen = set()
                for row in cur.fetchall():
                    name = str(row[0] or "").strip()
                    if name and name not in seen:
                        seen.add(name)
                        names.append(name)

                if names:
                    return names

            # マスタが空の場合は、過去の sales に存在するスタッフ名を補助的に使う
            try:
                cur.execute(
                    """
                    SELECT DISTINCT staff_name
                    FROM sales
                    WHERE staff_name IS NOT NULL AND TRIM(staff_name) <> ''
                    ORDER BY staff_name
                    """
                )
                names = [str(row[0]).strip() for row in cur.fetchall() if str(row[0]).strip()]
                if names:
                    return names
            except Exception:
                pass

    except Exception as e:
        print(f"⚠️ [REGI-MULTI-SHOP] staff list DB load failed: {e}", flush=True)
    finally:
        if conn is not None:
            conn.close()

    return fallback or DEFAULT_STAFF_LIST


def _admin_password(shop_key: str) -> str:
    """
    店舗別管理画面パスワード。
    Render の Environment に以下を設定すると変更できます。
      REGI_ONOSUN_ADMIN_PASSWORD
      REGI_BASILISK_ADMIN_PASSWORD
    未設定時は onosun=admin123 / basilisk=basilisk123。
    """
    if shop_key == "onosun":
        return os.environ.get("REGI_ONOSUN_ADMIN_PASSWORD") or os.environ.get("REGI_ADMIN_PASSWORD") or "admin123"
    if shop_key == "basilisk":
        return os.environ.get("REGI_BASILISK_ADMIN_PASSWORD") or "basilisk123"
    return os.environ.get("REGI_ADMIN_PASSWORD") or "admin123"


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
    if shop_key == "basilisk":
        return "キャンペーン出店料（対面20％・コンピューター20％）"
    if force_special:
        return "特別出店料（対面20％・コンピューター40％）"
    return "通常出店料（対面30％・コンピューター50％）"


def _special_query(force_special: bool) -> str:
    return "&special=1" if force_special else ""


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


def _daily_details(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """PDF用の日別内訳を既存請求書と同じ列構成で作る。"""
    details: Dict[str, Dict[str, int]] = {}
    for row in rows:
        date_str = str(row.get("date") or "")
        if not date_str:
            continue
        method = str(row.get("method") or "")
        amount = int(row.get("amount") or 0)
        if date_str not in details:
            details[date_str] = {"対面": 0, "コンピューター": 0, "現金外": 0}

        if _is_cashless(method):
            details[date_str]["現金外"] += amount
        elif _is_taimen(method):
            details[date_str]["対面"] += amount
        elif _is_pc(method):
            details[date_str]["コンピューター"] += amount

    return dict(sorted(details.items(), key=lambda item: item[0]))


def _fmt_yen(value: Any) -> str:
    return f"{int(value):,}"


def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def _current_day() -> str:
    return date.today().isoformat()



LOGIN_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ shop.name }} 管理ログイン</title>
<style>
body{font-family:sans-serif;margin:0;padding:20px;background:#f6f6f6}.wrap{max-width:420px;margin:40px auto;background:#fff;border-radius:12px;padding:22px;box-shadow:0 2px 8px rgba(0,0,0,.08)}label,input,button{display:block;width:100%;box-sizing:border-box;font-size:17px}input{padding:12px;margin:8px 0 16px}button{padding:12px;border:0;border-radius:8px;background:#1976d2;color:#fff;font-weight:bold}.error{background:#ffebee;border:1px solid #ef9a9a;color:#b71c1c;padding:10px;border-radius:6px;margin-bottom:14px}.links a{display:inline-block;margin-top:12px;color:#1976d2}
</style></head><body><div class="wrap">
<h2>{{ shop.name }} 管理ログイン</h2>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<form method="post">
  <input type="hidden" name="next" value="{{ next_url }}">
  <label>管理パスワード</label>
  <input type="password" name="password" autocomplete="current-password" required autofocus>
  <button type="submit">管理画面へ入る</button>
</form>
<div class="links"><a href="/regi/{{ shop_key }}">売上入力へ戻る</a> / <a href="/regi-shops">店舗選択</a></div>
</div></body></html>
"""

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
<div class="top"><a href="/regi-shops">店舗選択</a><a href="/admin/regi/{{ shop_key }}">管理画面（要パスワード）</a></div>
<div class="shop"><h2>{{ shop.name }} 売上入力</h2><div class="note">{{ shop.invoice_note }}</div></div>
{% if success %}<div class="success">✅ 登録が完了しました</div>{% endif %}{% if not staff_list %}<div class="success" style="background:#fff8e1;border-color:#ffe082">⚠️ スタッフマスタが取得できません。DBの tellers/staffs テーブルを確認してください。</div>{% endif %}
<form method="post">
  <label>日付:</label>
  <input type="date" name="date" value="{{ selected_date }}" required>
  <label>店員名:</label>
  <select name="staff" required>
    {% if staff_list %}
      {% for s in staff_list %}<option value="{{ s }}">{{ s }}</option>{% endfor %}
    {% else %}
      <option value="" disabled selected>スタッフマスタ未登録</option>
    {% endif %}
  </select>
  <label>鑑定方法:</label>
  <select name="method" required>{% for m in method_list %}<option value="{{ m }}">{{ m }}</option>{% endfor %}</select>
  <label>金額:</label>
  <input type="number" name="amount" min="0" inputmode="numeric" required>
  <button type="submit" {% if not staff_list %}disabled{% endif %}>{{ shop.short_name }}の売上として登録</button>
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
<a class="btn gray" href="/regi-shops">店舗選択</a><a class="btn" href="/regi/{{ shop_key }}">売上入力</a><a class="btn" href="/admin/regi/{{ shop_key }}/daily?date={{ current_date }}">日別売上</a><a class="btn" href="/admin/regi/{{ shop_key }}/monthly">月別集計</a><a class="btn gray" href="/admin/regi/{{ shop_key }}/logout">ログアウト</a>
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
<a class="btn" href="/admin/regi/{{ shop_key }}">管理画面</a><a class="btn" href="/regi/{{ shop_key }}">売上入力</a><a class="btn" href="/admin/regi/{{ shop_key }}/monthly">月別集計</a>
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
body{font-family:sans-serif;font-size:16px;padding:20px;margin:0}.btn{display:inline-block;margin:4px 4px 12px 0;padding:8px 12px;background:#1976d2;color:white;text-decoration:none;border-radius:5px}.btn.gray{background:#555}.btn.green{background:#2e7d32}.btn.orange{background:#ef6c00}input,button{font-size:16px;padding:8px}table{width:100%;border-collapse:collapse;display:block;overflow-x:auto;margin-top:12px}th,td{border:1px solid #bbb;padding:8px;text-align:center;white-space:nowrap}th{background:#f0f0f0}.note{background:#fff8e1;border:1px solid #ffe082;padding:10px;margin:12px 0;line-height:1.6}.staffbox{margin:8px 0;padding:10px;border:1px solid #ddd;border-radius:8px}
</style></head><body>
<h2>{{ shop.name }} 月別売上集計</h2>
<a class="btn gray" href="/regi-shops">店舗選択</a><a class="btn" href="/admin/regi/{{ shop_key }}">管理画面</a><a class="btn" href="/regi/{{ shop_key }}">売上入力</a><a class="btn gray" href="/admin/regi/{{ shop_key }}/logout">ログアウト</a>
<div class="note">{{ shop.invoice_note }}</div>
<form method="get"><input type="month" name="month" value="{{ month }}"><button type="submit">表示</button></form>
<h3>{{ month }} 請求書作成</h3>
{% if shop_key == "onosun" %}
  <a class="btn green" href="/admin/regi/{{ shop_key }}/invoice?month={{ month }}" target="_blank">通常出店料で請求書</a>
  <a class="btn orange" href="/admin/regi/{{ shop_key }}/invoice?month={{ month }}&special=1" target="_blank">特別出店料で請求書</a>
{% else %}
  <a class="btn orange" href="/admin/regi/{{ shop_key }}/invoice?month={{ month }}" target="_blank">キャンペーン20％で請求書</a>
{% endif %}
<table><tr><th>店員</th><th>方法</th><th>合計金額</th></tr>
{% for key, total in grouped.items() %}<tr><td>{{ key[0] }}</td><td>{{ key[1] }}</td><td>{{ total|yen }}</td></tr>{% endfor %}
</table>
<h3>占い師ごとの請求書</h3>
{% for staff in staff_list %}
  <div class="staffbox">
    <b>{{ staff }}</b><br>
    {% if shop_key == "onosun" %}
      <a class="btn green" href="/admin/regi/{{ shop_key }}/invoice_staff?month={{ month }}&staff={{ staff|urlencode }}" target="_blank">通常</a>
      <a class="btn green" href="/admin/regi/{{ shop_key }}/invoice_staff_pdf?month={{ month }}&staff={{ staff|urlencode }}" target="_blank">通常PDF</a>
      <a class="btn orange" href="/admin/regi/{{ shop_key }}/invoice_staff?month={{ month }}&staff={{ staff|urlencode }}&special=1" target="_blank">特別</a>
      <a class="btn orange" href="/admin/regi/{{ shop_key }}/invoice_staff_pdf?month={{ month }}&staff={{ staff|urlencode }}&special=1" target="_blank">特別PDF</a>
    {% else %}
      <a class="btn orange" href="/admin/regi/{{ shop_key }}/invoice_staff?month={{ month }}&staff={{ staff|urlencode }}" target="_blank">20％請求書</a>
      <a class="btn orange" href="/admin/regi/{{ shop_key }}/invoice_staff_pdf?month={{ month }}&staff={{ staff|urlencode }}" target="_blank">20％PDF</a>
    {% endif %}
  </div>
{% endfor %}
</body></html>
"""

INVOICE_TEMPLATE = """
<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ month }} {{ shop.name }} 請求書</title><style>
body{font-family:sans-serif;padding:20px;max-width:900px;margin:auto;font-size:16px;line-height:1.6}h2{text-align:center}table{width:100%;border-collapse:collapse;margin-bottom:20px}th,td{border:1px solid #ccc;padding:8px;text-align:right}th{text-align:center;background:#f0f0f0}.left{text-align:left}.total-row td{font-weight:bold;font-size:18px;background:#f9f9f9}.btn{display:inline-block;margin:4px 4px 12px 0;padding:9px 14px;background:#1976d2;color:white;text-decoration:none;border-radius:5px}button{padding:9px 14px;font-size:16px}@media print{.noprint{display:none}}
</style></head><body>
<h2>{{ month }} {{ shop.name }} 請求書</h2>
<p><b>計算条件：{{ invoice_label }}</b></p>
<p>{{ shop.invoice_note }}</p>
<div class="noprint"><button onclick="window.print()">印刷</button> <a class="btn" href="/admin/regi/{{ shop_key }}/invoice_pdf?month={{ month }}{{ special_query }}">PDF出力</a></div>
<table><tr><th>占い師</th><th>対面売上</th><th>コンピューター売上</th><th>現金外</th><th>出店料率</th><th>出店料 税抜</th><th>税込10%</th><th>請求額</th><th class="noprint">個別</th></tr>
{% for staff, d in details.items() %}
<tr><td class="left">{{ staff }}</td><td>{{ d.total_taimen|yen }}</td><td>{{ d.total_pc|yen }}</td><td>{{ d.total_cashless|yen }}</td><td>対面{{ d.rate_taimen }}% / PC{{ d.rate_pc }}%</td><td>{{ d.store_fee|yen }}</td><td>{{ d.store_fee_tax|yen }}</td><td>{{ d.final_invoice|yen }}</td><td class="noprint"><a href="/admin/regi/{{ shop_key }}/invoice_staff?month={{ month }}&staff={{ staff|urlencode }}{{ special_query }}">表示</a></td></tr>
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
<p><b>計算条件：{{ invoice_label }}</b></p>
<p>{{ shop.invoice_note }}</p>
<div class="noprint"><button onclick="window.print()">印刷</button> <a class="btn" href="/admin/regi/{{ shop_key }}/invoice_staff_pdf?month={{ month }}&staff={{ staff|urlencode }}{{ special_query }}">PDF出力</a></div>
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
            "static/ipaexg.ttf",
            "ipaexg.ttf",
            os.path.join(os.getcwd(), "static", "ipaexg.ttf"),
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


def _pdf_response(
    title: str,
    d: Dict[str, Any],
    daily_details: Dict[str, Dict[str, int]],
    *,
    shop_name: str,
    invoice_label: str,
    filename_prefix: str = "invoice",
) -> Response:
    """
    既存 app_unified.py の generate_invoice_pdf() に寄せた請求書PDF。
    構成: タイトル → 会社情報 → 売上・請求額 → 日別内訳 → 振込先。
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = _register_pdf_font()

    # タイトル
    c.setFont(font_name, 18)
    c.drawString(20 * mm, height - 20 * mm, title)

    # 会社情報（元の請求書レイアウト準拠）
    c.setFont(font_name, 9)
    company_info = [
        "〒756-0817 山口県山陽小野田市大字小野田７３０番地２",
        "合同会社むすび家プランニング",
        "代表社員　新保　保（しんぽ　たもつ）",
        "TEL: 090-7506-2065",
        "Email: musubiya.planning@gmail.com",
    ]
    y_info = height - 35 * mm
    for line in company_info:
        c.drawString(20 * mm, y_info, line)
        y_info -= 5 * mm

    c.drawString(20 * mm, y_info, "適格請求書発行事業者登録番号：＿＿＿＿＿＿＿＿＿＿＿＿")
    y_info -= 5 * mm
    c.drawString(20 * mm, y_info, f"店舗：{shop_name}")
    y_info -= 5 * mm
    c.drawString(20 * mm, y_info, f"計算条件：{invoice_label}")

    # 売上・請求額
    y = height - 80 * mm
    c.setFont(font_name, 10)
    rows = [
        ("対面売上合計", d.get("total_taimen", 0)),
        ("コンピューター売上合計", d.get("total_pc", 0)),
        ("現金外合計", d.get("total_cashless", 0)),
        ("出店料率", f"対面 {d.get('rate_taimen', 0)}% / コンピューター {d.get('rate_pc', 0)}%"),
        ("出店料（税抜）", d.get("store_fee", 0)),
        ("出店料（税込10％）", d.get("store_fee_tax", 0)),
        ("請求額（現金外差引後）", d.get("final_invoice", 0)),
    ]
    for label, value in rows:
        c.drawString(20 * mm, y, str(label))
        if isinstance(value, str):
            c.drawRightString(180 * mm, y, value)
        else:
            c.drawRightString(180 * mm, y, f"{_fmt_yen(value)} 円")
        y -= 10 * mm

    # 日別内訳
    y -= 8 * mm
    c.setFont(font_name, 12)
    c.drawString(20 * mm, y, "【日別内訳】")
    y -= 8 * mm

    def draw_daily_header(current_y: float) -> float:
        c.setFont(font_name, 10)
        c.drawString(20 * mm, current_y, "日付")
        c.drawString(70 * mm, current_y, "対面")
        c.drawString(110 * mm, current_y, "コンピューター")
        c.drawString(150 * mm, current_y, "現金外")
        current_y -= 6 * mm
        c.line(20 * mm, current_y, 180 * mm, current_y)
        current_y -= 6 * mm
        return current_y

    y = draw_daily_header(y)

    c.setFont(font_name, 10)
    if daily_details:
        for date_str, amounts in daily_details.items():
            if y < 45 * mm:
                c.showPage()
                c.setFont(font_name, 10)
                y = height - 20 * mm
                y = draw_daily_header(y)
            c.drawString(20 * mm, y, str(date_str))
            c.drawRightString(90 * mm, y, f"{_fmt_yen(amounts.get('対面', 0))}")
            c.drawRightString(130 * mm, y, f"{_fmt_yen(amounts.get('コンピューター', 0))}")
            c.drawRightString(170 * mm, y, f"{_fmt_yen(amounts.get('現金外', 0))}")
            y -= 6 * mm
    else:
        c.drawString(20 * mm, y, "該当する売上データがありません。")
        y -= 8 * mm

    # 振込先情報
    if y < 60 * mm:
        c.showPage()
        y = height - 20 * mm
    else:
        y -= 10 * mm

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
    buffer.seek(0)

    filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


def register_regi_multi_shop_routes(
    app,
    database_url: Optional[str],
    staff_list: Optional[Iterable[str]] = None,
    method_list: Optional[Iterable[str]] = None,
) -> None:
    """Flask app に店舗別レジのルートを追加する。"""
    fallback_staffs = _normalize_staff_list(staff_list)
    methods = _normalize_method_list(method_list)

    app.jinja_env.filters["yen"] = _fmt_yen

    def current_staffs() -> List[str]:
        return _fetch_staff_list(database_url, fallback_staffs)

    def require_shop_admin(shop_key: str):
        _shop_or_404(shop_key)
        if _is_shop_admin(shop_key):
            return None
        next_url = quote(request.full_path if request.query_string else request.path, safe="/:?=&%")
        return redirect(f"/admin/regi/{shop_key}/login?next={next_url}")

    def portal():
        return render_template_string(PORTAL_TEMPLATE, shops=SHOP_CONFIGS)

    def admin_login(shop_key: str):
        shop = _shop_or_404(shop_key)
        next_url = request.values.get("next") or f"/admin/regi/{shop_key}"
        error = ""
        if request.method == "POST":
            entered = request.form.get("password") or ""
            expected = _admin_password(shop_key)
            if hmac.compare_digest(entered, expected):
                session[_admin_session_key(shop_key)] = True
                return redirect(_safe_next_url(shop_key, next_url))
            error = "パスワードが違います。"
        return render_template_string(
            LOGIN_TEMPLATE,
            shop_key=shop_key,
            shop=shop,
            next_url=_safe_next_url(shop_key, next_url),
            error=error,
        )

    def admin_logout(shop_key: str):
        _shop_or_404(shop_key)
        session.pop(_admin_session_key(shop_key), None)
        return redirect(f"/admin/regi/{shop_key}/login")

    def input_sales(shop_key: str):
        shop = _shop_or_404(shop_key)
        selected_date = request.values.get("date") or _current_day()
        success = request.args.get("success") == "1"
        staffs = current_staffs()

        if request.method == "POST":
            sale_date = request.form.get("date") or _current_day()
            staff = (request.form.get("staff") or "").strip()
            method = (request.form.get("method") or "").strip()
            try:
                amount = int(request.form.get("amount") or 0)
            except Exception:
                return "❌ 金額は数字で入力してください。", 400

            if not staff:
                return "❌ スタッフ名が未選択です。スタッフマスタを確認してください。", 400
            if not method:
                return "❌ 鑑定方法が未選択です。", 400

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
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
        shop = _shop_or_404(shop_key)
        today = _current_day()
        rows = _fetch_sales(database_url, shop_key, day=today)
        total = sum(int(r.get("amount") or 0) for r in rows if not _is_cashless(str(r.get("method") or "")))
        return render_template_string(ADMIN_TEMPLATE, shop_key=shop_key, shop=shop, sales=rows, total=total, current_date=today)

    def daily(shop_key: str):
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
        shop = _shop_or_404(shop_key)
        selected_date = request.args.get("date") or _current_day()
        rows = _fetch_sales(database_url, shop_key, day=selected_date)
        total = sum(int(r.get("amount") or 0) for r in rows if not _is_cashless(str(r.get("method") or "")))
        return render_template_string(DAILY_TEMPLATE, shop_key=shop_key, shop=shop, sales=rows, total=total, selected_date=selected_date)

    def monthly(shop_key: str):
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        rows = _fetch_sales(database_url, shop_key, month=month)
        grouped = _monthly_group(rows)
        staff_names = sorted({str(r.get("staff_name") or "") for r in rows if str(r.get("staff_name") or "").strip()} | set(current_staffs()))
        return render_template_string(MONTHLY_TEMPLATE, shop_key=shop_key, shop=shop, month=month, grouped=grouped, staff_list=staff_names)

    def invoice(shop_key: str):
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        rows = _fetch_sales(database_url, shop_key, month=month)
        force_special = _invoice_force_special(shop_key)
        totals = _calc_totals(rows, shop_key, force_special=force_special)
        details = _staff_details(rows, shop_key, force_special=force_special)
        return render_template_string(
            INVOICE_TEMPLATE,
            shop_key=shop_key,
            shop=shop,
            month=month,
            totals=totals,
            details=details,
            invoice_label=_invoice_label(shop_key, force_special),
            special_query=_special_query(force_special),
        )

    def invoice_pdf(shop_key: str):
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        rows = _fetch_sales(database_url, shop_key, month=month)
        force_special = _invoice_force_special(shop_key)
        d = _calc_totals(rows, shop_key, force_special=force_special)
        invoice_label = _invoice_label(shop_key, force_special)
        title = f"{month} {shop['name']} 請求書"
        return _pdf_response(
            title,
            d,
            _daily_details(rows),
            shop_name=shop["name"],
            invoice_label=invoice_label,
            filename_prefix=f"invoice_{shop_key}_{month}",
        )

    def invoice_staff(shop_key: str):
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        staff = request.args.get("staff") or ""
        rows = _fetch_sales(database_url, shop_key, month=month, staff=staff)
        force_special = _invoice_force_special(shop_key)
        d = _calc_totals(rows, shop_key, force_special=force_special)
        return render_template_string(
            STAFF_INVOICE_TEMPLATE,
            shop_key=shop_key,
            shop=shop,
            month=month,
            staff=staff,
            d=d,
            invoice_label=_invoice_label(shop_key, force_special),
            special_query=_special_query(force_special),
        )

    def invoice_staff_pdf(shop_key: str):
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
        shop = _shop_or_404(shop_key)
        month = request.args.get("month") or _current_month()
        staff = request.args.get("staff") or ""
        rows = _fetch_sales(database_url, shop_key, month=month, staff=staff)
        force_special = _invoice_force_special(shop_key)
        d = _calc_totals(rows, shop_key, force_special=force_special)
        invoice_label = _invoice_label(shop_key, force_special)
        title = f"{month} {staff} 請求書"
        return _pdf_response(
            title,
            d,
            _daily_details(rows),
            shop_name=shop["name"],
            invoice_label=invoice_label,
            filename_prefix=f"invoice_{shop_key}_{staff}_{month}",
        )

    def edit_sale(shop_key: str, sale_id: int):
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
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

        staffs = current_staffs()
        existing_staff = str(sale.get("staff_name") or "").strip()
        if existing_staff and existing_staff not in staffs:
            staffs.append(existing_staff)
        return render_template_string(EDIT_TEMPLATE, shop_key=shop_key, shop=shop, sale=sale, staff_list=staffs, method_list=methods)

    def delete_sale(shop_key: str, sale_id: int):
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
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
        auth = require_shop_admin(shop_key)
        if auth:
            return auth
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

    # 新規URLだけを追加し、既存 /regi /admin/monthly などは壊さない。
    app.add_url_rule("/regi-shops", endpoint="regi_multi_shop_portal", view_func=portal, methods=["GET"])
    app.add_url_rule("/regi/<shop_key>", endpoint="regi_multi_shop_input", view_func=input_sales, methods=["GET", "POST"])

    app.add_url_rule("/admin/regi/<shop_key>/login", endpoint="regi_multi_shop_login", view_func=admin_login, methods=["GET", "POST"])
    app.add_url_rule("/admin/regi/<shop_key>/logout", endpoint="regi_multi_shop_logout", view_func=admin_logout, methods=["GET"])

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
