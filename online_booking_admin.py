# -*- coding: utf-8 -*-
"""
Online booking + teller admin module for shincom-unified (Flask + psycopg2 direct SQL).

Public:
- GET  /online
- GET/POST /online/booking
- GET  /teller/<slug>        (profile)

Admin:
- GET  /admin/tellers
- GET/POST /admin/tellers/new
- GET/POST /admin/tellers/<id>/edit
- POST /admin/tellers/<id>/toggle
- GET  /admin/bookings       (minimal list)

Integration:
- app_unified.py should call init_online_tables(conn) after it creates the other tables.
- app_unified.py should call register_online_routes(app, DATABASE_URL) after Flask app creation.

Notes:
- Admin auth check is centralized in _require_admin(); align its session key with your app.
- Email notification on booking completion is optional; enabled only when SMTP env vars are set.
"""

import json
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import jsonify, render_template, request, redirect, session, abort


# ---------------------------
# Helpers
# ---------------------------

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
    return datetime.fromisoformat(v)


def _db_conn(database_url: str):
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def _require_admin():
    # Align with your existing admin auth pattern.
    # If your app uses a different key, change this function only.
    if not session.get("admin"):
        return redirect("/admin/login")
    return None


def _ensure_text(v: Optional[str]) -> str:
    return (v or "").strip()


def _guess_contact_type(contact: str) -> str:
    if "@" in (contact or ""):
        return "email"
    # phone / line / other
    return "phone"


# ---------------------------
# Email (optional)
# ---------------------------

def send_booking_email(subject: str, body: str) -> None:
    """
    Send a notification email to BOOKING_NOTIFY_TO.
    If required env vars are missing, this becomes a no-op.

    Env:
      BOOKING_NOTIFY_TO  (e.g. musubiya.uo@gmail.com)
      SMTP_HOST          (e.g. smtp.gmail.com or SendGrid/others)
      SMTP_PORT          (587 typical)
      SMTP_USER
      SMTP_PASS
      SMTP_FROM          optional (e.g. '"うらなや予約" <noreply@...>')
    """
    to_addr = os.getenv("BOOKING_NOTIFY_TO", "").strip()
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASS", "").strip()
    from_raw = os.getenv("SMTP_FROM", "").strip()

    if not (to_addr and host and user and pwd):
        return  # no-op

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = to_addr
    msg["From"] = from_raw if from_raw else formataddr(("うらなや予約", user))
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(user, pwd)
        smtp.send_message(msg)


# ---------------------------
# DB init
# ---------------------------

def init_online_tables(conn) -> None:
    """
    Create/upgrade tables/indexes required for online LP + booking + admin.
    Safe to run on every boot.
    """
    with conn.cursor() as cur:
        # Base tables (idempotent)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tellers (
              id SERIAL PRIMARY KEY,
              slug TEXT UNIQUE NOT NULL,
              display_name TEXT NOT NULL,
              short_bio TEXT DEFAULT '',
              long_bio TEXT DEFAULT '',
              art1 TEXT DEFAULT '',
              art2 TEXT DEFAULT '',
              art3 TEXT DEFAULT '',
              photo_url TEXT DEFAULT '',
              tags_json TEXT DEFAULT '[]',
              is_active BOOLEAN DEFAULT TRUE,
              is_accepting BOOLEAN DEFAULT TRUE,
              sort_order INT DEFAULT 100,
              created_at TIMESTAMP DEFAULT NOW(),
              updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # If DB already had old schema, ensure new columns exist (PostgreSQL supports IF NOT EXISTS)
        cur.execute("""ALTER TABLE tellers ADD COLUMN IF NOT EXISTS long_bio TEXT DEFAULT '';""")
        cur.execute("""ALTER TABLE tellers ADD COLUMN IF NOT EXISTS art1 TEXT DEFAULT '';""")
        cur.execute("""ALTER TABLE tellers ADD COLUMN IF NOT EXISTS art2 TEXT DEFAULT '';""")
        cur.execute("""ALTER TABLE tellers ADD COLUMN IF NOT EXISTS art3 TEXT DEFAULT '';""")

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

        # Indexes
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_tellers_active_order ON tellers(is_active, sort_order, id);""")
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_bookings_teller_created ON bookings(teller_id, created_at DESC);""")
        cur.execute("""CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);""")

    conn.commit()


# ---------------------------
# Routes registration
# ---------------------------

def register_online_routes(app, database_url: str) -> None:
    """Register all routes. Call this once from app_unified.py after app creation."""

    # --------- queries ---------

    def fetch_public_tellers() -> List[Dict[str, Any]]:
        conn = _db_conn(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, slug, display_name, short_bio, long_bio, art1, art2, art3,
                           photo_url, tags_json, is_active, is_accepting, sort_order
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
                    SELECT id, slug, display_name, short_bio, long_bio, art1, art2, art3,
                           photo_url, tags_json, is_active, is_accepting, sort_order,
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
                    SELECT id, slug, display_name, short_bio, long_bio, art1, art2, art3,
                           photo_url, tags_json, is_active, is_accepting, sort_order,
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

    def fetch_teller_by_slug(slug: str) -> Optional[Dict[str, Any]]:
        conn = _db_conn(database_url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, slug, display_name, short_bio, long_bio, art1, art2, art3,
                           photo_url, tags_json, is_active, is_accepting, sort_order,
                           created_at, updated_at
                    FROM tellers
                    WHERE slug = %s
                    LIMIT 1;
                """, (slug,))
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

    # ---------------------------
    # Public
    # ---------------------------

    @app.get("/online")
    def online_lp():
        tellers = fetch_public_tellers()
        return render_template("online/lp_online_dynamic.html", tellers=tellers)

    @app.get("/teller/<slug>")
    def teller_profile(slug: str):
        t = fetch_teller_by_slug(slug)
        if not t:
            abort(404)
        return render_template("online/teller_profile.html", teller=t)

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

                contact = _ensure_text(request.form.get("contact")) or _ensure_text(request.form.get("email"))
                contact_type = _ensure_text(request.form.get("contact_type"))
                if contact and not contact_type:
                    contact_type = _guess_contact_type(contact)

                payload = {
                    "teller_id": int(teller_id),
                    "category": _ensure_text(request.form.get("category")),
                    "mode": _ensure_text(request.form.get("mode")),
                    "slot1": _parse_dt_local(request.form.get("slot1")),
                    "slot2": _parse_dt_local(request.form.get("slot2")),
                    "slot3": _parse_dt_local(request.form.get("slot3")),
                    "message": _ensure_text(request.form.get("message")),
                    "name": _ensure_text(request.form.get("name")),
                    "contact_type": contact_type,
                    "contact": contact,
                    "agree": agree,
                }

                must = ["category", "mode", "slot1", "message", "name", "contact_type", "contact"]
                for k in must:
                    if not payload.get(k):
                        raise ValueError("未入力の必須項目があります。")

                booking_id = insert_booking(payload)
                success = f"予約リクエストを受け付けました（受付番号：{booking_id}）。折り返しご連絡します。"

                # Email notification (optional)
                try:
                    teller_name = selected_teller.get("display_name", "")
                    subject = f"[うらなや予約] 新規予約 #{booking_id} / {teller_name}"
                    body = "\n".join([
                        f"予約ID: {booking_id}",
                        f"占い師: {teller_name} (id={payload['teller_id']})",
                        f"カテゴリ: {payload['category']}",
                        f"鑑定メニュー: {payload['mode']}",
                        f"希望日時1: {payload['slot1']}",
                        f"希望日時2: {payload.get('slot2') or '-'}",
                        f"希望日時3: {payload.get('slot3') or '-'}",
                        f"名前: {payload['name']}",
                        f"連絡手段: {payload['contact_type']}",
                        f"連絡先: {payload['contact']}",
                        "",
                        "相談内容:",
                        payload["message"],
                    ])
                    send_booking_email(subject, body)
                except Exception as e:
                    print("⚠️ booking mail failed:", e)

            except Exception as e:
                error = str(e)

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

    # ---------------------------
    # Contact
    # ---------------------------

    @app.route("/contact", methods=["GET", "POST"])
    def contact_page():
        """
        LPからの問い合わせ用。
        - GET: フォーム表示
        - POST: SMTPが設定されていればメール送信、未設定なら完了表示のみ
        """
        error = ""
        success = ""

        if request.method == "POST":
            try:
                name = (request.form.get("name") or "").strip()
                contact = (request.form.get("contact") or "").strip()
                message = (request.form.get("message") or "").strip()

                if not (name and contact and message):
                    raise ValueError("未入力の必須項目があります。")

                subject = f"[うらなや お問い合わせ] {name}"
                body = "\n".join([
                    f"名前: {name}",
                    f"連絡先: {contact}",
                    "",
                    "内容:",
                    message,
                ])

                try:
                    send_booking_email(subject, body)
                except Exception as e:
                    # メール失敗でも問い合わせ自体は受理
                    print("⚠️ contact mail failed:", e)

                success = "お問い合わせを受け付けました。折り返しご連絡いたします。"

            except Exception as e:
                error = str(e)

        return render_template(
            "online/contact.html",
            error=error,
            success=success
        )


    # ---------------------------
    # Admin (Tellers)
    # ---------------------------

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
                slug = _ensure_text(request.form.get("slug"))
                display_name = _ensure_text(request.form.get("display_name"))
                short_bio = _ensure_text(request.form.get("short_bio"))
                long_bio = _ensure_text(request.form.get("long_bio"))
                art1 = _ensure_text(request.form.get("art1"))
                art2 = _ensure_text(request.form.get("art2"))
                art3 = _ensure_text(request.form.get("art3"))
                photo_url = _ensure_text(request.form.get("photo_url"))
                tags_raw = _ensure_text(request.form.get("tags"))  # comma separated
                sort_order = int((_ensure_text(request.form.get("sort_order")) or "100"))
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
                              (slug, display_name, short_bio, long_bio, art1, art2, art3,
                               photo_url, tags_json, is_active, is_accepting, sort_order, updated_at)
                            VALUES
                              (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW());
                        """, (slug, display_name, short_bio, long_bio, art1, art2, art3,
                              photo_url, tags_json, is_active, is_accepting, sort_order))
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
                slug = _ensure_text(request.form.get("slug"))
                display_name = _ensure_text(request.form.get("display_name"))
                short_bio = _ensure_text(request.form.get("short_bio"))
                long_bio = _ensure_text(request.form.get("long_bio"))
                art1 = _ensure_text(request.form.get("art1"))
                art2 = _ensure_text(request.form.get("art2"))
                art3 = _ensure_text(request.form.get("art3"))
                photo_url = _ensure_text(request.form.get("photo_url"))
                tags_raw = _ensure_text(request.form.get("tags"))
                sort_order = int((_ensure_text(request.form.get("sort_order")) or "100"))
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
                                long_bio=%s,
                                art1=%s,
                                art2=%s,
                                art3=%s,
                                photo_url=%s,
                                tags_json=%s,
                                is_active=%s,
                                is_accepting=%s,
                                sort_order=%s,
                                updated_at=NOW()
                            WHERE id=%s;
                        """, (slug, display_name, short_bio, long_bio, art1, art2, art3,
                              photo_url, tags_json, is_active, is_accepting, sort_order, teller_id))
                        conn.commit()
                finally:
                    conn.close()

                return redirect("/admin/tellers")
            except Exception as e:
                error = str(e)

        teller = dict(teller)
        teller["tags_csv"] = ", ".join(teller.get("tags") or [])
        return render_template("admin/teller_form.html", mode="edit", teller=teller, error=error)

    @app.post("/admin/tellers/<int:teller_id>/toggle")
    def admin_tellers_toggle(teller_id: int):
        r = _require_admin()
        if r:
            return r

        field = _ensure_text(request.form.get("field"))
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

    # ---------------------------
    # Admin (Bookings) minimal
    # ---------------------------

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
