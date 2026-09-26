# -*- coding: utf-8 -*-
"""
aeg_service.py
ماژول اختصاصی و کاملاً مستقل همگام‌سازی و بارگذاری محصولات آاگ از سایت aegkala.com
- استخراج محصولات دارای قیمت (price > 0)
- دسته‌بندی هوشمند در زیرشاخه‌های یخچال، لباسشویی، ظرفشویی، فر توکار/مایکرویو، جاروبرقی/شارژی
- استخراج مشخصات فنی و تصاویر کیفیت بالا
- ذخیره در فایل محلی aeg_products.json و تزریق بدون تداخل به کاتالوگ و جستجوی ربات
"""

import os
import json
import base64
import logging
import urllib.request
import re
from typing import List, Dict, Any, Optional, Tuple

try:
    import config
    AEG_SITE_URL = getattr(config, "AEG_SITE_URL", "https://aegkala.com")
    AEG_CONSUMER_KEY = getattr(config, "AEG_CONSUMER_KEY", "ck_354a7bbd2855cad4f15db1080299b313ff8577f6")
    AEG_CONSUMER_SECRET = getattr(config, "AEG_CONSUMER_SECRET", "cs_8adb5c723f3b57974f88790fb516d13de33c5886")
    AEG_CAT_ID = getattr(config, "AEG_CAT_ID", 202)
except Exception:
    AEG_SITE_URL = "https://aegkala.com"
    AEG_CONSUMER_KEY = "ck_354a7bbd2855cad4f15db1080299b313ff8577f6"
    AEG_CONSUMER_SECRET = "cs_8adb5c723f3b57974f88790fb516d13de33c5886"
    AEG_CAT_ID = 202

logger = logging.getLogger(__name__)

AEG_PRODUCTS_FILE = "aeg_products.json"

AEG_SUBCATEGORIES_CONFIG = [
    {
        "key": "aeg_refrigerator",
        "title": "❄️ یخچال و ساید بای ساید آاگ",
        "keywords": ["یخچال", "ساید", "refrigerator", "fridge", "rmb"]
    },
    {
        "key": "aeg_washing",
        "title": "🧺 ماشین لباسشویی آاگ",
        "keywords": ["لباسشویی", "washing", "lr7", "lr8", "l9", "lf7"]
    },
    {
        "key": "aeg_dishwasher",
        "title": "🍽 ماشین ظرفشویی آاگ",
        "keywords": ["ظرفشویی", "dishwasher", "ffb", "ffe"]
    },
    {
        "key": "aeg_oven",
        "title": "♨️ فر توکار و مایکرویو آاگ",
        "keywords": ["فر", "مایکرویو", "ماکروویو", "ماکروفر", "oven", "microwave", "beb", "bpk", "bsk", "mbe"]
    },
    {
        "key": "aeg_vacuum",
        "title": "🧹 جاروبرقی و جاروشارژی آاگ",
        "keywords": ["جارو", "vacuum", "guard", "vx8", "ab61", "ab81"]
    },
    {
        "key": "aeg_other",
        "title": "📦 سایر لوازم خانگی آاگ",
        "keywords": []
    }
]

def determine_aeg_subcategory(product_name: str, categories_list: List[str]) -> Dict[str, str]:
    """تعیین دقیق و هوشمند زیرشاخه آاگ بر اساس نام و دسته‌بندی‌های سایت"""
    all_text = (product_name + " " + " ".join(categories_list)).lower()
    for sub in AEG_SUBCATEGORIES_CONFIG[:-1]:
        for kw in sub["keywords"]:
            if kw in all_text:
                return {"key": sub["key"], "title": sub["title"]}
    return {"key": "aeg_other", "title": "📦 سایر لوازم خانگی آاگ"}

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', raw_html)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def extract_advanced_aeg_specs(item: Dict[str, Any], sub_title: str) -> Dict[str, str]:
    """
    استخراج کامل، دقیق و بدون خطا مشخصات فنی و جدول ویژگی‌ها از توضیحات محصول ووکامرس
    شامل:
    ۱. پارس جداول HTML (مشخصات فنی استاندارد)
    ۲. پارس تگ‌های برجسته <strong> (ویژگی‌های کلیدی نظیر سنسورها، فیلترها، سطح صدا و ...)
    ۳. استخراج پارامترهای کلیدی (توان مکش/مصرفی، دسی‌بل صدا، ظرفیت، موتور، خشک‌کن)
    """
    raw_desc = item.get("description", "") or ""
    raw_short = item.get("short_description", "") or ""
    raw_html = (raw_short + "\n" + raw_desc).strip()
    pname = item.get("name", "").strip()

    specs = {
        "برند": "آاگ (AEG) اورجینال",
        "دسته‌بندی": sub_title,
        "اصالت و گارانتی": "تضمین ۱۰۰٪ اصالت کالا و گارانتی معتبر شرکتی"
    }

    # ۱. پارس ویژگی‌های تعریف شده در ووکامرس (Attributes)
    for attr in item.get("attributes", []):
        attr_name = attr.get("name", "").strip()
        attr_options = attr.get("options", [])
        if attr_name and attr_options:
            specs[attr_name] = ", ".join(attr_options)

    if not raw_html:
        return specs

    # ۲. استخراج جداول HTML (مانند جدول جامع مشخصات فنی لباسشویی و ظرفشویی و فر)
    import html as html_lib
    table_matches = re.findall(r'<table[^>]*>(.*?)</table>', raw_html, flags=re.I | re.DOTALL)
    for tbl in table_matches:
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, flags=re.I | re.DOTALL):
            tds = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', tr, flags=re.I | re.DOTALL)
            if len(tds) >= 2:
                k = html_lib.unescape(re.sub(r'<[^>]+>', '', tds[0]).strip())
                v = html_lib.unescape(re.sub(r'<[^>]+>', '', tds[1]).strip())
                if 2 < len(k) < 45 and 1 < len(v) < 150:
                    if not any(bad in k for bad in ["ردیف", "ویژگی", "مشخصات", "http"]):
                        if k not in specs:
                            specs[k] = v

    # ۳. استخراج عناوین برجسته <strong> حاوی دو نقطه یا نمادهای مشخصه فنی
    parts = re.split(r'<strong>(.*?)</strong>', raw_html, flags=re.I | re.DOTALL)
    bad_strong_keys = [
        "خرید", "فروش", "قیمت", "http", "مدل های محبوب", "تجربه نظافتی",
        "بیشترین کیفیت", "مزایای خرید", "ارزش خرید", "تضمین اصالت", "این محصول برای چه",
        "ویژگی‌های استثنایی", "شماره‌های مشاوره", "ارسال سریع", "aegkala", "aeg", "www.",
        "لباسشویی", "ظرفشویی", "جاروبرقی", "فر توکار", "مایکرویو"
    ]
    for i in range(1, len(parts), 2):
        raw_part = parts[i]
        # فقط عناوینی که واقعاً یک برچسب ویژگی هستند (دارای دو نقطه یا کلیدواژه مشخصه فنی)
        is_labeled_spec = (":" in raw_part or "：" in raw_part or any(w in raw_part for w in ["دسی‌بل", "دسی بل", "وات", "کیلو", "لیتر", "نفره", "A+++", "A++", "موتور", "سیستم", "فیلتر"]))
        if not is_labeled_spec:
            continue

        st_title = html_lib.unescape(re.sub(r'<[^>]+>', '', raw_part).strip()).rstrip(':： ')
        st_title = st_title.lstrip('•-▪️▫️🔹🔸✔✓* ')
        if any(b in st_title.lower() for b in bad_strong_keys) or len(st_title) > 35 or len(st_title) < 3:
            continue

        content = parts[i+1] if i+1 < len(parts) else ""
        content_clean = html_lib.unescape(re.sub(r'<[^>]+>', '\n', content).strip())
        val_lines = [l.strip().lstrip('•-▪️▫️🔹🔸✔✓* ') for l in content_clean.split('\n') if l.strip()]

        if any(w in st_title for w in ["دسی‌بل", "دسی بل", "وات", "کیلو", "لیتر", "نفره", "A+++", "A++"]):
            if "دسی" in st_title and "سطح صدا" not in specs:
                specs["سطح صدا"] = st_title
            elif "وات" in st_title and "توان مصرفی / مکش" not in specs:
                specs["توان مصرفی / مکش"] = st_title
            else:
                specs[st_title] = val_lines[0] if val_lines else "دارد"
        elif val_lines:
            val = val_lines[0]
            if len(val) < 130 and st_title not in specs:
                specs[st_title] = val

    # ۴. پالایش خط‌به‌خط برچسب‌های دو نقطه‌ای (Key: Value)
    clean = re.sub(r'<\s*br\s*/?>', '\n', raw_html, flags=re.I)
    clean = re.sub(r'</?(?:p|div|tr|li|h[1-6]|ul|ol|table|tbody)[^>]*>', '\n', clean, flags=re.I)
    clean = clean.replace('&nbsp;', ' ')
    clean = html_lib.unescape(clean)
    clean = re.sub(r'<[^>]+>', '', clean)

    lines = [l.strip() for l in clean.split('\n') if l.strip()]
    bad_keys = ["http", "خرید", "فروش", "قیمت", "تلفن", "شماره", "تماس", "آدرس", "مشاوره", "آاگ کالا", "ارسال", "پرداخت", "تضمین اصالت", "گارانتی کتبی"]

    for line in lines:
        line = line.lstrip('•-▪️▫️🔹🔸✔✓* ').strip()
        if len(line) < 3 or any(b in line for b in ["شماره‌های مشاوره", "پرداخت درب منزل", "ارسال سریع به سراسر", "تضمین اصالت کالا", "مزایای خرید از آاگ کالا"]):
            continue

        if (":" in line or "：" in line) and not line.startswith("http"):
            p_parts = re.split(r'[:：]', line, 1)
            k = p_parts[0].strip()
            v = p_parts[1].strip()
            if 2 < len(k) < 30 and 2 < len(v) < 130:
                if not any(bk in k for bk in bad_keys) and not any(bk in k for bk in ["www.", ".com", ".ir", "دارد", "است", "می باشد"]) and k not in specs:
                    specs[k] = v
        elif any(sym in line for sym in [" – ", " - "]):
            p_parts = re.split(r'[-–]', line, 1)
            k = p_parts[0].strip()
            v = p_parts[1].strip()
            if 3 < len(k) < 25 and 3 < len(v) < 110:
                if not any(bk in k for bk in bad_keys) and not any(bk in k for bk in ["www.", ".com", ".ir", "دارد", "است", "می باشد"]) and k not in specs:
                    specs[k] = v

    # ۵. استخراج مقادیر کلیدی از طریق الگوهای منظم در صورت عدم وجود
    all_text = pname + " " + clean
    m_sound = re.search(r'(\d{2}\s*دسی[‌\s]*بل)', all_text)
    if m_sound and not any("صدا" in k for k in specs):
        specs["سطح صدا"] = m_sound.group(1)

    m_watt = re.search(r'(\d{3,4}\s*وات)', all_text)
    if m_watt and not any("توان" in k or "وات" in k or "قدرت" in k for k in specs):
        specs["توان مصرفی / مکش"] = m_watt.group(1)

    m_cap = re.search(r'(\d{1,2}(?:\.\d+)?\s*(?:نفره|کیلو|کیلوگرم|لیتر|فوت))', all_text)
    if m_cap and not any("ظرفیت" in k for k in specs):
        specs["ظرفیت"] = m_cap.group(1)

    # ویژگی‌های خاص ظرفشویی
    if any(w in pname for w in ["ظرفشویی", "FFE", "FFB"]):
        if "Air Dray" in clean or "AirDry" in clean or "جریان هوا" in clean:
            specs["سیستم خشک‌کن"] = "جریان هوا (AirDry) بدون لک"
        if "Proclean" in clean or "ProClean" in clean:
            specs["تکنولوژی شستشو"] = "سیستم هوشمند ProClean"
        m_prog = re.search(r'(\d\s*برنامه[\sی]*شستشو)', clean)
        if m_prog and not any("برنامه" in k for k in specs):
            specs["برنامه‌های شستشو"] = m_prog.group(1)
        m_rack = re.search(r'(\d\s*کشو|\d\s*سبد)', clean)
        if m_rack and not any("سبد" in k or "کشو" in k for k in specs):
            specs["تعداد سبد / کشو"] = m_rack.group(1)

    # ویژگی‌های خاص فر و مایکرویو
    if any(w in pname for w in ["فر توکار", "مایکرویو", "BEB", "BPK", "BSK", "MBE"]):
        if "SteamBoost" in clean or "Steamify" in clean:
            specs["قابلیت بخارپز"] = "تکنولوژی انحصاری Steamify / SteamBoost"
        if "حسگر غذا" in clean or "سنسور غذا" in clean:
            specs["حسگر پخت"] = "دارد (سنسور اندازه‌گیری دمای عمق غذا)"

    return specs

def sync_aeg_products_from_api() -> Tuple[int, int, str]:
    """
    خواندن تمام محصولات دسته آاگ (ID: 202) از سایت aegkala.com
    فیلتر کردن فقط محصولاتی که قیمت معتبر دارند (price > 0)
    ذخیره در aeg_products.json و آماده‌سازی برای کاتالوگ
    خروجی: (تعداد کل دریافت شده، تعداد دارای قیمت، پیام گزارش)
    """
    auth_str = f"{AEG_CONSUMER_KEY}:{AEG_CONSUMER_SECRET}"
    auth_header = base64.b64encode(auth_str.encode()).decode()

    all_raw_products = []
    page = 1
    while True:
        url = f"{AEG_SITE_URL}/wp-json/wc/v3/products?category={AEG_CAT_ID}&per_page=100&page={page}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Basic {auth_header}",
                "User-Agent": "AiKalaBot/1.0 (Linux; Telegram Bot)"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode())
                if not data:
                    break
                all_raw_products.extend(data)
                page += 1
        except Exception as e:
            logger.warning(f"Error fetching page {page} from AEG API: {e}")
            break

    if not all_raw_products:
        return 0, 0, "❌ پاسخی از سرور وب‌سایت دریافت نشد یا کلیدها نامعتبر است."

    formatted_products = []
    for item in all_raw_products:
        raw_price = item.get("price")
        try:
            price_int = int(float(str(raw_price).strip())) if raw_price else 0
        except Exception:
            price_int = 0

        # شرط اصلی: حتماً قیمت‌خورده و موجود باشد
        if price_int <= 0:
            continue

        wp_id = str(item.get("id"))
        pname = item.get("name", "").strip()
        cats = [c.get("name", "") for c in item.get("categories", [])]
        sub_info = determine_aeg_subcategory(pname, cats)

        # استخراج تصاویر و آلبوم کامل کالا از وب‌سایت
        images = [img.get("src", "") for img in item.get("images", []) if img.get("src")]
        main_img = images[0] if images else ""

        # ساخت مشخصات فنی پیشرفته و کامل از توضیحات و جداول وب‌سایت
        specs = extract_advanced_aeg_specs(item, sub_info["title"])

        prod_dict = {
            "product_id": f"AEG_{wp_id}",
            "wp_id": wp_id,
            "name": pname,
            "title": pname,
            "brand": "آاگ",
            "category_key": "aeg",
            "category": "محصولات آاگ/AEG",
            "category_name": "محصولات آاگ/AEG",
            "subcategory": sub_info["title"],
            "subcategory_key": sub_info["key"],
            "price": price_int,
            "price_formatted": f"{price_int:,} تومان",
            "stock_status": item.get("stock_status", "instock"),
            "image_url": main_img,
            "images": images,
            "permalink": item.get("permalink", ""),
            "specs": specs,
            "score": "۹.۸"
        }
        formatted_products.append(prod_dict)

    # ذخیره در فایل محلی
    try:
        with open(AEG_PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump(formatted_products, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving AEG products file: {e}")

    # ثبت خودکار تصاویر باکیفیت و رسمی وب‌سایت در سیستم آلبوم تصاویر ربات (photo_service)
    try:
        from photo_service import save_verified_product_entry
        for prod in formatted_products:
            prod_imgs = prod.get("images", [])
            if not prod_imgs and prod.get("image_url"):
                prod_imgs = [prod.get("image_url")]
            if prod_imgs:
                pid = prod.get("product_id")
                pname = prod.get("name")
                save_verified_product_entry(
                    pid=pid,
                    product_name=pname,
                    channel="aegkala.com",
                    message_ids=[],
                    file_ids=prod_imgs,
                    link=prod.get("permalink", ""),
                    brand="آاگ",
                    category=prod.get("subcategory", "لوازم خانگی آاگ"),
                    caption=f"محصول رسمی آاگ: {pname}"
                )
    except Exception as e:
        logger.warning(f"Note on auto-registering AEG photos to photo_service: {e}")

    return len(all_raw_products), len(formatted_products), f"✅ همگام‌سازی موفق: تعداد {len(formatted_products)} محصول دارای قیمت آاگ همراه با تصاویر و مشخصات فنی کامل ثبت شد."

def load_aeg_products() -> List[Dict[str, Any]]:
    """خواندن لیست ذخیره‌شده محصولات آاگ از فایل محلی"""
    if os.path.exists(AEG_PRODUCTS_FILE):
        try:
            with open(AEG_PRODUCTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Error loading {AEG_PRODUCTS_FILE}: {e}")
    return []
