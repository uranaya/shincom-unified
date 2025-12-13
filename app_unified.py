import os
import base64
import uuid
import json
import random
import requests
import traceback
import io
import csv
from io import TextIOWrapper
from datetime import datetime
from urllib.parse import quote
from sqlalchemy import create_engine, text
import csv
from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify, make_response,render_template_string
from fortune_logic import generate_fortune
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta
from yearly_fortune_utils import generate_yearly_fortune
from fortune_logic import generate_fortune as generate_fortune_shincom, get_nicchu_eto
from kyusei_utils import get_honmeisei, get_kyusei_fortune
from pdf_generator_unified import create_pdf_unified
from fortune_logic import generate_renai_fortune
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# --- 星座・干支番号・動物占い（PDF用共通ロジック） ---

# 60干支の並び順に対応する番号マップ（1〜60）
ETO_ORDER_MAP = {
    "甲子": 1, "乙丑": 2, "丙寅": 3, "丁卯": 4, "戊辰": 5, "己巳": 6, "庚午": 7, "辛未": 8, "壬申": 9, "癸酉": 10,
    "甲戌": 11, "乙亥": 12, "丙子": 13, "丁丑": 14, "戊寅": 15, "己卯": 16, "庚辰": 17, "辛巳": 18, "壬午": 19, "癸未": 20,
    "甲申": 21, "乙酉": 22, "丙戌": 23, "丁亥": 24, "戊子": 25, "己丑": 26, "庚寅": 27, "辛卯": 28, "壬辰": 29, "癸巳": 30,
    "甲午": 31, "乙未": 32, "丙申": 33, "丁酉": 34, "戊戌": 35, "己亥": 36, "庚子": 37, "辛丑": 38, "壬寅": 39, "癸卯": 40,
    "甲辰": 41, "乙巳": 42, "丙午": 43, "丁未": 44, "戊申": 45, "己酉": 46, "庚戌": 47, "辛亥": 48, "壬子": 49, "癸丑": 50,
    "甲寅": 51, "乙卯": 52, "丙辰": 53, "丁巳": 54, "戊午": 55, "己未": 56, "庚申": 57, "辛酉": 58, "壬戌": 59, "癸亥": 60,
}

# 動物占い60分類（index: 干支番号-1）
ANIMAL60 = [
    "長距離ランナーのチータ", "社交家のたぬき", "落ち着きのない猿", "フットワークの軽い子守熊", "面倒見のいい黒ひょう",
    "愛情あふれる虎", "全力疾走するチータ", "磨き上げられたたぬき", "大きな志をもった猿", "母性豊かな子守熊",
    "正直なこじか", "人気者のゾウ", "ネアカの狼", "協調性のないひつじ", "どっしりとした猿", "コアラのなかの子守熊",
    "強い意志をもったこじか", "デリケートなゾウ", "放浪の狼", "物静かなひつじ", "落ち着きのあるペガサス",
    "強靭な翼をもつペガサス", "無邪気なひつじ", "クリエイティブな狼", "穏やかな狼", "粘り強いひつじ",
    "波乱に満ちたペガサス", "優雅なペガサス", "チャレンジ精神旺盛なひつじ", "順応性のある狼",
    "リーダーとなるゾウ", "しっかり者のこじか", "活動的な子守熊", "気分屋の猿", "頼られると嬉しいひつじ",
    "好感のもたれる狼", "まっしぐらに突き進むゾウ", "華やかなこじか", "夢とロマンの子守熊", "尽す猿",
    "大器晩成のたぬき", "足腰の強いチータ", "動きまわる虎", "情熱的な黒ひょう", "サービス精神旺盛な子守熊",
    "守りの猿", "人間味あふれるたぬき", "品格のあるチータ", "ゆったりとした悠然の虎", "落ち込みの激しい黒ひょう",
    "我が道を行くライオン", "統率力のあるライオン", "感情豊かな黒ひょう", "楽天的な虎", "パワフルな虎",
    "気どらない黒ひょう", "感情的なライオン", "傷つきやすいライオン", "束縛を嫌う黒ひょう", "慈悲深い虎",
]


def get_zodiac_sign(month: int, day: int) -> str:
    """西洋12星座（フロントの getZodiacSign と同じ境界）"""
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "牡羊座"
    if (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "牡牛座"
    if (month == 5 and day >= 21) or (month == 6 and day <= 21):
        return "双子座"
    if (month == 6 and day >= 22) or (month == 7 and day <= 22):
        return "蟹座"
    if (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "獅子座"
    if (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "乙女座"
    if (month == 9 and day >= 23) or (month == 10 and day <= 23):
        return "天秤座"
    if (month == 10 and day >= 24) or (month == 11 and day <= 22):
        return "蠍座"
    if (month == 11 and day >= 23) or (month == 12 and day <= 21):
        return "射手座"
    if (month == 12 and day >= 22) or (month == 1 and day <= 20):
        return "山羊座"
    if (month == 1 and day >= 21) or (month == 2 and day <= 18):
        return "水瓶座"
    return "魚座"



from aura_fortune_utils import generate_aura_fortune
from aura_image_utils import generate_aura_image
from pdf_generator_aura import create_aura_pdf
from prompt_utils import extract_prompts_from_result

from tarot_fortune_logic import generate_tarot_fortune
from pdf_generator_tarot import create_pdf_tarot

from collections import defaultdict
from flask import send_from_directory

import sqlite3
import threading
import psycopg2


# 料金設定（テスト中はここをいじるだけ）
PRICE_MAP = {
    "tarotmob": 550,
    "selfmob": 550,
    "selfmob_full": 1100,
    "renaiselfmob": 550,
    "renaiselfmob_full": 1100
}



# --- 環境変数とパス ---
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
USED_UUID_FILE = "used_orders.txt"
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", ".")

# Flask アプリ初期化
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret!123")


# Initialize locks for thread-safe operations
used_file_lock = threading.Lock()


# used_orders.txt 存在チェック
os.makedirs(os.path.dirname(USED_UUID_FILE) or ".", exist_ok=True)
if not os.path.exists(USED_UUID_FILE):
    open(USED_UUID_FILE, "w").close()

# webhook_sessions.txt 存在チェック
if not os.path.exists("webhook_sessions.txt"):
    open("webhook_sessions.txt", "w").close()

# --- データベース初期化 ---
if DATABASE_URL:
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # shop_logs テーブル（店舗別カウント）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shop_logs (
                date DATE,
                shop_id TEXT,
                service TEXT,
                count INT DEFAULT 0,
                PRIMARY KEY (date, shop_id, service)
            );
        """)

        # webhook_events テーブル（KOMOJU決済記録）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                uuid TEXT PRIMARY KEY,
                shop_id TEXT,
                service TEXT,
                date DATE
            );
        """)

        # ✅ sales テーブル（レジ用売上記録）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                date DATE DEFAULT CURRENT_DATE,
                staff_name TEXT,
                method TEXT,
                amount INTEGER
            );
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("✅ データベース初期化完了（shop_logs, webhook_events, sales）")
    except Exception as e:
        print("❌ DB初期化エラー:", e)
else:
    print("⚠️ DATABASE_URL が未設定。ローカル実行ではDB非使用。")



# Background thread task to generate PDF and handle post-processing
def background_generate_pdf(filepath, result_data, pdf_mode, size="a4", include_yearly=False, uuid_str=None, shop_id=None):
    try:
        create_pdf_unified(filepath, result_data, pdf_mode, size=size, include_yearly=include_yearly)
    except Exception as e:
        print(f"❌ PDF generation error (mode={pdf_mode}, uuid={uuid_str}):", e)
        traceback.print_exc()
        return
    # Mark UUID as used if applicable
    if uuid_str:
        try:
            with used_file_lock:
                lines_content = []
                if os.path.exists(USED_UUID_FILE):
                    with open(USED_UUID_FILE, "r") as f:
                        lines_content = [line.strip() for line in f if line.strip()]
                updated_lines = []
                for line in lines_content:
                    parts = line.split(",")
                    if len(parts) >= 3:
                        uid, flag, mode = parts[0], parts[1], parts[2]
                        if uid == uuid_str:
                            updated_lines.append(f"{uid},used,{mode}")
                        else:
                            updated_lines.append(line)
                with open(USED_UUID_FILE, "w") as f:
                    for line in updated_lines:
                        f.write(line + "\n")
        except Exception as e:
            print(f"❌ Error updating {USED_UUID_FILE} for {uuid_str}:", e)
            traceback.print_exc()
    # Write to access_log.txt if applicable
    if shop_id and uuid_str:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("access_log.txt", "a", encoding="utf-8") as f:
                f.write(f"{now_str},{shop_id},{uuid_str}\n")
        except Exception as e:
            print(f"❌ Error writing access_log for {uuid_str}:", e)
            traceback.print_exc()



@app.route("/thanks")
def thanks():
    uuid_str = request.cookies.get("uuid") or request.args.get("uuid")
    if not uuid_str:
        return render_template("thanks.html", uuid_str="")

    is_paid = False
    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM webhook_events WHERE uuid = %s LIMIT 1;", (uuid_str,))
            result = cur.fetchone()
            if result:
                is_paid = True
            cur.close()
            conn.close()
    except Exception as e:
        print("❌ DBチェック失敗 (/thanks):", e)

    if not is_paid:
        return "<h1>決済が確認できません</h1><p>決済が完了していない、またはセッションが無効です。もう一度やり直してください。</p>", 403

    return render_template("thanks.html", uuid_str=uuid_str)


@app.route("/verify_payment/<uuid_str>")
def verify_payment(uuid_str):
    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM webhook_events WHERE uuid = %s", (uuid_str,))
            found = cur.fetchone()
            cur.close()
            conn.close()
            if found:
                return jsonify({"status": "valid"})
        return jsonify({"status": "invalid"})
    except Exception as e:
        print("❌ verify_paymentエラー:", e)
        return jsonify({"status": "error"})


def create_payment_session(amount, uuid_str, return_url_thanks, shop_id, mode="selfmob"):
    secret = os.getenv("KOMOJU_SECRET_KEY")
    if not secret:
        raise RuntimeError("KOMOJU_SECRET_KEY is not set")

    if mode == "renaiselfmob":
        redirect_path = "renaiselfmob_full" if amount >= 1000 else "renaiselfmob"
    elif mode == "tarotmob":
        redirect_path = "tarotmob"
    else:
        redirect_path = "selfmob_full" if amount >= 1000 else "selfmob"

    customer_redirect_url = f"{BASE_URL}/{redirect_path}/{uuid_str}"
    cancel_url = f"{BASE_URL}/pay.html"

    payload = {
        "amount": amount,
        "currency": "JPY",
        "return_url": cancel_url,
        "customer_redirect_url": customer_redirect_url,
        "payment_data": {"external_order_num": uuid_str},
        "metadata": {"external_order_num": uuid_str, "shop_id": shop_id},
        "payment_methods": [{"type": "credit_card"}, {"type": "paypay"}],
        "description": "シン・コンピューター占い"
    }

    response = requests.post(
        "https://komoju.com/api/v1/sessions",
        auth=(secret, ""),
        json=payload
    )
    response.raise_for_status()
    session = response.json()
    return session.get("session_url"), session.get("id")




def _generate_session_for_shop(shop_id, full_year=False, mode="selfmob"):
    uuid_str = str(uuid.uuid4())
    return_url_thanks = f"{BASE_URL}/thanks?uuid={uuid_str}"

    mode_key = mode + ("_full" if full_year and mode != "tarotmob" else "")
    amount = PRICE_MAP.get(mode_key, 500)  # 不明な場合はデフォルト500円

    session_url, session_id = create_payment_session(
        amount=amount,
        uuid_str=uuid_str,
        return_url_thanks=return_url_thanks,
        shop_id=shop_id,
        mode=mode
    )

    try:
        with open(USED_UUID_FILE, "a") as f:
            f.write(f"{uuid_str},,{mode_key},{shop_id},{session_id}\n")
    except Exception as e:
        print("⚠️ UUID書き込み失敗:", e)

    resp = make_response(redirect(session_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp




def get_uuid_and_mode_by_session_id(session_id):
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 5:
                    uuid_str, _, mode_key, _, sid = parts
                    if sid == session_id:
                        return uuid_str, mode_key
    except Exception as e:
        print("❌ セッションIDの検索エラー:", e)
    return None, None


@app.route("/pay.html")
def pay_redirect():
    session_id = request.args.get("session_id", "")
    if not session_id:
        return "セッションIDがありません", 400

    uuid_str, mode_key = get_uuid_and_mode_by_session_id(session_id)
    if not uuid_str or not mode_key:
        print("❌ セッションIDが未登録 or モードなし:", session_id)
        return render_template("thanks.html", uuid_str="")

    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM webhook_events WHERE uuid = %s", (uuid_str,))
            result = cur.fetchone()
            cur.close()
            conn.close()
            if not result:
                print("🔒 決済未確認UUID:", uuid_str)
                return render_template("thanks.html", uuid_str="")
    except Exception as e:
        print("❌ DB確認エラー:", e)
        return render_template("thanks.html", uuid_str="")

    if "tarotmob" in mode_key:
        return redirect(f"/tarotmob/{uuid_str}")
    elif "renaiselfmob" in mode_key:
        return redirect(f"/renaiselfmob/{uuid_str}")
    elif "selfmob" in mode_key:
        return redirect(f"/selfmob/{uuid_str}")
    else:
        return "不明なモードです", 400



def record_shop_log_if_needed(uuid_str, mode):
    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = f.readlines()
        for line in lines:
            parts = line.strip().split(",")
            if len(parts) >= 4 and parts[0] == uuid_str:
                shop_id = parts[3]
                break
        else:
            shop_id = "default"

        today = datetime.now().strftime("%Y-%m-%d")

        if DATABASE_URL:
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO shop_logs (date, shop_id, service, count)
                    VALUES (%s, %s, %s, 1)
                    ON CONFLICT (date, shop_id, service)
                    DO UPDATE SET count = shop_logs.count + 1;
                """, (today, shop_id, mode))
                conn.commit()
                cur.close()
                conn.close()
                print(f"📝 DBカウント更新: {today} / {shop_id} / {mode}")
            except Exception as e:
                print("❌ DB記録失敗 (record_shop_log_if_needed):", e)

        with open("shop_logs.csv", "a") as log:
            log.write(f"{shop_id},{mode},{today}\n")
            print(f"🧮 CSVカウント記録: {shop_id},{mode},{today}")

    except Exception as e:
        print("⚠️ カウント記録エラー:", e)






# --- 決済リンク生成ルート ---
@app.route("/selfmob-<shop_id>")
def selfmob_shop_entry(shop_id):
    session["shop_id"] = shop_id
    return render_template("pay.html", shop_id=shop_id)



@app.route("/selfmob/<uuid_str>")
def selfmob_entry_uuid(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "このUUIDは未決済です", 403
    record_shop_log_if_needed(uuid_str, "selfmob")
    return render_template("index_selfmob.html", full_year=False)



@app.route("/renaiselfmob/<uuid_str>")
def renaiselfmob_entry_uuid(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "このUUIDは未決済です", 403
    record_shop_log_if_needed(uuid_str, "renaiselfmob")
    return render_template("index_renaiselfmob.html", full_year=False)



@app.route("/renaiselfmob_full/<uuid_str>")
def renaiselfmob_full_entry_uuid(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "このUUIDは未決済です", 403
    record_shop_log_if_needed(uuid_str, "renaiselfmob_full")
    return render_template("index_renaiselfmob.html", full_year=True)









@app.route("/generate_link/<shop_id>")
def generate_link(shop_id):
    return _generate_session_for_shop(shop_id, full_year=False, mode="selfmob")

@app.route("/generate_link_full/<shop_id>")
def generate_link_full(shop_id):
    return _generate_session_for_shop(shop_id, full_year=True,  mode="selfmob")

@app.route("/generate_link_renai/<shop_id>")
def generate_link_renai(shop_id):
    return _generate_session_for_shop(shop_id, full_year=False, mode="renaiselfmob")

@app.route("/generate_link_renai_full/<shop_id>")
def generate_link_renai_full(shop_id):
    return _generate_session_for_shop(shop_id, full_year=True,  mode="renaiselfmob")




# 決済済みか判定

def is_paid_uuid(uuid_str):
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 1 and parts[0] == uuid_str:
                    return True
    except Exception as e:
        print("⚠️ used_orders.txt 読み込みエラー(is_paid_uuid):", e)
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM webhook_events WHERE uuid=%s AND service LIKE %s", (uuid_str, '%thanks'))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        print("❌ 決済確認エラー:", e)
        return False






# --- Komoju Webhook ルート ---
@app.route("/webhook/selfmob", methods=["POST"])
def webhook_selfmob():
    data = request.get_json()
    print("📩 Webhook受信: selfmob", data)

    session_id = data.get("data", {}).get("session")
    metadata = data.get("data", {}).get("metadata", {})
    uuid_from_metadata = metadata.get("external_order_num")

    matched_uuid = None
    shop_id = metadata.get("shop_id", "default")

    if session_id:
        try:
            with open("webhook_sessions.txt", "a") as f:
                f.write(f"{session_id}\n")
        except Exception as e:
            print("⚠️ Webhookセッション記録失敗:", e)

    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            parts = line.strip().split(",")
            if len(parts) >= 4 and (parts[0] == uuid_from_metadata or parts[1] == session_id):
                matched_uuid = parts[0]
                shop_id = parts[3]
                if not parts[1] and session_id:
                    parts[1] = session_id
                    lines[i] = ",".join(parts) + "\n"
                break
        if matched_uuid:
            with open(USED_UUID_FILE, "w") as f:
                f.writelines(lines)
    except Exception as e:
        print("⚠️ UUID逆照合失敗:", e)

    if matched_uuid:
        try:
            if DATABASE_URL:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                today = datetime.now().strftime("%Y-%m-%d")
                cur.execute("""
                    INSERT INTO webhook_events (uuid, shop_id, service, date)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (matched_uuid, shop_id, "selfmob_thanks", today))
                conn.commit()
                cur.close()
                conn.close()
                print(f"✅ Webhook DB記録済: {matched_uuid} / {shop_id}")
        except Exception as e:
            print("❌ Webhook DBエラー:", e)

    return "", 200




@app.route("/webhook/renaiselfmob", methods=["POST"])
def webhook_renaiselfmob():
    data = request.get_json()
    print("📩 Webhook受信: renaiselfmob", data)
    session_id = data.get("data", {}).get("session")
    metadata = data.get("data", {}).get("metadata", {})
    uuid_from_metadata = metadata.get("external_order_num")

    matched_uuid = None
    shop_id = metadata.get("shop_id", "default")

    if session_id:
        try:
            with open("webhook_sessions.txt", "a") as f:
                f.write(f"{session_id}\n")
        except Exception as e:
            print("⚠️ Webhookセッション記録失敗:", e)

    try:
        with open(USED_UUID_FILE, "r") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            parts = line.strip().split(",")
            if len(parts) >= 4 and (parts[0] == uuid_from_metadata or parts[1] == session_id):
                matched_uuid = parts[0]
                shop_id = parts[3]
                if not parts[1] and session_id:
                    parts[1] = session_id
                    lines[i] = ",".join(parts) + "\n"
                break
        if matched_uuid:
            with open(USED_UUID_FILE, "w") as f:
                f.writelines(lines)
    except Exception as e:
        print("⚠️ UUID逆照合失敗:", e)

    if matched_uuid:
        try:
            if DATABASE_URL:
                conn = psycopg2.connect(DATABASE_URL)
                cur = conn.cursor()
                today = datetime.now().strftime("%Y-%m-%d")
                cur.execute("""
                    INSERT INTO webhook_events (uuid, shop_id, service, date)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """, (matched_uuid, shop_id, "renaiselfmob_thanks", today))
                conn.commit()
                cur.close()
                conn.close()
                print(f"✅ Webhook DB記録済: {matched_uuid} / {shop_id}")
        except Exception as e:
            print("❌ Webhook DBエラー:", e)

    return "", 200



# --- self系実占い部分  ---



@app.route("/selfmob/<uuid_str>", methods=["GET", "POST"])
def selfmob_uuid(uuid_str):
    full_year = None
    try:
        with open(USED_UUID_FILE, "r") as f:
            for line in f:
                parts = line.strip().split(",")
                if not parts or len(parts) < 3:
                    continue
                uid, flag, mode = parts[0], parts[1], parts[2]
                if uid == uuid_str and mode.startswith("selfmob"):
                    full_year = mode.endswith("_full")
                    break
        if full_year is None:
            return "無効なリンクです（UUID不一致）", 400
    except FileNotFoundError:
        return "使用履歴が確認できません", 400

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

            result_data = {
                "palm_titles": palm_titles,
                "palm_texts": palm_texts,
                "titles": {
                    "palm_summary": "手相の総合アドバイス",
                    "personality": "性格診断",
                    "year_fortune": f"{today.year}年の運勢",
                    "month_fortune": f"{target1.year}年{target1.month}月の運勢",
                    "next_month_fortune": f"{target2.year}年{target2.month}月の運勢",
                },
                "texts": {
                    "palm_summary": summary_text,
                    "personality": shichu_result.get("personality", ""),
                    "year_fortune": shichu_result.get("year_fortune", ""),
                    "month_fortune": shichu_result.get("month_fortune", ""),
                    "next_month_fortune": shichu_result.get("next_month_fortune", ""),
                },
                "lucky_info": lucky_lines,
                "lucky_direction": kyusei_text,
                "birthdate": birthdate,
                "palm_result": palm_result,
                "shichu_result": shichu_result,
                "iching_result": iching_result,
                "palm_image": image_data,
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
                args=(filepath, result_data, "shincom", "a4", full_year, uuid_str, shop_id),
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
            lines = [line.strip() for line in f if line.strip()]
        for line in lines:
            parts = line.strip().split(",", 3)
            if len(parts) < 4:
                continue
            uid, flag, mode, shop_id = parts
            if uid == uuid_str:
                full_year = mode.endswith("_full")
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
    """占い結果PDFのプレビュー画面表示"""
    user_agent = request.headers.get("User-Agent", "").lower()

    # iPhoneまたはAndroidの簡易判定（必要に応じて拡張可）
    if "iphone" in user_agent or "android" in user_agent:
        return redirect(url_for("view_pdf", filename=filename))

    referer = request.referrer or ""
    return render_template("fortune_pdf.html", filename=filename, referer=referer)



import time
@app.route('/view/<filename>')
def view_pdf(filename):
    full_path = os.path.join(UPLOAD_FOLDER, filename)
    wait_time = 0
    while not os.path.exists(full_path) and wait_time < 5:
        time.sleep(0.5)
        wait_time += 0.5
    if not os.path.exists(full_path):
        return "PDFが見つかりませんでした", 404
    return send_file(full_path, mimetype="application/pdf")



@app.route("/view_shop_log")
def view_shop_log():
    """shop_logsテーブルの内容を表示（ソート付き）"""
    sort_column = request.args.get("sort", "date")
    sort_order = request.args.get("order", "desc")

    allowed = {"date", "shop_id", "service", "count"}
    if sort_column not in allowed:
        sort_column = "date"

    logs = []
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            query = f"SELECT date, shop_id, service, count FROM shop_logs ORDER BY {sort_column} {sort_order};"
            cur.execute(query)
            logs = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            return f"エラー: {e}"
    return render_template("shop_log.html", logs=logs, sort_column=sort_column, sort_order=sort_order)


@app.route("/view_shop_log_monthly")
def view_shop_log_monthly():
    """月ごと + shop_id + service ごとの集計"""
    sort_column = request.args.get("sort", "month")
    sort_order = request.args.get("order", "desc")
    allowed = {"month", "shop_id", "service", "total"}
    if sort_column not in allowed:
        sort_column = "month"

    logs = []
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            query = f"""
                SELECT TO_CHAR(date, 'YYYY-MM') AS month, shop_id, service, SUM(count) AS total
                FROM shop_logs
                GROUP BY TO_CHAR(date, 'YYYY-MM'), shop_id, service
                ORDER BY {sort_column} {sort_order};
            """
            cur.execute(query)
            logs = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            return f"エラー: {e}"

    return render_template("shop_log_monthly.html", logs=logs, sort_column=sort_column, sort_order=sort_order)



@app.route("/reset_shop_log", methods=["POST"])
def reset_shop_log():
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("DELETE FROM shop_logs;")
            conn.commit()
            cur.close()
            conn.close()
            print("✅ shop_logs 全リセット完了")
        except Exception as e:
            return f"削除エラー: {e}"
    return redirect(url_for("view_shop_log"))




# ログイン制御（シンプルな仮ユーザー認証）
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password")
        if pw == os.getenv("ADMIN_PASSWORD", "pass"):
            session["logged_in"] = True
            return redirect("/home")
        return render_template("login.html", error="パスワードが間違っています")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/ten", methods=["GET", "POST"], endpoint="ten")
@app.route("/tenmob", methods=["GET", "POST"], endpoint="tenmob")
def ten_shincom():
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
            # 生年月日から星座・干支番号・動物占い・本命星を算出（PDF用）
            zodiac = get_zodiac_sign(month, day)
            eto_number = ETO_ORDER_MAP.get(eto)
            animal = ""
            if eto_number is not None and 1 <= eto_number <= len(ANIMAL60):
                animal = ANIMAL60[eto_number - 1]
            try:
                honmeisei = get_honmeisei(year, month, day)
            except Exception as e:
                print("❌ 本命星取得エラー:", e)
                honmeisei = ""
            palm_titles, palm_texts, shichu_result, iching_result, lucky_lines = generate_fortune(image_data, birthdate, kyusei_text)
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
                "zodiac": zodiac,
                "eto": eto,
                "eto_number": eto_number,
                "animal": animal,
                "honmeisei": honmeisei,
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
            threading.Thread(target=background_generate_pdf, args=(filepath, result_data, mode, size.lower(), full_year)).start()
            redirect_url = url_for("preview", filename=filename)
            if is_json:
                return jsonify({"redirect_url": redirect_url})
            else:
                return redirect(redirect_url)
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}) if request.is_json else "処理中にエラーが発生しました"
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

        now = datetime.now()
        target1 = now.replace(day=15)
        if now.day >= 20:
            target1 += relativedelta(months=1)
        target2 = target1 + relativedelta(months=1)

        year_label = f"{now.year}年の恋愛運"
        month_label = f"{target1.year}年{target1.month}月の恋愛運"
        next_month_label = f"{target2.year}年{target2.month}月の恋愛運"

        # 🎯 正しく texts/titles を含んだ構造で取得
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

        # ✅ PDFを直接ダウンロードではなくプレビュー表示へ変更
        return redirect(url_for("preview", filename=filename))

    return render_template("renai_form.html")



@app.route("/selfmob", methods=["GET"])
def selfmob_start():
    return render_template("pay.html", shop_id="default")



@app.route("/get_eto", methods=["POST"])
def get_eto():
    try:
        birthdate = request.json.get("birthdate")
    except:
        return jsonify({"error": "無効な生年月日です"}), 400
    if not birthdate or not isinstance(birthdate, str):
        return jsonify({"error": "無効な生年月日です"}), 400
    try:
        y, m, d = map(int, birthdate.split("-"))
    except:
        return jsonify({"error": "無効な生年月日です"}), 400
    eto = get_nicchu_eto(birthdate)
    honmeisei = get_honmeisei(y, m, d)
    return jsonify({"eto": eto, "honmeisei": honmeisei})

@app.route("/")
@app.route("/home")
def home():
    return render_template("home-unified.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/tokutei")
def tokutei():
    return render_template("tokutei.html")





# JSONデータ読み込み（プレーンおみくじ）
with open("omikuji_plain.json", encoding="utf-8") as f:
    OMikuji_DATA = json.load(f)

@app.route("/omikuji", methods=["GET"])
def omikuji_top():
    return render_template("omikuji_index.html")

@app.route("/omikuji/result", methods=["POST"])
def result():
    try:
        with open("omikuji_plain.json", encoding="utf-8") as f:
            OMikuji_DATA = json.load(f)

        omikuji = random.choice(OMikuji_DATA)

        return render_template("omikuji.html", omikuji=omikuji)

    except Exception as e:
        print("🔴 Error in /omikuji/result:", e)
        return "エラーが発生しました。"




@app.route("/weekly")
def weekly():
    # スプレッドシートのCSV出力URL（公開済みである必要あり）
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTtv13kPxmrU7u6ug1XkRiwgEM5XZQAzMHVp679eUKGNCpoijBEnoD-KLGuknvF-AZbi8g0kEdOuXjt/pub?output=csv"
    response = requests.get(url)
    response.encoding = "utf-8"

    # CSVをパース
    rows = list(csv.reader(response.text.splitlines()))
    headers = rows[0]
    data = rows[1:]  # ヘッダーを除いたデータ部分

    return render_template("weekly.html", headers=headers, data=data)




# --- /aura へのアクセス時にUUIDを生成してリダイレクト ---
@app.route("/aura", methods=["GET"])
def aura_redirect():
    new_uuid = str(uuid.uuid4())
    return redirect(f"/aura/{new_uuid}")

# --- AURAルート：フォーム表示 ---
@app.route("/aura/<uuid_str>", methods=["GET"])
def aura_entry(uuid_str):
    return render_template("index_aura.html", uuid=uuid_str)

# --- AURAルート：POST処理 ---
@app.route("/aura/<uuid_str>", methods=["POST"])
def aura_submit(uuid_str):
    image_data = request.form.get("image_data", "")
    if not image_data:
        return "画像が送信されていません", 400

    # 🧠 1. 占い結果生成（テキスト）
    try:
        result = generate_aura_fortune(image_data)
        result_text = result.get("text", "")
    except Exception as e:
        return f"OpenAI診断エラー: {e}", 500

    # 🔤 2. プロンプト生成（result_textから抽出）
    try:
        from prompt_utils import extract_prompts_from_result
        aura_color_prompt, past_prompt, spirit_prompt = extract_prompts_from_result(result_text)
    except Exception as e:
        return f"プロンプト抽出エラー: {e}", 500

    # 🖼 3. 合成画像生成（オーラ色＋前世＋守護霊）
    try:
        from aura_image_utils import generate_aura_image
        merged_image_base64 = generate_aura_image(
            user_image_base64=image_data,
            past_prompt=past_prompt,
            spirit_prompt=spirit_prompt,
            aura_prompt=aura_color_prompt
        )
    except Exception as e:
        return f"画像合成エラー: {e}", 500

    # 🖨 4. PDF出力
    filename = f"aura_{uuid_str}.pdf"
    output_path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        from pdf_generator_aura import create_aura_pdf
        create_aura_pdf(output_path, merged_image_base64, result_text)
    except Exception as e:
        return f"PDF生成エラー: {e}", 500

    # 📄 5. 表示またはダウンロード
    return send_file(output_path, mimetype="application/pdf")




# ✅ PDF保存フォルダ設定（Render対応）


UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "static/pdf")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --- タロット：ランディングページ（紹介・決済誘導） ---
@app.route("/tarotmob", defaults={"shop_id": "default"})
@app.route("/tarotmob-<shop_id>")
def tarotmob_landing(shop_id):
    return render_template("tarotmob_landing.html", shop_id=shop_id)


# --- タロット：決済セッション生成 ---
@app.route("/generate_link_tarot/<shop_id>")
def generate_link_tarot(shop_id):
    return _generate_session_for_shop(shop_id, full_year=False, mode="tarotmob")


# --- タロット：決済後にリダイレクトされるUUIDページ（フォーム表示／診断） ---
@app.route("/tarotmob/<uuid_str>", methods=["GET", "POST"])
def tarotmob_entry(uuid_str):
    if not is_paid_uuid(uuid_str):
        return "このUUIDは未決済です", 403

    if request.method == "GET":
        return render_template("index_tarotmob.html")

    # POST: 質問取得
    question = request.form.get("question", "").strip()
    if not question:
        return "質問文が空です", 400

    try:
        fortune = generate_tarot_fortune(question)
        if "error" in fortune:
            return fortune["error"], 500
    except Exception as e:
        return f"OpenAI診断エラー: {e}", 500

    try:
        filename = f"{uuid_str}.pdf"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        create_pdf_tarot(question, fortune, save_path)

        record_shop_log_if_needed(uuid_str, "tarotmob")
        return redirect(url_for("static", filename=f"pdf/{filename}"))
    except Exception as e:
        return f"PDF生成エラー: {e}", 500


# --- タロット：Webhook受信（決済成功） ---
@app.route("/webhook/tarotmob", methods=["POST"])
def webhook_tarotmob():
    data = request.get_json()
    uuid_str = data.get("external_order_num", "")
    if not uuid_str:
        return "NG: UUIDなし", 400
    with open(USED_UUID_FILE, "a") as f:
        f.write(f"{uuid_str},1,tarotmob\n")
    return "OK", 200




# 占い師・鑑定方法の選択肢（input.htmlと同じ構成に統一）
STAFF_LIST = [
    "HIROMI", "美帆", "あい", "礼", "あお",
    "月のかけら", "金子美月", "水木杏香", "幽香", "優芳",
    "蛍石", "うらなや","ふく","COCORAKU"
]

METHOD_LIST = ["対面", "コンピューター", "現金外（クレカQR)"]

def normalize_method(method: str) -> str:
    """DBに入っている '現金外（クレカQR）' などをPDF集計用に正規化"""
    if method == "対面":
        return "対面"
    if method == "コンピューター":
        return "コンピューター"
    if "現金外" in method:
        return "現金外"
    return method or ""


@app.route("/regi", methods=["GET", "POST"])
def regi_input_form():
    if request.method == "POST":
        staff = request.form.get("staff")
        method = request.form.get("method")
        amount = request.form.get("amount")
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO sales (staff_name, method, amount) VALUES (%s, %s, %s);",
                (staff, method, amount)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            return f"❌ DBエラー: {e}", 500
        return redirect(url_for('regi_input_form', success=1))

    success = request.args.get("success") == "1"
    return render_template("input.html", success=success, staff_list=STAFF_LIST, method_list=METHOD_LIST)




@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login_sales():
    if request.method == 'POST':
        if request.form['password'] == 'admin123':  # パスワード変更可
            session['admin'] = True
            return redirect(url_for('admin_dashboard_sales'))
    return render_template('login_regi.html')


@app.route('/admin')
def admin_dashboard_sales():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # ✅ 列名を取得して値にマッピング
        cur.execute("""
            SELECT date, staff_name, method, amount
            FROM sales
            WHERE date = CURRENT_DATE
            ORDER BY date DESC;
        """)
        rows = cur.fetchall()
        sales = [
            {"date": r[0].strftime('%Y-%m-%d'), "staff_name": r[1], "method": r[2], "amount": r[3]}
            for r in rows
        ]
        total_today = sum(r["amount"] for r in sales)

        cur.close()
        conn.close()

    except Exception as e:
        return f"❌ DB取得エラー: {e}", 500

    return render_template("admin.html", sales=sales, total=total_today)





@app.route('/admin/monthly')
def monthly_summary_sales():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))
    monthly_data = defaultdict(lambda: defaultdict(int))
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT date, staff_name, method, amount FROM sales;")
        all_sales = cur.fetchall()
        for date_obj, staff_name, method, amount in all_sales:
            key = date_obj.strftime('%Y-%m')
            monthly_data[key][(staff_name, method)] += amount
        cur.close()
        conn.close()
    except Exception as e:
        return f"❌ 集計エラー: {e}", 500

    return render_template("monthly.html", data=monthly_data)




@app.route('/admin/export', methods=['POST'])
def export_sales_csv():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['日付', '店員', '方法', '金額'])  # ヘッダー
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT date, staff_name, method, amount FROM sales ORDER BY date;")
        for row in cur.fetchall():
            writer.writerow([row[0].strftime('%Y-%m-%d'), row[1], row[2], row[3]])
        cur.close()
        conn.close()
    except Exception as e:
        return f"❌ エクスポートエラー: {e}", 500
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=sales_backup.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return response




@app.route('/admin/daily', methods=['GET'])
def view_sales_by_day():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))

    date_str = request.args.get('date')
    if not date_str:  # None または "" の場合
        date_str = datetime.today().strftime('%Y-%m-%d')

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, date, staff_name, method, amount
            FROM sales
            WHERE date = %s
            ORDER BY id;
        """, (date_str,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        sales = [
            {"id": r[0], "date": r[1], "staff_name": r[2], "method": r[3], "amount": r[4]}
            for r in rows
        ]
        total = sum(r["amount"] for r in sales)
    except Exception as e:
        return f"❌ DBエラー: {e}", 500

    return render_template("admin_daily.html", sales=sales, date=date_str, total=total)






@app.route('/admin/edit/<int:sales_id>', methods=['GET', 'POST'])
def edit_sale(sales_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))

    if request.method == 'POST':
        staff = request.form.get('staff')
        method = request.form.get('method')
        amount = request.form.get('amount')
        date = request.form.get('date')

        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("""
                UPDATE sales
                SET staff_name = %s, method = %s, amount = %s
                WHERE id = %s;
            """, (staff, method, amount, sales_id))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            return f"❌ 修正エラー: {e}", 500

        return redirect(url_for('view_sales_by_day', date=date))

    # GET: 既存データ読み込み
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT id, date, staff_name, method, amount FROM sales WHERE id = %s;", (sales_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return "該当データが見つかりません", 404

        sale = {
            "id": row[0],
            "date": row[1].strftime('%Y-%m-%d'),
            "staff_name": row[2],
            "method": row[3],
            "amount": row[4]
        }

    except Exception as e:
        return f"❌ 読み込みエラー: {e}", 500

    return render_template(
        "edit_sale.html",
        sale=sale,
        staff_list=STAFF_LIST,
        method_list=METHOD_LIST
    )





@app.route('/admin/invoice', methods=['GET'])
def admin_invoice():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))

    month = request.args.get('month', datetime.today().strftime('%Y-%m'))
    month_start = month + "-01"
    month_end = (datetime.strptime(month_start, "%Y-%m-%d") + relativedelta(months=1)).strftime('%Y-%m-%d')

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 占い師ごと・方法ごとの売上合計
        cur.execute("""
            SELECT staff_name, method, SUM(amount)
            FROM sales
            WHERE date >= %s AND date < %s
            GROUP BY staff_name, method
            ORDER BY staff_name, method;
        """, (month_start, month_end))
        rows = cur.fetchall()

        details = {}
        staff_list = set()

        for staff, method, total in rows:
            if staff not in details:
                details[staff] = {
                    "methods": {},
                    "total": 0,          # 対面＋コンピューターの合計
                    "cashless_total": 0, # 現金外のみ
                    "visit_days": 0,
                    "avg_sales": 0
                }
            details[staff]["methods"][method] = total
            staff_list.add(staff)

            if method == "対面" or method == "コンピューター":
                details[staff]["total"] += total
            elif "現金外" in method:
                details[staff]["cashless_total"] += total

        # 出店日数と1日平均売上（現金外は除外）
        for staff in staff_list:
            cur.execute("""
                SELECT COUNT(DISTINCT date)
                FROM sales
                WHERE date >= %s AND date < %s AND staff_name = %s;
            """, (month_start, month_end, staff))
            visit_days = cur.fetchone()[0]
            details[staff]["visit_days"] = visit_days
            details[staff]["avg_sales"] = (
                int(details[staff]["total"] / visit_days) if visit_days > 0 else 0
            )

        # 全体集計（現金外除外）
        total_taiken = sum(details[s]["methods"].get("対面", 0) for s in details)
        total_pc = sum(details[s]["methods"].get("コンピューター", 0) for s in details)
        total_cashless = sum(details[s]["cashless_total"] for s in details)

        store_fee = total_taiken * 0.30 + total_pc * 0.50
        store_fee_tax = int(store_fee * 1.10)
        final_invoice = store_fee_tax - total_cashless

        cur.close()
        conn.close()

    except Exception as e:
        return f"❌ 集計エラー: {e}", 500

    return render_template(
        "invoice.html",
        month=month,
        details=details,
        staff_list=sorted(staff_list),
        total_taiken=total_taiken,
        total_pc=total_pc,
        total_cashless=total_cashless,
        store_fee=store_fee,
        store_fee_tax=store_fee_tax,
        final_invoice=final_invoice
    )





@app.route('/admin/invoice_staff')
def admin_invoice_staff():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))

    month = request.args.get('month', datetime.today().strftime('%Y-%m'))
    staff = request.args.get('staff')
    if not staff:
        return "占い師を指定してください", 400

    month_start = month + "-01"
    month_end = (datetime.strptime(month_start, "%Y-%m-%d") + relativedelta(months=1)).strftime('%Y-%m-%d')

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT method, SUM(amount)
            FROM sales
            WHERE date >= %s AND date < %s AND staff_name = %s
            GROUP BY method;
        """, (month_start, month_end, staff))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        total_taiken = 0
        total_pc = 0
        total_cashless = 0

        # ①の normalize_method を使用（関数内で再定義しません）
        for method, total in rows:
            cat = normalize_method(method)
            if cat == "対面":
                total_taiken += total
            elif cat == "コンピューター":
                total_pc += total
            elif cat == "現金外":
                total_cashless += total
            # 想定外カテゴリは現状ロジックでは集計対象外

        # 出店料計算（既存ロジックのまま）
        store_fee = total_taiken * 0.30 + total_pc * 0.50
        store_fee_tax = int(store_fee * 1.10)  # 消費税10%
        final_invoice = store_fee_tax - total_cashless  # 正確な請求額

    except Exception as e:
        return f"❌ 集計エラー: {e}", 500

    return render_template(
        "invoice_staff.html",
        month=month,
        staff=staff,
        total_taiken=total_taiken,
        total_pc=total_pc,
        total_cashless=total_cashless,
        store_fee=store_fee,
        store_fee_tax=store_fee_tax,
        final_invoice=final_invoice
    )





@app.route('/admin/import_csv', methods=['GET', 'POST'])
def import_sales_csv():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))

    if request.method == 'POST':
        if 'csv_file' not in request.files:
            return "❌ CSVファイルが選択されていません", 400
        file = request.files['csv_file']
        if file.filename == '':
            return "❌ ファイル名が空です", 400

        try:
            # Shift_JISで読み込み
            csv_reader = csv.DictReader(TextIOWrapper(file, encoding='shift_jis'))
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            inserted = 0
            skipped = 0
            for row in csv_reader:
                date_val = row['日付']
                staff_val = row['店員']
                method_val = row['方法']
                amount_val = int(row['金額'])

                # 重複チェック
                cur.execute("""
                    SELECT COUNT(*) FROM sales
                    WHERE date = %s AND staff_name = %s AND method = %s AND amount = %s;
                """, (date_val, staff_val, method_val, amount_val))
                exists = cur.fetchone()[0]

                if exists == 0:
                    # 新規データを挿入
                    cur.execute("""
                        INSERT INTO sales (date, staff_name, method, amount)
                        VALUES (%s, %s, %s, %s);
                    """, (date_val, staff_val, method_val, amount_val))
                    inserted += 1
                else:
                    skipped += 1

            conn.commit()
            cur.close()
            conn.close()

            return f"✅ インポート完了: {inserted} 件追加, {skipped} 件スキップしました"

        except Exception as e:
            return f"❌ インポートエラー: {e}", 500

    return render_template("import_csv.html")



def generate_invoice_pdf(output_path, month, staff, total_taiken, total_pc, total_cashless,
                         store_fee, store_fee_tax, final_invoice, daily_details):

    # 日本語フォント登録
    pdfmetrics.registerFont(TTFont('IPAexGothic', 'static/ipaexg.ttf'))

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # タイトル
    c.setFont("IPAexGothic", 18)
    c.drawString(20 * mm, height - 20 * mm, f"{month} {staff} 請求書")

    # 会社情報
    c.setFont("IPAexGothic", 9)
    company_info = [
        "〒756-0817 山口県山陽小野田市大字小野田７３０番地２",
        "合同会社むすび家プランニング",
        "代表社員　新保　保（しんぽ　たもつ）",
        "TEL: 090-7506-2065",
        "Email: musubiya.planning@gmail.com"
    ]
    y_info = height - 35 * mm
    for line in company_info:
        c.drawString(20 * mm, y_info, line)
        y_info -= 5 * mm

    c.drawString(20 * mm, y_info, "適格請求書発行事業者登録番号：＿＿＿＿＿＿＿＿＿＿＿＿")

    # 売上・請求額
    y = height - 70 * mm
    c.setFont("IPAexGothic", 10)
    rows = [
        ("対面売上合計", total_taiken),
        ("コンピューター売上合計", total_pc),
        ("現金外合計", total_cashless),
        ("出店料（税抜）", round(store_fee)),
        ("出店料（税込10％）", store_fee_tax),
        ("請求額（現金外差引後）", final_invoice),
    ]
    for label, value in rows:
        c.drawString(20 * mm, y, label)
        c.drawRightString(180 * mm, y, f"{value} 円")
        y -= 10 * mm

    # 日別内訳
    y -= 10 * mm
    c.setFont("IPAexGothic", 12)
    c.drawString(20 * mm, y, "【日別内訳】")
    y -= 8 * mm

    c.setFont("IPAexGothic", 10)
    c.drawString(20 * mm, y, "日付")
    c.drawString(70 * mm, y, "対面")
    c.drawString(110 * mm, y, "コンピューター")
    c.drawString(150 * mm, y, "現金外")
    y -= 6 * mm
    c.line(20 * mm, y, 180 * mm, y)
    y -= 6 * mm

    for date_str, amounts in daily_details.items():
        c.drawString(20 * mm, y, date_str)
        c.drawRightString(90 * mm, y, str(amounts.get("対面", 0)))
        c.drawRightString(130 * mm, y, str(amounts.get("コンピューター", 0)))
        c.drawRightString(170 * mm, y, str(amounts.get("現金外", 0)))
        y -= 6 * mm
        if y < 40 * mm:
            c.showPage()
            c.setFont("IPAexGothic", 10)
            y = height - 20 * mm

    # 振込先情報
    y -= 10 * mm
    c.setFont("IPAexGothic", 11)
    c.drawString(20 * mm, y, "【振込先】")
    y -= 6 * mm
    bank_info = [
        "山口銀行　西ノ浜　普通　5016837",
        "ゆうちょ　15580-30544691",
        "PayPay　005-6931827",
        "西京銀行　日の出　普通　2055422"
    ]
    for line in bank_info:
        c.drawString(25 * mm, y, line)
        y -= 6 * mm

    c.save()





@app.route('/admin/invoice_staff_pdf')
def admin_invoice_staff_pdf():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))

    month = request.args.get('month', datetime.today().strftime('%Y-%m'))
    staff = request.args.get('staff')
    if not staff:
        return "占い師を指定してください", 400

    month_start = month + "-01"
    month_end = (datetime.strptime(month_start, "%Y-%m-%d") + relativedelta(months=1)).strftime('%Y-%m-%d')

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 月合計
        cur.execute("""
            SELECT method, SUM(amount)
            FROM sales
            WHERE date >= %s AND date < %s AND staff_name = %s
            GROUP BY method;
        """, (month_start, month_end, staff))
        rows = cur.fetchall()

        total_taiken = sum(total for method, total in rows if method == "対面")
        total_pc = sum(total for method, total in rows if method == "コンピューター")
        total_cashless = sum(total for method, total in rows if "現金外" in method)
        store_fee = total_taiken * 0.30 + total_pc * 0.50
        store_fee_tax = int(store_fee * 1.10)
        final_invoice = store_fee_tax - total_cashless

        # 日別内訳
        cur.execute("""
            SELECT date, method, SUM(amount)
            FROM sales
            WHERE date >= %s AND date < %s AND staff_name = %s
            GROUP BY date, method
            ORDER BY date, method;
        """, (month_start, month_end, staff))
        daily_rows = cur.fetchall()
        cur.close()
        conn.close()

        daily_details = {}
        for date, method, total in daily_rows:
            date_str = date.strftime("%Y-%m-%d")
            if date_str not in daily_details:
                daily_details[date_str] = {"対面": 0, "コンピューター": 0, "現金外": 0}

            # ①で定義済みの正規化関数を使用して列ズレを防止
            cat = normalize_method(method)
            if cat not in daily_details[date_str]:
                daily_details[date_str][cat] = 0
            daily_details[date_str][cat] += total

        # PDF生成
        pdf_path = os.path.join(UPLOAD_FOLDER, f"invoice_{staff}_{month}.pdf")
        generate_invoice_pdf(pdf_path, month, staff, total_taiken, total_pc,
                             total_cashless, store_fee, store_fee_tax, final_invoice, daily_details)

        return send_file(pdf_path, as_attachment=True, mimetype='application/pdf')

    except Exception as e:
        return f"❌ PDF生成エラー: {e}", 500




@app.route('/admin/sales_add_missing', methods=['GET', 'POST'])
def admin_sales_add_missing():
    if not session.get('admin'):
        return redirect(url_for('admin_login_sales'))

    # ---- GET: フォーム表示（STAFF_LIST / METHOD_LIST を使用）----
    if request.method == 'GET':
        preselect_staff = request.args.get('staff', '').strip()
        today_str = datetime.today().strftime("%Y-%m-%d")

        # STAFF_LIST / METHOD_LIST は既存マスタをそのまま使用
        # 例：STAFF_LIST = ["HIROMI", "美帆", ...], METHOD_LIST = ["対面","コンピューター","現金外（クレカQR)"]
        options_staff = []
        # 先頭に「選択してください」を入れ、?staff= 指定時はプリセレクト
        options_staff.append(f'<option value="" disabled{" selected" if not preselect_staff else ""}>選択してください</option>')
        for s in STAFF_LIST:
            selected = ' selected' if preselect_staff and s == preselect_staff else ''
            options_staff.append(f'<option value="{s}"{selected}>{s}</option>')
        options_staff_html = "\n".join(options_staff)

        options_method_html = "\n".join([f'<option value="{m}">{m}</option>' for m in METHOD_LIST])

        return render_template_string(f"""
        <!doctype html>
        <html>
        <head><meta charset="utf-8"><title>打ち忘れ追加</title>
        <style>
            body {{ font-family: sans-serif; padding: 16px; }}
            form {{ max-width: 520px; display: grid; gap: 12px; }}
            label {{ font-weight: 600; }}
            input, select {{ padding: 8px; font-size: 14px; }}
            .row {{ display: grid; gap: 4px; }}
            .actions {{ display: flex; gap: 8px; }}
        </style>
        </head>
        <body>
            <h1>打ち忘れ追加</h1>
            <form method="post">
                <div class="row">
                    <label>日付 (YYYY-MM-DD)</label>
                    <input type="date" name="date" value="{today_str}" required>
                </div>
                <div class="row">
                    <label>占い師（staff_name）</label>
                    <select name="staff_name" required>
                        {options_staff_html}
                    </select>
                </div>
                <div class="row">
                    <label>方法（method）</label>
                    <select name="method" required>
                        {options_method_html}
                    </select>
                </div>
                <div class="row">
                    <label>金額（円）</label>
                    <input type="number" name="amount" min="1" step="1" required>
                </div>
                <div class="actions">
                    <button type="submit">追加する</button>
                    <a href="/admin/invoice_staff">請求集計へ戻る</a>
                </div>
            </form>
        </body>
        </html>
        """)

    # ---- POST: 1行を sales に挿入（既存集計に即反映）----
    date_str = request.form.get('date', '').strip()
    staff_name = request.form.get('staff_name', '').strip()
    method = request.form.get('method', '').strip()
    amount_str = request.form.get('amount', '').strip()

    # 入力バリデーション（最小限）
    if not date_str or not staff_name or not method or not amount_str:
        return "❌ 必須項目が未入力です。", 400
    try:
        _ = datetime.strptime(date_str, "%Y-%m-%d")
        amount = int(amount_str)
        if amount <= 0:
            return "❌ 金額は正の整数で入力してください。", 400
    except Exception:
        return "❌ 入力形式を確認してください。（日付 or 金額）", 400

    # 既存の正規化関数で表記ゆれを吸収
    method = normalize_method(method)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # 既存スキーマ: sales(date, method, amount, staff_name)
        cur.execute("""
            INSERT INTO sales (date, method, amount, staff_name)
            VALUES (%s, %s, %s, %s);
        """, (date_str, method, amount, staff_name))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return f"❌ 追加に失敗しました: {e}", 500

    # 追加後は同月の請求集計へ
    month = date_str[:7]  # "YYYY-MM"
    return redirect(url_for('admin_invoice_staff', month=month, staff=staff_name))






@app.route('/selfmob/google808abc9a83ba5e55.html')
def google_verification_file():
    return send_from_directory('static', 'google808abc9a83ba5e55.html')



