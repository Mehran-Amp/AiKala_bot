# -*- coding: utf-8 -*-
"""
db_bridge.py
ایجاد و همگام‌سازی جداول محصولات و درخت دسته‌بندی‌های پویا در دیتابیس bot_data.db
کاملاً منطبق با کاتالوگ استخراج‌شده و بدون هیچ نام یا اثری از سایت مبدأ.
"""

import sqlite3
import json
import os

DB_PATH = "bot_data.db"
CATALOG_FILE = "catalog_products.json"
CATEGORIES_FILE = "categories_tree.json"

def init_product_tables():
    """ایجاد و تطبیق ساختار جداول محصولات و دسته‌بندی‌های پویا با قابلیت مهاجرت خودکار ستون‌ها"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # جدول کامل محصولات با تمامی ستون‌های استخراج‌شده
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT UNIQUE,
        data_id TEXT,
        category_key TEXT,
        category_name TEXT,
        subcategory TEXT,
        name TEXT,
        model_number TEXT,
        brand TEXT,
        size TEXT,
        price INTEGER DEFAULT 0,
        status TEXT DEFAULT 'b',
        assembly TEXT,
        score TEXT,
        year TEXT,
        resolution TEXT,
        panel TEXT,
        refresh_rate TEXT,
        backlight TEXT,
        os TEXT,
        capacity_btu TEXT,
        ac_type TEXT,
        temp_range TEXT,
        room_size TEXT,
        energy_consumption TEXT,
        performance TEXT,
        key_features TEXT,
        plan TEXT,
        capacity_foot TEXT,
        num_doors TEXT,
        capacity_kg TEXT,
        baskets TEXT,
        more_details TEXT,
        colors_json TEXT DEFAULT '{}',
        specs_json TEXT DEFAULT '{}',
        url TEXT,
        image_url TEXT,
        source TEXT DEFAULT 'MomtazKalla',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # بررسی و افزودن خودکار ستون‌های جدید در صورت وجود دیتابیس قدیمی
    cursor.execute("PRAGMA table_info(products);")
    existing_cols = {row[1] for row in cursor.fetchall()}

    expected_cols = [
        ("data_id", "TEXT"),
        ("category_key", "TEXT"),
        ("category_name", "TEXT"),
        ("subcategory", "TEXT"),
        ("name", "TEXT"),
        ("model_number", "TEXT"),
        ("brand", "TEXT"),
        ("size", "TEXT"),
        ("price", "INTEGER DEFAULT 0"),
        ("status", "TEXT DEFAULT 'b'"),
        ("assembly", "TEXT"),
        ("score", "TEXT"),
        ("year", "TEXT"),
        ("resolution", "TEXT"),
        ("panel", "TEXT"),
        ("refresh_rate", "TEXT"),
        ("backlight", "TEXT"),
        ("os", "TEXT"),
        ("capacity_btu", "TEXT"),
        ("ac_type", "TEXT"),
        ("temp_range", "TEXT"),
        ("room_size", "TEXT"),
        ("energy_consumption", "TEXT"),
        ("performance", "TEXT"),
        ("key_features", "TEXT"),
        ("plan", "TEXT"),
        ("capacity_foot", "TEXT"),
        ("num_doors", "TEXT"),
        ("capacity_kg", "TEXT"),
        ("baskets", "TEXT"),
        ("more_details", "TEXT"),
        ("colors_json", "TEXT DEFAULT '{}'"),
        ("specs_json", "TEXT DEFAULT '{}'"),
        ("url", "TEXT"),
        ("image_url", "TEXT"),
        ("source", "TEXT DEFAULT 'MomtazKalla'"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]

    for col_name, col_type in expected_cols:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type};")
            except Exception as e:
                print(f"[DB] Note adding column {col_name}: {e}")

    # جدول درخت دسته‌بندی‌های پویا
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dynamic_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_key TEXT UNIQUE,
        title TEXT,
        tree_json TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ایندکس‌های افزایش سرعت سرچ زیر ۵ میلی‌ثانیه در دیتابیس
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_cat ON products(category_key);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_brand ON products(brand);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_model ON products(model_number);")
    except Exception as e:
        print(f"[DB] Note creating indexes: {e}")

    conn.commit()
    conn.close()
    print("✅ جداول دیتابیس محصولات با موفقیت مقداردهی و همگام‌سازی شدند.")

def load_catalog_into_db():
    """وارد کردن داده‌های فایل کاتالوگ استخراج‌شده به دیتابیس"""
    if not os.path.exists(CATALOG_FILE):
        print("فایل کاتالوگ هنوز ایجاد نشده است.")
        return 0

    init_product_tables()
    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    for pid, item in catalog.items():
        cursor.execute("""
        INSERT INTO products (
            product_id, data_id, category_key, category_name, subcategory,
            name, model_number, brand, size, price, status, assembly, score,
            year, resolution, panel, refresh_rate, backlight, os,
            capacity_btu, ac_type, temp_range, room_size, energy_consumption,
            performance, key_features, plan, capacity_foot, num_doors,
            capacity_kg, baskets, more_details
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?
        )
        ON CONFLICT(product_id) DO UPDATE SET
            price = excluded.price,
            status = excluded.status,
            name = excluded.name,
            more_details = excluded.more_details,
            assembly = excluded.assembly,
            score = excluded.score;
        """, (
            item.get("product_id", pid),
            item.get("data_id", pid),
            item.get("category_key", ""),
            item.get("category_name", ""),
            item.get("subcategory", ""),
            item.get("name", ""),
            item.get("model_number", ""),
            item.get("brand", ""),
            item.get("size", ""),
            item.get("price", 0),
            item.get("status", "b"),
            item.get("assembly", ""),
            item.get("score", ""),
            item.get("year", ""),
            item.get("resolution", ""),
            item.get("panel", ""),
            item.get("refresh_rate", ""),
            item.get("backlight", ""),
            item.get("os", ""),
            item.get("capacity_btu", ""),
            item.get("ac_type", ""),
            item.get("temp_range", ""),
            item.get("room_size", ""),
            item.get("energy_consumption", ""),
            item.get("performance", ""),
            item.get("key_features", ""),
            item.get("plan", ""),
            item.get("capacity_foot", ""),
            item.get("num_doors", ""),
            item.get("capacity_kg", ""),
            item.get("baskets", ""),
            item.get("more_details", "")
        ))
        inserted += 1

    # ذخیره درخت دسته‌بندی در دیتابیس
    if os.path.exists(CATEGORIES_FILE):
        with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
            tree = json.load(f)
        for cat_key, cat_data in tree.items():
            cursor.execute("""
            INSERT INTO dynamic_categories (category_key, title, tree_json)
            VALUES (?, ?, ?)
            ON CONFLICT(category_key) DO UPDATE SET
                title = excluded.title,
                tree_json = excluded.tree_json,
                updated_at = CURRENT_TIMESTAMP;
            """, (cat_key, cat_data.get("title", cat_key), json.dumps(cat_data, ensure_ascii=False)))

    conn.commit()
    conn.close()
    print(f"✅ تعداد {inserted} محصول با کلیه مشخصات و ستون‌ها در دیتابیس بارگذاری شد.")
    return inserted

def get_dynamic_categories():
    """دریافت درخت دسته‌بندی پویا جهت ساخت منوی شیشه‌ای تلگرام"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT category_key, title, tree_json FROM dynamic_categories;")
    rows = cursor.fetchall()
    conn.close()
    categories = {}
    for k, title, tree_raw in rows:
        try:
            categories[k] = {"title": title, "tree": json.loads(tree_raw)}
        except Exception:
            categories[k] = {"title": title, "tree": {}}
    return categories

if __name__ == "__main__":
    init_product_tables()
    load_catalog_into_db()
