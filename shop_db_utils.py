
import sqlite3
from datetime import datetime

def init_shop_db():
    with sqlite3.connect("shop_log.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                shop_id TEXT,
                count INTEGER DEFAULT 1
            )
        """)
        conn.commit()
    print("✅ shop_log.db initialized")

def update_shop_db(shop_id):
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📝 update_shop_db called with shop_id = {shop_id}")
    with sqlite3.connect("shop_log.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count FROM shop_logs WHERE date = ? AND shop_id = ?",
            (today, shop_id)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE shop_logs SET count = count + 1 WHERE date = ? AND shop_id = ?",
                (today, shop_id)
            )
        else:
            cursor.execute(
                "INSERT INTO shop_logs (date, shop_id, count) VALUES (?, ?, 1)",
                (today, shop_id)
            )
        conn.commit()
