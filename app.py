import os
import base64
from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
from datetime import datetime
from dotenv import load_dotenv
from affiliate import create_qr_code, get_affiliate_link
from pdf_generator_b4 import create_pdf as create_pdf_b4
from pdf_generator_a4 import create_pdf as create_pdf_a4
from fortune_logic import analyze_palm, get_shichu_fortune, get_iching_advice, get_lucky_info, get_nicchu_eto
from hayami_table import find_eto

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

def generate_fortune(image_data, birthdate):
    palm_result = analyze_palm(image_data)
    shichu_result = get_shichu_fortune(birthdate)
    iching_result = get_iching_advice()
    lucky_info = get_lucky_info(birthdate)
    return palm_result, shichu_result, iching_result, lucky_info

@app.route("/")
def root():
    return redirect("/ten")

@app.route("/ten", methods=["GET", "POST"])
def ten():
    if request.method == "POST":
        image_data = request.form.get("image_data")
        birthdate = request.form.get("birthdate")
        palm_result, shichu_result, iching_result, lucky_info = generate_fortune(image_data, birthdate)
        filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        create_pdf_b4(image_data, palm_result, shichu_result, iching_result, lucky_info, filename)
        return redirect(url_for("preview", filename=filename))
    return render_template("index.html")

@app.route("/tenmob", methods=["GET", "POST"])
def tenmob():
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
