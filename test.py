def _generate_session_for_shop(shop_id, full_year=False, mode="selfmob"):
    uuid_str = str(uuid.uuid4())
    return_url_thanks = f"{BASE_URL}/thanks?uuid={uuid_str}"

    # ✅ テスト中につき、金額をすべて1円に固定
    amount = 1

    session_url = create_payment_session(
        amount=amount,
        uuid_str=uuid_str,
        return_url_thanks=return_url_thanks,
        shop_id=shop_id,
        mode=mode
    )

    mode_key = mode + ("_full" if full_year else "")
    try:
        with open(USED_UUID_FILE, "a") as f:
            f.write(f"{uuid_str},,{mode_key},{shop_id}\n")
    except Exception as e:
        print("⚠️ UUID書き込み失敗:", e)

    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO webhook_events (uuid, shop_id, service, date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (uuid_str, shop_id, mode_key, today))
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print("❌ DB記録失敗 (generate_link):", e)

    resp = make_response(redirect(session_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp



def _generate_session_for_shop(shop_id, full_year=False, mode="selfmob"):
    uuid_str = str(uuid.uuid4())
    return_url_thanks = f"{BASE_URL}/thanks?uuid={uuid_str}"

    # ✅ 本番価格に設定：通常500円／年運付き1000円
    if mode == "renaiselfmob":
        amount = 1000 if full_year else 500
    else:
        amount = 1000 if full_year else 500

    session_url = create_payment_session(
        amount=amount,
        uuid_str=uuid_str,
        return_url_thanks=return_url_thanks,
        shop_id=shop_id,
        mode=mode
    )

    mode_key = mode + ("_full" if full_year else "")
    try:
        with open(USED_UUID_FILE, "a") as f:
            f.write(f"{uuid_str},,{mode_key},{shop_id}\n")
    except Exception as e:
        print("⚠️ UUID書き込み失敗:", e)

    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO webhook_events (uuid, shop_id, service, date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (uuid_str, shop_id, mode_key, today))
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print("❌ DB記録失敗 (generate_link):", e)

    resp = make_response(redirect(session_url))
    resp.set_cookie("uuid", uuid_str, max_age=600)
    return resp