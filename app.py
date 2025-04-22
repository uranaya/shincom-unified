import os
import base64
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from fortune_logic import generate_fortune, get_nicchu_eto
from pdf_generator_b4 import create_pdf as create_pdf_b4
from pdf_generator_a4 import create_pdf as create_pdf_a4

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 最大10MB

# === /ten（店頭）===
@app.route("/ten", methods=["GET", "POST"])
def ten():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        try:
            image_data = request.form.get("image_data")
            birthdate = request.form.get("birthdate")
            eto = get_nicchu_eto(birthdate)
            palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            create_pdf_b4(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)
            return redirect(url_for("preview", filename=filename))
        except Exception as e:
            print("❌ tenエラー:", e)
            return "処理中にエラーが発生しました"
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.getenv("LOGIN_PASSWORD", "pass"):
            session["logged_in"] = True
            return redirect(url_for("ten"))
    return render_template("login.html")

# === /tenmob（スマホ店頭操作）===
@app.route("/tenmob", methods=["GET", "POST"])
def tenmob():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        try:
            data = request.get_json()
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
            eto = get_nicchu_eto(birthdate)
            palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            create_pdf_a4(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)
            return jsonify({"redirect_url": url_for("preview", filename=filename)})
        except Exception as e:
            print("❌ tenmobエラー:", e)
            return jsonify({"message": "処理中にエラーが発生しました"}), 500
    return render_template("tenmob/index.html")

# === /selfmob（KOMOJU連携）===
used_uuids = set()

@app.route("/webhook/selfmob", methods=["POST"])
def webhook_selfmob():
    data = request.json
    payment_id = data.get("id")
    if payment_id:
        used_uuids.add(payment_id)
    return "", 200

@app.route("/selfmob/<uuid_str>", methods=["GET", "POST"])
def selfmob(uuid_str):
    if uuid_str not in used_uuids:
        return "無効なアクセスです", 403
    if request.method == "POST":
        try:
            data = request.get_json()
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
            eto = get_nicchu_eto(birthdate)
            palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            create_pdf_a4(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)
            return jsonify({"redirect_url": url_for("preview", filename=filename)})
        except Exception as e:
            print("❌ selfmobエラー:", e)
            return jsonify({"message": "処理中にエラーが発生しました"}), 500
    return render_template("selfmob/index.html")

# === 共通ルート ===
@app.route("/get_eto", methods=["POST"])
def get_eto():
    birthdate = request.json.get("birthdate")
    eto = get_nicchu_eto(birthdate)
    return {"eto": eto}

@app.route("/logout")
def logout():
    session.clear()
    referer = request.referrer or ""
    if "/tenmob" in referer:
        return redirect(url_for("login"))
    elif "/selfmob" in referer:
        return redirect("https://checkout.komoju.com/")  # カスタマイズ可
    else:
        return redirect(url_for("login"))

@app.route("/preview/<filename>")
def preview(filename):
    referer = request.referrer or ""
    if "/tenmob" in referer:
        template_path = "tenmob/fortune_pdf.html"
    elif "/selfmob" in referer:
        template_path = "selfmob/fortune_pdf.html"
    else:
        template_path = "fortune_pdf.html"
    return render_template(template_path, filename=filename)

@app.route("/view/<filename>")
def view_pdf(filename):
    filepath = os.path.join("static", filename)
    return send_file(filepath, mimetype='application/pdf')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
