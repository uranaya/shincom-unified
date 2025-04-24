import os
import base64
import uuid
import json
import requests
from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
# from shichu_utils import get_nicchu_eto  ← これを削除
from fortune_logic import generate_fortune, get_nicchu_eto
from fortune_logic import generate_fortune
from kyusei_utils import get_honmeisei
from pdf_generator_b4 import create_pdf as create_pdf_b4
from pdf_generator_a4 import create_pdf as create_pdf_a4

load_dotenv()

# static フォルダがなければ作成（PDF出力用）
STATIC_DIR = os.path.join(os.getcwd(), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 最大10MB

uuid_file = "used_uuids.json"
if os.path.exists(uuid_file):
    with open(uuid_file, "r") as f:
        used_uuids = set(json.load(f))
else:
    used_uuids = set()

def save_uuids():
    with open(uuid_file, "w") as f:
        json.dump(list(used_uuids), f)

@app.route("/create_payment_link", methods=["GET"])
def create_payment_link():
    komoju_secret = os.getenv("KOMOJU_API_KEY")
    komoju_url = os.getenv("KOMOJU_API_URL", "https://sandbox.komoju.com/api/v1/payment_links")
    uuid_str = str(uuid.uuid4())
    redirect_url = f"https://shincom-unified.onrender.com/selfmob/{uuid_str}"
    payload = {
        "amount": 500,
        "currency": "JPY",
        "payment_method_types": ["konbini", "credit_card"],
        "external_order_num": uuid_str,
        "return_url": redirect_url
    }

    response = requests.post(
        komoju_url,
        auth=(komoju_secret, ""),
        json=payload
    )

    if response.status_code == 201:
        payment_url = response.json()["url"]
        print(f"🧾 新規UUID生成: {uuid_str}")
        return redirect(payment_url)
    else:
        print("❌ KOMOJU連携失敗:", response.text)
        return "決済リンク生成に失敗しました", 500

@app.route("/webhook/selfmob", methods=["POST"])
def webhook_selfmob():
    data = request.json
    payment_id = data.get("id")
    if payment_id:
        print(f"✅ Webhook受信: {payment_id}")
        used_uuids.add(payment_id)
        save_uuids()
    return "", 200


@app.route("/selfmob")
def selfmob_login():
    return render_template("selfmob_login.html")

@app.route("/selfmob/pay")
def selfmob_pay():
    return render_template("selfmob_pay.html")

@app.route("/selfmob/index")
def selfmob_index():
    return render_template("index.html")  # 実際の鑑定フォーム


@app.route("/")
def index():
    return redirect(url_for("ten"))


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


@app.route("/tenmob", methods=["GET", "POST"])
def tenmob():
    if "logged_in" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            print("📩 POST受信開始")
            data = request.get_json()
            print("📨 JSON受信成功:", data)

            image_data = data.get("image_data")
            birthdate = data.get("birthdate")

            eto = get_nicchu_eto(birthdate)
            print("🔢 干支取得成功:", eto)

            palm_result, shichu_result, iching_result, lucky_info = generate_fortune(
                image_data, birthdate
            )
            print("🔮 占い生成成功")

            # staticフォルダがなければ作成
            os.makedirs("static", exist_ok=True)

            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            create_pdf_a4(
                image_data, palm_result, shichu_result, iching_result, lucky_info, filename
            )
            print("📄 PDF生成成功:", filename)

            redirect_url = url_for("preview", filename=filename)
            print("✅ tenmob PDF作成成功:", redirect_url)

            response = jsonify({"redirect_url": redirect_url})
            print("📦 JSONレスポンス返却:", response.get_data())
            return response, 200

        except Exception as e:
            print("❌ tenmob POST処理エラー:", e)
            return jsonify({"error": str(e)}), 500

    # 🔻 GETリクエストでフォーム画面を表示
    return render_template("tenmob/index.html")





@app.route("/tokutei")
def tokutei():
    return render_template("tokutei.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.getenv("LOGIN_PASSWORD", "pass"):
            session["logged_in"] = True
            return redirect(session.get("next_url", url_for("tenmob")))  # ✅ デフォルトは /tenmob に変更

    # GET時のみ next_url を記録
    referer = request.referrer or ""
    if "/tenmob" in referer:
        session["next_url"] = url_for("tenmob")
    elif "/ten" in referer:
        session["next_url"] = url_for("ten")
    else:
        session["next_url"] = url_for("tenmob")  # ✅ 安全なデフォルトを tenmob に

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    referer = request.referrer or ""
    if "/tenmob" in referer:
        return redirect(url_for("login"))
    elif "/selfmob" in referer:
        return redirect("https://checkout.komoju.com/")
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

@app.route("/get_eto", methods=["POST"])
def get_eto():
    birthdate = request.json.get("birthdate")
    eto = get_nicchu_eto(birthdate)
    y, m, d = map(int, birthdate.split("-"))
    honmeisei = get_honmeisei(y, m, d)
    return jsonify({"eto": eto, "honmeisei": honmeisei})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
