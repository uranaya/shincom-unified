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


# Initialize logging and upload directories
UPLOAD_FOLDER = 'static/uploads'
USED_UUID_FILE = 'used_orders.txt'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
if not os.path.exists(USED_UUID_FILE):
    open(USED_UUID_FILE, "w").close()

# Initialize Flask app and configuration
app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
BASE_URL = os.getenv("BASE_URL", "https://shincom-unified.onrender.com")

# Initialize locks for thread-safe operations
used_file_lock = threading.Lock()


# 環境変数からPostgreSQL接続URLを取得
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)



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
    # Payment start page (offers normal or love purchase options)
    return render_template("pay.html")

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
        f.write(f"{uuid_str},0,selfmob,{shop_id}\n")
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
        f.write(f"{uuid_str},1,selfmob,{shop_id}\n")
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
        f.write(f"{uuid_str},0,renaiselfmob,{shop_id}\n")
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
        f.write(f"{uuid_str},1,renaiselfmob,{shop_id}\n")
    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp



@app.route("/thanks")
def thanks():
    uuid_str = request.cookies.get("uuid") or request.args.get("uuid")
    if not uuid_str:
        return render_template("thanks.html")

    mode = "selfmob"
    shop_id = "default"
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4 and parts[0] == uuid_str:
                    _, _, mode, shop_id = parts[:4]
                    break
    except FileNotFoundError:
        pass

    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO webhook_events (uuid, shop_id, service, date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (uuid) DO NOTHING
        """, (uuid_str, shop_id, f"{mode}_thanks", today))

        cur.execute("""
            INSERT INTO shop_logs (date, shop_id, service, count)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (date, shop_id, service)
            DO UPDATE SET count = shop_logs.count + 1
        """, (today, shop_id, mode))

        conn.commit()
        cur.close()
        conn.close()
        print("📝 thanksページでカウント:", shop_id, "/", today, "/", mode)
    except Exception as e:
        print("❌ thanksでの保存失敗:", e)

    return redirect(f"/{mode}/{uuid_str}")



@app.route("/selfmob/<uuid_str>", methods=["GET", "POST"])
def selfmob_uuid(uuid_str):
    full_year = None
    lines = []
    # Verify UUID existence and get full_year flag from used_orders.txt
    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = [line.strip().split(",") for line in f if line.strip()]
        for parts in lines:
            if len(parts) >= 3:
                uid, flag, mode = parts[:3]
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
                    "personality": shichu_result.get("personality", ""),
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
            shop_id = session.get("shop_id", "default")
            threading.Thread(
                target=background_generate_pdf,
                args=(filepath, result_data, "shincom", "a4", full_year, uuid_str, shop_id)
            ).start()

            redirect_url = url_for("preview", filename=filename)
            return jsonify({"redirect_url": redirect_url}) if is_json else redirect(redirect_url)

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
        for parts in lines:
            if len(parts) >= 3:
                uid, flag, mode = parts[:3]
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
            shop_id = session.get("shop_id", "default")
            threading.Thread(
                target=background_generate_pdf,
                args=(filepath, result_data, "renai", "a4", full_year, uuid_str, shop_id)
            ).start()

            return redirect(url_for("preview", filename=filename))

        except Exception as e:
            print("処理エラー:", e)
            return "処理中にエラーが発生しました", 500

    return render_template("index_renaiselfmob.html", uuid_str=uuid_str, full_year=full_year)






@app.route("/preview/<filename>")
def preview(filename):
    # If coming from an internal route, show PDF inline; otherwise show a static page with a link
    referer = request.referrer or ""
    if any(x in referer for x in ["/tenmob", "/selfmob", "/renai"]):
        return redirect(url_for("view_pdf", filename=filename))
    return render_template("fortune_pdf.html", filename=filename, referer=referer)

@app.route("/view/<filename>")
def view_pdf(filename):
    # Serve the generated PDF file if it exists
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
        if next_url_post not in ["ten", "tenmob", "renai", "renaib4"]:
            next_url_post = "tenmob"
        if password == os.getenv("LOGIN_PASSWORD", "pass"):
            session["logged_in"] = True
            return redirect(url_for(next_url_post))
        else:
            return render_template("login.html", next_url=next_url_post)
    # GET: show login form
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



@app.route("/selfmob-<shop_id>")
def selfmob_shop_entry(shop_id):
    session["shop_id"] = shop_id
    return render_template("pay.html", shop_id=shop_id)




def _generate_link_with_shopid(shop_id, full_year=False):
    uuid_str = str(uuid.uuid4())
    redirect_url = f"{BASE_URL}/thanks?uuid={uuid_str}"
    metadata = json.dumps({"shop_id": shop_id})
    komoju_url = create_payment_link(
        price=1000 if full_year else 500,
        uuid_str=uuid_str,
        redirect_url=redirect_url,
        metadata=metadata,
        full_year=full_year,
        mode="selfmob"
    )
    print("🔗 補助リンク生成:", komoju_url)
    with open(USED_UUID_FILE, "a") as f:
        f.write(f"{uuid_str},{int(full_year)},selfmob\n")
    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp



@app.route("/view_shop_log")
def view_shop_log():
    try:
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT date, shop_id, service, count FROM shop_logs ORDER BY date DESC")).fetchall()
        return render_template("shop_log.html", logs=rows)
    except Exception as e:
        return f"エラー: {e}"



def create_payment_link(price, uuid_str, redirect_url, metadata, full_year=False, mode="selfmob"):
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




def get_shop_id_from_log(uuid_str):
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 4:
                    uid, _, _, shop_id = parts[:4]
                    if uid == uuid_str:
                        return shop_id
        # セッション形式のUUID（external_order_numがnullだったとき）も探す
        print("⚠️ UUID not found in used_orders.txt:", uuid_str)
    except Exception as e:
        print("⚠️ shop_id読み取り失敗:", e)
    return "default"



# PostgreSQL登録処理

        # イベント保存（重複防止用）
        cur.execute("""
            INSERT INTO webhook_events (uuid, shop_id, service, date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (uuid) DO NOTHING
        """, (uuid_str, shop_id, service, today))

        # count を加算（あれば更新、なければ挿入）
        cur.execute("""
            INSERT INTO shop_logs (date, shop_id, service, count)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (date, shop_id, service)
            DO UPDATE SET count = shop_logs.count + 1
        """, (today, shop_id, service))

        conn.commit()
        cur.close()
        conn.close()
        print("📝 PostgreSQL shop_logs に記録:", shop_id, "/", today, "/", service)
    except Exception as e:
        print("❌ PostgreSQLへの保存失敗:", e)





# Webhook Selfmob with session補完


# Webhook Renai with session補完