import os
import base64
import uuid
import json
import requests
import traceback
from datetime import datetime
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify, make_response
from fortune_logic import generate_fortune
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta
from yearly_fortune_utils import generate_yearly_fortune
from fortune_logic import generate_fortune as generate_fortune_shincom, get_nicchu_eto
from kyusei_utils import get_honmeisei, get_kyusei_fortune
from pdf_generator_unified import create_pdf_unified
from fortune_logic import generate_renai_fortune

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/ten", methods=["GET", "POST"], endpoint="ten")
@app.route("/tenmob", methods=["GET", "POST"], endpoint="tenmob")
def ten_shincom():
    if "logged_in" not in session:
        return redirect(url_for("login", next=request.endpoint))

    mode = "shincom"
    size = "B4" if request.path == "/ten" else "A4"
    is_json = request.is_json

    if request.method == "POST":
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
            palm_titles, palm_texts, shichu_result, iching_result, lucky_lines = generate_fortune(
                image_data, birthdate, kyusei_text
            )

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
            create_pdf_unified(filepath, result_data, mode, size=size.lower(), include_yearly=full_year)
            return jsonify({"redirect_url": url_for("preview", filename=filename)}) if is_json else redirect(url_for("preview", filename=filename))
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}) if is_json else "処理中にエラーが発生しました"

    return render_template("index.html")

@app.route("/renai", methods=["GET", "POST"])
@app.route("/renaib4", methods=["GET", "POST"])
def renai():
    # Login required for store usage (love fortune)
    if "logged_in" not in session:
        return redirect(url_for("login", next=request.endpoint))

    size = "A4" if request.path == "/renai" else "B4"

    if request.method == "POST":
        user_birth = request.form.get("user_birth")
        partner_birth = request.form.get("partner_birth")
        include_yearly = request.form.get("include_yearly") == "yes"

        # Prepare labels for love fortune sections
        now = datetime.now()
        target1 = now.replace(day=15)
        if now.day >= 20:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)
        year_label = f"{now.year}年の恋愛運"
        month_label = f"{target1.year}年{target1.month}月の恋愛運"
        next_month_label = f"{target2.year}年{target2.month}月の恋愛運"

        # Generate love fortune results (with optional yearly data)
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

        filename = f"renai_{uuid.uuid4()}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        create_pdf_unified(filepath, result_data, "renai", size=size.lower(), include_yearly=include_yearly)
        return send_file(filepath, as_attachment=True)

    # Render input form for love fortune (two birthdates)
    return render_template("renai_form.html")

@app.route("/selfmob", methods=["GET"])
def selfmob_start():
    # Payment start page (offers normal or love purchase options)
    return render_template("pay.html")

# Enhanced UUID flow for selfmob (normal) and renaiselfmob (love)
UPLOAD_FOLDER = "static/uploads"
USED_UUID_FILE = "used_orders.txt"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
if not os.path.exists(USED_UUID_FILE):
    open(USED_UUID_FILE, "w").close()

@app.route("/generate_link")
def generate_link():
    return _generate_link(full_year=False)

@app.route("/generate_link_full")
def generate_link_full():
    return _generate_link(full_year=True)

@app.route("/generate_link_renai")
def generate_link_renai():
    return _generate_link_renai(full_year=False)

@app.route("/generate_link_renai_full")
def generate_link_renai_full():
    return _generate_link_renai(full_year=True)

def _generate_link(full_year=False):
    komoju_id = os.getenv("KOMOJU_PUBLIC_LINK_ID_FULL" if full_year else "KOMOJU_PUBLIC_LINK_ID")
    new_uuid = str(uuid.uuid4())
    redirect_url = "https://shincom-unified.onrender.com/thanks"
    encoded_redirect = quote(redirect_url, safe='')

    # Record new UUID with mode "selfmob"
    with open(USED_UUID_FILE, "a") as f:
        f.write(f"{new_uuid},{int(full_year)},selfmob\n")

    komoju_url = f"https://komoju.com/payment_links/{komoju_id}?external_order_num={new_uuid}&customer_redirect_url={encoded_redirect}"
    print("🔗 決済URL:", komoju_url)

    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", new_uuid, max_age=600)
    return resp

def _generate_link_renai(full_year=False):
    komoju_id = os.getenv("KOMOJU_RENAI_PUBLIC_LINK_ID_FULL" if full_year else "KOMOJU_RENAI_PUBLIC_LINK_ID")
    new_uuid = str(uuid.uuid4())
    redirect_url = "https://shincom-unified.onrender.com/thanks"
    encoded_redirect = quote(redirect_url, safe='')

    # Record new UUID with mode "renaiselfmob"
    with open(USED_UUID_FILE, "a") as f:
        f.write(f"{new_uuid},{int(full_year)},renaiselfmob\n")

    komoju_url = f"https://komoju.com/payment_links/{komoju_id}?external_order_num={new_uuid}&customer_redirect_url={encoded_redirect}"
    print("🔗 RENAI決済URL:", komoju_url)

    resp = make_response(redirect(komoju_url))
    resp.set_cookie("uuid", new_uuid, max_age=600)
    return resp

@app.route("/thanks")
def thanks():
    # After payment, redirect to the appropriate UUID page
    uuid_str = request.cookies.get("uuid")
    if not uuid_str:
        return render_template("thanks.html")

    mode = "selfmob"
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 3 and parts[0] == uuid_str:
                    mode = parts[2]  # e.g. "selfmob" or "renaiselfmob"
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
            if uuid_str:
                print("✅ Webhook captured:", uuid_str)
        return "", 200
    except Exception as e:
        print("Webhook error:", e)
        return "", 400

@app.route("/webhook/renaiselfmob", methods=["POST"])
def webhook_renaiselfmob():
    try:
        data = request.get_json()
        if data.get("event") == "payment.captured":
            uuid_str = data["data"]["attributes"].get("external_order_num")
            if uuid_str:
                print("✅ RENAI Webhook captured:", uuid_str)
        return "", 200
    except Exception as e:
        print("Webhook error (renai):", e)
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

            shichu_texts = {}
            parts = [part for part in str(shichu_result).split("■ ") if part.strip()]
            for part in parts:
                if "\n" in part:
                    title, body = part.split("\n", 1)
                else:
                    title, body = part, ""
                shichu_texts[title.strip()] = body.strip()

            # ✅ lucky_lines 修正（◆は付けない）
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
                    "personality": shichu_texts.get("性格", ""),
                    "year_fortune": shichu_texts.get(year_label, ""),
                    "month_fortune": shichu_texts.get(month_label, ""),
                    "next_month_fortune": shichu_texts.get(next_month_label, "")
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

            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            create_pdf_unified(filepath, result_data, "shincom", size="a4", include_yearly=full_year)

            with open(USED_UUID_FILE, "w") as f:
                for uid, flag, mode in lines:
                    if uid != uuid_str:
                        f.write(f"{uid},{flag},{mode}\n")
                    else:
                        f.write(f"{uid},used,{mode}\n")

            redirect_url = url_for("preview", filename=filename)
            return jsonify({"redirect_url": redirect_url}) if request.is_json else redirect(redirect_url)
        except Exception as e:
            print("処理エラー:", e)
            return jsonify({"error": str(e)}) if request.is_json else "処理中にエラーが発生しました"

    return render_template("index_selfmob.html", uuid_str=uuid_str, full_year=full_year)



@app.route("/renaiselfmob/<uuid_str>", methods=["GET", "POST"])
@app.route("/renaiselfmob_full/<uuid_str>", methods=["GET", "POST"])
def renaiselfmob_uuid(uuid_str):
    # Handle the form after payment for love fortune
    full_year = None
    lines = []
    try:
        # Verify UUID from used_orders log
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
        user_birth = request.form.get("user_birth")
        partner_birth = request.form.get("partner_birth")
        if not user_birth or not isinstance(user_birth, str):
            return "生年月日が不正です", 400

        # Determine labels for love fortune sections (relative months)
        now = datetime.now()
        target1 = now.replace(day=15)
        if now.day >= 20:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)
        year_label = f"{now.year}年の恋愛運"
        month_label = f"{target1.year}年{target1.month}月の恋愛運"
        next_month_label = f"{target2.year}年{target2.month}月の恋愛運"

        # Generate love fortune (with include_yearly flag)
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

        filename = f"renai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        create_pdf_unified(filepath, result_data, "renai", size="a4", include_yearly=full_year)

        # Mark UUID as used (remove from file)
        with open(USED_UUID_FILE, "w") as f:
            for uid, flag, mode in lines:
                if uid != uuid_str:
                    f.write(f"{uid},{flag},{mode}\n")
        return redirect(url_for("preview", filename=filename))

    # Render the form (post-payment) for love fortune input
    return render_template("index_renaiselfmob.html", uuid_str=uuid_str)



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


