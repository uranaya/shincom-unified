import os
import base64
import uuid
import json
import requests
import traceback
from datetime import datetime
from urllib.parse import quote
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
from threading import Thread

load_dotenv()
BASE_URL = os.getenv("BASE_URL", "https://shincom-unified.onrender.com")
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
init_shop_db()


def init_shop_db():
    with sqlite3.connect("shop_log.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                shop_id TEXT,
                count INTEGER DEFAULT 1
            )
        """)
        conn.commit()
    print("✅ shop_log.db initialized")

def update_shop_db(shop_id):
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📝 update_shop_db called with shop_id = {shop_id}")
    try:
        with sqlite3.connect("shop_log.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT count FROM shop_logs WHERE date = ? AND shop_id = ?",
                (today, shop_id)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE shop_logs SET count = count + 1 WHERE date = ? AND shop_id = ?",
                    (today, shop_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO shop_logs (date, shop_id, count) VALUES (?, ?, 1)",
                    (today, shop_id)
                )
            conn.commit()
    except Exception as e:
        print("❌ DB logging failed:", e)
    try:
        update_shop_counter(shop_id)
    except Exception as e:
        print("❌ CSV logging failed:", e)
    now = datetime.now().isoformat()
    try:
        with open("shop_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{now},{shop_id}\n")
    except Exception as e:
        print("❌ Text logging failed:", e)

def update_shop_counter(shop_id):
    today = datetime.now().strftime("%Y-%m-%d")
    filepath = "shop_counter.csv"
    rows = []
    updated = False
    try:
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except FileNotFoundError:
        rows = [["date", "shop_id", "count"]]
    for row in rows:
        if len(row) == 3 and row[0] == today and row[1] == shop_id:
            row[2] = str(int(row[2]) + 1)
            updated = True
            break
    if not updated:
        rows.append([today, shop_id, "1"])
    with open(filepath, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

# Payment start page (offers normal or love purchase options)
@app.route("/selfmob")
def selfmob_start():
    return render_template("pay.html")

# Enhanced UUID flow for selfmob (normal) and renaiselfmob (love)
UPLOAD_FOLDER = "static/uploads"
USED_UUID_FILE = "used_orders.txt"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
if not os.path.exists(USED_UUID_FILE):
    open(USED_UUID_FILE, "w").close()

def generate_pdf_async(filepath, data, mode, size, include_yearly=False, uuid_str=None, lines=None):
    """Perform PDF creation and optional UUID file update in background."""
    try:
        create_pdf_unified(filepath, data, mode, size=size.lower() if isinstance(size, str) else str(size).lower(), include_yearly=include_yearly)
        if uuid_str and lines is not None:
            with open(USED_UUID_FILE, "w") as f:
                for uid, flag, mode_line in lines:
                    if uid != uuid_str:
                        f.write(f"{uid},{flag},{mode_line}\n")
                    else:
                        f.write(f"{uid},used,{mode_line}\n")
    except Exception as e:
        print("❌ Error in background PDF generation:", e)

@app.route("/generate_link/<shop_id>")
def generate_link(shop_id):
    uuid_str = str(uuid.uuid4())
    redirect_url = f"{BASE_URL}/thanks?uuid={uuid_str}"
    metadata = json.dumps({"shop_id": shop_id})
    komoju_url = create_payment_link(
        price=500,
        uuid_str=uuid_str,
        redirect_url=redirect_url,
        metadata=metadata,
        full_year=False,
        mode="selfmob"
    )
    print("🔗 通常決済URL:", komoju_url)
    with open(USED_UUID_FILE, "a") as f:
        f.write(f"{uuid_str},0,selfmob\n")
    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp

@app.route("/generate_link_full/<shop_id>")
def generate_link_full(shop_id):
    uuid_str = str(uuid.uuid4())
    redirect_url = f"{BASE_URL}/thanks?uuid={uuid_str}"
    metadata = json.dumps({"shop_id": shop_id})
    komoju_url = create_payment_link(
        price=1000,
        uuid_str=uuid_str,
        redirect_url=redirect_url,
        metadata=metadata,
        full_year=True,
        mode="selfmob"
    )
    print("🔗 FULL通常決済URL:", komoju_url)
    with open(USED_UUID_FILE, "a") as f:
        f.write(f"{uuid_str},1,selfmob\n")
    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp

@app.route("/generate_link_renai/<shop_id>")
def generate_link_renai(shop_id):
    uuid_str = str(uuid.uuid4())
    redirect_url = f"{BASE_URL}/thanks?uuid={uuid_str}"
    metadata = json.dumps({"shop_id": shop_id})
    komoju_url = create_payment_link(
        price=500,
        uuid_str=uuid_str,
        redirect_url=redirect_url,
        metadata=metadata,
        full_year=False,
        mode="renaiselfmob"
    )
    print("🔗 恋愛通常決済URL:", komoju_url)
    with open(USED_UUID_FILE, "a") as f:
        f.write(f"{uuid_str},0,renaiselfmob\n")
    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp

@app.route("/generate_link_renai_full/<shop_id>")
def generate_link_renai_full_with_shopid(shop_id):
    uuid_str = str(uuid.uuid4())
    redirect_url = f"{BASE_URL}/thanks?uuid={uuid_str}"
    metadata = json.dumps({"shop_id": shop_id})
    komoju_url = create_payment_link(
        price=1000,
        uuid_str=uuid_str,
        redirect_url=redirect_url,
        metadata=metadata,
        full_year=True,
        mode="renaiselfmob"
    )
    print("🔗 FULL恋愛決済URL:", komoju_url)
    with open(USED_UUID_FILE, "a") as f:
        f.write(f"{uuid_str},1,renaiselfmob\n")
    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp

@app.route("/thanks")
def thanks():
    uuid_str = request.cookies.get("uuid") or request.args.get("uuid")
    if not uuid_str:
        return render_template("thanks.html")
    mode = "selfmob"
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 3 and parts[0] == uuid_str:
                    mode = parts[2]
                    break
    except:
        pass
    return redirect(f"/{mode}/{uuid_str}")

@app.route("/webhook/selfmob", methods=["POST"])
def webhook_selfmob():
    try:
        data = request.get_json()
        if data.get("event") == "payment.captured":
            uuid_str = data["data"]["attributes"].get("external_order_num")
            metadata = data["data"]["attributes"].get("metadata", {})
            shop_id = metadata.get("shop_id", "default") if isinstance(metadata, dict) else "default"
            if uuid_str:
                print("✅ Webhook captured:", uuid_str, "from shop:", shop_id)
                update_shop_db(shop_id)
                # ✅ UUID を used に更新
                updated_lines = []
                found = False
                if os.path.exists(USED_UUID_FILE):
                    with open(USED_UUID_FILE, "r") as f:
                        for line in f:
                            parts = line.strip().split(",")
                            if len(parts) == 3 and parts[0] == uuid_str and parts[2] == "selfmob":
                                updated_lines.append(f"{uuid_str},used,selfmob\n")
                                found = True
                            else:
                                updated_lines.append(line)
                    if found:
                        with open(USED_UUID_FILE, "w") as f:
                            f.writelines(updated_lines)
        return "", 200
    except Exception as e:
        print("❌ Webhook error (selfmob):", e)
        return "", 400

@app.route("/webhook/renaiselfmob", methods=["POST"])
def webhook_renaiselfmob():
    try:
        data = request.get_json()
        if data.get("event") == "payment.captured":
            uuid_str = data["data"]["attributes"].get("external_order_num")
            metadata = data["data"]["attributes"].get("metadata", {})
            shop_id = metadata.get("shop_id", "default") if isinstance(metadata, dict) else "default"
            if uuid_str:
                print("✅ RENAI Webhook captured:", uuid_str, "from shop:", shop_id)
                update_shop_db(shop_id)
                # ✅ UUID を used に更新
                updated_lines = []
                found = False
                if os.path.exists(USED_UUID_FILE):
                    with open(USED_UUID_FILE, "r") as f:
                        for line in f:
                            parts = line.strip().split(",")
                            if len(parts) == 3 and parts[0] == uuid_str and parts[2] == "renaiselfmob":
                                updated_lines.append(f"{uuid_str},used,renaiselfmob\n")
                                found = True
                            else:
                                updated_lines.append(line)
                    if found:
                        with open(USED_UUID_FILE, "w") as f:
                            f.writelines(updated_lines)
        return "", 200
    except Exception as e:
        print("❌ Webhook error (renai):", e)
        return "", 400

@app.route("/selfmob/<uuid_str>", methods=["GET", "POST"])
def selfmob_uuid(uuid_str):
    full_year = None
    lines = []
    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = [line.strip().split(",") for line in f if line.strip()]
            for uid, flag, mode in lines:
                if uid == uuid_str and mode == "selfmob":
                    full_year = (flag == "1")
                    break
        if full_year is None:
            return "無効なリンクです（UUID不一致）", 400
    except FileNotFoundError:
        return "使用履歴が確認できません", 400

    if request.method == "POST":
        try:
            data = request.get_json() if request.is_json else request.form
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
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
            palm_titles, palm_texts, shichu_result, iching_result, lucky_info = generate_fortune_shincom(
                image_data, birthdate, kyusei_text
            )
            palm_result = "\n".join(palm_texts)
            summary_text = palm_texts[5] if len(palm_texts) > 5 else ""
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
            filename = f"result_{uuid_str}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            Thread(target=generate_pdf_async, args=(filepath, result_data, "shincom", "a4", full_year, uuid_str, lines), daemon=True).start()
            redirect_url = url_for("preview", filename=filename)
            return jsonify({"redirect_url": redirect_url}) if request.is_json else redirect(redirect_url)
        except Exception as e:
            print("処理エラー:", e)
            return jsonify({"error": str(e)}) if request.is_json else "処理中にエラーが発生しました"
    return render_template("index_selfmob.html", uuid_str=uuid_str, full_year=full_year)

@app.route("/renaiselfmob/<uuid_str>", methods=["GET", "POST"])
@app.route("/renaiselfmob_full/<uuid_str>", methods=["GET", "POST"])
def renaiselfmob_uuid(uuid_str):
    full_year = None
    lines = []
    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = [line.strip().split(",") for line in f if line.strip()]
            for uid, flag, mode in lines:
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
            Thread(target=generate_pdf_async, args=(filepath, result_data, "renai", "a4", full_year, uuid_str, lines), daemon=True).start()
            return redirect(url_for("preview", filename=filename))
        except Exception as e:
            print("処理エラー:", e)
            return "処理中にエラーが発生しました", 500
    return render_template("index_renaiselfmob.html", uuid_str=uuid_str, full_year=full_year)

@app.route("/preview/<filename>")
def preview(filename):
    # If coming from an internal route, show PDF inline; otherwise show a static page with link
    referer = request.referrer or ""
    if any(x in referer for x in ["/tenmob", "/selfmob", "/renai"]):
        return redirect(url_for("view_pdf", filename=filename))
    return render_template("fortune_pdf.html", filename=filename, referer=referer)

@app.route("/view/<filename>")
def view_pdf(filename):
    # Serve the generated PDF file
    filepath = os.path.join("static", "uploads", filename)
    if not os.path.exists(filepath):
        return "ファイルが存在しません", 404
    return send_file(filepath, mimetype='application/pdf')

@app.route("/login", methods=["GET", "POST"])
def login():
    # Simple password login for store mode
    if request.method == "POST":
        password = request.form.get("password")
        next_url_post = request.form.get("next_url", "tenmob")
        # Allow only known endpoints
        if next_url_post not in ["ten", "tenmob", "renai", "renaimob", "renaib4"]:
            next_url_post = "tenmob"
        if password == os.getenv("LOGIN_PASSWORD", "pass"):
            session["logged_in"] = True
            return redirect(url_for(next_url_post))
        else:
            return render_template("login.html", next_url=next_url_post)
    # GET request: show login form
    next_url = request.args.get("next", "tenmob")
    return render_template("login.html", next_url=next_url)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    return render_template("home-unified.html")

@app.route("/tokutei")
def legal():
    return render_template("tokutei.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/get_eto", methods=["POST"])
def get_eto():
    try:
        birthdate = request.json.get("birthdate")
        if not birthdate or not isinstance(birthdate, str):
            return jsonify({"error": "無効な生年月日です"}), 400
        y, m, d = map(int, birthdate.split("-"))
        eto = get_nicchu_eto(birthdate)
        honmeisei = get_honmeisei(y, m, d)
        return jsonify({"eto": eto, "honmeisei": honmeisei})
    except Exception as e:
        print("❌ /get_eto エラー:", e)
        return jsonify({"error": "干支または本命星の取得中にエラーが発生しました"}), 500


@app.route("/view_txt_log")
def view_txt_log():
    try:
        with open("shop_log.txt", encoding="utf-8") as f:
            content = f.read()
        return f"<pre>{content}</pre>"
    except Exception as e:
        return f"ログファイルの読み込みに失敗しました: {e}"


@app.route("/download_shop_log")
def download_shop_log():
    filepath = "shop_counter.csv"
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("date,shop_id,count\n")
    return send_file(filepath, as_attachment=True)

@app.route("/view_shop_log")
def view_shop_log():
    with sqlite3.connect("shop_log.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT date, shop_id, count FROM shop_logs ORDER BY date DESC")
        logs = cursor.fetchall()
    return render_template("shop_log.html", logs=logs)

def create_payment_link(price, uuid_str, redirect_url, metadata, full_year=False, mode="selfmob"):
    """
    KOMOJU決済リンク生成（通常・恋愛／年運オプション対応）
    
    Parameters:
        - price: 決済金額
        - uuid_str: 一意の外部ID
        - redirect_url: 決済完了後の遷移先URL
        - metadata: JSON文字列（例：{"shop_id": "01"}）
        - full_year: Trueの場合は年運付き（Public Link IDが異なる）
        - mode: "selfmob" or "renaiselfmob"
    """
    if mode == "renaiselfmob":
        komoju_id = os.getenv(
            "KOMOJU_RENAI_PUBLIC_LINK_ID_FULL" if full_year else "KOMOJU_RENAI_PUBLIC_LINK_ID"
        )
    else:
        komoju_id = os.getenv(
            "KOMOJU_PUBLIC_LINK_ID_FULL" if full_year else "KOMOJU_PUBLIC_LINK_ID"
        )
    if not komoju_id:
        raise ValueError("KOMOJUのPublic Link IDが未設定です。環境変数を確認してください。")
    encoded_redirect = quote(redirect_url, safe='')
    encoded_metadata = quote(metadata)
    komoju_url = (
        f"https://komoju.com/payment_links/{komoju_id}"
        f"?external_order_num={uuid_str}"
        f"&customer_redirect_url={encoded_redirect}"
        f"&metadata={encoded_metadata}"
    )
    print(f"🔗 決済URL [{mode}] (full={full_year}):", komoju_url)
    return komoju_url

@app.route("/selfmob-<shop_id>")
def selfmob_branch(shop_id):
    session["shop_id"] = shop_id
    return redirect("/selfmob")

@app.route("/renaiselfmob-<shop_id>")
def renaiselfmob_branch(shop_id):
    session["shop_id"] = shop_id
    return redirect("/renaiselfmob")

@app.route("/generate_link/<shop_id>")
def generate_link(shop_id):
    session["shop_id"] = shop_id
    return _generate_link(full_year=False)

@app.route("/generate_link_full/<shop_id>")
def generate_link_full(shop_id):
    session["shop_id"] = shop_id
    return _generate_link(full_year=True)

@app.route("/generate_link_renai/<shop_id>")
def generate_link_renai(shop_id):
    session["shop_id"] = shop_id
    return _generate_link_renai(full_year=False)

@app.route("/generate_link_renai_full/<shop_id>")
def generate_link_renai_full(shop_id):
    session["shop_id"] = shop_id
    return _generate_link_renai(full_year=True)