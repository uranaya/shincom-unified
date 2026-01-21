# -*- coding: utf-8 -*-
"""
Online booking + teller admin module for shincom-unified (Flask + psycopg2 direct SQL).

Integration goal:
- Public LP:      GET  /online
- Public booking: GET/POST /online/booking
- Admin tellers:  GET  /admin/tellers
                 GET/POST /admin/tellers/new
                 GET/POST /admin/tellers/<id>/edit
                 POST /admin/tellers/<id>/toggle
- Admin bookings: GET  /admin/bookings   (minimal list)

Assumptions:
- app_unified.py already defines:
    * Flask `app`
    * DATABASE_URL env var
    * admin login sets `session["admin"] = True` (or similar)
    * `jsonify`, `render_template`, `request`, `redirect`, `session`
- This module provides:
    * init_online_tables(conn)  -> create tellers/bookings tables (idempotent)
    * register_online_routes(app) -> register routes on the given Flask app
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import jsonify, render_template, request, redirect, session


def _parse_tags(tags_json: str) -> List[str]:
    try:
        data = json.loads(tags_json or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _parse_dt_local(v: Optional[str]) -> Optional[datetime]:
    """Parse <input type="datetime-local">: 'YYYY-MM-DDTHH:MM'."""
    if not v:
        return None
    # datetime.fromisoformat handles 'YYYY-MM-DDTHH:MM'
    return datetime.fromisoformat(v)


def init_online_tables(conn) -> None:
    """
    Create tables/indexes required for online LP + booking + admin.
    Safe to run on every boot.
    """
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tellers (
              id SERIAL PRIMARY KEY,
              slug TEXT UNIQUE NOT NULL,
              display_name TEXT NOT NULL,
              short_bio TEXT DEFAULT '',
              photo_url TEXT DEFAULT '',
              tags_json TEXT DEFAULT '[]',
              is_active BOOLEAN DEFAULT TRUE,
              is_accepting BOOLEAN DEFAULT TRUE,
              sort_order INT DEFAULT 100,
              created_at TIMESTAMP DEFAULT NOW(),
              updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
              id SERIAL PRIMARY KEY,
              teller_id INT NOT NULL REFERENCES tellers(id),
              status TEXT DEFAULT 'new',
              category TEXT NOT NULL,
              mode TEXT NOT NULL,
              slot1 TIMESTAMP NOT NULL,
              slot2 TIMESTAMP NULL,
              slot3 TIMESTAMP NULL,
              message TEXT NOT NULL,
              name TEXT NOT NULL,
              contact_type TEXT NOT NULL,
              contact TEXT NOT NULL,
              agree BOOLEAN DEFAULT FALSE,
              memo TEXT DEFAULT '',
              created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_tellers_active_order ON tellers(is_active, sort_order, id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bookings_teller_created ON bookings(teller_id, created_at DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);")

    conn.commit()


def _db_conn(database_url: str):
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def _require_admin():
    # Align with your existing admin auth pattern.
    # If your app uses a different key, change this single function.
    if not session.get("admin"):
        return redirect("/admin/login")
    return None


def register_online_routes(app, database_url: str) -> None:
    """
    Register all routes. Call this once from app_unified.py after app creation.
    """

    def fetch_public_tellers() -> List[Dict[str, Any]]:
        conn = _db_conn(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, slug, display_name, short_bio, photo_url, tags_json,
                           is_active, is_accepting, sort_order
                    FROM tellers
                    WHERE is_active = TRUE
                    ORDER BY sort_order ASC, id ASC;
                """)
                rows = cur.fetchall()
                for r in rows:
                    r["tags"] = _parse_tags(r.get("tags_json"))
                return rows
        finally:
            conn.close()

    def fetch_all_tellers() -> List[Dict[str, Any]]:
        conn = _db_conn(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, slug, display_name, short_bio, photo_url, tags_json,
                           is_active, is_accepting, sort_order,
                           created_at, updated_at
                    FROM tellers
                    ORDER BY sort_order ASC, id ASC;
                """)
                rows = cur.fetchall()
                for r in rows:
                    r["tags"] = _parse_tags(r.get("tags_json"))
                return rows
        finally:
            conn.close()

    def fetch_teller_by_id(teller_id: int) -> Optional[Dict[str, Any]]:
        conn = _db_conn(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, slug, display_name, short_bio, photo_url, tags_json,
                           is_active, is_accepting, sort_order,
                           created_at, updated_at
                    FROM tellers
                    WHERE id = %s
                    LIMIT 1;
                """, (teller_id,))
                r = cur.fetchone()
                if not r:
                    return None
                r["tags"] = _parse_tags(r.get("tags_json"))
                return r
        finally:
            conn.close()

    def insert_booking(payload: Dict[str, Any]) -> int:
        conn = _db_conn(database_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bookings
                    (teller_id, category, mode, slot1, slot2, slot3, message, name, contact_type, contact, agree)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id;
                """, (
                    payload["teller_id"],
                    payload["category"],
                    payload["mode"],
                    payload["slot1"],
                    payload.get("slot2"),
                    payload.get("slot3"),
                    payload["message"],
                    payload["name"],
                    payload["contact_type"],
                    payload["contact"],
                    payload["agree"],
                ))
                booking_id = cur.fetchone()[0]
                conn.commit()
                return booking_id
        finally:
            conn.close()

    # ---------- Public ----------

    @app.get("/online")
    def online_lp():
        tellers = fetch_public_tellers()
        # templates/online/lp_online_dynamic.html
        return render_template("online/lp_online_dynamic.html", tellers=tellers)

    @app.route("/online/booking", methods=["GET", "POST"])
    def online_booking():
        tellers = fetch_public_tellers()
        selected_teller = None
        error = ""
        success = ""

        tid = request.args.get("teller_id")
        if tid and tid.isdigit():
            selected_teller = fetch_teller_by_id(int(tid))

        if request.method == "POST":
            try:
                teller_id = request.form.get("teller_select") or request.form.get("teller_id")
                if not teller_id or not str(teller_id).isdigit():
                    raise ValueError("占い師を選択してください。")

                selected_teller = fetch_teller_by_id(int(teller_id))
                if not selected_teller or not selected_teller.get("is_active"):
                    raise ValueError("選択された占い師は現在受付できません。")
                if not selected_teller.get("is_accepting"):
                    raise ValueError("選択された占い師は現在受付停止中です。")

                agree = (request.form.get("agree") == "1")
                if not agree:
                    raise ValueError("利用規約・プライバシーポリシーへの同意が必要です。")

                payload = {
                    "teller_id": int(teller_id),
                    "category": (request.form.get("category") or "").strip(),
                    "mode": (request.form.get("mode") or "").strip(),
                    "slot1": _parse_dt_local(request.form.get("slot1")),
                    "slot2": _parse_dt_local(request.form.get("slot2")),
                    "slot3": _parse_dt_local(request.form.get("slot3")),
                    "message": (request.form.get("message") or "").strip(),
                    "name": (request.form.get("name") or "").strip(),
                    "contact_type": (request.form.get("contact_type") or "").strip(),
                    "contact": (request.form.get("contact") or "").strip(),
                    "agree": agree,
                }

                must = ["category", "mode", "slot1", "message", "name", "contact_type", "contact"]
                for k in must:
                    if not payload.get(k):
                        raise ValueError("未入力の必須項目があります。")

                booking_id = insert_booking(payload)
                success = f"予約リクエストを受け付けました（受付番号：{booking_id}）。折り返しご連絡します。"

            except Exception as e:
                error = str(e)

        # templates/online/booking.html
        return render_template(
            "online/booking.html",
            tellers=tellers,
            selected_teller=selected_teller,
            error=error,
            success=success,
        )

    @app.get("/api/online/tellers")
    def api_online_tellers():
        return jsonify({"tellers": fetch_public_tellers()})

    # ---------- Admin (Tellers) ----------

    @app.get("/admin/tellers")
    def admin_tellers_list():
        r = _require_admin()
        if r:
            return r
        tellers = fetch_all_tellers()
        return render_template("admin/tellers_list.html", tellers=tellers)

    @app.route("/admin/tellers/new", methods=["GET", "POST"])
    def admin_tellers_new():
        r = _require_admin()
        if r:
            return r

        error = ""
        if request.method == "POST":
            try:
                slug = (request.form.get("slug") or "").strip()
                display_name = (request.form.get("display_name") or "").strip()
                short_bio = (request.form.get("short_bio") or "").strip()
                photo_url = (request.form.get("photo_url") or "").strip()
                tags_raw = (request.form.get("tags") or "").strip()  # comma separated
                sort_order = int((request.form.get("sort_order") or "100").strip())
                is_active = (request.form.get("is_active") == "1")
                is_accepting = (request.form.get("is_accepting") == "1")

                if not slug or not display_name:
                    raise ValueError("slug と表示名は必須です。")

                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                tags_json = json.dumps(tags, ensure_ascii=False)

                conn = _db_conn(database_url)
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO tellers
                              (slug, display_name, short_bio, photo_url, tags_json, is_active, is_accepting, sort_order, updated_at)
                            VALUES
                              (%s,%s,%s,%s,%s,%s,%s,%s,NOW());
                        """, (slug, display_name, short_bio, photo_url, tags_json, is_active, is_accepting, sort_order))
                        conn.commit()
                finally:
                    conn.close()

                return redirect("/admin/tellers")
            except Exception as e:
                error = str(e)

        return render_template("admin/teller_form.html", mode="new", teller=None, error=error)

    @app.route("/admin/tellers/<int:teller_id>/edit", methods=["GET", "POST"])
    def admin_tellers_edit(teller_id: int):
        r = _require_admin()
        if r:
            return r

        teller = fetch_teller_by_id(teller_id)
        if not teller:
            return "Not Found", 404

        error = ""
        if request.method == "POST":
            try:
                slug = (request.form.get("slug") or "").strip()
                display_name = (request.form.get("display_name") or "").strip()
                short_bio = (request.form.get("short_bio") or "").strip()
                photo_url = (request.form.get("photo_url") or "").strip()
                tags_raw = (request.form.get("tags") or "").strip()
                sort_order = int((request.form.get("sort_order") or "100").strip())
                is_active = (request.form.get("is_active") == "1")
                is_accepting = (request.form.get("is_accepting") == "1")

                if not slug or not display_name:
                    raise ValueError("slug と表示名は必須です。")

                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                tags_json = json.dumps(tags, ensure_ascii=False)

                conn = _db_conn(database_url)
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE tellers
                            SET slug=%s,
                                display_name=%s,
                                short_bio=%s,
                                photo_url=%s,
                                tags_json=%s,
                                is_active=%s,
                                is_accepting=%s,
                                sort_order=%s,
                                updated_at=NOW()
                            WHERE id=%s;
                        """, (slug, display_name, short_bio, photo_url, tags_json, is_active, is_accepting, sort_order, teller_id))
                        conn.commit()
                finally:
                    conn.close()

                return redirect("/admin/tellers")
            except Exception as e:
                error = str(e)

        # Provide CSV tags string for form display
        teller = dict(teller)
        teller["tags_csv"] = ", ".join(teller.get("tags") or [])
        return render_template("admin/teller_form.html", mode="edit", teller=teller, error=error)

    @app.post("/admin/tellers/<int:teller_id>/toggle")
    def admin_tellers_toggle(teller_id: int):
        r = _require_admin()
        if r:
            return r

        field = (request.form.get("field") or "").strip()
        if field not in ("is_active", "is_accepting"):
            return "Bad Request", 400

        conn = _db_conn(database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE tellers SET {field} = NOT {field}, updated_at=NOW() WHERE id=%s;", (teller_id,))
                conn.commit()
        finally:
            conn.close()

        return redirect("/admin/tellers")

    # ---------- Admin (Bookings) minimal ----------

    @app.get("/admin/bookings")
    def admin_bookings_list():
        r = _require_admin()
        if r:
            return r

        conn = _db_conn(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                      b.id,
                      b.created_at,
                      b.status,
                      b.category,
                      b.mode,
                      b.slot1,
                      b.slot2,
                      b.slot3,
                      b.name,
                      b.contact_type,
                      b.contact,
                      b.message,
                      COALESCE(t.display_name, '') AS teller_name
                    FROM bookings b
                    LEFT JOIN tellers t ON t.id = b.teller_id
                    ORDER BY b.created_at DESC
                    LIMIT 200;
                """)
                rows = cur.fetchall()
        finally:
            conn.close()

        return render_template("admin/bookings_list.html", bookings=rows)

