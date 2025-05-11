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
        return redirect(url_for("login"))
    mode = "shincom"
    size = "B4" if request.path == "/ten" else "A4"
    is_json = request.is_json
    if request.method == "POST":
        try:
            data = request.get_json() if is_json else request.form
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
            full_year = data.get("full_year", False) if is_json else (data.get("full_year") == "yes")
            # 九星気学の吉方位テキストを取得
            try:
                year, month, day = map(int, birthdate.split("-"))
                kyusei_text = get_kyusei_fortune(year, month, day)
            except Exception as e:
                print("❌ lucky_direction 取得エラー:", e)
                kyusei_text = ""
            # 占い結果を生成
            eto = get_nicchu_eto(birthdate)
            palm_result, shichu_result, iching_result, lucky_info = generate_fortune_shincom(image_data, birthdate, kyusei_text)
            # palm_resultテキストを解析し各項目を抽出
            palm_sections = [sec for sec in palm_result.split("### ") if sec.strip()]
            palm_texts = []
            summary_text = ""
            if palm_sections:
                *main_sections, summary_section = palm_sections
                for sec in main_sections:
                    if "\n" in sec:
                        title_line, body = sec.split("\n", 1)
                    else:
                        title_line, body = sec, ""
                    body = body.strip()
                    if body:
                        palm_texts.append(body)
                if summary_section:
                    if "\n" in summary_section:
                        _, summary_body = summary_section.split("\n", 1)
                    else:
                        summary_body = summary_section
                    summary_text = summary_body.strip()
            # 四柱推命（性格・月運）結果を解析
            shichu_texts = {}
            shichu_parts = [part for part in shichu_result.split("■ ") if part.strip()]
            for part in shichu_parts:
                if "\n" in part:
                    title, body = part.split("\n", 1)
                else:
                    title, body = part, ""
                shichu_texts[title] = body.strip()
            # ラッキー情報をリスト化
            lucky_direction = kyusei_text
            lucky_lines = []
            if isinstance(lucky_info, str):
                for line in lucky_info.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
                    line = line.strip()
                    if line:
                        line = line.replace(":", "：", 1)
                        lucky_lines.append(f"◆ {line}")
            elif isinstance(lucky_info, dict):
                for k, v in lucky_info.items():
                    lucky_lines.append(f"◆ {k}：{v}")
            else:
                lucky_lines = list(lucky_info)
            # PDF生成用データ構築
            result_data = {
                "palm_titles": ["生命線", "運命線", "金運線", "特殊線1", "特殊線2"],
                "palm_texts": palm_texts,
                "titles": {
                    "palm_summary": "手相の総合アドバイス",
                    "personality": "性格診断",
                    "month_fortune": "今月の運勢",
                    "next_month_fortune": "来月の運勢"
                },
                "texts": {
                    "palm_summary": summary_text,
                    "personality": shichu_texts.get("性格", ""),
                    "month_fortune": shichu_texts.get("今月の運勢", ""),
                    "next_month_fortune": shichu_texts.get("来月の運勢", "")
                },
                "lucky_info": lucky_lines,
                "lucky_direction": lucky_direction,
                "birthdate": birthdate,
                "palm_result": "\n".join(palm_texts),
                "shichu_result": shichu_result.replace("\r\n", "\n").replace("\r", "\n"),
                "iching_result": iching_result.replace("\r\n", "\n").replace("\r", "\n")
            }
            result_data["palm_image"] = image_data
            if full_year:
                now = datetime.now()
                result_data["yearly_fortunes"] = generate_yearly_fortune(birthdate, now)
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            create_pdf_unified(filepath, result_data, mode, size=size.lower(), include_yearly=full_year)
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
        include_yearly = request.form.get("include_yearly") == "yes"

        raw_result = generate_renai_fortune(user_birth, partner_birth, include_yearly=include_yearly)

        result_data = {
            "texts": {
                "compatibility": raw_result.get("compatibility_text", ""),
                "overall_love_fortune": raw_result.get("overall_love_fortune", ""),
                "year_love": raw_result.get("year_love", ""),
                "month_love": raw_result.get("month_love", ""),
                "next_month_love": raw_result.get("next_month_love", "")
            },
            "titles": {
                "compatibility": "相性診断" if partner_birth else "恋愛傾向と出会い",
                "overall_love_fortune": "総合恋愛運",
                "year_love": "今年の恋愛運",
                "month_love": "今月の恋愛運",
                "next_month_love": "来月の恋愛運"
            },
            "themes": raw_result.get("topic_fortunes", []),
            "lucky_info": raw_result.get("lucky_info", []),
            "lucky_direction": raw_result.get("lucky_direction", ""),
            "yearly_love_fortunes": raw_result.get("yearly_love_fortunes", {})
        }

        filename = f"renai_{uuid.uuid4()}.pdf"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        create_pdf_unified(filepath, result_data, "renai", size=size.lower(), include_yearly=include_yearly)
        return send_file(filepath, as_attachment=True)
    return render_template("renai_form.html")



@app.route("/selfmob", methods=["GET"])
def selfmob_start():
    return render_template("pay.html")

@app.route("/selfmob/index", methods=["GET", "POST"])
def selfmob_index():
    mode = "shincom"
    size = "A4"
    is_json = request.is_json
    if request.method == "POST":
        try:
            data = request.get_json() if is_json else request.form
            image_data = data.get("image_data")
            birthdate = data.get("birthdate")
            full_year = data.get("full_year", False) if is_json else (data.get("full_year") == "yes")

            # 吉方位テキスト取得
            try:
                year, month, day = map(int, birthdate.split("-"))
                kyusei_text = get_kyusei_fortune(year, month, day)
            except Exception as e:
                print("❌ lucky_direction 取得エラー:", e)
                kyusei_text = ""

            eto = get_nicchu_eto(birthdate)
            palm_result, shichu_result, iching_result, lucky_info = generate_fortune_shincom(image_data, birthdate, kyusei_text)

            # 手相パート抽出
            palm_sections = [sec for sec in palm_result.split("### ") if sec.strip()]
            palm_texts = []
            summary_text = ""
            if palm_sections:
                *main_sections, summary_section = palm_sections
                for sec in main_sections:
                    if "\n" in sec:
                        _, body = sec.split("\n", 1)
                    else:
                        body = sec
                    body = body.strip()
                    if body:
                        palm_texts.append(body)
                if summary_section:
                    if "\n" in summary_section:
                        _, summary_body = summary_section.split("\n", 1)
                    else:
                        summary_body = summary_section
                    summary_text = summary_body.strip()

            # 四柱推命パート抽出
            shichu_parts = [part for part in shichu_result.split("■ ") if part.strip()]
            shichu_texts = {}
            for part in shichu_parts:
                if "\n" in part:
                    title, body = part.split("\n", 1)
                else:
                    title, body = part, ""
                shichu_texts[title] = body.strip()

            # ラッキー情報整形
            lucky_lines = []
            if isinstance(lucky_info, str):
                for line in lucky_info.replace("\r\n", "\n").split("\n"):
                    line = line.strip()
                    if line:
                        line = line.replace(":", "：", 1)
                        lucky_lines.append(f"◆ {line}")
            elif isinstance(lucky_info, dict):
                for k, v in lucky_info.items():
                    lucky_lines.append(f"◆ {k}：{v}")
            else:
                lucky_lines = list(lucky_info)

            # PDF出力用データ
            result_data = {
                "palm_titles": ["生命線", "運命線", "金運線", "特殊線1", "特殊線2"],
                "palm_texts": palm_texts,
                "titles": {
                    "palm_summary": "手相の総合アドバイス",
                    "personality": "性格診断",
                    "month_fortune": "今月の運勢",
                    "next_month_fortune": "来月の運勢"
                },
                "texts": {
                    "palm_summary": summary_text,
                    "personality": shichu_texts.get("性格", ""),
                    "month_fortune": shichu_texts.get("今月の運勢", ""),
                    "next_month_fortune": shichu_texts.get("来月の運勢", "")
                },
                "lucky_info": lucky_lines,
                "lucky_direction": kyusei_text,
                "birthdate": birthdate,
                "palm_result": "\n".join(palm_texts),
                "shichu_result": shichu_result,
                "iching_result": iching_result,
                "palm_image": image_data
            }

            if full_year:
                now = datetime.now()
                result_data["yearly_fortunes"] = generate_yearly_fortune(birthdate, now)

            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            create_pdf_unified(filepath, result_data, mode, size="a4", include_yearly=full_year)
            redirect_url = url_for("preview", filename=filename)
            return jsonify({"redirect_url": redirect_url}) if is_json else redirect(redirect_url)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}) if is_json else "処理中にエラーが発生しました"
    return render_template("index.html")



@app.route("/preview/<filename>")
def preview(filename):
    referer = request.referrer or ""
    if any(x in referer for x in ["/tenmob", "/selfmob", "/renai"]):
        return redirect(url_for("view_pdf", filename=filename))
    return render_template("fortune_pdf.html", filename=filename, referer=referer)


@app.route("/view/<filename>")
def view_pdf(filename):
    filepath = os.path.join("static", "uploads", filename)
    if not os.path.exists(filepath):
        return "ファイルが存在しません", 404
    return send_file(filepath, mimetype='application/pdf')


@app.route("/get_eto", methods=["POST"])
def get_eto():
    try:
        data = request.get_json()
        birthdate = data.get("birthdate", "").strip()

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", birthdate):
            return jsonify({"error": "日付の形式が正しくありません"}), 400

        datetime.strptime(birthdate, "%Y-%m-%d")  # 存在しない日付を除外
        eto = get_nicchu_eto(birthdate)
        honmeisei = get_honmeisei(*map(int, birthdate.split("-")))
        return jsonify({"eto": eto, "honmeisei": honmeisei})
    except Exception as e:
        return jsonify({"error": "サーバー内部エラー"}), 500


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        next_url_post = request.form.get("next_url", "tenmob")  # デフォルトは安全な方に

        # 安全なエンドポイント名のみ許可
        if next_url_post not in ["ten", "tenmob", "renai", "renaimob"]:
            next_url_post = "tenmob"

        if password == os.getenv("LOGIN_PASSWORD", "pass"):
            session["logged_in"] = True
            return redirect(url_for(next_url_post))

    # GET時: Referer から次の遷移先を決める
    referer = request.referrer or ""
    if "/tenmob" in referer:
        next_url = "tenmob"
    elif "/ten" in referer:
        next_url = "ten"
    elif "/renaimob" in referer:
        next_url = "renaimob"
    elif "/renai" in referer:
        next_url = "renai"
    else:
        next_url = "tenmob"  # フォールバック

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
