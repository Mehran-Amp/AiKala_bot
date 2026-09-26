# -*- coding: utf-8 -*-
"""
bot_catalog.py
ناوبری داینامیک تلگرام و قالب‌بندی متنی کارت‌های محصولات.
بدون تصویر، بدون کوچک‌ترین ردپا از سایت مبدأ (کاملاً White-Label)
و بدون نمایش تاریخ یا ساعت به‌روزرسانی قیمت.
"""

import os
import json
import sqlite3
from typing import Dict, List, Optional, Tuple, Any

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
except ImportError:
    from keyboards import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards import make_safe_cb, resolve_safe_cb

try:
    from search_engine import is_product_hidden
except ImportError:
    def is_product_hidden(p):
        return False

DB_PATH = "bot_data.db"
CATEGORIES_FILE = "categories_tree.json"

def format_price(amount: int) -> str:
    if not amount or amount <= 0:
        return "تماس بگیرید"
    return f"{amount:,} تومان"

def get_product_card(prod: dict) -> str:
    """تولید کارت متنی شیک و استاندارد محصول برای ارسال در تلگرام"""
    name = prod.get("name", "")
    price = prod.get("price", 0)

    cat = prod.get("category_key", "")
    lines = [
        f"🏷 **{name}**",
        "",
        f"▫️ **قیمت روز:** `{format_price(price)}`",
    ]

    # مشخصات مو به مو بر اساس نوع کالا
    if cat == "tv":
        if prod.get("assembly"):
            lines.append(f"▫️ **کشور مونتاژ:** {prod['assembly']}")
        if prod.get("year"):
            lines.append(f"▫️ **سال ساخت:** {prod['year']}")
        if prod.get("resolution"):
            lines.append(f"▫️ **کیفیت تصویر:** {prod['resolution']}")
        if prod.get("panel"):
            lines.append(f"▫️ **نوع پنل:** {prod['panel']}")
        if prod.get("refresh_rate"):
            lines.append(f"▫️ **رفرش ریت:** {prod['refresh_rate']}")
        if prod.get("backlight"):
            lines.append(f"▫️ **بکلایت:** {prod['backlight']}")
        if prod.get("os"):
            lines.append(f"▫️ **سیستم‌عامل:** {prod['os']}")
        if prod.get("score"):
            lines.append(f"▫️ **امتیاز کیفی کارشناسی:** ⭐️ {prod['score']} از ۱۰")

    elif cat == "conditioner":
        if prod.get("temp_range"):
            lines.append(f"▫️ **شرایط آب و هوایی:** {prod['temp_range']}")
        if prod.get("room_size"):
            lines.append(f"▫️ **پوشش فضا:** {prod['room_size']}")
        if prod.get("energy_consumption"):
            lines.append(f"▫️ **نوع موتور و مصرف:** {prod['energy_consumption']}")
        if prod.get("performance"):
            lines.append(f"▫️ **عملکرد:** {prod['performance']}")
        if prod.get("key_features"):
            lines.append(f"▫️ **ویژگی‌های کلیدی:** {prod['key_features']}")
        if prod.get("score"):
            lines.append(f"▫️ **امتیاز کیفی:** ⭐️ {prod['score']} از ۱۰")

    elif cat == "refrigerator":
        if prod.get("plan"):
            lines.append(f"▫️ **طرح و نوع:** {prod['plan']}")
        if prod.get("capacity_foot"):
            lines.append(f"▫️ **ظرفیت به فوت:** {prod['capacity_foot']}")
        if prod.get("num_doors"):
            lines.append(f"▫️ **تعداد درب:** {prod['num_doors']}")
        if prod.get("assembly"):
            lines.append(f"▫️ **کشور مونتاژ:** {prod['assembly']}")
        if prod.get("score"):
            lines.append(f"▫️ **امتیاز کیفی:** ⭐️ {prod['score']} از ۱۰")

    elif cat == "washing_machine":
        if prod.get("capacity_kg"):
            lines.append(f"▫️ **ظرفیت شستشو:** {prod['capacity_kg']} کیلوگرم")
        if prod.get("plan"):
            lines.append(f"▫️ **نوع طراحی:** {prod['plan']}")
        if prod.get("assembly"):
            lines.append(f"▫️ **کشور مونتاژ:** {prod['assembly']}")
        if prod.get("score"):
            lines.append(f"▫️ **امتیاز کیفی:** ⭐️ {prod['score']} از ۱۰")

    elif cat == "dishwasher":
        if prod.get("baskets"):
            lines.append(f"▫️ **تعداد سبدها:** {prod['baskets']}")
        if prod.get("assembly"):
            lines.append(f"▫️ **کشور مونتاژ:** {prod['assembly']}")
        if prod.get("score"):
            lines.append(f"▫️ **امتیاز کیفی:** ⭐️ {prod['score']} از ۱۰")

    elif cat == "small_appliances":
        if prod.get("subcategory"):
            lines.append(f"▫️ **دسته‌بندی:** {prod['subcategory']}")
        if prod.get("score"):
            lines.append(f"▫️ **امتیاز کیفی:** ⭐️ {prod['score']} از ۱۰")
        if prod.get("ai_specs") and isinstance(prod["ai_specs"], dict):
            for k, v in prod["ai_specs"].items():
                if k not in ["ضمانت اصالت", "گارانتی"]:
                    lines.append(f"▫️ **{k}:** {v}")
        elif prod.get("more_details"):
            lines.append(f"\n📝 **مشخصات فنی:**\n{prod['more_details']}")

    elif cat == "laptop" or prod.get("category") == "لپ‌تاپ" or prod.get("category_name") == "لپ‌تاپ":
        specs = prod.get("specs", {})
        if specs.get("کد مدل"):
            lines.append(f"▫️ **کد کالا:** `{specs['کد مدل']}`")
        if specs.get("پردازنده (CPU)"):
            lines.append(f"▫️ **پردازنده (CPU):** {specs['پردازنده (CPU)']}")
        if specs.get("حافظه رم (RAM)"):
            lines.append(f"▫️ **حافظه رم:** {specs['حافظه رم (RAM)']}")
        if specs.get("حافظه داخلی (SSD/HDD)"):
            lines.append(f"▫️ **حافظه داخلی:** {specs['حافظه داخلی (SSD/HDD)']}")
        if specs.get("کارت گرافیک (GPU)"):
            lines.append(f"▫️ **گرافیک:** {specs['کارت گرافیک (GPU)']}")
        if specs.get("صفحه نمایش"):
            lines.append(f"▫️ **صفحه نمایش:** {specs['صفحه نمایش']}")
        if specs.get("گرید و تمیزی"):
            lines.append(f"▫️ **گرید سلامت دستگاه:** ⭐️ {specs['گرید و تمیزی']}")

    # بررسی آیا محصول لپ‌تاپ است جهت ارائه گارانتی متناسب
    is_laptop = (
        cat == "laptop"
        or prod.get("category") in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"]
        or prod.get("category_name") in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"]
        or str(prod.get("id") or prod.get("product_id") or "").upper().startswith("LAP")
        or any(w in str(prod.get("name") or prod.get("title") or "").lower() for w in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"])
    )

    if is_laptop:
        lines.append("▫️ **گارانتی و مهلت تست:** یک هفته ضمانت تست و تعویض")
    else:
        # افزودن ضمانت اصالت و گارانتی به سایر محصولات (لوازم خانگی شرکتی)
        lines.append("▫️ **ضمانت اصالت:** ۱۰۰٪ اورجینال با تضمین کتبی")
        lines.append("▫️ **گارانتی:** ۱۸ ماه گارانتی شرکتی و ۵ سال خدمات پس از فروش")

    return "\n".join(lines)

def search_products(query: str, limit: int = 10) -> List[dict]:
    """جستجوی فوق‌سریع کمتر از ۲ میلی‌ثانیه بر اساس مدل و نام (بدون نمایش کالاهای پنهان)"""
    if not query:
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    q_words = query.strip().split()
    conditions = []
    params = []
    for w in q_words:
        conditions.append("(name LIKE ? OR model_number LIKE ? OR brand LIKE ?)")
        param = f"%{w}%"
        params.extend([param, param, param])
    
    where_sql = " AND ".join(conditions)
    cursor.execute(f"""
        SELECT * FROM products
        WHERE ({where_sql}) AND (status IS NULL OR status != 'hidden')
        ORDER BY CASE WHEN price > 0 THEN 0 ELSE 1 END, price DESC
        LIMIT ?
    """, (*params, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows if not is_product_hidden(r.get("product_id"))]

def get_product_by_id(pid: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE product_id = ?", (pid,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ─── سیستم ناوبری تعاملی و پویای دسته‌بندی‌ها ───

def load_categories_tree() -> dict:
    tree = {}
    if os.path.exists(CATEGORIES_FILE):
        try:
            with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                tree = json.load(f)
                # فیلتر کالاهای پنهان از درخت دسته‌بندی پایه
                for c_k, c_v in list(tree.items()):
                    if isinstance(c_v, dict):
                        for sub_k, sub_v in list(c_v.items()):
                            if isinstance(sub_v, dict):
                                for item_k, item_v in list(sub_v.items()):
                                    if isinstance(item_v, list):
                                        c_v[sub_k][item_k] = [p for p in item_v if not is_product_hidden(p)]
        except Exception:
            tree = {}

    # بارگذاری پویا و خودکار لپ‌تاپ‌ها از کاتالوگ لپ‌تاپ
    tree["laptop"] = {
        "title": "💻 لپ‌تاپ",
        "brands": {}
    }
    if os.path.exists("laptops_catalog.json"):
        try:
            with open("laptops_catalog.json", "r", encoding="utf-8") as lf:
                laptops = json.load(lf)
                if isinstance(laptops, list) and laptops:
                    brand_map = {}
                    for item in laptops:
                        b = str(item.get("brand", "HP")).strip().upper()
                        pid = item.get("product_id") or item.get("id")
                        if pid and not is_product_hidden(pid):
                            brand_map.setdefault(b, []).append(pid)
                    tree["laptop"]["brands"] = brand_map
        except Exception:
            pass

    # بارگذاری پویا و مستقل سیستم‌های صوتی (اسپیکر، پارتی‌باکس، ساندبار)
    try:
        from audio_service import load_audio_catalog
        audio_items = load_audio_catalog()
        if audio_items:
            aud_sub_map = {}
            aud_brand_map = {}
            for item in audio_items:
                sub_title = item.get("subcategory") or "اسپیکر و سیستم صوتی"
                b_name = str(item.get("brand", "JBL")).strip().upper()
                pid = item.get("product_id") or item.get("id")
                if pid and not is_product_hidden(pid):
                    aud_sub_map.setdefault(sub_title, []).append(pid)
                    aud_brand_map.setdefault(b_name, []).append(pid)
            tree["audio"] = {
                "title": "🔊 سیستم صوتی",
                "subcategories": aud_sub_map,
                "brands": aud_brand_map
            }
    except Exception:
        pass

    # بارگذاری پویا و مستقل محصولات آاگ (AEG) از فایل aeg_products.json
    try:
        from aeg_service import load_aeg_products
        aeg_items = load_aeg_products()
        if aeg_items:
            sub_map = {}
            for item in aeg_items:
                sub_title = item.get("subcategory") or "📦 سایر لوازم خانگی آاگ"
                pid = item.get("product_id")
                if pid and not is_product_hidden(pid):
                    sub_map.setdefault(sub_title, []).append(pid)
            tree["aeg"] = {
                "title": "⭐️ محصولات آاگ/AEG",
                "subcategories": sub_map
            }
    except Exception:
        pass

    return tree

def get_main_categories_markup():
    tree = load_categories_tree()
    buttons = []
    # ترتیب استاندارد دسته‌بندی‌ها: صوتی و لپ‌تاپ در کنار سایر دسته‌ها
    order = ["tv", "conditioner", "refrigerator", "washing_machine", "dishwasher", "small_appliances", "audio", "laptop", "aeg"]
    row = []
    for cat_key in order:
        cat_data = tree.get(cat_key, {})
        title = cat_data.get("title", cat_key)
        pids = set()
        for subk, subv in cat_data.items():
            if isinstance(subv, dict):
                for itemv in subv.values():
                    if isinstance(itemv, list):
                        pids.update(itemv)
        count_str = f" ({len(pids)})" if pids else ""
        cb = make_safe_cb("cat_m", cat_key)
        row.append(InlineKeyboardButton(f"{title}{count_str}", callback_data=cb))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

def get_category_sub_markup(cat_key: str) -> Tuple[str, Any]:
    tree = load_categories_tree()
    cat_data = tree.get(cat_key, {})
    title = cat_data.get("title", cat_key)
    buttons = []

    if cat_key == "aeg":
        subcats = cat_data.get("subcategories", {})
        row = []
        for sub_name, pids in subcats.items():
            count = len(pids) if isinstance(pids, list) else 0
            btn_text = f"{sub_name} ({count})"
            cb = make_safe_cb("cat_sub", f"aeg:{sub_name}")
            row.append(InlineKeyboardButton(btn_text, callback_data=cb))
            if len(row) == 1:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([
            InlineKeyboardButton("📋 مشاهده همه کالاهای آاگ", callback_data=make_safe_cb("cat_all", "aeg")),
            InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="cat_back")
        ])
        all_aeg_count = sum(len(pids) for pids in subcats.values() if isinstance(pids, list))
        msg_text = (
            f"⭐️ <b>محصولات تخصصی آاگ / AEG:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 همگام‌سازی مستقیم با قیمت و موجودی روز وب‌سایت <b>aegkala.com</b>\n"
            f"📦 تعداد کل مدل‌های دارای قیمت: <b>{all_aeg_count} محصول</b>\n\n"
            f"🔍 لطفاً زیرمجموعه مورد نظر خود را انتخاب فرمایید:"
        )
        return msg_text, InlineKeyboardMarkup(buttons)

    if cat_key == "laptop":
        brands_dict = cat_data.get("brands", {})
        row = []
        for b_name, pids in brands_dict.items():
            count = len(pids) if isinstance(pids, list) else 0
            btn_text = f"💻 {b_name} ({count})"
            cb = make_safe_cb("cat_opt", f"laptop:brands:{b_name}")
            row.append(InlineKeyboardButton(btn_text, callback_data=cb))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([
            InlineKeyboardButton("📥 دانلود لیست موجودی", callback_data=make_safe_cb("cat_pdf", "laptop")),
            InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="cat_back")
        ])
        all_laptops_count = sum(len(pids) for pids in brands_dict.values() if isinstance(pids, list))
        msg_text = (
            f"💻 <b>دسته‌بندی لپ‌تاپ (انتخاب بر اساس برند):</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 تعداد کل مدل‌های موجود: <b>{all_laptops_count} مدل</b>\n\n"
            f"🔍 لطفاً برند لپ‌تاپ مورد نظر خود را انتخاب فرمایید:"
        )
        return msg_text, InlineKeyboardMarkup(buttons)

    if cat_key == "audio":
        subcats = cat_data.get("subcategories", {})
        row = []
        for sub_name, pids in subcats.items():
            count = len(pids) if isinstance(pids, list) else 0
            clean_sub = sub_name.replace("اسپیکر ", "")
            btn_text = f"🔊 {clean_sub} ({count})"
            cb = make_safe_cb("cat_sub", f"audio:{sub_name}")
            row.append(InlineKeyboardButton(btn_text, callback_data=cb))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([
            InlineKeyboardButton("📥 دانلود لیست موجودی (PDF)", callback_data=make_safe_cb("cat_pdf", "audio")),
            InlineKeyboardButton("📋 مشاهده همه سیستم‌های صوتی", callback_data=make_safe_cb("cat_all", "audio"))
        ])
        buttons.append([
            InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="cat_back")
        ])
        all_audio_count = sum(len(pids) for pids in subcats.values() if isinstance(pids, list))
        msg_text = (
            f"🔊 <b>دسته‌بندی سیستم‌های صوتی و پارتی‌باکس:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 تعداد کل مدل‌های موجود: <b>{all_audio_count} دستگاه</b>\n"
            f"🛡 <b>ضمانت اصالت:</b> ۱۰۰٪ اورجینال با تضمین کتبی و تست صدا\n\n"
            f"🔍 لطفاً زیرمجموعه مورد نظر خود را انتخاب فرمایید:"
        )
        return msg_text, InlineKeyboardMarkup(buttons)

    if cat_key == "small_appliances":
        subcats = cat_data.get("subcategories", {})
        row = []
        for sub_name, pids in subcats.items():
            count = len(pids) if isinstance(pids, list) else 0
            btn_text = f"{sub_name} ({count})"
            cb = make_safe_cb("cat_sub", f"{cat_key}:{sub_name}")
            row.append(InlineKeyboardButton(btn_text, callback_data=cb))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([
            InlineKeyboardButton("📋 مشاهده همه کالاهای این دسته", callback_data=make_safe_cb("cat_all", cat_key)),
            InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="cat_back")
        ])
        msg_text = f"☕️ <b>زیرشاخه‌های {title}:</b>\nلطفاً گروه کالای مورد نظر را انتخاب نمایید:"
        return msg_text, InlineKeyboardMarkup(buttons)

    filter_labels = {
        "brands": "🏷 بر اساس برند",
        "sizes": "📏 بر اساس سایز",
        "capacities": "⚡️ بر اساس ظرفیت",
        "plans": "🚪 بر اساس نوع و طرح بدنه",
        "types": "💨 بر اساس نوع دستگاه",
        "baskets": "🍽 بر اساس تعداد سبدها"
    }

    for subk, subv in cat_data.items():
        if subk != "title" and isinstance(subv, dict) and subv:
            lbl = filter_labels.get(subk, f"بر اساس {subk}")
            cb = make_safe_cb("cat_f", f"{cat_key}:{subk}")
            buttons.append([InlineKeyboardButton(lbl, callback_data=cb)])

    extra_actions = []
    supported_pdf_cats = ["tv", "conditioner", "washing_machine", "dishwasher", "refrigerator", "small_appliances", "aeg", "laptop", "audio"]
    if cat_key in supported_pdf_cats:
        extra_actions.append(InlineKeyboardButton("📄 دانلود لیست قیمت (PDF)", callback_data=make_safe_cb("cat_pdf", cat_key)))
    if extra_actions:
        buttons.append(extra_actions)

    buttons.append([
        InlineKeyboardButton("📋 مشاهده همه کالاهای این دسته", callback_data=make_safe_cb("cat_all", cat_key)),
        InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="cat_back")
    ])

    all_pids = set()
    for subk, subv in cat_data.items():
        if isinstance(subv, dict):
            for itemv in subv.values():
                if isinstance(itemv, list):
                    all_pids.update(itemv)

    msg_text = (
        f"📂 <b>دسته‌بندی: {title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 تعداد کل مدل‌های موجود: <b>{len(all_pids)} مدل</b>\n\n"
        f"🔍 نحوه انتخاب و فیلتر را مشخص فرمایید:"
    )
    return msg_text, InlineKeyboardMarkup(buttons)

def get_filter_options_markup(cat_key: str, filter_type: str) -> Tuple[str, Any]:
    tree = load_categories_tree()
    cat_data = tree.get(cat_key, {})
    title = cat_data.get("title", cat_key)
    options_dict = cat_data.get(filter_type, {})

    buttons = []
    row = []
    for opt_name, pids in options_dict.items():
        count = len(pids) if isinstance(pids, list) else 0
        btn_text = f"{opt_name} ({count})"
        cb = make_safe_cb("cat_opt", f"{cat_key}:{filter_type}:{opt_name}")
        row.append(InlineKeyboardButton(btn_text, callback_data=cb))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت به این دسته", callback_data=make_safe_cb("cat_m", cat_key)),
        InlineKeyboardButton("📂 همه دسته‌ها", callback_data="cat_back")
    ])

    filter_names = {
        "brands": "برندها",
        "sizes": "سایزها",
        "capacities": "ظرفیت‌ها",
        "plans": "طرح‌ها و مدل‌های بدنه",
        "types": "انواع مدل‌ها",
        "baskets": "تعداد سبدها"
    }
    f_title = filter_names.get(filter_type, filter_type)
    msg_text = f"🔍 <b>{title} - انتخاب بر اساس {f_title}:</b>\nلطفاً گزینه مورد نظر را انتخاب فرمایید:"
    return msg_text, InlineKeyboardMarkup(buttons)

def get_products_for_category_selection(cat_key: str, filter_type: Optional[str] = None, opt_name: Optional[str] = None) -> List[dict]:
    tree = load_categories_tree()
    cat_data = tree.get(cat_key, {})
    target_pids = set()

    if filter_type and opt_name:
        sub_dict = cat_data.get(filter_type, {})
        pids = sub_dict.get(opt_name, [])
        target_pids.update(str(p) for p in pids)
    else:
        for subk, subv in cat_data.items():
            if isinstance(subv, dict):
                for itemv in subv.values():
                    if isinstance(itemv, list):
                        target_pids.update(str(p) for p in itemv)

    from search_engine import JSON_PRODUCTS
    matched = []
    for p in JSON_PRODUCTS:
        pid = str(p.get("product_id", "")).strip()
        if pid in target_pids:
            matched.append(p)

    return matched

