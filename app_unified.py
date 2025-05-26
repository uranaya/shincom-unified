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


# Initialize locks for thread-safe operations
used_file_lock = threading.Lock()


# used_orders.txt 存在チェック
os.makedirs(os.path.dirname(USED_UUID_FILE) or ".", exist_ok=True)
if not os.path.exists(USED_UUID_FILE):
    open(USED_UUID_FILE, "w").close()

# webhook_sessions.txt 存在チェック
if not os.path.exists("webhook_sessions.txt"):
    open("webhook_sessions.txt", "w").close()

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


# Background thread task to generate PDF and handle post-processing
def background_generate_pdf(filepath, result_data, pdf_mode, size="a4", include_yearly=False, uuid_str=None, shop_id=None):
    try:
        create_pdf_unified(filepath, result_data, pdf_mode, size=size, include_yearly=include_yearly)
    except Exception as e:
        print(f"❌ PDF generation error (mode={pdf_mode}, uuid={uuid_str}):", e)
        traceback.print_exc()
        return
    # Mark UUID as used if applicable
    if uuid_str:
        try:
            with used_file_lock:
                lines_content = []
                if os.path.exists(USED_UUID_FILE):
                    with open(USED_UUID_FILE, "r") as f:
                        lines_content = [line.strip() for line in f if line.strip()]
                updated_lines = []
                for line in lines_content:
                    parts = line.split(",")
                    if len(parts) >= 3:
                        uid, flag, mode = parts[0], parts[1], parts[2]
                        if uid == uuid_str:
                            updated_lines.append(f"{uid},used,{mode}")
                        else:
                            updated_lines.append(line)
                with open(USED_UUID_FILE, "w") as f:
                    for line in updated_lines:
                        f.write(line + "\n")
        except Exception as e:
            print(f"❌ Error updating {USED_UUID_FILE} for {uuid_str}:", e)
            traceback.print_exc()
    # Write to access_log.txt if applicable
    if shop_id and uuid_str:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("access_log.txt", "a", encoding="utf-8") as f:
                f.write(f"{now_str},{shop_id},{uuid_str}\n")
        except Exception as e:
            print(f"❌ Error writing access_log for {uuid_str}:", e)
            traceback.print_exc()


# --- thanksルート ---
@app.route("/thanks")
def thanks():
    uuid_str = request.cookies.get("uuid") or request.args.get("uuid")
    if not uuid_str:
        # UUID未指定の場合は通常のthanksページ
        return render_template("thanks.html", uuid_str="")
    # UUIDあり: thanksページにuuidを渡す（カウント処理は /start へ移動）
    return render_template("thanks.html", uuid_str=uuid_str)



def create_payment_session(amount, uuid_str, return_url_thanks, shop_id, mode="selfmob"):
    """KOMOJUのセッションAPIを使って支払い画面URLを生成する（selfmob系ルート自動判定付き）"""
    secret = os.getenv("KOMOJU_SECRET_KEY")
    if not secret:
        raise RuntimeError("KOMOJU_SECRET_KEY is not set")

    # ✅ ルーティング判定：決済金額とモードに応じて自動で分岐
    if mode == "renaiselfmob":
        redirect_path = "renaiselfmob_full" if amount >= 1000 else "renaiselfmob"
    else:
        redirect_path = "selfmob_full" if amount >= 1000 else "selfmob"

    customer_redirect_url = f"{BASE_URL}/{redirect_path}/{uuid_str}"
    cancel_url = customer_redirect_url  # 戻るボタンでも同じ場所に戻す

    payload = {
        "amount": amount,
        "currency": "JPY",
        "return_url": cancel_url,
        "customer_redirect_url": customer_redirect_url,
        "payment_data": {
            "external_order_num": uuid_str
        },
        "metadata": {
            "external_order_num": uuid_str,
            "shop_id": shop_id
        },
        "payment_methods": [
            {"type": "credit_card"},
            {"type": "paypay"}
        ],
        "description": "シン・コンピューター占い"
    }

    response = requests.post(
        "https://komoju.com/api/v1/sessions",
        auth=(secret, ""),
        json=payload
    )
    response.raise_for_status()

    session = response.json()
    session_url = session.get("session_url")
    if not session_url:
        raise RuntimeError("KOMOJUセッションURLの取得に失敗しました")
    return session_url






# カウント記録処理

def record_shop_log_if_needed(uuid_str, mode):
    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = f.readlines()
        for line in lines:
            parts = line.strip().split(",")
            if len(parts) >= 4 and parts[0] == uuid_str:
                shop_id = parts[3]
                break
        else:
            shop_id = "default"

        today = datetime.now().strftime("%Y-%m-%d")

        # ✅ DBにも記録（同日・同shop_id・同modeがあれば更新）
        if DATABASE_URL:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO shop_logs (date, shop_id, service, count)
                    VALUES (%s, %s, %s, 1)
                    ON CONFLICT (date, shop_id, service)
                    DO UPDATE SET count = shop_logs.count + 1;
                """, (today, shop_id, mode))
                conn.commit()
                cur.close()
                conn.close()
                print(f"📝 DBカウント更新: {today} / {shop_id} / {mode}")
            except Exception as e:
                print("❌ DB記録失敗 (record_shop_log_if_needed):", e)

        # ✅ CSVにもログ（参考用）
        log_line = f"{shop_id},{mode},{today}\n"
        with open("shop_logs.csv", "a") as log:
            log.write(log_line)
            print(f"🧮 CSVカウント記録: {log_line.strip()}")

    except Exception as e:
        print("⚠️ カウント記録エラー:", e)




# --- 決済リンク生成ルート ---
@app.route("/selfmob-<shop_id>")
def selfmob_shop_entry(shop_id):
    session["shop_id"] = shop_id
    return render_template("pay.html", shop_id=shop_id)

@app.route("/selfmob/<uuid_str>")
def selfmob_entry_uuid(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "このUUIDは未決済です", 403
    record_shop_log_if_needed(uuid_str, "selfmob")
    return render_template("index_selfmob.html", full_year=False)

@app.route("/selfmob_full/<uuid_str>")
def selfmob_full_entry_uuid(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "このUUIDは未決済です", 403
    record_shop_log_if_needed(uuid_str, "selfmob_full")
    return render_template("index_selfmob.html", full_year=True)

@app.route("/renaiselfmob/<uuid_str>")
def renaiselfmob_entry_uuid(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "このUUIDは未決済です", 403
    record_shop_log_if_needed(uuid_str, "renaiselfmob")
    return render_template("index_renaiselfmob.html", full_year=False)

@app.route("/renaiselfmob_full/<uuid_str>")
def renaiselfmob_full_entry_uuid(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "このUUIDは未決済です", 403
    record_shop_log_if_needed(uuid_str, "renaiselfmob_full")
    return render_template("index_renaiselfmob.html", full_year=True)



def _generate_session_for_shop(shop_id, full_year=False, mode="selfmob"):
    uuid_str = str(uuid.uuid4())
    return_url_thanks = f"{BASE_URL}/thanks?uuid={uuid_str}"

    # ✅ テスト中につき、金額をすべて1円に固定
    amount = 1

    session_url = create_payment_session(
        amount=amount,
        uuid_str=uuid_str,
        return_url_thanks=return_url_thanks,
        shop_id=shop_id,
        mode=mode
    )

    mode_key = mode + ("_full" if full_year else "")
    try:
        with open(USED_UUID_FILE, "a") as f:
            f.write(f"{uuid_str},,{mode_key},{shop_id}\n")
    except Exception as e:
        print("⚠️ UUID書き込み失敗:", e)

    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO webhook_events (uuid, shop_id, service, date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (uuid_str, shop_id, mode_key, today))
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print("❌ DB記録失敗 (generate_link):", e)

    resp = make_response(redirect(session_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp




@app.route("/generate_link/<shop_id>")
def generate_link(shop_id):
    return _generate_session_for_shop(shop_id, full_year=False, mode="selfmob")

@app.route("/generate_link_full/<shop_id>")
def generate_link_full(shop_id):
    return _generate_session_for_shop(shop_id, full_year=True,  mode="selfmob")

@app.route("/generate_link_renai/<shop_id>")
def generate_link_renai(shop_id):
    return _generate_session_for_shop(shop_id, full_year=False, mode="renaiselfmob")

@app.route("/generate_link_renai_full/<shop_id>")
def generate_link_renai_full(shop_id):
    return _generate_session_for_shop(shop_id, full_year=True,  mode="renaiselfmob")




# 決済済みか判定

def is_paid_uuid(uuid_str):
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 1 and parts[0] == uuid_str:
                    return True
    except Exception as e:
        print("⚠️ used_orders.txt 読み込みエラー(is_paid_uuid):", e)
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM webhook_events WHERE uuid=%s AND service LIKE %s", (uuid_str, '%thanks'))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        print("❌ 決済確認エラー:", e)
        return False




def _generate_link_with_shopid(shop_id, full_year=False, mode="selfmob"):
    uuid_str = str(uuid.uuid4())
    redirect_url = f"{BASE_URL}/thanks?uuid={uuid_str}"

    komoju_url = create_payment_link(
        price=1000 if full_year else 500,
        uuid_str=uuid_str,
        redirect_url=redirect_url,
        shop_id=shop_id,  # ✅ ← ここが変更点
        full_year=full_year,
        mode=mode
    )

    mode_str = mode
    if full_year:
        mode_str = f"{mode}_full"
    try:
        with open(USED_UUID_FILE, "a") as f:
            f.write(f"{uuid_str},,{mode_str},{shop_id}\n")
    except Exception as e:
        print("⚠️ UUID書き込み失敗:", e)
    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO webhook_events (uuid, shop_id, service, date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (uuid_str, shop_id, mode_str, today))
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print("❌ DB記録失敗 (generate_link):", e)

    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp



# --- Komoju Webhook ルート ---
@app.route("/webhook/selfmob", methods=["POST"])
def webhook_selfmob():
    data = request.get_json()
    print("📩 Webhook受信: selfmob", data)

    session_id = data.get("data", {}).get("session")
    metadata = data.get("data", {}).get("metadata", {})
    uuid_from_metadata = metadata.get("external_order_num")

    matched_uuid = None
    shop_id = metadata.get("shop_id", "default")

    if session_id:
        try:
            with open("webhook_sessions.txt", "a") as f:
                f.write(f"{session_id}\n")
        except Exception as e:
            print("⚠️ Webhookセッション記録失敗:", e)

    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            parts = line.strip().split(",")
            if len(parts) >= 4 and (parts[0] == uuid_from_metadata or parts[1] == session_id):
                matched_uuid = parts[0]
                shop_id = parts[3]
                if not parts[1] and session_id:
                    parts[1] = session_id
                    lines[i] = ",".join(parts) + "\n"
                break
        if matched_uuid:
            with open(USED_UUID_FILE, "w") as f:
                f.writelines(lines)
    except Exception as e:
        print("⚠️ UUID逆照合失敗:", e)

    if matched_uuid:
        try:
            if DATABASE_URL:
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
    metadata = data.get("data", {}).get("metadata", {})
    uuid_from_metadata = metadata.get("external_order_num")

    matched_uuid = None
    shop_id = metadata.get("shop_id", "default")

    if session_id:
        try:
            with open("webhook_sessions.txt", "a") as f:
                f.write(f"{session_id}\n")
        except Exception as e:
            print("⚠️ Webhookセッション記録失敗:", e)

    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            parts = line.strip().split(",")
            if len(parts) >= 4 and (parts[0] == uuid_from_metadata or parts[1] == session_id):
                matched_uuid = parts[0]
                shop_id = parts[3]
                if not parts[1] and session_id:
                    parts[1] = session_id
                    lines[i] = ",".join(parts) + "\n"
                break
        if matched_uuid:
            with open(USED_UUID_FILE, "w") as f:
                f.writelines(lines)
    except Exception as e:
        print("⚠️ UUID逆照合失敗:", e)

    if matched_uuid:
        try:
            if DATABASE_URL:
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



# --- self系実占い部分  ---



@app.route("/selfmob/<uuid_str>", methods=["GET", "POST"])
def selfmob_uuid(uuid_str):
    full_year = None
    lines = []
    # Verify UUID existence and get full_year flag from used_orders.txt
    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = [line.strip().split(",") for line in f if line.strip()]
        for uid, flag, mode, shop_id in lines:
            if uid == uuid_str and mode == "selfmob":
                full_year = (flag == "1")
                break
        if full_year is None:
            return "無効なリンクです（UUID不一致）", 400
    except FileNotFoundError:
        return "使用履歴が確認できません", 400
    # Handle fortune generation after payment
    if request.method == "POST":
        is_json = request.is_json
        try:
            data = request.get_json() if is_json else request.form
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
            # Validate birthdate
            try:
                year, month, day = map(int, birthdate.split("-"))
            except Exception:
                return "生年月日が不正です", 400
            # Get lucky direction (with error handling)
            try:
                kyusei_text = get_kyusei_fortune(year, month, day)
            except Exception as e:
                print("❌ lucky_direction 取得エラー:", e)
                kyusei_text = ""
            eto = get_nicchu_eto(birthdate)
            # Generate results using shincom fortune logic
            palm_titles, palm_texts, shichu_result, iching_result, lucky_info = generate_fortune_shincom(
                image_data, birthdate, kyusei_text
            )
            palm_result = "\n".join(palm_texts)
            summary_text = palm_texts[5] if len(palm_texts) > 5 else ""
            # Convert lucky_info to a list of lines (string or list/dict)
            lucky_lines = []
            if isinstance(lucky_info, str):
                for line in lucky_info.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
                    line = line.strip()
                    if line:
                        if line.startswith("・"):
                            line = line[1:].strip()
                        lucky_lines.append(line.replace(":", "：", 1))
            elif isinstance(lucky_info, dict):
                for k, v in lucky_info.items():
                    line = f"{k}：{v}".strip()
                    if line:
                        if line.startswith("・"):
                            line = line[1:].strip()
                        lucky_lines.append(line)
            else:
                for item in lucky_info:
                    for line in str(item).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
                        line = line.strip()
                        if line:
                            if line.startswith("・"):
                                line = line[1:].strip()
                            lucky_lines.append(line.replace(":", "：", 1))
            # Prepare titles for output sections
            today = datetime.today()
            target1 = today.replace(day=15)
            if today.day >= 20:
                target1 += relativedelta(months=1)
            target2 = target1 + relativedelta(months=1)
            year_label = f"{today.year}年の運勢"
            month_label = f"{target1.year}年{target1.month}月の運勢"
            next_month_label = f"{target2.year}年{target2.month}月の運勢"
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
                "palm_result": palm_result,
                "shichu_result": shichu_result,
                "iching_result": iching_result,
                "palm_image": image_data
            }
            if full_year:
                yearly_data = generate_yearly_fortune(birthdate, today)
                result_data["yearly_fortunes"] = yearly_data
                result_data["titles"]["year_fortune"] = yearly_data["year_label"]
                result_data["texts"]["year_fortune"] = yearly_data["year_text"]
            # Generate PDF in background thread and mark usage
            filename = f"result_{uuid_str}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            shop_id = session.get("shop_id", "default")
            threading.Thread(
                target=background_generate_pdf,
                args=(filepath, result_data, "shincom", "a4", full_year, uuid_str, shop_id)
            ).start()
            redirect_url = url_for("preview", filename=filename)
            if is_json:
                return jsonify({"redirect_url": redirect_url})
            else:
                return redirect(redirect_url)
        except Exception as e:
            print("処理エラー:", e)
            return jsonify({"error": str(e)}) if request.is_json else "処理中にエラーが発生しました"
    # GET: render the input page for paid user
    return render_template("index_selfmob.html", uuid_str=uuid_str, full_year=full_year)

@app.route("/renaiselfmob/<uuid_str>", methods=["GET", "POST"])
@app.route("/renaiselfmob_full/<uuid_str>", methods=["GET", "POST"])
def renaiselfmob_uuid(uuid_str):
    full_year = None
    lines = []
    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = [line.strip().split(",") for line in f if line.strip()]
        for uid, flag, mode, shop_id in lines:
            if uid == uuid_str:
                full_year = (flag == "1")
                break
        if full_year is None:
            return "無効なリンクです（UUID不一致）", 400
    except FileNotFoundError:
        return "使用履歴が確認できません", 400
    if request.method == "POST":
        try:
            user_birth = request.form.get("user_birth")
            partner_birth = request.form.get("partner_birth")
            if not user_birth or not isinstance(user_birth, str):
                return "生年月日が不正です", 400
            # Prepare labels for the love fortune output
            now = datetime.now()
            target1 = now.replace(day=15)
            if now.day >= 20:
                target1 += relativedelta(months=1)
            target2 = target1 + relativedelta(months=1)
            year_label = f"{now.year}年の恋愛運"
            month_label = f"{target1.year}年{target1.month}月の恋愛運"
            next_month_label = f"{target2.year}年{target2.month}月の恋愛運"
            raw_result = generate_renai_fortune(user_birth, partner_birth, include_yearly=full_year)
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
            filename = f"renai_{uuid_str}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            shop_id = session.get("shop_id", "default")
            threading.Thread(
                target=background_generate_pdf,
                args=(filepath, result_data, "renai", "a4", full_year, uuid_str, shop_id)
            ).start()
            return redirect(url_for("preview", filename=filename))
        except Exception as e:
            print("処理エラー:", e)
            return "処理中にエラーが発生しました", 500
    # GET: render the input page for love fortune (after payment)
    return render_template("index_renaiselfmob.html", uuid_str=uuid_str, full_year=full_year)




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
            try:
                year, month, day = map(int, birthdate.split("-"))
            except Exception:
                return "生年月日が不正です", 400
            try:
                kyusei_text = get_kyusei_fortune(year, month, day)
            except Exception as e:
                print("❌ lucky_direction 取得エラー:", e)
                kyusei_text = ""
            eto = get_nicchu_eto(birthdate)
            palm_titles, palm_texts, shichu_result, iching_result, lucky_lines = generate_fortune(image_data, birthdate, kyusei_text)
            summary_text = ""
            if len(palm_texts) == 6:
                summary_text = palm_texts.pop()
            now = datetime.now()
            target1 = now.replace(day=15)
            if now.day >= 20:
                target1 += relativedelta(months=1)
            target2 = target1 + relativedelta(months=1)
            year_label = f"{now.year}年の運勢"
            month_label = f"{target1.year}年{target1.month}月の運勢"
            next_month_label = f"{target2.year}年{target2.month}月の運勢"
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
            if full_year:
                yearly_data = generate_yearly_fortune(birthdate, now)
                result_data["yearly_fortunes"] = yearly_data
                result_data["titles"]["year_fortune"] = yearly_data["year_label"]
                result_data["texts"]["year_fortune"] = yearly_data["year_text"]
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            threading.Thread(target=background_generate_pdf, args=(filepath, result_data, mode, size.lower(), full_year)).start()
            redirect_url = url_for("preview", filename=filename)
            if is_json:
                return jsonify({"redirect_url": redirect_url})
            else:
                return redirect(redirect_url)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}) if request.is_json else "処理中にエラーが発生しました"
    return render_template("index.html")

@app.route("/renai", methods=["GET", "POST"])
@app.route("/renaib4", methods=["GET", "POST"])
def renai():
    if "logged_in" not in session:
        return redirect(url_for("login", next=request.endpoint))
    size = "A4" if request.path == "/renai" else "B4"
    if request.method == "POST":
        user_birth = request.form.get("user_birth")
        partner_birth = request.form.get("partner_birth")
        include_yearly = (request.form.get("full_year") == "yes")
        raw_result = generate_renai_fortune(user_birth, partner_birth, include_yearly)
        now = datetime.now()
        target1 = now.replace(day=15)
        if now.day >= 20:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)
        result_data = {
            "texts": {
                "compatibility": raw_result.get("texts", {}).get("compatibility", ""),
                "overall_love_fortune": raw_result.get("texts", {}).get("overall_love_fortune", ""),
                "year_love": raw_result.get("texts", {}).get("year_love", ""),
                "month_love": raw_result.get("texts", {}).get("month_love", ""),
                "next_month_love": raw_result.get("texts", {}).get("next_month_love", "")
            },
            "titles": raw_result.get("titles", {}),
            "themes": raw_result.get("themes", []),
            "lucky_info": raw_result.get("lucky_info", []),
            "lucky_direction": raw_result.get("lucky_direction", ""),
            "yearly_love_fortunes": raw_result.get("yearly_love_fortunes", {})
        }
        filename = f"renai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        threading.Thread(target=background_generate_pdf, args=(filepath, result_data, "renai", size.lower(), include_yearly)).start()
        return redirect(url_for("preview", filename=filename))
    return render_template("renai_form.html")

@app.route("/selfmob", methods=["GET"])
def selfmob_start():
    return render_template("pay.html", shop_id="default")



@app.route("/get_eto", methods=["POST"])
def get_eto():
    try:
        birthdate = request.json.get("birthdate")
    except:
        return jsonify({"error": "無効な生年月日です"}), 400
    if not birthdate or not isinstance(birthdate, str):
        return jsonify({"error": "無効な生年月日です"}), 400
    try:
        y, m, d = map(int, birthdate.split("-"))
    except:
        return jsonify({"error": "無効な生年月日です"}), 400
    eto = get_nicchu_eto(birthdate)
    honmeisei = get_honmeisei(y, m, d)
    return jsonify({"eto": eto, "honmeisei": honmeisei})

@app.route("/")
@app.route("/home")
def home():
    return render_template("home-unified.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/tokutei")
def tokutei():
    return render_template("tokutei.html")
