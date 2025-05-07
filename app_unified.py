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
from fortune_logic import generate_fortune as generate_fortune_shincom, get_nicchu_eto, generate_renai_fortune as renai_generate_fortune
from kyusei_utils import get_honmeisei
from pdf_generator_unified import create_pdf_unified

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/ten", methods=["GET", "POST"])
@app.route("/tenmob", methods=["GET", "POST"])
def ten_shincom():
    if "logged_in" not in session and request.path == "/ten":
        return redirect(url_for("login"))

    mode = "shincom"
    size = "B4" if request.path == "/ten" else "A4"

    if request.method == "POST":
        if request.is_json:
            data = request.get_json()
            image_data = data["image"]
            birthdate = data["birthdate"]
            eto = data["eto"]
        else:
            image_data = request.form["image"]
            birthdate = request.form["birthdate"]
            eto = request.form["eto"]

        result_data = generate_fortune(birthdate, eto, mode=mode)
        result_data["image_path"] = save_image(image_data)
        result_data["titles"] = get_titles(mode)
        result_data["palm_titles"] = get_palm_titles(mode)

        filename = generate_filename()
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        full_year = "full_year" in request.form or (
            request.is_json and data.get("full_year")
        )
        create_pdf_unified(filepath, result_data, mode, size=size, include_yearly=full_year)

        if request.is_json:
            return jsonify({"redirect_url": url_for("download_file", filename=filename)})
        else:
            return redirect(url_for("download_file", filename=filename))

    return render_template("index.html", mode="ten", size="B4")




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

        raw_result = renai_generate_fortune(user_birth, partner_birth, selected_topics, include_yearly)

        titles = {
            "compatibility": "相性診断" if partner_birth else "恋愛傾向と出会い",
            "love_summary": "総合恋愛運"
        }
        texts = {
            "compatibility": raw_result.get("compatibility_text", ""),
            "love_summary": raw_result.get("overall_love_fortune", "")
        }

        result_data = {
            "titles": titles,
            "texts": texts,
            "themes": raw_result.get("topic_fortunes", []),
            "lucky_info": raw_result.get("lucky_info", "取得できませんでした。"),
            "lucky_direction": raw_result.get("lucky_direction", ""),
            "birthdate": user_birth
        }

        if include_yearly:
            result_data["yearly_fortunes"] = raw_result.get("yearly_love_fortunes", {})

        filename = f"renai_{uuid.uuid4()}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        create_pdf_unified(filepath, result_data, "renai", size=size, include_yearly=include_yearly)

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
    filepath = os.path.join("static", "uploads", filename)  # 修正点ここ
    print(f"[DEBUG] Looking for PDF at: {filepath}")

    if not os.path.exists(filepath):
        print("[ERROR] PDF file not found!")
        return "ファイルが存在しません", 404

    return send_file(filepath, mimetype='application/pdf')




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
