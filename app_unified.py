import os
import base64
import uuid
import json
import requests
import traceback
from datetime import datetime
from urllib.parse import quote
from sqlalchemy import create_engine, text
import csv
from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify, make_response
from fortune_logic import generate_fortune
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta
from yearly_fortune_utils import generate_yearly_fortune
from fortune_logic import generate_fortune as generate_fortune_shincom, get_nicchu_eto
from kyusei_utils import get_honmeisei, get_kyusei_fortune
from pdf_generator_unified import create_pdf_unified
from fortune_logic import generate_renai_fortune
import sqlite3
import threading
import psycopg2

# --- 環境変数とパス ---
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
USED_UUID_FILE = "used_orders.txt"
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", ".")

# Flask アプリ初期化
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret!123")

# used_orders.txt 存在チェック
os.makedirs(os.path.dirname(USED_UUID_FILE) or ".", exist_ok=True)
if not os.path.exists(USED_UUID_FILE):
    open(USED_UUID_FILE, "w").close()

# --- データベース初期化 ---
if DATABASE_URL:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shop_logs (
                date DATE,
                shop_id TEXT,
                service TEXT,
                count INT DEFAULT 0,
                PRIMARY KEY (date, shop_id, service)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                uuid TEXT PRIMARY KEY,
                shop_id TEXT,
                service TEXT,
                date DATE
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ DB初期化エラー:", e)
else:
    print("⚠️ DATABASE_URL が未設定。ローカル実行ではDB非使用。")

# --- thanksルート（カウント処理） ---
@app.route("/thanks")
def thanks():
    uuid_str = request.cookies.get("uuid") or request.args.get("uuid")
    if not uuid_str:
        return render_template("thanks.html")

    # UUIDに対応するデータをデータベースから取得
    mode = None
    shop_id = None
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT shop_id, service FROM webhook_events WHERE uuid=%s", (uuid_str,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                shop_id_db, service_db = row
                shop_id = shop_id_db
                if service_db and "renai" in service_db:
                    mode = "renaiselfmob"
                else:
                    mode = "selfmob"
        except Exception as e:
            print("⚠️ DB検索エラー:", e)

    # データベースに存在しない場合、used_orders.txtから照合
    if mode is None or shop_id is None:
        try:
            with open(USED_UUID_FILE, "r") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) >= 4 and parts[0] == uuid_str:
                        mode = parts[2]
                        shop_id = parts[3]
                        break
        except Exception as e:
            print("⚠️ used_orders.txt 読み込みエラー:", e)

    if mode is None or shop_id is None:
        print(f"⚠️ UUID見つからず: {uuid_str}")
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO webhook_events (uuid, shop_id, service, date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (uuid_str, "default", "invalid_thanks", today))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("❌ DB記録失敗:", e)
        return render_template("thanks.html")

    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        final_service = f"{mode}_thanks"
        cur.execute("""
            UPDATE webhook_events SET shop_id=%s, service=%s, date=%s
            WHERE uuid=%s AND service != %s;
        """, (shop_id, final_service, today, uuid_str, final_service))
        updated = cur.rowcount
        if updated == 0:
            cur.execute("""
                INSERT INTO webhook_events (uuid, shop_id, service, date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (uuid_str, shop_id, final_service, today))
        if updated or cur.rowcount:
            cur.execute("""
                INSERT INTO shop_logs (date, shop_id, service, count)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (date, shop_id, service)
                DO UPDATE SET count = shop_logs.count + 1;
            """, (today, shop_id, mode))
            print(f"📝 shop_logs カウント更新: {today} / {shop_id} / {mode}")
        else:
            print(f"ℹ️ UUID {uuid_str} は重複でカウントスキップ")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ DB保存エラー:", e)

    return redirect(url_for(f"{mode}_uuid", uuid_str=uuid_str))




def create_payment_link(price, uuid_str, redirect_url, metadata, full_year=False, mode="selfmob"):
    if mode == "renaiselfmob":
        komoju_id = os.getenv("KOMOJU_RENAI_PUBLIC_LINK_ID_FULL") if full_year else os.getenv("KOMOJU_RENAI_PUBLIC_LINK_ID")
    else:
        komoju_id = os.getenv("KOMOJU_PUBLIC_LINK_ID_FULL") if full_year else os.getenv("KOMOJU_PUBLIC_LINK_ID")

    if not komoju_id:
        raise ValueError("KOMOJUリンクID未設定")

    encoded_redirect = quote(redirect_url, safe='')
    encoded_metadata = quote(metadata)
    url = f"https://komoju.com/payment_links/{komoju_id}?external_order_num={uuid_str}&customer_redirect_url={encoded_redirect}&metadata={encoded_metadata}"

    print(f"🔗 決済URL [{mode}] (full={full_year}): {url}")
    return url




# 決済ページ入口（pay.html表示）とリンク生成用ルート
@app.route("/selfmob-<shop_id>")
def selfmob_shop_entry(shop_id):
    session["shop_id"] = shop_id
    return render_template("pay.html", shop_id=shop_id)

@app.route("/generate_link/<shop_id>")
def generate_link(shop_id):
    return _generate_link_with_shopid(shop_id, full_year=False, mode="selfmob")

@app.route("/generate_link_full/<shop_id>")
def generate_link_full(shop_id):
    return _generate_link_with_shopid(shop_id, full_year=True, mode="selfmob")

@app.route("/generate_link_renai/<shop_id>")
def generate_link_renai(shop_id):
    return _generate_link_with_shopid(shop_id, full_year=False, mode="renaiselfmob")

@app.route("/generate_link_renai_full/<shop_id>")
def generate_link_renai_full(shop_id):
    return _generate_link_with_shopid(shop_id, full_year=True, mode="renaiselfmob")


@app.route("/webhook/selfmob", methods=["POST"])
def webhook_selfmob():
    data = request.get_json()
    print("📩 Webhook受信: selfmob", data)
    session_id = data.get("data", {}).get("session")
    matched_uuid, shop_id = None, "default"
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4 and session_id in parts[0]:
                    matched_uuid, shop_id = parts[0], parts[3]
                    break
    except Exception as e:
        print("⚠️ UUID逆照合失敗:", e)

    if matched_uuid:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO webhook_events (uuid, shop_id, service, date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (matched_uuid, shop_id, "selfmob_thanks", today))
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ Webhook DB記録済: {matched_uuid} / {shop_id}")
        except Exception as e:
            print("❌ Webhook DBエラー:", e)
    return "", 200


@app.route("/webhook/renaiselfmob", methods=["POST"])
def webhook_renaiselfmob():
    data = request.get_json()
    print("📩 Webhook受信: renaiselfmob", data)
    session_id = data.get("data", {}).get("session")
    matched_uuid, shop_id = None, "default"
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4 and session_id in parts[0]:
                    matched_uuid, shop_id = parts[0], parts[3]
                    break
    except Exception as e:
        print("⚠️ UUID逆照合失敗:", e)

    if matched_uuid:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO webhook_events (uuid, shop_id, service, date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (matched_uuid, shop_id, "renaiselfmob_thanks", today))
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ Webhook DB記録済: {matched_uuid} / {shop_id}")
        except Exception as e:
            print("❌ Webhook DBエラー:", e)
    return "", 200




def is_paid_uuid(uuid_str):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM webhook_events WHERE uuid=%s AND service LIKE '%thanks'", (uuid_str,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None  # ✅ ここだけで判定する
    except Exception as e:
        print("❌ 決済確認エラー:", e)
        return False




def _generate_link_with_shopid(shop_id, full_year=False, mode="selfmob"):
    uuid_str = str(uuid.uuid4())
    redirect_url = f"{BASE_URL}/thanks?uuid={uuid_str}"
    metadata = json.dumps({"shop_id": shop_id})
    komoju_url = create_payment_link(
        price=1000 if full_year else 500,
        uuid_str=uuid_str,
        redirect_url=redirect_url,
        metadata=metadata,
        full_year=full_year,
        mode=mode
    )

    try:
        with open(USED_UUID_FILE, "a") as f:
            f.write(f"{uuid_str},{int(full_year)},{mode},{shop_id}\n")
    except Exception as e:
        print("⚠️ UUID書き込み失敗:", e)

    # ✅ 明示的な shop_id と mode を記録
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cur.execute("""
            INSERT INTO webhook_events (uuid, shop_id, service, date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (uuid_str, shop_id, mode, today))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ DB記録失敗 (generate_link):", e)

    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)  # 有効期限10分
    return resp




@app.route("/selfmob/<uuid_str>", methods=["GET", "POST"])
def selfmob_uuid(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "未決済またはセッション切れです。再度決済してください。", 403

    full_year = None
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4 and parts[0] == uuid_str and parts[2] == "selfmob":
                    full_year = (parts[1] == "1")
                    break
        if full_year is None:
            return "無効なUUIDです", 400
    except Exception as e:
        return f"UUID確認エラー: {e}", 500

    if request.method == "GET":
        return render_template("index_selfmob.html", uuid_str=uuid_str, full_year=full_year)

    try:
        data = request.get_json() if request.is_json else request.form
        image_data = data.get("image_data")
        birthdate = data.get("birthdate")
        year, month, day = map(int, birthdate.split("-"))

        kyusei_text = get_kyusei_fortune(year, month, day)
        eto = get_nicchu_eto(birthdate)
        palm_titles, palm_texts, shichu_result, iching_result, lucky_info = generate_fortune_shincom(image_data, birthdate, kyusei_text)

        result_data = {
            "eto": eto,
            "palm": {
                "titles": palm_titles,
                "result": "\n".join(palm_texts)
            },
            "shichu": shichu_result,
            "iching": iching_result,
            "lucky_info": lucky_info
        }

        filename = f"{uuid_str}.pdf"
        filepath = os.path.join(".", filename)
        shop_id = session.get("shop_id", "default")

        threading.Thread(
            target=background_generate_pdf,
            args=(filepath, result_data, "selfmob", "a4", full_year, uuid_str, shop_id)
        ).start()

        return redirect(url_for("preview", filename=filename))
    except Exception as e:
        print("❌ 通常占いエラー:", e)
        return "占い結果生成エラー", 500




@app.route("/renaiselfmob/<uuid_str>", methods=["GET", "POST"])
def renaiselfmob_uuid(uuid_str):
    full_year = None
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4 and parts[0] == uuid_str and parts[2] == "renaiselfmob":
                    full_year = (parts[1] == "1")
                    break
        if full_year is None:
            return "無効なUUIDです", 400
    except Exception as e:
        return f"UUID確認エラー: {e}", 500

    if request.method == "GET":
        return render_template("index_renaiselfmob.html", uuid_str=uuid_str, full_year=full_year)

    try:
        user_birth = request.form.get("user_birth")
        partner_birth = request.form.get("partner_birth")

        raw_result = generate_renai_fortune(user_birth, partner_birth, include_yearly=full_year)
        now = datetime.now()
        from dateutil.relativedelta import relativedelta
        target1 = now.replace(day=15)
        if now.day >= 20:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)

        result_data = {
            "texts": {
                "compatibility": raw_result["texts"].get("compatibility", ""),
                "overall_love_fortune": raw_result["texts"].get("overall_love_fortune", ""),
                "year_love": raw_result["texts"].get("year_love", ""),
                "month_love": raw_result["texts"].get("month_love", ""),
                "next_month_love": raw_result["texts"].get("next_month_love", "")
            },
            "titles": raw_result["titles"],
            "themes": raw_result["themes"],
            "lucky_info": raw_result["lucky_info"],
            "lucky_direction": raw_result["lucky_direction"],
            "yearly_love_fortunes": raw_result["yearly_love_fortunes"]
        }

        filename = f"renai_{uuid_str}.pdf"
        filepath = os.path.join(".", filename)
        shop_id = session.get("shop_id", "default")

        threading.Thread(
            target=background_generate_pdf,
            args=(filepath, result_data, "renai", "a4", full_year, uuid_str, shop_id)
        ).start()

        return redirect(url_for("preview", filename=filename))
    except Exception as e:
        print("❌ 恋愛占いエラー:", e)
        return "恋愛占い結果生成エラー", 500

@app.route("/preview/<filename>")
def preview(filename):
    """占い結果PDFのプレビュー画面表示"""
    referer = request.referrer or ""
    return render_template("fortune_pdf.html", filename=filename, referer=referer)

@app.route("/view/<filename>")
def view_file(filename):
    """PDFファイルをクライアントに送信"""
    try:
        return send_file(os.path.join(".", filename), as_attachment=False)
    except Exception as e:
        return f"ファイルの送信エラー: {e}", 404

@app.route("/view_shop_log")
def view_shop_log():
    """shop_logsテーブルの内容を表示（管理用）"""
    logs = []
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT date, shop_id, service, count FROM shop_logs ORDER BY date DESC;")
            logs = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            return f"エラー: {e}"
    return render_template("shop_log.html", logs=logs)

# ログイン制御（シンプルな仮ユーザー認証）
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password")
        if pw == os.getenv("ADMIN_PASSWORD", "pass"):
            session["logged_in"] = True
            return redirect("/home")
        return render_template("login.html", error="パスワードが間違っています")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/ten", methods=["GET", "POST"], endpoint="ten")
@app.route("/tenmob", methods=["GET", "POST"], endpoint="tenmob")
def ten_shincom():
    # Login required for store mode
    if "logged_in" not in session:
        return redirect(url_for("login", next=request.endpoint))
    mode = "shincom"
    size = "B4" if request.path == "/ten" else "A4"
    if request.method == "POST":
        is_json = request.is_json
        try:
            data = request.get_json() if is_json else request.form
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
            full_year = data.get("full_year", False) if is_json else (data.get("full_year") == "yes")
            # Validate birthdate format
            try:
                year, month, day = map(int, birthdate.split("-"))
            except Exception:
                return "生年月日が不正です", 400
            # Get lucky direction text (九星気学), with fallback on error
            try:
                kyusei_text = get_kyusei_fortune(year, month, day)
            except Exception as e:
                print("❌ lucky_direction 取得エラー:", e)
                kyusei_text = ""
            eto = get_nicchu_eto(birthdate)
            # Generate fortune results
            palm_titles, palm_texts, shichu_result, iching_result, lucky_lines = generate_fortune(
                image_data, birthdate, kyusei_text
            )
            summary_text = ""
            if len(palm_texts) == 6:
                # If palm_texts has a summary element, separate it
                summary_text = palm_texts.pop()
            # Prepare labels for year and month sections
            now = datetime.now()
            target1 = now.replace(day=15)
            if now.day >= 20:
                target1 += relativedelta(months=1)
            target2 = target1 + relativedelta(months=1)
            year_label = f"{now.year}年の運勢"
            month_label = f"{target1.year}年{target1.month}月の運勢"
            next_month_label = f"{target2.year}年{target2.month}月の運勢"
            # Compile result data for PDF template
            result_data = {
                "palm_titles": palm_titles,
                "palm_texts": palm_texts,
                "titles": {
                    "palm_summary": "手相の総合アドバイス",
                    "personality": "性格診断",
                    "year_fortune": year_label,
                    "month_fortune": month_label,
                    "next_month_fortune": next_month_label
                },
                "texts": {
                    "palm_summary": summary_text,
                    "personality": shichu_result.get("personality", ""),
                    "year_fortune": shichu_result.get("year_fortune", ""),
                    "month_fortune": shichu_result.get("month_fortune", ""),
                    "next_month_fortune": shichu_result.get("next_month_fortune", "")
                },
                "lucky_info": lucky_lines,
                "lucky_direction": kyusei_text,
                "birthdate": birthdate,
                "palm_result": "\n".join(palm_texts),
                "shichu_result": shichu_result,
                "iching_result": iching_result.replace("\r\n", "\n").replace("\r", "\n"),
                "palm_image": image_data
            }
            # Include full-year fortunes if requested
            if full_year:
                yearly_data = generate_yearly_fortune(birthdate, now)
                result_data["yearly_fortunes"] = yearly_data
                result_data["titles"]["year_fortune"] = yearly_data["year_label"]
                result_data["texts"]["year_fortune"] = yearly_data["year_text"]
            # Generate PDF asynchronously to avoid blocking
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            threading.Thread(
                target=background_generate_pdf,
                args=(filepath, result_data, mode, size.lower(), full_year)
            ).start()
            # Return a redirect to the preview page (or JSON link if API call)
            redirect_url = url_for("preview", filename=filename)
            if is_json:
                return jsonify({"redirect_url": redirect_url})
            else:
                return redirect(redirect_url)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}) if request.is_json else "処理中にエラーが発生しました"
    # GET request: render input form
    return render_template("index.html")

@app.route("/renai", methods=["GET", "POST"])
@app.route("/renaib4", methods=["GET", "POST"])
def renai():
    # Login required for store mode (love fortune)
    if "logged_in" not in session:
        return redirect(url_for("login", next=request.endpoint))
    size = "A4" if request.path == "/renai" else "B4"
    if request.method == "POST":
        user_birth = request.form.get("user_birth")
        partner_birth = request.form.get("partner_birth")
        include_yearly = request.form.get("include_yearly") == "yes"
        # Validate user birthdate
        if not user_birth or not isinstance(user_birth, str):
            return "生年月日が不正です", 400
        # Prepare labels for love fortune sections
        now = datetime.now()
        target1 = now.replace(day=15)
        if now.day >= 20:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)
        year_label = f"{now.year}年の恋愛運"
        month_label = f"{target1.year}年{target1.month}月の恋愛運"
        next_month_label = f"{target2.year}年{target2.month}月の恋愛運"
        # Generate love fortune results (including yearly if selected)
        raw_result = generate_renai_fortune(user_birth, partner_birth, include_yearly=include_yearly)
        result_data = {
            "texts": {
                "compatibility": raw_result.get("texts", {}).get("compatibility", ""),
                "overall_love_fortune": raw_result.get("texts", {}).get("overall_love_fortune", ""),
                "year_love": raw_result.get("texts", {}).get("year_love", ""),
                "month_love": raw_result.get("texts", {}).get("month_love", ""),
                "next_month_love": raw_result.get("texts", {}).get("next_month_love", "")
            },
            "titles": {
                "compatibility": raw_result.get("titles", {}).get("compatibility", "相性診断" if partner_birth else "恋愛傾向と出会い"),
                "overall_love_fortune": raw_result.get("titles", {}).get("overall_love_fortune", "総合恋愛運"),
                "year_love": raw_result.get("titles", {}).get("year_love", year_label),
                "month_love": raw_result.get("titles", {}).get("month_love", month_label),
                "next_month_love": raw_result.get("titles", {}).get("next_month_love", next_month_label)
            },
            "themes": raw_result.get("themes", []),
            "lucky_info": raw_result.get("lucky_info", []),
            "lucky_direction": raw_result.get("lucky_direction", ""),
            "yearly_love_fortunes": raw_result.get("yearly_love_fortunes", {})
        }
        # Generate PDF asynchronously (filename includes a random UUID for uniqueness)
        filename = f"renai_{uuid.uuid4()}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        threading.Thread(
            target=background_generate_pdf,
            args=(filepath, result_data, "renai", size.lower(), include_yearly)
        ).start()
        # Redirect to preview page to view/download the PDF
        return redirect(url_for("preview", filename=filename))
    # GET: render input form for love fortune
    return render_template("renai_form.html")



@app.route("/selfmob", methods=["GET"])
def selfmob_start():
    return render_template("pay.html", shop_id="default")  # ✅ 明示的に shop_id を指定


@app.route("/get_eto", methods=["POST"])
def get_eto():
    # AJAX endpoint to get Chinese zodiac (eto) and honmeisei from birthdate
    try:
        birthdate = request.json.get("birthdate")
    except Exception:
        return jsonify({"error": "無効な生年月日です"}), 400
    if not birthdate or not isinstance(birthdate, str):
        return jsonify({"error": "無効な生年月日です"}), 400
    try:
        y, m, d = map(int, birthdate.split("-"))
    except Exception:
        return jsonify({"error": "無効な生年月日です"}), 400
    eto = get_nicchu_eto(birthdate)
    honmeisei = get_honmeisei(y, m, d)
    return jsonify({"eto": eto, "honmeisei": honmeisei})

# ホームページ
@app.route("/")
@app.route("/home")
def home():
    return render_template("home-unified.html")

# 特定商取引・プライバシーポリシーなど
@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/tokutei")
def tokutei():
    return render_template("tokutei.html")
