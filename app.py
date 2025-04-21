from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash, jsonify
import os
from dotenv import load_dotenv
from datetime import datetime
from hayami_table_full_complete import hayami_table
from fortune_logic import get_nicchu_eto, get_shichu_fortune, get_iching_advice, get_lucky_info, analyze_palm
from pdf_generator_a4 import create_pdf as create_pdf_a4
from pdf_generator_b4 import create_pdf as create_pdf_b4

app = Flask(__name__)
app.secret_key = "supersecretkey"

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 最大5MBに設定

load_dotenv()
PASSWORD = "uranaya2024"

@app.route("/login", methods=["GET", "POST"])
@app.route("/<mode>/login", methods=["GET", "POST"])
def login(mode="ten"):
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            return redirect(url_for(f"{mode}_mode"))
        else:
            flash("パスワードが違います")
    return render_template(f"{mode}/login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET"])
def root():
    return redirect(url_for("ten_mode"))

@app.route("/ten", methods=["GET", "POST"])
def ten_mode():
    return handle_mode("ten")

from flask import request, redirect, url_for, render_template, session, jsonify
import os
from datetime import datetime

@app.route("/tenmob", methods=["GET", "POST"])
def tenmob():
    if request.method == "POST":
        try:
            image_data = request.form.get("image_data")
            birthdate = request.form.get("birthdate")

            if not image_data or not birthdate:
                flash("画像または生年月日がありません")
                return redirect(url_for("tenmob"))

            palm_result = analyze_palm(image_data)
            shichu_result = get_shichu_fortune(birthdate)
            iching_result = get_iching_advice()
            lucky_info = get_lucky_info(birthdate)

            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)

            return redirect(url_for("preview", filename=filename))

        except Exception as e:
            print("❌ /tenmob POSTエラー:", e)
            flash("エラーが発生しました")
            return redirect(url_for("tenmob"))

    return render_template("tenmob/index.html")


@app.route("/selfmob", methods=["GET", "POST"])
def selfmob_mode():
    return handle_mode("selfmob")

def handle_mode(mode):
    if not session.get("authenticated") and mode in ["ten", "tenmob"]:
        return redirect(url_for("login", mode=mode))

    if request.method == "POST":
        image_data = request.form.get("image_data")
        birthdate = request.form.get("birthdate")

        if not image_data or not birthdate:
            flash("画像または生年月日がありません")
            return redirect(url_for(f"{mode}_mode"))

        print("✅ image_data:", image_data[:20], flush=True)
        print("✅ birthdate:", birthdate, flush=True)

        palm_result = analyze_palm(image_data)
        print("✅ palm_result:", palm_result[:100], flush=True)

        shichu_result = get_shichu_fortune(birthdate)
        print("✅ shichu_result:", shichu_result[:100], flush=True)

        iching_result = get_iching_advice()
        print("✅ iching_result:", iching_result[:100], flush=True)

        lucky_info = get_lucky_info(birthdate)
        print("✅ lucky_info:", lucky_info[:100], flush=True)

        filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        create_pdf = create_pdf_b4 if mode == "ten" else create_pdf_a4
        filepath = create_pdf(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)

        print("✅ filename:", filename, flush=True)
        return redirect(url_for("preview", filename=os.path.basename(filepath)))

    return render_template(f"{mode}/index.html")

@app.route("/get_eto", methods=["POST"])
def get_eto():
    birthdate = request.json.get("birthdate")
    eto = get_nicchu_eto(birthdate)
    return jsonify({"eto": eto})

@app.route("/preview/<filename>")
def preview(filename):
    referer = request.referrer or ""
    if "/tenmob" in referer:
        mode = "tenmob"
        template_path = "tenmob/fortune_pdf.html"
    elif "/selfmob" in referer:
        mode = "selfmob"
        template_path = "selfmob/fortune_pdf.html"
    else:
        mode = "ten"
        template_path = "fortune_pdf.html"
    return render_template(template_path, filename=filename, mode=mode)

@app.route("/view/<filename>")
def view_pdf(filename):
    filepath = os.path.join("static", filename)
    return send_file(filepath, mimetype='application/pdf')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
