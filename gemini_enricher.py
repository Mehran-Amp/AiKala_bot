# -*- coding: utf-8 -*-
"""
gemini_enricher.py
==================
موتور مدیریت هوشمند مشخصات فنی محصولات با قابلیت تنظیم در پنل ادمین
(Google Gemini / DeepSeek / خاموش)
کاملاً تقاضامحور (On-Demand / Lazy):
۱. فقط در صورت کلیک کاربر روی کارت یا پست محصول اجرا می‌شود.
۲. مشخصات ۱۰۰٪ منطبق با نام، برند و کد مدل دقیق کالا جهت جلوگیری از اطلاعات الکی و غیرواقعی استخراج می‌شود.
۳. مشخصات استخراج‌شده «یکبار برای همیشه» در کاتالوگ و دیتابیس ذخیره می‌شود.
۴. امکان تغییر موتور (جمینای، دیپ‌سیک یا خاموش) از طریق پنل مدیریت ربات.
"""

import os
import io
import re
import json
import sqlite3
import time
import asyncio
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger("AIEnricher")

CATALOG_FILE = "catalog_products.json"
DB_FILE = "bot_data.db"
AI_SETTINGS_FILE = "ai_settings.json"

# تنظیمات پیش‌فرض مدل‌ها
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
FALLBACK_GEMINI_MODEL = "gemini-2.5-flash"
EXTRA_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
FALLBACK_DEEPSEEK_MODEL = "deepseek-reasoner"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# کلیدهای نامعتبر و آزمایشی سندباکس جهت جلوگیری از خطای ۴۰۰ کاذب
DUMMY_KEYS = {
    "AIzaSyA9sNhKxkCbyL5ic04jd3RDN8POy6V2rxc",
    "your_api_key_here",
    "YOUR_GEMINI_API_KEY",
    "YOUR_DEEPSEEK_API_KEY",
}

# ─── مدیریت تنظیمات هوش مصنوعی (Gemini / DeepSeek / Off) ───

def get_ai_settings() -> dict:
    """دریافت تنظیمات فعلی هوش مصنوعی از فایل یا مقدار پیش‌فرض"""
    default_settings = {
        "provider": "gemini",  # gemini | deepseek | off
        "gemini_model": DEFAULT_GEMINI_MODEL,
        "deepseek_model": DEFAULT_DEEPSEEK_MODEL,
        "gemini_api_key": "",
        "deepseek_api_key": "",
        "updated_at": ""
    }
    if os.path.exists(AI_SETTINGS_FILE):
        try:
            with open(AI_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_settings.update({k: v for k, v in saved.items() if v is not None})
        except Exception as e:
            logger.debug(f"Error loading AI settings: {e}")
    return default_settings

def set_ai_provider(provider: str) -> bool:
    """تغییر موتور فعال هوش مصنوعی (gemini, deepseek, off)"""
    clean_provider = provider.lower().strip()
    if clean_provider not in ["gemini", "deepseek", "off", "disabled"]:
        return False
    if clean_provider == "disabled":
        clean_provider = "off"

    settings = get_ai_settings()
    settings["provider"] = clean_provider
    try:
        import datetime
        settings["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(AI_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        logger.info(f"🔧 [AI SETTINGS] موتور فعال هوش مصنوعی به '{clean_provider}' تغییر یافت.")
        return True
    except Exception as e:
        logger.error(f"Error saving AI settings: {e}")
        return False

def get_active_provider_label() -> str:
    """عنوان فارسی و نشانگر موتور فعال هوش مصنوعی"""
    provider = get_ai_settings().get("provider", "gemini")
    if provider == "gemini":
        return "♊️ گوگل جمینای (Google Gemini) - فعال"
    elif provider == "deepseek":
        return "🤖 دیپ‌سیک (DeepSeek) - فعال"
    else:
        return "🛑 خاموش (غیرفعال)"

# ─── دریافت و ذخیره امن کلیدهای API ───

def _update_env_file(key_name: str, value: str):
    """ذخیره یا به‌روزرسانی متغیر در فایل .env"""
    env_path = os.path.join(os.getcwd(), ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                if line.strip().startswith(f"{key_name}="):
                    new_lines.append(f'{key_name}="{value}"\n')
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f'{key_name}="{value}"\n')
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return
        except Exception:
            pass

    try:
        with open(env_path, "a", encoding="utf-8") as f:
            f.write(f'{key_name}="{value}"\n')
    except Exception:
        pass

def save_ai_api_key(provider: str, key: str) -> bool:
    """ذخیره کلید API برای Gemini یا DeepSeek در تنظیمات و متغیر محیطی"""
    clean_provider = provider.lower().strip()
    clean_key = key.strip().strip('"').strip("'")
    settings = get_ai_settings()

    if clean_provider == "gemini":
        settings["gemini_api_key"] = clean_key
        if clean_key:
            os.environ["GEMINI_API_KEY"] = clean_key
        else:
            os.environ.pop("GEMINI_API_KEY", None)
        _update_env_file("GEMINI_API_KEY", clean_key)
    elif clean_provider == "deepseek":
        settings["deepseek_api_key"] = clean_key
        if clean_key:
            os.environ["DEEPSEEK_API_KEY"] = clean_key
        else:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        _update_env_file("DEEPSEEK_API_KEY", clean_key)
    else:
        return False

    try:
        import datetime
        settings["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(AI_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        logger.info(f"🔑 [AI KEY SAVED] کلید API برای '{clean_provider}' با موفقیت ذخیره شد.")
        return True
    except Exception as e:
        logger.error(f"Error saving AI key: {e}")
        return False

def _read_key_from_env_files(key_name: str) -> str:
    """جستجوی کلید در فایل‌های .env مسیر پروژه"""
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        ".env"
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.startswith(f"{key_name}="):
                            _, val = line.split("=", 1)
                            clean_val = val.strip().strip('"').strip("'")
                            if clean_val and not clean_val.startswith("MY_") and clean_val not in DUMMY_KEYS:
                                os.environ[key_name] = clean_val
                                return clean_val
            except Exception:
                pass
    return ""

def get_gemini_api_key() -> str:
    """دریافت کلید API معتبر جمینای"""
    # ۱. اولویت نخست: تنظیمات ذخیره شده توسط ادمین در ai_settings.json
    settings = get_ai_settings()
    custom_key = str(settings.get("gemini_api_key") or "").strip()
    if custom_key and custom_key not in DUMMY_KEYS and not custom_key.startswith("MY_") and len(custom_key) >= 15:
        return custom_key

    # ۲. فایل‌های .env
    file_key = _read_key_from_env_files("GEMINI_API_KEY")
    if file_key and file_key not in DUMMY_KEYS:
        return file_key

    # ۳. متغیر محیطی سیستم (در صورت معتبر بودن و ساختگی نبودن)
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key and env_key not in DUMMY_KEYS and not env_key.startswith("MY_") and len(env_key) >= 15:
        return env_key

    # ۴. فایل تنظیمات config.py
    try:
        import config
        c_key = getattr(config, "GEMINI_API_KEY", "").strip()
        if c_key and c_key not in DUMMY_KEYS and not c_key.startswith("MY_"):
            return c_key
    except Exception:
        pass

    return ""

def get_deepseek_api_key() -> str:
    """دریافت کلید API معتبر دیپ‌سیک"""
    # ۱. اولویت نخست: تنظیمات ذخیره شده توسط ادمین در ai_settings.json
    settings = get_ai_settings()
    custom_key = str(settings.get("deepseek_api_key") or "").strip()
    if custom_key and custom_key not in DUMMY_KEYS and not custom_key.startswith("MY_") and len(custom_key) >= 15:
        return custom_key

    # ۲. فایل‌های .env
    file_key = _read_key_from_env_files("DEEPSEEK_API_KEY")
    if file_key and file_key not in DUMMY_KEYS:
        return file_key

    # ۳. متغیر محیطی سیستم
    env_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if env_key and env_key not in DUMMY_KEYS and not env_key.startswith("MY_"):
        return env_key

    try:
        import config
        c_key = getattr(config, "DEEPSEEK_API_KEY", "").strip()
        if c_key and c_key not in DUMMY_KEYS and not c_key.startswith("MY_"):
            return c_key
    except Exception:
        pass

    return ""

# کلیدهایی که صرفاً اطلاعات جانبی، دسته‌بندی یا گارانتی هستند و مشخصه فنی کارخانه‌ای به شمار نمی‌روند
NON_SPEC_KEYS = {
    "زیرشاخه", "دسته‌بندی", "دسته", "امتیاز کیفی", "امتیاز",
    "ضمانت اصالت", "گارانتی", "گارانتی و مهلت تست", "مهلت تست و تعویض"
}

# ─── بررسی وجود مشخصات در کالا (Zero Delay / 0 Latency) ───

def count_product_technical_specs(p: dict) -> int:
    """
    شمارش دقیق تعداد مشخصات فنی معتبر کالا (بدون احتساب رنگ، قیمت، امتیاز و گارانتی).
    """
    if not p or not isinstance(p, dict):
        return 0

    found_keys = set()
    banned_prefixes = ("رنگ", "color", "colour", "قیمت", "price", "گارانتی", "ضمانت", "امتیاز", "دسته", "زیرشاخه", "عکس", "تصویر")

    # ۱. بررسی ai_specs
    ai_specs = p.get("ai_specs")
    if isinstance(ai_specs, str):
        try:
            ai_specs = json.loads(ai_specs)
        except Exception:
            ai_specs = {}
    if isinstance(ai_specs, dict):
        for k, v in ai_specs.items():
            k_c = str(k).strip()
            v_c = str(v).strip()
            if not k_c or not v_c:
                continue
            if k_c in NON_SPEC_KEYS:
                continue
            if any(b in k_c.lower() for b in banned_prefixes):
                continue
            if "رنگ" in v_c or "color" in v_c.lower():
                continue
            found_keys.add(k_c)

    # ۲. بررسی specs
    specs = p.get("specs")
    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except Exception:
            specs = {}
    if isinstance(specs, dict):
        for k, v in specs.items():
            k_c = str(k).strip()
            v_c = str(v).strip()
            if not k_c or not v_c:
                continue
            if k_c in NON_SPEC_KEYS:
                continue
            if any(b in k_c.lower() for b in banned_prefixes):
                continue
            if "رنگ" in v_c or "color" in v_c.lower():
                continue
            found_keys.add(k_c)

    # ۳. فیلدهای مستقیم کاتالوگ (در صورت عدم وجود شیء مشخصات)
    if len(found_keys) == 0:
        meaningful_fields = [
            ("assembly", "کشور مونتاژ"), ("resolution", "کیفیت تصویر"), ("panel", "نوع پنل"),
            ("refresh_rate", "نرخ نوسازی"), ("os", "سیستم عامل"), ("capacity_btu", "ظرفیت کولر"),
            ("temp_range", "شرایط آب و هوایی"), ("room_size", "پوشش فضا"), ("energy_consumption", "مصرف انرژی"),
            ("plan", "طرح بدنه"), ("capacity_foot", "ظرفیت به فوت"), ("num_doors", "تعداد درب"),
            ("capacity_kg", "ظرفیت شستشو"), ("baskets", "تعداد سبد"), ("key_features", "ویژگی‌ها"),
            ("cpu", "پردازنده"), ("ram", "رم"), ("gpu", "گرافیک"), ("power", "توان مصرفی"),
            ("capacity", "ظرفیت"), ("blade", "جنس تیغه")
        ]
        for field_key, field_name in meaningful_fields:
            val = p.get(field_key)
            if val is not None and str(val).strip():
                found_keys.add(field_name)

    return len(found_keys)

def get_products_for_batch_enrich(mode: str) -> List[dict]:
    """
    دریافت لیست کالاهای واجد شرایط جهت تکمیل گروهی مشخصات فنی:
    - mode == 'no_specs': کالاهای کاملاً فاقد مشخصات فنی (0 مشخصه)
    - mode == 'under_3': کالاهای دارای مشخصات ناقص یا ناکافی (۳ مشخصه و کمتر: 0، 1، 2 و 3 مشخصه)
    """
    catalog_items = []
    if os.path.exists(CATALOG_FILE):
        try:
            with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                catalog_items = list(data.values())
            elif isinstance(data, list):
                catalog_items = data
        except Exception as e:
            logger.error(f"Error reading {CATALOG_FILE}: {e}")

    if not catalog_items:
        try:
            from search_engine import JSON_PRODUCTS
            catalog_items = list(JSON_PRODUCTS)
        except Exception:
            catalog_items = []

    targets = []
    for item in catalog_items:
        if not isinstance(item, dict):
            continue
        c = count_product_technical_specs(item)
        if mode == "no_specs" and c == 0:
            targets.append(item)
        elif mode == "under_3" and c <= 3:
            targets.append(item)

    return targets

def get_batch_specs_counts() -> Tuple[int, int, int]:
    """محاسبه تعداد کالاهای بدون مشخصات (0)، ناقص (۳ مشخصه و کمتر) و کل کاتالوگ"""
    catalog_items = []
    if os.path.exists(CATALOG_FILE):
        try:
            with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                catalog_items = list(data.values())
            elif isinstance(data, list):
                catalog_items = data
        except Exception:
            pass
    if not catalog_items:
        try:
            from search_engine import JSON_PRODUCTS
            catalog_items = list(JSON_PRODUCTS)
        except Exception:
            pass

    no_specs = 0
    under_3 = 0
    for item in catalog_items:
        if isinstance(item, dict):
            c = count_product_technical_specs(item)
            if c == 0:
                no_specs += 1
            if c <= 3:
                under_3 += 1

    return no_specs, under_3, len(catalog_items)

def product_has_specs(product: dict) -> bool:
    """
    بررسی اینکه آیا کالا از قبل مشخصات فنی واقعی، کافی و معتبر دارد یا خیر.
    نکته: مواردی مانند زیرشاخه، امتیاز کیفی، ضمانت اصالت و گارانتی جزء مشخصات فنی محصول نیستند
    و حضور آنها مانع از استعلام هوش مصنوعی نخواهد شد.
    کالاهایی که ۳ مشخصه یا کمتر دارند مشمول تکمیل مشخصات هوشمند می‌شوند (> 3 کافی در نظر گرفته می‌شود).
    """
    if not product or not isinstance(product, dict):
        return True

    return count_product_technical_specs(product) > 3

# ─── تولید پرامپت با تاکید موکد بر مدل دقیق جهت جلوگیری از مشخصات فیک و حذف قطعی رنگ ───

def build_grounded_specs_prompt(product: dict) -> str:
    """
    پرامپت تخصصی و فوق‌العاده سخت‌گیرانه برای استخراج منحصراً مشخصات واقعی کارخانه‌ای
    بر اساس نام کالا، برند و کد مدل دقیق با حذف قطعی رنگ و ممانعت از اطلاعات اشتباه.
    """
    name = str(product.get("name") or "").strip()
    brand = str(product.get("brand") or "").strip()
    model = str(product.get("model_number") or "").strip()
    subcat = str(product.get("subcategory") or "").strip()
    cat = str(product.get("category_name") or product.get("category_key") or "").strip()

    prompt = (
        f"تو کارشناس ارشد و متخصص فنی دیتاشیت کاتالوگ لوازم خانگی، صوتی‌تصویری و دیجیتال هستی.\n\n"
        f"کالای مورد نظر برای استخراج مشخصات فنی رسمی کارخانه:\n"
        f"▫️ نام کامل محصول: «{name}»\n"
        f"▫️ برند سازنده: «{brand}»\n"
        f"▫️ کد مدل دقیق: «{model}»\n"
        f"{f'▫️ نوع کالا: «{subcat}»' if subcat else ''}\n"
        f"{f'▫️ دسته‌بندی: «{cat}»' if cat else ''}\n\n"
        f"⚠️ دستورات و الزامات بسیار حیاتی (عدم رعایت هرکدام تخلف جدی است):\n"
        f"۱. مشخصات فنی باید منحصراً و ۱۰۰٪ مربوط به همین محصول و همین کد مدل دقیق («{model}») باشد. خریدار بر اساس این اطلاعات تصمیم‌گیری و هزینه پرداخت می‌کند؛ بنابراین تحت هیچ شرایطی اطلاعات اشتباه، حدسی یا عمومی نده. اگر درباره ویژگی خاصی از این کد مدل اطمینان ۱۰۰٪ نداری، آن را کلاً نیاور.\n"
        f"۲. اطلاعات به‌هیچ‌وجه و تحت هیچ شرایطی نباید شامل رنگ، رنگ‌بندی، یا تنوع رنگ محصول باشد (رنگ جزء مشخصات فنی کارخانه‌ای مدنظر ما نیست و ذکر رنگ چه در کلید و چه در مقدار کاملاً ممنوع است).\n"
        f"۳. مقادیر باید کاملاً فنی، مستند و همراه با عدد و واحد اندازه‌گیری رسمی باشند (مانند توان مصرفی به وات W، گنجایش یا حجم به لیتر L یا کیلوگرم kg، رفرش ریت به هرتز Hz، نوع پنل، سیستم‌عامل، نوع موتور اینورتر، کشور مونتاژ و سازنده، مشخصات پردازنده و رم).\n"
        f"۴. عبارات کیفی و مبهم کلی مانند 'عالی'، 'خوب'، 'دارد'، 'قوی'، 'مناسب' بدون عدد و مشخصه دقیق ممنوع است.\n"
        f"۵. از ذکر قیمت، گارانتی، ضمانت، شرایط خرید یا کلمات تبلیغاتی اکیداً خودداری کن.\n"
        f"۶. فقط ۳ تا ۶ ویژگی فنی کلیدی، موثق و قطعی را به صورت یک شیء JSON با کلید و مقدار متنی فارسی برگردان.\n\n"
        f"نمونه ساختار استاندارد مورد انتظار:\n"
        f'{{"توان مصرفی": "۲۲۰۰ وات", "ظرفیت مخزن": "۴ لیتر", "نوع موتور": "اینورتر خطی دیجیتال", "نوع فیلتر": "فیلتر بهداشتی HEPA 13", "کشور سازنده": "لهستان"}}'
    )
    return prompt

def _validate_and_filter_specs(raw_dict: dict) -> Optional[Dict[str, str]]:
    """فیلتر و اعتبارسنجی دقیق مشخصات برای تضمین فنی، غیرالکی بودن و حذف قطعی رنگ و قیمت"""
    if not isinstance(raw_dict, dict):
        return None

    banned_keywords = [
        "قیمت", "رنگ", "color", "colour", "خرید", "تومان", "ریال",
        "گارانتی", "ضمانت", "تخفیف", "فروش", "امتیاز", "دسته", "زیرشاخه",
        "کد کالا", "شناسه", "عکس", "تصویر", "سایز"
    ]
    color_names = [
        "مشکی", "سفید", "نقره‌ای", "نقره ای", "سیلور", "دودی", "طوسی", "خاکستری",
        "قرمز", "آبی", "زرد", "سبز", "طلایی", "رزگلد", "استیل", "تیتانیوم", "نوک مدادی",
        "black", "white", "silver", "gray", "grey", "gold", "red", "blue"
    ]
    vague_values = ["بله", "دارد", "خوب", "عالی", "مناسب", "بسیار خوب", "قوی", "کیفیت بالا", "موجود", "ندارد", "ok", "yes"]

    specs = {}
    for k, v in raw_dict.items():
        k_clean = str(k).strip().lstrip("-*▫️• ")
        v_clean = str(v).strip()

        # ۱. بررسی کلمات ممنوعه در کلید (از جمله رنگ، قیمت، گارانتی)
        k_lower = k_clean.lower()
        if any(b in k_lower for b in banned_keywords):
            continue

        # ۲. بررسی اینکه آیا مقدار کلاً بیانگر رنگ است یا کلمه رنگ دارد
        v_lower = v_clean.lower()
        if "رنگ" in v_clean or "color" in v_lower:
            continue
        if v_lower in [c.lower() for c in color_names]:
            continue

        # ۳. بررسی مقادیر مبهم و بدون محتوای فنی
        if v_clean in vague_values or len(v_clean) < 2:
            continue

        if len(k_clean) < 40 and len(v_clean) < 130:
            specs[k_clean] = v_clean

    return specs if len(specs) >= 2 else None

def _parse_ai_json_response(raw_text: str) -> Optional[Dict[str, str]]:
    """پارس امن خروجی هوش مصنوعی به صورت شیء مشخصات معتبر"""
    if not raw_text:
        return None

    cleaned_text = raw_text.strip()
    if "```" in cleaned_text:
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned_text)
        if m:
            cleaned_text = m.group(1).strip()

    try:
        data = json.loads(cleaned_text)
        if isinstance(data, dict):
            filtered = _validate_and_filter_specs(data)
            if filtered:
                return filtered
    except Exception:
        pass

    # روش پشتیبان خط‌به‌خط
    specs = {}
    for line in cleaned_text.split("\n"):
        line = line.strip().lstrip("-*▫️•#▪️ ")
        line = re.sub(r'^\s*[\d۰-۹]+[\.\-\)\s]+\s*', '', line)
        clean_line = line.replace("**", "").replace("__", "").strip()
        if ":" in clean_line:
            parts = clean_line.split(":", 1)
            k = parts[0].strip()
            v = parts[1].strip()
            specs[k] = v

    return _validate_and_filter_specs(specs)

# ─── فراخوانی Gemini API ───

def call_gemini_api_with_error(api_key: str, product: dict) -> Tuple[Optional[Dict[str, str]], str]:
    """فراخوانی جمینای با تنظیم دما روی 0.1 جهت بیشترین انطباق و کمترین خطا با گزارش ارور"""
    if not api_key:
        return None, "کلید GEMINI_API_KEY تنظیم نشده است."

    prompt = build_grounded_specs_prompt(product)
    pname = product.get("name", "")
    last_error = "پاسخی از مدل دریافت نشد."

    models_to_try = [
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-flash-latest"
    ]
    models_to_try = list(dict.fromkeys(models_to_try))

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payloads = [
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 600,
                    "responseMimeType": "application/json"
                }
            }
        ]

        model_exhausted = False
        for payload in payloads:
            if model_exhausted:
                break
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=9.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        continue
                    raw_text = parts[0].get("text", "")
                    specs = _parse_ai_json_response(raw_text)
                    if specs:
                        logger.info(f"✅ [GEMINI AI] مشخصات دقیق '{pname}' با موفقیت از مدل {model_name} استخراج شد.")
                        return specs, ""
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {he.code}: {err_body[:180]}"
                logger.warning(f"⚠️ [GEMINI HTTP {he.code}] Model {model_name}: {err_body[:180]}")
                if he.code in [400, 403] and ("API key not valid" in err_body or "API_KEY_INVALID" in err_body):
                    return None, f"کلید API نامعتبر است (HTTP {he.code})"
                if he.code == 429:
                    last_error = f"سهمیه مدل {model_name} تکمیل است (Rate Limit 429)."
                    model_exhausted = True
                    break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ [GEMINI ERROR] Model {model_name} for '{pname}': {e}")

    return None, last_error

def call_gemini_api(api_key: str, product: dict) -> Optional[Dict[str, str]]:
    """فراخوانی جمینای جهت سازگاری کامل با توابع قبلی"""
    specs, _ = call_gemini_api_with_error(api_key, product)
    return specs

# ─── فراخوانی DeepSeek API ───

def call_deepseek_api_with_error(api_key: str, product: dict) -> Tuple[Optional[Dict[str, str]], str]:
    """فراخوانی دیپ‌سیک با پرامپت دقیق منطبق بر مدل با گزارش ارور"""
    if not api_key:
        return None, "کلید DEEPSEEK_API_KEY تنظیم نشده است."

    prompt = build_grounded_specs_prompt(product)
    pname = product.get("name", "")

    endpoint = f"{DEFAULT_DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"
    models_to_try = [DEFAULT_DEEPSEEK_MODEL, FALLBACK_DEEPSEEK_MODEL]
    last_error = "پاسخی از مدل دریافت نشد."

    for model_name in models_to_try:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "تو متخصص فنی کاتالوگ لوازم خانگی هستی. خروجی فقط یک شیء JSON با مشخصات فنی واقعی کارخانه است."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 600,
            "temperature": 0.1,
            "stream": False
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=9.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                content = (choice.get("message", {}).get("content") or "").strip()
                reasoning = (choice.get("message", {}).get("reasoning_content") or "").strip()
                if not content and reasoning:
                    content = reasoning
                specs = _parse_ai_json_response(content)
                if specs:
                    logger.info(f"✅ [DEEPSEEK AI] مشخصات دقیق '{pname}' با موفقیت از مدل {model_name} استخراج شد.")
                    return specs, ""
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            last_error = f"HTTP {he.code}: {err_body[:180]}"
            logger.warning(f"⚠️ [DEEPSEEK HTTP {he.code}] Model {model_name}: {err_body[:180]}")
            if he.code in [401, 403]:
                return None, f"کلید DeepSeek نامعتبر است (HTTP {he.code})"
        except Exception as e:
            last_error = str(e)
            logger.warning(f"⚠️ [DEEPSEEK ERROR] for '{pname}': {e}")

    return None, last_error

def call_deepseek_api(api_key: str, product: dict) -> Optional[Dict[str, str]]:
    """فراخوانی دیپ‌سیک جهت سازگاری با توابع قبلی"""
    specs, _ = call_deepseek_api_with_error(api_key, product)
    return specs

# ─── تست زنده اتصال هوش مصنوعی ───

def test_ai_connection(provider: Optional[str] = None) -> Tuple[bool, str, float]:
    """تست زنده اتصال به هوش مصنوعی (Google Gemini یا DeepSeek)"""
    import time
    start_t = time.time()

    settings = get_ai_settings()
    active_p = (provider or settings.get("provider", "gemini")).lower().strip()

    if active_p in ["off", "disabled"]:
        return False, "موتور هوش مصنوعی در پنل خاموش است.", 0.0

    test_product = {
        "name": "تلویزیون 55 اینچ ال جی مدل C3",
        "brand": "ال جی",
        "model_number": "OLED55C3",
        "category_name": "تلویزیون"
    }

    if active_p == "gemini":
        key = get_gemini_api_key()
        if not key:
            return False, "کلید GEMINI_API_KEY تنظیم نشده است یا نامعتبر است. لطفاً از دکمه «🔑 ثبت / ویرایش کلید Gemini» کلید معتبر را وارد فرمایید.", 0.0

        specs, err = call_gemini_api_with_error(key, test_product)
        elapsed = round(time.time() - start_t, 2)
        if specs:
            sample_specs = " | ".join([f"{k}: {v}" for k, v in list(specs.items())[:3]])
            return True, f"اتصال به Google Gemini کاملاً برقرار است! (زمان پاسخ: {elapsed} ثانیه)\nنمونه مشخصات استخراج شده:\n{sample_specs}", elapsed
        else:
            return False, f"خطا در ارتباط با Gemini: {err}", elapsed

    elif active_p == "deepseek":
        key = get_deepseek_api_key()
        if not key:
            return False, "کلید DEEPSEEK_API_KEY تنظیم نشده است. لطفاً از دکمه «🔑 ثبت / ویرایش کلید DeepSeek» کلید وارد فرمایید.", 0.0

        specs, err = call_deepseek_api_with_error(key, test_product)
        elapsed = round(time.time() - start_t, 2)
        if specs:
            sample_specs = " | ".join([f"{k}: {v}" for k, v in list(specs.items())[:3]])
            return True, f"اتصال به DeepSeek کاملاً برقرار است! (زمان پاسخ: {elapsed} ثانیه)\nنمونه مشخصات استخراج شده:\n{sample_specs}", elapsed
        else:
            return False, f"خطا در ارتباط با DeepSeek: {err}", elapsed

    return False, f"ارائه‌دهنده نامشخص: {active_p}", 0.0

# ─── ذخیره‌سازی دائمی یکبار برای همیشه ───

def sync_save_ai_specs(pid: str, specs: dict):
    """ذخیره دائمی مشخصات در catalog_products.json و bot_data.db"""
    if not pid or not specs:
        return

    spec_str = " | ".join([f"{k}: {v}" for k, v in specs.items()])

    # ۱. ذخیره در کاتالوگ JSON
    try:
        if os.path.exists(CATALOG_FILE):
            with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated = False
            if isinstance(data, dict):
                if pid in data:
                    data[pid]["ai_specs"] = specs
                    data[pid]["more_details"] = spec_str
                    updated = True
                else:
                    for _, v in data.items():
                        if str(v.get("product_id")) == str(pid):
                            v["ai_specs"] = specs
                            v["more_details"] = spec_str
                            updated = True
                            break
            elif isinstance(data, list):
                for item in data:
                    if str(item.get("product_id")) == str(pid):
                        item["ai_specs"] = specs
                        item["more_details"] = spec_str
                        updated = True
                        break

            if updated:
                with open(CATALOG_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"💾 [AI DISK SAVED] مشخصات کالا {pid} برای همیشه در کاتالوگ ذخیره شد.")
    except Exception as e:
        logger.error(f"Error saving AI specs for {pid} to JSON: {e}")

    # ۲. ذخیره در جدول SQLite
    try:
        if os.path.exists(DB_FILE):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            specs_json = json.dumps(specs, ensure_ascii=False)
            cursor.execute("""
                UPDATE products
                SET specs_json = ?, more_details = ?, updated_at = CURRENT_TIMESTAMP
                WHERE product_id = ?
            """, (specs_json, spec_str, pid))
            conn.commit()
            conn.close()
            logger.info(f"💾 [AI DB SAVED] مشخصات کالا {pid} در جدول دیتابیس SQLite ثبت شد.")
    except Exception as e:
        logger.error(f"Error saving AI specs for {pid} to SQLite: {e}")

# ─── روال اصلی On-Demand با مدیریت ارائه‌دهنده فعال ───

async def async_enrich_product_with_gemini_on_demand(
    product: dict,
    force: bool = False,
    return_error: bool = False
) -> Any:
    """
    روال آن‌دیمند یکپارچه:
    ۱. بررسی وضعیت هوش مصنوعی (خاموش/روشن، جمینای یا دیپ‌سیک)
    ۲. بررسی اینکه آیا کالا از قبل مشخصات دارد؟ (در صورت داشتن مشخصات ۰ معطلی، مگر اینکه force=True باشد)
    ۳. استخراج منحصراً مشخصات واقعی کارخانه‌ای مدل
    ۴. ذخیره‌سازی دائمی یکبار برای همیشه
    """
    if not product or not isinstance(product, dict):
        return (False, "اطلاعات کالا معتبر نیست") if return_error else False

    # بررسی تنظیمات فعال ادمین
    ai_settings = get_ai_settings()
    provider = ai_settings.get("provider", "gemini")

    if provider in ["off", "disabled"]:
        logger.debug("AI specs enrichment is currently disabled by admin.")
        return (False, "هوش مصنوعی در تنظیمات پنل ادمین خاموش است.") if return_error else False

    # بررسی اولیه مشخصات کالا (در صورت force بودن بازنویسی می‌شود)
    if not force and product_has_specs(product):
        return (False, "کالا از قبل دارای مشخصات فنی کامل است.") if return_error else False

    pname = product.get("name", "")
    if not pname:
        return (False, "نام کالا خالی است.") if return_error else False

    specs = None
    err_detail = ""

    if provider == "gemini":
        api_key = get_gemini_api_key()
        if not api_key:
            err_msg = "کلید GEMINI_API_KEY تنظیم نشده یا نامعتبر است."
            logger.debug(err_msg)
            return (False, err_msg) if return_error else False
        logger.info(f"🤖 [GEMINI LAZY] استعلام مشخصات موثق برای: '{pname}'...")
        try:
            specs, err_detail = await asyncio.wait_for(
                asyncio.to_thread(call_gemini_api_with_error, api_key, product),
                timeout=8.5
            )
        except Exception as e:
            logger.warning(f"Gemini on-demand note for '{pname}': {e}")
            return (False, f"تایم‌اوت یا خطای شبکه: {e}") if return_error else False

    elif provider == "deepseek":
        api_key = get_deepseek_api_key()
        if not api_key:
            err_msg = "کلید DEEPSEEK_API_KEY تنظیم نشده است."
            logger.debug(err_msg)
            return (False, err_msg) if return_error else False
        logger.info(f"🤖 [DEEPSEEK LAZY] استعلام مشخصات موثق برای: '{pname}'...")
        try:
            specs, err_detail = await asyncio.wait_for(
                asyncio.to_thread(call_deepseek_api_with_error, api_key, product),
                timeout=10.0
            )
        except Exception as e:
            logger.warning(f"DeepSeek on-demand note for '{pname}': {e}")
            return (False, f"تایم‌اوت یا خطای شبکه: {e}") if return_error else False

    if specs and isinstance(specs, dict):
        product["ai_specs"] = specs
        if not isinstance(product.get("specs"), dict):
            product["specs"] = {}
        for k, v in specs.items():
            product["specs"][k] = v
        product["more_details"] = " | ".join([f"{k}: {v}" for k, v in specs.items()])

        pid = str(product.get("product_id") or "").strip()

        # به‌روزرسانی کش درون‌حافظه‌ای ربات
        try:
            from search_engine import JSON_PRODUCTS
            for p in JSON_PRODUCTS:
                if str(p.get("product_id")) == pid:
                    p["ai_specs"] = specs
                    if not isinstance(p.get("specs"), dict):
                        p["specs"] = {}
                    for k, v in specs.items():
                        p["specs"][k] = v
                    p["more_details"] = product["more_details"]
                    break
        except Exception:
            pass

        # ذخیره‌سازی دائمی یکبار برای همیشه در پس‌زمینه
        if pid:
            asyncio.create_task(asyncio.to_thread(sync_save_ai_specs, pid, specs))

        logger.info(f"🎉 [AI APPLIED] مشخصات کالا '{pname}' با موفقیت روی کارت اعمال و ذخیره شد.")
        return (True, "") if return_error else True

    return (False, err_detail or "مدل هوش مصنوعی مشخصاتی برای این مدل استخراج نکرد.") if return_error else False


# ─── سیستم تکمیل گروهی و دسته‌ای مشخصات با گوگل جمینای ───

_BATCH_STATUS = {
    "is_running": False,
    "mode": None,
    "total": 0,
    "current": 0,
    "success": 0,
    "failed": 0,
    "stop_requested": False,
    "start_time": 0.0,
    "current_product": ""
}

def get_batch_enrichment_status() -> dict:
    return dict(_BATCH_STATUS)

def stop_gemini_batch_enrichment() -> bool:
    if _BATCH_STATUS["is_running"]:
        _BATCH_STATUS["stop_requested"] = True
        return True
    return False

async def run_gemini_batch_enrichment(mode: str, bot, chat_id: int, message_id: int):
    """
    پردازش پس‌زمینه تکمیل دسته‌ای مشخصات کالاها منحصراً با Google Gemini.
    - mode == 'no_specs': کالاهای کاملاً فاقد مشخصات (۰ مورد)
    - mode == 'under_3': کالاهای با مشخصات کمتر از ۳ مورد
    """
    global _BATCH_STATUS
    if _BATCH_STATUS["is_running"]:
        return

    _BATCH_STATUS["is_running"] = True
    _BATCH_STATUS["mode"] = mode
    _BATCH_STATUS["total"] = 0
    _BATCH_STATUS["current"] = 0
    _BATCH_STATUS["success"] = 0
    _BATCH_STATUS["failed"] = 0
    _BATCH_STATUS["stop_requested"] = False
    _BATCH_STATUS["start_time"] = time.time()
    _BATCH_STATUS["current_product"] = ""

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    mode_title = (
        "کالاهای کاملاً فاقد مشخصات فنی (۰ مشخصه)"
        if mode == "no_specs"
        else "کالاهای با مشخصات ناقص (۳ مشخصه و کمتر)"
    )

    btn_stop = InlineKeyboardButton("🛑 توقف عملیات", callback_data="adm_ai_batch_stop")
    kb_running = InlineKeyboardMarkup([[btn_stop]])

    api_key = get_gemini_api_key()
    if not api_key:
        _BATCH_STATUS["is_running"] = False
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    "❌ <b>خطا در دسترسی به کلید API جمینای!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "کلید اختصاصی Google Gemini یافت نشد. لطفاً ابتدا از منوی هوش مصنوعی کلید خود را ثبت فرمایید."
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]])
            )
        except Exception:
            pass
        return

    targets = get_products_for_batch_enrich(mode)
    _BATCH_STATUS["total"] = len(targets)

    if not targets:
        _BATCH_STATUS["is_running"] = False
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"🎉 <b>تمام کالاهای این بخش دارای مشخصات فنی کامل هستند!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"▫️ بخش انتخابی: <b>{mode_title}</b>\n"
                    f"▫️ هیچ کالایی نیازمند پردازش و استخراج مشخصات جدید یافت نشد."
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]])
            )
        except Exception:
            pass
        return

    last_edit_time = 0.0

    for idx, product in enumerate(targets):
        if _BATCH_STATUS["stop_requested"]:
            logger.info("🛑 عملیات تکمیل مشخصات توسط ادمین متوقف شد.")
            break

        _BATCH_STATUS["current"] = idx + 1
        pid = str(product.get("product_id") or "")
        pname = str(product.get("name") or f"کد {pid}")
        _BATCH_STATUS["current_product"] = pname

        now = time.time()
        # بروزرسانی وضعیت تلگرام (حداکثر هر ۴.۵ ثانیه یکبار برای رعایت محدودیت Rate Limit تلگرام)
        if (now - last_edit_time > 4.5) or idx == 0:
            elapsed_sec = int(now - _BATCH_STATUS["start_time"])
            mins, secs = divmod(elapsed_sec, 60)
            pct = int((idx / len(targets)) * 100) if len(targets) > 0 else 0
            filled_bars = min(10, pct // 10)
            progress_bar = "▓" * filled_bars + "░" * (10 - filled_bars)

            status_text = (
                f"⚙️ <b>در حال استخراج مشخصات فنی با Google Gemini...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"▫️ دسته پردازش: <b>{mode_title}</b>\n"
                f"▫️ پیشرفت: <b>{idx + 1} از {len(targets)}</b> ({pct}%)\n"
                f"<code>[{progress_bar}]</code>\n\n"
                f"▫️ کالای در حال بررسی: <code>{pname[:38]}</code>\n"
                f"▫️ ✅ ثبت موفق: <b>{_BATCH_STATUS['success']}</b> کالا\n"
                f"▫️ ⏭ نامشخص / ردشده: <b>{_BATCH_STATUS['failed']}</b> کالا\n"
                f"▫️ ⏱ زمان سپری‌شده: <b>{mins:02d}:{secs:02d}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>مشخصات ۱۰۰٪ بر اساس کد مدل کارخانه استخراج شده و فاقد هرگونه رنگ هستند.</i>"
            )
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=status_text,
                    parse_mode="HTML",
                    reply_markup=kb_running
                )
                last_edit_time = now
            except Exception:
                pass

        # فراخوانی API جمینای
        try:
            specs, err = await asyncio.wait_for(
                asyncio.to_thread(call_gemini_api_with_error, api_key, product),
                timeout=18.0
            )
        except Exception as e:
            specs, err = None, str(e)

        if specs and isinstance(specs, dict) and len(specs) >= 2:
            # اعمال روی شیء کالا
            product["ai_specs"] = specs
            if not isinstance(product.get("specs"), dict):
                product["specs"] = {}
            for k, v in specs.items():
                product["specs"][k] = v
            product["more_details"] = " | ".join([f"{k}: {v}" for k, v in specs.items()])

            # اعمال در کش حافظه
            try:
                from search_engine import JSON_PRODUCTS
                for p in JSON_PRODUCTS:
                    if str(p.get("product_id")) == pid:
                        p["ai_specs"] = specs
                        if not isinstance(p.get("specs"), dict):
                            p["specs"] = {}
                        for k, v in specs.items():
                            p["specs"][k] = v
                        p["more_details"] = product["more_details"]
                        break
            except Exception:
                pass

            # ذخیره‌سازی دائمی دیسک و SQLite
            if pid:
                await asyncio.to_thread(sync_save_ai_specs, pid, specs)

            _BATCH_STATUS["success"] += 1
            logger.info(f"✅ [BATCH GEMINI] ({idx+1}/{len(targets)}) '{pname}' با {len(specs)} مشخصه فنی ذخیره شد.")
        else:
            _BATCH_STATUS["failed"] += 1
            logger.info(f"⏭ [BATCH GEMINI] ({idx+1}/{len(targets)}) '{pname}': مشخصاتی دریافت نشد ({err[:80]})")

        # فاصله کوتاه برای جلوگیری از Rate Limit
        await asyncio.sleep(1.8)

    # پایان عملیات و ارسال گزارش نهایی
    total_time = int(time.time() - _BATCH_STATUS["start_time"])
    mins, secs = divmod(total_time, 60)
    was_stopped = _BATCH_STATUS["stop_requested"]
    success_count = _BATCH_STATUS["success"]
    failed_count = _BATCH_STATUS["failed"]
    processed_count = _BATCH_STATUS["current"]
    total_count = len(targets)

    _BATCH_STATUS["is_running"] = False
    _BATCH_STATUS["stop_requested"] = False

    kb_done = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]
    ])

    title = "🛑 <b>عملیات تکمیل مشخصات توسط ادمین متوقف شد.</b>" if was_stopped else "🏁 <b>عملیات تکمیل مشخصات با موفقیت به پایان رسید!</b>"
    final_text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ بخش: <b>{mode_title}</b>\n"
        f"▫️ موتور هوش مصنوعی: <b>گوگل جمینای (Google Gemini ♊️)</b>\n"
        f"▫️ کل اقلام بررسی‌شده: <b>{processed_count} از {total_count} کالا</b>\n"
        f"▫️ ✅ تکمیل موفق مشخصات فنی: <b>{success_count} کالا</b>\n"
        f"▫️ ⏭ اقلام فاقد مدارک رسمی کارخانه: <b>{failed_count} کالا</b>\n"
        f"▫️ ⏱ مدت زمان عملیات: <b>{mins:02d}:{secs:02d}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💾 تمامی مشخصات جدید در کاتالوگ و پایگاه داده به‌صورت دائمی ذخیره شدند."
    )

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=final_text,
            parse_mode="HTML",
            reply_markup=kb_done
        )
    except Exception:
        try:
            await bot.send_message(chat_id=chat_id, text=final_text, parse_mode="HTML", reply_markup=kb_done)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# 🌟 بخش تولید هوشمند توضیحات تکمیلی محصولات (AI Generated Description)
# ═══════════════════════════════════════════════════════════════════════════

def sync_save_ai_description(pid: str, description: str):
    """ذخیره دائمی فیلد ai_generated_description در کاتالوگ دیسک، حافظه و دیتابیس SQLite"""
    if not pid or not description:
        return

    clean_pid = str(pid).strip()
    clean_desc = str(description).strip()

    # ۱. ذخیره در کش حافظه موتور جستجو
    try:
        from search_engine import JSON_PRODUCTS
        for p in JSON_PRODUCTS:
            p_id = str(p.get("product_id") or p.get("id") or "").strip()
            if p_id == clean_pid or p_id.lower() == clean_pid.lower():
                p["ai_generated_description"] = clean_desc
    except Exception as e:
        logger.debug(f"Error updating JSON_PRODUCTS memory with AI description: {e}")

    # ۲. ذخیره در کاتالوگ JSON دیسک
    try:
        for cat_f in [CATALOG_FILE, "momtazkalla_all_products.json"]:
            if os.path.exists(cat_f):
                with open(cat_f, "r", encoding="utf-8") as f:
                    data = json.load(f)
                updated = False
                if isinstance(data, dict):
                    if clean_pid in data:
                        data[clean_pid]["ai_generated_description"] = clean_desc
                        updated = True
                    else:
                        for _, v in data.items():
                            if str(v.get("product_id")) == clean_pid or str(v.get("id")) == clean_pid:
                                v["ai_generated_description"] = clean_desc
                                updated = True
                                break
                elif isinstance(data, list):
                    for item in data:
                        if str(item.get("product_id")) == clean_pid or str(item.get("id")) == clean_pid:
                            item["ai_generated_description"] = clean_desc
                            updated = True
                            break
                if updated:
                    with open(cat_f, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    logger.info(f"💾 [AI DESC DISK SAVED] توضیحات تکمیلی کالا {clean_pid} در {cat_f} ثبت شد.")
    except Exception as e:
        logger.error(f"Error saving AI description to JSON for {clean_pid}: {e}")

    # ۳. ذخیره در جدول SQLite
    try:
        if os.path.exists(DB_FILE):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE products
                SET ai_generated_description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE product_id = ?
            """, (clean_desc, clean_pid))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Error saving AI description to SQLite for {clean_pid}: {e}")


def generate_product_description_with_gemini(api_key: str, product: dict) -> Tuple[Optional[str], str]:
    """تولید توضیحات تکمیلی و معرفی تخصصی با Google Gemini"""
    if not api_key:
        return None, "کلید GEMINI_API_KEY تنظیم نشده است."

    pname = str(product.get("name", "")).strip()
    brand = str(product.get("brand", "")).strip()
    category = str(product.get("category") or product.get("category_name") or "لوازم خانگی").strip()
    specs = product.get("specs", {})
    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except Exception:
            specs = {}
    specs_summary = ""
    if isinstance(specs, dict):
        specs_summary = "\n".join([f"- {k}: {v}" for k, v in specs.items() if v])

    prompt = f"""You are a professional technical writer and consumer electronics specialist for the AiKala store.
Generate a concise, elegant, highly persuasive, and accurate Persian complementary description (معرفی و نکات برجسته محصول) for this item:

Product: {pname}
Brand: {brand}
Category: {category}
Technical Highlights:
{specs_summary}

Rules:
1. Write 3 to 5 structured, high-value Persian bullet points.
2. Each bullet point MUST start with '▫️ ' (e.g. '▫️ موتور قدرتمند اینورتر دیجیتال با مصرف بهینه A+++ و طول عمر بسیار بالا').
3. Focus on real technologies, build materials, energy efficiency, user convenience, and key selling advantages.
4. DO NOT invent fake warranties or fictional details. Keep it realistic and brand-accurate.
5. Return ONLY the bullet points, one per line. No introduction, no markdown headings, no JSON.
"""

    models_to_try = [
        "gemini-flash-lite-latest",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-flash-latest"
    ]
    models_to_try = list(dict.fromkeys(models_to_try))

    last_error = "پاسخی از مدل دریافت نشد."

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 700
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    continue
                raw_text = parts[0].get("text", "").strip()
                if raw_text and len(raw_text) > 20:
                    clean_lines = []
                    for line in raw_text.splitlines():
                        l = line.strip().lstrip("*-• ").strip()
                        if l and not l.startswith("```"):
                            if not l.startswith("▫️"):
                                l = f"▫️ {l}"
                            clean_lines.append(l)
                    if clean_lines:
                        res = "\n".join(clean_lines)
                        logger.info(f"✨ [GEMINI DESC] توضیحات تکمیلی '{pname}' از مدل {model_name} با موفقیت تولید شد.")
                        return res, ""
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            last_error = f"HTTP {he.code}: {err_body[:180]}"
            if he.code in [400, 403] and ("API key not valid" in err_body or "API_KEY_INVALID" in err_body):
                return None, f"کلید API نامعتبر است (HTTP {he.code})"
            if he.code == 429:
                last_error = f"سهمیه مدل {model_name} تکمیل است (Rate Limit 429)."
                continue
        except Exception as e:
            last_error = str(e)

    return None, last_error


def get_batch_description_counts() -> Tuple[int, int]:
    """تعداد کل محصولات و تعداد کالاهای فاقد توضیحات تکمیلی هوش مصنوعی"""
    from search_engine import JSON_PRODUCTS, load_json_products
    if not JSON_PRODUCTS:
        load_json_products()
    
    total = len(JSON_PRODUCTS)
    no_desc = 0
    for p in JSON_PRODUCTS:
        d = str(p.get("ai_generated_description") or "").strip()
        if not d:
            no_desc += 1
    return no_desc, total


def get_products_for_description_batch(only_missing: bool = False) -> List[dict]:
    """لیست محصولات جهت تولید توضیحات تکمیلی (در صورت False بودن، تمام کاتالوگ را جهت جایگزینی بررسی می‌کند)"""
    from search_engine import JSON_PRODUCTS, load_json_products
    if not JSON_PRODUCTS:
        load_json_products()
    
    if only_missing:
        return [p for p in JSON_PRODUCTS if not str(p.get("ai_generated_description") or "").strip()]
    return list(JSON_PRODUCTS)


_DESC_BATCH_STATUS = {
    "is_running": False,
    "total": 0,
    "current": 0,
    "success": 0,
    "failed": 0,
    "stop_requested": False,
    "start_time": 0.0,
    "current_product": ""
}

def get_description_batch_status() -> dict:
    return dict(_DESC_BATCH_STATUS)

def stop_description_batch() -> bool:
    if _DESC_BATCH_STATUS["is_running"]:
        _DESC_BATCH_STATUS["stop_requested"] = True
        return True
    return False

async def run_gemini_description_batch(bot, chat_id: int, message_id: int, only_missing: bool = False):
    """
    پردازش صف با Rate Limit دقیق ۱۵ درخواست در دقیقه (۴ ثانیه تاخیر بین هر درخواست)
    تولید توضیحات تکمیلی با Gemini API و ذخیره در ai_generated_description
    نمایش Progress Bar و گزارش نهایی به ادمین با parse_mode="HTML"
    """
    global _DESC_BATCH_STATUS
    if _DESC_BATCH_STATUS["is_running"]:
        return

    _DESC_BATCH_STATUS["is_running"] = True
    _DESC_BATCH_STATUS["total"] = 0
    _DESC_BATCH_STATUS["current"] = 0
    _DESC_BATCH_STATUS["success"] = 0
    _DESC_BATCH_STATUS["failed"] = 0
    _DESC_BATCH_STATUS["stop_requested"] = False
    _DESC_BATCH_STATUS["start_time"] = time.time()
    _DESC_BATCH_STATUS["current_product"] = ""

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    btn_stop = InlineKeyboardButton("🛑 توقف عملیات", callback_data="adm_ai_desc_stop")
    kb_running = InlineKeyboardMarkup([[btn_stop]])

    api_key = get_gemini_api_key()
    if not api_key:
        _DESC_BATCH_STATUS["is_running"] = False
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    "❌ <b>خطا در دسترسی به کلید API جمینای!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "کلید اختصاصی Google Gemini یافت نشد. لطفاً ابتدا از منوی هوش مصنوعی کلید خود را ثبت فرمایید."
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]])
            )
        except Exception:
            pass
        return

    targets = get_products_for_description_batch(only_missing=only_missing)
    _DESC_BATCH_STATUS["total"] = len(targets)

    if not targets:
        _DESC_BATCH_STATUS["is_running"] = False
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    "🎉 <b>تمامی کالاهای کاتالوگ دارای توضیحات تکمیلی هوش مصنوعی هستند!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "▫️ هیچ کالایی نیازمند تولید توضیحات تکمیلی جدید یافت نشد."
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]])
            )
        except Exception:
            pass
        return

    last_edit_time = 0.0

    for idx, product in enumerate(targets):
        if _DESC_BATCH_STATUS["stop_requested"]:
            logger.info("🛑 عملیات تولید توضیحات تکمیلی توسط ادمین متوقف شد.")
            break

        _DESC_BATCH_STATUS["current"] = idx + 1
        pid = str(product.get("product_id") or product.get("id") or "")
        pname = str(product.get("name") or f"کد {pid}")
        _DESC_BATCH_STATUS["current_product"] = pname

        now = time.time()
        # به‌روزرسانی نوار پیشرفت زنده تلگرام هر ۴.۵ ثانیه
        if (now - last_edit_time > 4.5) or idx == 0:
            elapsed_sec = int(now - _DESC_BATCH_STATUS["start_time"])
            mins, secs = divmod(elapsed_sec, 60)
            pct = int((idx / len(targets)) * 100) if len(targets) > 0 else 0
            filled_bars = min(10, pct // 10)
            progress_bar = "▓" * filled_bars + "░" * (10 - filled_bars)

            status_text = (
                f"✨ <b>در حال تولید توضیحات تکمیلی با Google Gemini...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"▫️ صف پردازش: <b>Rate Limit استاندارد (۱۵ درخواست در دقیقه)</b>\n"
                f"▫️ پیشرفت: <b>{idx + 1} از {len(targets)}</b> ({pct}%)\n"
                f"<code>[{progress_bar}]</code>\n\n"
                f"▫️ کالای در حال پردازش: <code>{pname[:38]}</code>\n"
                f"▫️ ✅ تولید موفق: <b>{_DESC_BATCH_STATUS['success']}</b> کالا\n"
                f"▫️ ⏭ ناموفق/خطا: <b>{_DESC_BATCH_STATUS['failed']}</b> کالا\n"
                f"▫️ ⏱ زمان سپری‌شده: <b>{mins:02d}:{secs:02d}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>توضیحات تکمیلی به صورت کشویی (&lt;blockquote expandable&gt;) در کارت کالا نمایش داده می‌شوند.</i>"
            )
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=status_text,
                    parse_mode="HTML",
                    reply_markup=kb_running
                )
                last_edit_time = now
            except Exception as e_edit:
                logger.debug(f"Progress bar edit note: {e_edit}")

        # تولید متن با جمینای
        desc_text, err = generate_product_description_with_gemini(api_key, product)
        if desc_text:
            sync_save_ai_description(pid, desc_text)
            product["ai_generated_description"] = desc_text
            _DESC_BATCH_STATUS["success"] += 1
        else:
            _DESC_BATCH_STATUS["failed"] += 1
            logger.warning(f"Failed to generate AI description for {pname}: {err}")

        # اعمال دقیق Rate Limit (۱۵ درخواست در دقیقه -> ۴.۰ ثانیه وقفه بین هر درخواست)
        await asyncio.sleep(4.0)

    # پایان عملیات و ارسال گزارش نهایی به ادمین
    total_time = int(time.time() - _DESC_BATCH_STATUS["start_time"])
    tot_mins, tot_secs = divmod(total_time, 60)
    was_stopped = _DESC_BATCH_STATUS["stop_requested"]

    final_header = "🛑 <b>عملیات تولید توضیحات تکمیلی متوقف شد</b>" if was_stopped else "🎉 <b>تکمیل هوشمند توضیحات کاتالوگ با موفقیت پایان یافت!</b>"

    final_report = (
        f"{final_header}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>گزارش نهایی پردازش هوش مصنوعی (Google Gemini):</b>\n\n"
        f"▫️ کل کالاهای بررسی‌شده: <b>{_DESC_BATCH_STATUS['current']} از {_DESC_BATCH_STATUS['total']}</b>\n"
        f"▫️ ✅ تولید و ثبت موفق در کاتالوگ: <b>{_DESC_BATCH_STATUS['success']} کالا</b>\n"
        f"▫️ ⚠️ موارد ناموفق یا ردشده: <b>{_DESC_BATCH_STATUS['failed']} کالا</b>\n"
        f"▫️ ⏱ مدت زمان کل عملیات: <b>{tot_mins:02d}:{tot_secs:02d}</b>\n"
        f"▫️ ⚡️ نرخ پردازش: <b>۱۵ درخواست در دقیقه (کنترل‌شده)</b>\n"
        f"▫️ 📦 فرمت نمایش: <b>کشویی با تگ <code>&lt;blockquote expandable&gt;</code></b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"کارت محصولات هم‌اکنون با توضیحات جامع و معرفی حرفه‌ای به‌روزرسانی شدند."
    )

    kb_final = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]
    ])

    _DESC_BATCH_STATUS["is_running"] = False

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=final_report,
            parse_mode="HTML",
            reply_markup=kb_final
        )
    except Exception as e_final:
        logger.warning(f"Could not send final description batch report: {e_final}")
        try:
            await bot.send_message(chat_id=chat_id, text=final_report, parse_mode="HTML", reply_markup=kb_final)
        except Exception:
            pass

