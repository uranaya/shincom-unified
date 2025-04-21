import os
import base64
from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, session
from datetime import datetime
from dotenv import load_dotenv
from affiliate import create_qr_code, get_affiliate_link
from pdf_generator_b4 import create_pdf as create_pdf_b4
from pdf_generator_a4 import create_pdf as create_pdf_a4
from fortune_logic import analyze_palm, get_shichu_fortune, get_iching_advice, get_lucky_info, get_nicchu_eto
from hayami_table_full_complete import hayami_table

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.secret_key = os.getenv("SECRET_KEY", "defaultsecret")

def generate_fortune(image_data, birthdate):
    palm_result = analyze_palm(image_data)
    shichu_result = get_shichu_fortune(birthdate)
    iching_result = get_iching_advice()
    lucky_info = get_lucky_info(birthdate)
    return palm_result, shichu_result, iching_result, lucky_info

@app.route("/")
def root():
    return redirect("/ten")

@app.route("/login/<mode>", methods=["GET", "POST"])
def login(mode):
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.getenv("LOGIN_PASSWORD", "uranaya"):
            session["logged_in"] = True
            return redirect(f"/{mode}")
        else:
            return render_template("login.html", error="パスワードが間違っています", mode=mode)
    return render_template("login.html", mode=mode)

@app.route("/logout")
def logout():
    session.clear()
    referer = request.referrer or ""
    if "/tenmob" in referer:
        return redirect(url_for("login", mode="tenmob"))
    elif "/selfmob" in referer:
        return redirect(url_for("login", mode="selfmob"))
    else:
        return redirect(url_for("login", mode="ten"))

@app.route("/ten", methods=["GET", "POST"])
def ten():
    if not session.get("logged_in"):
        return redirect(url_for("login", mode="ten"))
    if request.method == "POST":
        image_data = request.form.get("image_data")
        birthdate = request.form.get("birthdate")
        palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
        filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        create_pdf_b4(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)
        return redirect(url_for("preview", filename=filename))
    return render_template("ten/index.html")

@app.route("/tenmob", methods=["GET", "POST"])
def tenmob():
    if not session.get("logged_in"):
        return redirect(url_for("login", mode="tenmob"))
    if request.method == "POST":
        try:
            data = request.get_json()
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
            eto = get_nicchu_eto(birthdate)
            palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            create_pdf_a4(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)
            return redirect(url_for("preview", filename=filename))
        except Exception as e:
            print("❌ tenmobエラー:", e)
            return jsonify({"message": "処理中にエラーが発生しました"}), 500
    return render_template("tenmob/index.html")

@app.route("/selfmob", methods=["GET", "POST"])
def selfmob():
    if not session.get("logged_in"):
        return redirect(url_for("login", mode="selfmob"))
    if request.method == "POST":
        image_data = request.form.get("image_data")
        birthdate = request.form.get("birthdate")
        palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
        filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        create_pdf_a4(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)
        return redirect(url_for("preview", filename=filename))
    return render_template("selfmob/index.html")

@app.route("/get_eto", methods=["POST"])
def get_eto():
    birthdate = request.json.get("birthdate")
    eto = get_nicchu_eto(birthdate)
    return {"eto": eto}

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
