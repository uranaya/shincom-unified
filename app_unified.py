
import os
import base64
import uuid
import json
import requests
import traceback
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify
from dotenv import load_dotenv
from yearly_fortune_utils import generate_yearly_fortune
from fortune_logic import generate_fortune as generate_fortune_shincom, get_nicchu_eto
from kyusei_utils import get_honmeisei
from pdf_generator_unified import create_pdf_unified
from renai_fortune_utils import generate_fortune as generate_renai_fortune

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/ten", methods=["GET", "POST"])
@app.route("/tenmob", methods=["GET", "POST"])
def ten_shincom():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    
    mode = "shincom"
    size = "B4" if request.path == "/ten" else "A4"
    is_json = request.is_json

    if request.method == "POST":
        try:
            data = request.get_json() if is_json else request.form
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
            full_year = data.get("full_year", False) if is_json else data.get("full_year") == "yes"

            eto = get_nicchu_eto(birthdate)
            palm_result, shichu_result, iching_result, lucky_info = generate_fortune_shincom(image_data, birthdate)
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            create_pdf_unified(mode, size, {
                "image_data": image_data,
                "palm_result": palm_result,
                "shichu_result": shichu_result,
                "iching_result": iching_result,
                "lucky_info": lucky_info,
                "birthdate": birthdate
            }, filename, include_yearly=full_year)

            redirect_url = url_for("preview", filename=filename)
            return jsonify({"redirect_url": redirect_url}) if is_json else redirect(redirect_url)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}) if is_json else "処理中にエラーが発生しました"

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
        selected_topics = request.form.getlist("topics")
        include_yearly = request.form.get("include_yearly") == "yes"

        full_text = generate_renai_fortune(user_birth, partner_birth, selected_topics, include_yearly)

        result_data = {
            "titles": {
                "compatibility": "相性鑑定と総合恋愛運"
            },
            "texts": {
                "compatibility": full_text
            },
            "lucky_info": "",
            "lucky_direction": "",
            "themes": [],
            "yearly_fortunes": {}
        }

        filename = f"renai_{uuid.uuid4()}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        create_pdf_unified(filepath, result_data, "renai", size.lower(), include_yearly)
        return send_file(filepath, as_attachment=True)

    return render_template("renai_form.html")


@app.route("/preview/<filename>")
def preview(filename):
    referer = request.referrer or ""
    if any(x in referer for x in ["/tenmob", "/selfmob", "/renai"]):
        return redirect(url_for("view_pdf", filename=filename))
    return render_template("fortune_pdf.html", filename=filename, referer=referer)


@app.route("/view/<filename>")
def view_pdf(filename):
    return send_file(os.path.join("static", filename), mimetype='application/pdf')


@app.route("/get_eto", methods=["POST"])
def get_eto():
    birthdate = request.json.get("birthdate")
    eto = get_nicchu_eto(birthdate)
    y, m, d = map(int, birthdate.split("-"))
    honmeisei = get_honmeisei(y, m, d)
    return jsonify({"eto": eto, "honmeisei": honmeisei})


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next", "ten")
    if request.method == "POST":
        password = request.form.get("password")
        next_url_post = request.form.get("next_url", "ten")
        if password == os.getenv("LOGIN_PASSWORD", "pass"):
            session["logged_in"] = True
            return redirect(url_for(next_url_post))
        return render_template("login.html", next_url=next_url)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    return render_template("home-unified.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
