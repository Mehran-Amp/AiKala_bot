"""
Configuration Module — Home Appliance Bot
=========================================
All settings and environment variables for @AiKala_bot.
"""

import os
from typing import List, Dict, Any
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ------------------- Telegram Settings -------------------
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8837314491:AAGjg67CywBAubXmM2lPm1j3hhhe9W9TdCI")
ADMIN_IDS: List[int] = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "86900909").split(",")
    if x.strip().isdigit()
]
TARGET_CHANNEL_ID: str = os.getenv("TARGET_CHANNEL_ID", "@BanehErsal,@mahmodii_shop,@bazarganisalimi99,@bazargani_faghihzadeh,@solimanybanehtv,@LGBaneh,@arbil_gold")
BOT_LINK: str = os.getenv("BOT_LINK", "@AiKala_bot")
SATISFACTION_CHANNEL: str = os.getenv("SATISFACTION_CHANNEL", "https://t.me/AiKala_bot")

# کانال مقصد انتشار عکس‌ها و مشخصات پاکسازی شده (همگام‌سازی نام‌های PHOTOS_CHANNEL و TARGET_IMAGE_CHANNEL)
TARGET_IMAGE_CHANNEL: str = os.getenv("TARGET_IMAGE_CHANNEL", "@img_ai_amp")
PHOTOS_CHANNEL: str = TARGET_IMAGE_CHANNEL

# نام کاربری رسمی پشتیبانی در تلگرام
SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "@faridamp")

def clean_gemini_api_key(val: str) -> str:
    """استخراج کلید واقعی Gemini و حذف کاراکتر ماسک 'w' از انتها در صورت وجود"""
    if not val:
        return ""
    v = str(val).strip()
    if v.lower().startswith("bearer "):
        v = v[7:].strip()
    v = v.strip('"').strip("'").strip()
    if v.endswith("w"):
        v = v[:-1].strip()
    return v.strip('"').strip("'").strip()

def clean_deepseek_api_key(val: str) -> str:
    """استخراج کلید واقعی DeepSeek و حذف کاراکتر ماسک '5' از انتها در صورت وجود"""
    if not val:
        return ""
    v = str(val).strip()
    if v.lower().startswith("bearer "):
        v = v[7:].strip()
    v = v.strip('"').strip("'").strip()
    if v.endswith("5"):
        v = v[:-1].strip()
    return v.strip('"').strip("'").strip()

# ------------------- AI & Specs Settings -------------------
GEMINI_API_KEY: str = clean_gemini_api_key(os.getenv("GEMINI_API_KEY", ""))
DEEPSEEK_API_KEY: str = clean_deepseek_api_key(os.getenv("DEEPSEEK_API_KEY", ""))

# ------------------- Telethon (Channel Monitor) -------------------
TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "31810703"))
TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "43e05e117c0abddd1004e2bc2c478959")
TELEGRAM_SESSION: str = os.getenv("TELEGRAM_SESSION", "bot_session")
TG_PHONE: str = os.getenv("TG_PHONE", "+989195859434")

# ------------------- Google Sheets -------------------
GOOGLE_SHEETS_CREDENTIALS: str = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "credentials.json")
SHEET_NAME: str = os.getenv("SHEET_NAME", "HomeApplianceBot")
SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "1GGhqfVod6u54r0ceF7YLKLMoojgmjXKXEl5nqlLO9Zk")

# ------------------- Database -------------------
DB_PATH: str = os.getenv("DB_PATH", "bot_data.db")

# ------------------- Scraper Settings -------------------
MOMTAZ_BASE_URL: str = "https://momtazkalla.com"
PRICE_LIST_URL: str = f"{MOMTAZ_BASE_URL}/price/"
SYNC_INTERVAL_HOURS: int = int(os.getenv("SYNC_INTERVAL_HOURS", "24"))
PRICE_HISTORY_DAYS: int = int(os.getenv("PRICE_HISTORY_DAYS", "10"))
HEADLESS_BROWSER: bool = os.getenv("HEADLESS_BROWSER", "true").lower() == "true"

# ------------------- Shop Info & Payment -------------------
SHOP_NAME: str = os.getenv("SHOP_NAME", "ربات فروشگاهی هوشمند کالا AiKala_bot")
SHOP_PHONE: str = os.getenv("SHOP_PHONE", "۰۹۱۹۵۸۵۹۴۳۴")
SHOP_ADDRESS: str = os.getenv("SHOP_ADDRESS", "بازارچه مرزی منطقه آزاد کردستان-بانه، مجتمع تجاری پاسارگاد، فروشگاه AiKala")
LICENSE_NO: str = os.getenv("LICENSE_NO", "125366980")
SPONSOR_WEBSITE_URL: str = os.getenv("SPONSOR_WEBSITE_URL", "https://aegkala.com")
SPONSOR_WEBSITE_NAME: str = os.getenv("SPONSOR_WEBSITE_NAME", "aegkala.com")

import json
BANK_SETTINGS_FILE = "bank_settings.json"

def _load_bank_settings():
    default_cfg = {
        "card_number": os.getenv("DEPOSIT_CARD_NUMBER", "6104-3386-4929-6106"),
        "card_holder": os.getenv("DEPOSIT_CARD_NAME", "مهران امین پور (AiKala_bot)"),
        "card_shaba": os.getenv("DEPOSIT_CARD_SHABA", "IR 620120020000005786685564"),
        "deposit_percent": int(os.getenv("DEPOSIT_PERCENT", "8"))
    }
    if os.path.exists(BANK_SETTINGS_FILE):
        try:
            with open(BANK_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    if v is not None and str(v).strip():
                        default_cfg[k] = v
        except Exception:
            pass
    return default_cfg

_bank_cfg = _load_bank_settings()

DEPOSIT_PERCENT: int = int(_bank_cfg.get("deposit_percent", 8))
DEPOSIT_CARD_NUMBER: str = str(_bank_cfg.get("card_number", ""))
DEPOSIT_CARD_NAME: str = str(_bank_cfg.get("card_holder", ""))
DEPOSIT_CARD_SHABA: str = str(_bank_cfg.get("card_shaba", ""))

# متغیرهای معادل جهت سازگاری کامل با تمامی توابع bot.py
CARD_NUMBER: str = DEPOSIT_CARD_NUMBER
CARD_HOLDER: str = DEPOSIT_CARD_NAME
CARD_SHABA: str = DEPOSIT_CARD_SHABA

import re
def get_shaba_digits(shaba_str: str = None) -> str:
    """استخراج فقط ارقام عددی شبا جهت کپی شدن صرفاً بخش عددی بدون پیشوند IR"""
    target = shaba_str if shaba_str is not None else DEPOSIT_CARD_SHABA
    return "".join(re.findall(r'\d+', target or ""))

def get_shaba_html(shaba_str: str = None) -> str:
    """تولید قالب HTML شماره شبا که فقط ارقام آن داخل تگ code است تا با کلیک، فقط اعداد کپی شوند"""
    digits = get_shaba_digits(shaba_str)
    if not digits:
        return ""
    return f"IR <code>{digits}</code>"

SHABA_DIGITS: str = get_shaba_digits(DEPOSIT_CARD_SHABA)
SHABA_HTML: str = get_shaba_html(DEPOSIT_CARD_SHABA)

def update_bank_settings(
    card_number: str = None,
    card_holder: str = None,
    card_shaba: str = None,
    deposit_percent: int = None
) -> dict:
    """بروزرسانی مشخصات بانکی و درصد بیعانه و ذخیره پایدار در دیسک"""
    global DEPOSIT_CARD_NUMBER, DEPOSIT_CARD_NAME, DEPOSIT_CARD_SHABA, DEPOSIT_PERCENT
    global CARD_NUMBER, CARD_HOLDER, CARD_SHABA, SHABA_DIGITS, SHABA_HTML

    current = _load_bank_settings()
    if card_number is not None:
        current["card_number"] = str(card_number).strip()
    if card_holder is not None:
        current["card_holder"] = str(card_holder).strip()
    if card_shaba is not None:
        raw_s = str(card_shaba).strip()
        if not raw_s.upper().startswith("IR"):
            raw_s = f"IR {raw_s}"
        current["card_shaba"] = raw_s
    if deposit_percent is not None:
        current["deposit_percent"] = max(1, min(100, int(deposit_percent)))

    try:
        with open(BANK_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("خطا در ذخیره مشخصات بانکی:", e)

    DEPOSIT_PERCENT = int(current.get("deposit_percent", 8))
    DEPOSIT_CARD_NUMBER = str(current.get("card_number", ""))
    DEPOSIT_CARD_NAME = str(current.get("card_holder", ""))
    DEPOSIT_CARD_SHABA = str(current.get("card_shaba", ""))

    CARD_NUMBER = DEPOSIT_CARD_NUMBER
    CARD_HOLDER = DEPOSIT_CARD_NAME
    CARD_SHABA = DEPOSIT_CARD_SHABA
    SHABA_DIGITS = get_shaba_digits(DEPOSIT_CARD_SHABA)
    SHABA_HTML = get_shaba_html(DEPOSIT_CARD_SHABA)

    # همگام‌سازی با ماژول‌های دیگر در صورت بارگذاری قبلی
    try:
        import order_flow
        order_flow.CARD_NUMBER = CARD_NUMBER
        order_flow.CARD_HOLDER = CARD_HOLDER
        order_flow.CARD_SHABA = CARD_SHABA
        order_flow.SHABA_HTML = SHABA_HTML
        order_flow.DEPOSIT_PERCENT = DEPOSIT_PERCENT
    except Exception:
        pass

    try:
        import invoice_service
        invoice_service.CARD_NUMBER = CARD_NUMBER
        invoice_service.CARD_HOLDER = CARD_HOLDER
        invoice_service.CARD_SHABA = CARD_SHABA
    except Exception:
        pass

    return current
DEPOSIT_AMOUNT: str = "۲,۰۰۰,۰۰۰"
PRICE_NOTE: str = "⚠️ به علت نوسانات لحظه‌ای ارز، استعلام قیمت قطعی قبل از بارگیری الزامی است."

def round_deposit(amount: int) -> int:
    """گرد کردن مبلغ بیعانه به ارقام رند"""
    if amount >= 1_000_000:
        return round(amount / 1_000_000) * 1_000_000
    elif amount >= 100_000:
        return round(amount / 100_000) * 100_000
    return amount

# ------------------- Support Staff -------------------
SUPPORT_STAFF: List[Dict[str, str]] = []

SUPPORT_HOURS: str = "۹ صبح تا ۹ شب (پاسخگویی همه‌روزه)"

# ------------------- Category Detection -------------------
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "تلویزیون": ["tv", "television", "تلویزیون", "ال ای دی", "led", "oled", "qled", "qned", "nano", "اینچ", "inch", "اولد", "کیولد"],
    "یخچال": ["یخچال", "refrigerator", "فریزر", "ساید", "side", "دوقلو", "بالا فریزر", "دور این دور"],
    "لباسشویی": ["لباسشویی", "washing", "ماشین لباسشویی", "خشکشویی", "پتوشور", "پتو شور", "گیربکسی"],
    "ظرفشویی": ["ظرفشویی", "dishwasher", "ماشین ظرفشویی", "زئولیت"],
    "کولرگازی": ["کولر", "اسپلیت", "split", "air conditioner", "کولرگازی", "کولر گازی", "موتور سنگین"],
    "فر و مایکروویو": ["فر", "مایکروویو", "micro", "oven", "توکار", "سولاردام", "سولاردوم", "سولدام"],
    "جاروبرقی": ["جارو", "vacuum", "جاروشارژی", "جاروبرقی", "رباتیک", "جارو برقی"],
    "اتو": ["اتو", "iron", "بخارشو", "اتوپرس", "بخارگر"],
    "ساندبار و اسپیکر": ["ساندبار", "soundbar", "اسپیکر", "سیستم صوتی", "سینما خانگی"],
    "لوازم آشپزخانه": ["غذاساز", "مخلوط‌کن", "آبمیوه‌گیری", "ساندویچ‌ساز", "سرخ‌کن", "قهوه‌ساز", "چای‌ساز"],
    "لوازم ریز": ["خردکن", "همزن", "چرخ گوشت", "گوشت کوب", "آسیاب", "اسپرسوساز", "سرخ کن", "هواپز", "لوازم ریز"],
}

IMPORTANT_SPECS: Dict[str, List[str]] = {
    "تلویزیون": ["سایز", "اینچ", "کیفیت تصویر", "رزولوشن", "پنل", "رفرش ریت", "سیستم عامل", "مونتاژ", "سال"],
    "یخچال": ["ظرفیت", "لیتر", "فوت", "نوع موتور", "سیستم سرمایش", "رنگ", "مونتاژ", "ابعاد"],
    "لباسشویی": ["ظرفیت", "کیلوگرم", "دور خشک کن", "نوع موتور", "برنامه شستشو", "رنگ", "مونتاژ"],
    "ظرفشویی": ["ظرفیت", "نفره", "تعداد طبقات", "برنامه شستشو", "موتور", "مونتاژ"],
    "default": ["برند", "مدل", "رنگ", "ابعاد", "وزن", "توان", "مونتاژ"]
}

def detect_category(product_name: str) -> str:
    name_lower = product_name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in name_lower:
                return category
    return "default"

def get_important_specs(category: str) -> List[str]:
    return IMPORTANT_SPECS.get(category, IMPORTANT_SPECS["default"])

def format_price(num_str: str) -> str:
    if not num_str:
        return "استعلام"
    try:
        clean = str(num_str).replace(",", "").replace("،", "").strip()
        if not clean or clean == "0":
            return "استعلام"
        num = int(clean)
        return f"{num:,}".replace(",", "،")
    except:
        return str(num_str)

DEFAULT_CHANNELS = [
    {
        "channel_id": "@bazargani_faghihzadeh",
        "channel_name": "بازرگانی فقیه‌زاده",
        "keywords": [],
        "active": True
    },
    {
        "channel_id": "@LG_SAMSUNG_DEAWOO",
        "channel_name": "الجی سامسونگ دوو",
        "keywords": [],
        "active": True
    }
]

DEEPSEEK_API_KEY = clean_deepseek_api_key(os.getenv("DEEPSEEK_API_KEY", ""))
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ------------------- WooCommerce AEG Settings -------------------
AEG_SITE_URL: str = os.getenv("AEG_SITE_URL", "https://aegkala.com")
AEG_CONSUMER_KEY: str = os.getenv("AEG_CONSUMER_KEY", "ck_354a7bbd2855cad4f15db1080299b313ff8577f6")
AEG_CONSUMER_SECRET: str = os.getenv("AEG_CONSUMER_SECRET", "cs_8adb5c723f3b57974f88790fb516d13de33c5886")
AEG_CAT_ID: int = int(os.getenv("AEG_CAT_ID", "202"))
