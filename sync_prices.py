# -*- coding: utf-8 -*-
"""
sync_prices.py
همگام‌سازی سبک، امن و ۲ ساعته قیمت‌ها و وضعیت موجودی کالاها (زیر ۱ ثانیه).
بدون نیاز به اسکرپ HTML و کاملاً مستقیم از منبع زنده JSON.
"""

import urllib.request
import ssl
import json
import os
import sqlite3
import time
import datetime

LIVE_JSON_URL = "https://momtazkalla.com/wp-content/uploads/procache-live/live-data.json"
CATALOG_FILE = "catalog_products.json"
DB_FILE = "bot_data.db"
SYNC_INFO_FILE = "price_sync_info.json"

def gregorian_to_jalali(gy, gm, gd):
    """تبدیل دقیق میلادی به هجری شمسی بدون نیاز به کتابخانه‌های جانبی"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy if gm > 2 else gy - 1
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

def get_persian_date_str(dt: datetime.datetime = None) -> str:
    if dt is None:
        dt = datetime.datetime.now()
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d} ساعت {dt.strftime('%H:%M')}"

def get_last_price_sync_str() -> str:
    """دریافت تاریخ و ساعت آخرین بروزرسانی لیست قیمت محصولات ممتاز کالا"""
    if os.path.exists(SYNC_INFO_FILE):
        try:
            with open(SYNC_INFO_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("persian_datetime"):
                    return data["persian_datetime"]
        except Exception:
            pass

    # در صورت عدم وجود فایل رکورد، بررسی تاریخ تغییر فایل‌های اصلی کاتالوگ
    target_files = [CATALOG_FILE, "momtazkalla_all_products.json"]
    for tf in target_files:
        if os.path.exists(tf):
            try:
                mtime = os.path.getmtime(tf)
                dt = datetime.datetime.fromtimestamp(mtime)
                return get_persian_date_str(dt)
            except Exception:
                pass

    return get_persian_date_str()

def save_sync_info(updated_count: int = 0, total_items: int = 0):
    try:
        now_dt = datetime.datetime.now()
        data = {
            "timestamp": int(now_dt.timestamp()),
            "persian_datetime": get_persian_date_str(now_dt),
            "updated_count": updated_count,
            "total_items": total_items,
            "source": "ممتاز کالا (زنده)"
        }
        with open(SYNC_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[SYNC] Error saving sync timestamp record:", e)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_sync_info_dict() -> dict:
    """دریافت اطلاعات کامل آخرین بروزرسانی قیمت‌ها"""
    if os.path.exists(SYNC_INFO_FILE):
        try:
            with open(SYNC_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "persian_datetime": get_last_price_sync_str(),
        "updated_count": 0,
        "total_items": 0,
        "source": "ممتاز کالا (زنده)"
    }

def update_live_prices():
    """
    Fetch lightweight live JSON and update prices/status in:
    1. Base catalog JSON (catalog_products.json)
    2. Optional all products JSON (momtazkalla_all_products.json)
    3. SQLite database (bot_data.db)
    4. Active in-memory cache (search_engine.JSON_PRODUCTS) for immediate reflection
    """
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [SYNC] Checking live prices...")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(LIVE_JSON_URL, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            live_data = json.loads(resp.read().decode('utf-8', errors='ignore'))
    except Exception as e:
        print("[SYNC] Error fetching live price feed:", e)
        return False

    items = live_data.get("i", {})
    if not items:
        print("[SYNC] No items found in live price feed.")
        return False

    # 1. به‌روزرسانی فایل کاتالوگ اصلی (catalog_products.json)
    catalog = {}
    if os.path.exists(CATALOG_FILE):
        try:
            with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                catalog = json.load(f)
        except Exception as e:
            print("[SYNC] Error reading catalog file:", e)

    updated_count = 0
    for pid, live_info in items.items():
        # d: قیمت مصرف‌کننده به تومان
        # s: وضعیت (b: موجود، o: ناموجود، i: استعلام تلفنی)
        new_price = live_info.get("d", 0)
        new_status = live_info.get("s", "b")

        if pid in catalog:
            if catalog[pid].get("price") != new_price or catalog[pid].get("status") != new_status:
                catalog[pid]["price"] = new_price
                catalog[pid]["status"] = new_status
                catalog[pid]["price_formatted"] = f"{int(new_price):,} تومان" if new_price else "تماس بگیرید"
                updated_count += 1

    if updated_count > 0 and catalog:
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        print(f"✅ [SYNC] Updated {updated_count} products in {CATALOG_FILE}.")
    else:
        print("[SYNC] Catalog file prices are already up to date.")

    # 2. به‌روزرسانی فایل مکمل در صورت وجود (momtazkalla_all_products.json)
    alt_file = "momtazkalla_all_products.json"
    if os.path.exists(alt_file):
        try:
            with open(alt_file, "r", encoding="utf-8") as f:
                all_prods = json.load(f)
            alt_updated = 0
            if isinstance(all_prods, list):
                for p in all_prods:
                    pid_str = str(p.get("product_id", "")).strip()
                    # بررسی تطابق با ID یا تطابق مدل
                    matching_info = items.get(pid_str)
                    if not matching_info and pid_str in catalog:
                        cat_item = catalog[pid_str]
                        new_p = cat_item.get("price")
                        if new_p and p.get("price") != str(new_p):
                            p["price"] = str(new_p)
                            p["price_raw"] = new_p
                            alt_updated += 1
                    elif matching_info:
                        new_p = matching_info.get("d", 0)
                        new_s = matching_info.get("s", "b")
                        if new_p:
                            p["price"] = str(new_p)
                            p["price_raw"] = new_p
                            p["status"] = new_s
                            alt_updated += 1
                if alt_updated > 0:
                    with open(alt_file, "w", encoding="utf-8") as f:
                        json.dump(all_prods, f, ensure_ascii=False, indent=2)
                    print(f"✅ [SYNC] Updated {alt_updated} products in {alt_file}.")
        except Exception as e:
            print("[SYNC] Note updating alt catalog file:", e)

    # 3. همگام‌سازی با دیتابیس ربات (SQLite) با بررسی ایمن ستون‌ها
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # بررسی وجود جدول products
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products';")
        if cursor.fetchone():
            # بررسی و افزودن خودکار ستون status در صورت عدم وجود
            cursor.execute("PRAGMA table_info(products);")
            existing_cols = [row[1] for row in cursor.fetchall()]
            if "status" not in existing_cols:
                try:
                    cursor.execute("ALTER TABLE products ADD COLUMN status TEXT DEFAULT 'b';")
                    conn.commit()
                except Exception:
                    pass

            db_updates = 0
            for pid, live_info in items.items():
                p = live_info.get("d", 0)
                s = live_info.get("s", "b")
                cursor.execute(
                    "UPDATE products SET price = ?, status = ? WHERE product_id = ?",
                    (str(p), s, pid)
                )
                if cursor.rowcount > 0:
                    db_updates += cursor.rowcount
            conn.commit()
            if db_updates > 0:
                print(f"✅ [SYNC] Synchronized {db_updates} rows in SQLite database.")
        conn.close()
    except Exception as e:
        print("[SYNC] Database sync note:", e)

    # 4. بارگذاری مجدد فوری کش حافظه جستجوی ربات (بسیار مهم: رفع عدم تغییر قیمت در نتایج جستجو)
    try:
        from search_engine import load_json_products
        load_json_products()
        print("✅ [SYNC] In-memory product cache (JSON_PRODUCTS) successfully reloaded.")
    except Exception as e:
        print("[SYNC] Note reloading in-memory search engine cache:", e)

    save_sync_info(updated_count=updated_count, total_items=len(items))
    return True

if __name__ == "__main__":
    update_live_prices()
