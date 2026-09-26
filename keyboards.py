"""
AiKala - Keyboards, UI Layouts & Callback Mapping (keyboards.py)
===============================================================
شامل کیبوردهای تعاملی، سیستم امن جلوگیری از خطای ۶۴ بایت callback_data،
قالب‌بندی کارت مشخصات کالا و صفحه‌بندی هوشمند نتایج جستجو.
"""

import os
import json
import hashlib
import urllib.parse
from typing import List, Dict, Any, Optional

try:
    from telegram import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        ReplyKeyboardMarkup,
        KeyboardButton,
        Update
    )
    from telegram.ext import ContextTypes
except ImportError:
    class _MockTelegramObj:
        def __init__(self, *args, **kwargs):
            self.text = args[0] if args else kwargs.get("text", "")
            self.callback_data = kwargs.get("callback_data", "")
            self.url = kwargs.get("url", "")
            self.args = args
            self.kwargs = kwargs
            self.inline_keyboard = args[0] if (args and isinstance(args[0], list)) else kwargs.get("inline_keyboard", [])
    InlineKeyboardButton = _MockTelegramObj
    InlineKeyboardMarkup = _MockTelegramObj
    ReplyKeyboardMarkup = _MockTelegramObj
    KeyboardButton = _MockTelegramObj
    Update = _MockTelegramObj
    class ContextTypes:
        DEFAULT_TYPE = Any

try:
    import config
except ImportError:
    config = None

ADMIN_IDS = getattr(config, "ADMIN_IDS", [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()] if os.getenv("ADMIN_IDS") else [])
SUPPORT_USERNAME = getattr(config, "SUPPORT_USERNAME", "@AiKala_Admin")
PRICE_NOTE = getattr(config, "PRICE_NOTE", "⚠️ به علت نوسانات لحظه‌ای ارز، استعلام قیمت قطعی قبل از بارگیری الزامی است.")
BOT_LINK = getattr(config, "BOT_LINK", "@AiKala_bot")
BOT_USERNAME = str(BOT_LINK or "").replace("@", "").strip() or "AiKala_bot"

from search_engine import (
    clean_key,
    atomic_save_json,
    get_product_id,
    get_product_name,
    get_product_brand,
    get_product_category,
    get_product_price,
    get_product_specs,
    is_laptop_product,
    find_product_by_id
)

# ─── سیستم کش callback_data برای جلوگیری از خطای ۶۴ بایت تلگرام ───

CALLBACK_DATA_MAP: Dict[str, str] = {}
CALLBACK_MAP_FILE = "callback_map.json"

def load_callback_map():
    global CALLBACK_DATA_MAP
    if os.path.exists(CALLBACK_MAP_FILE):
        try:
            with open(CALLBACK_MAP_FILE, "r", encoding="utf-8") as f:
                CALLBACK_DATA_MAP = json.load(f)
        except Exception:
            CALLBACK_DATA_MAP = {}

def save_callback_map():
    try:
        atomic_save_json(CALLBACK_MAP_FILE, CALLBACK_DATA_MAP, indent=None)
    except Exception:
        pass

load_callback_map()

def make_safe_cb(prefix: str, payload: Any) -> str:
    """تولید callback_data تضمین‌شده زیر ۶۴ بایت برای تلگرام"""
    s_payload = str(payload if payload is not None else "").strip()
    full = f"{prefix}|{s_payload}"
    if len(full.encode("utf-8")) <= 64:
        return full
    h = hashlib.md5(s_payload.encode("utf-8")).hexdigest()[:16]
    short_cb = f"{prefix}|h_{h}"
    CALLBACK_DATA_MAP[short_cb] = s_payload
    save_callback_map()
    return short_cb

def resolve_safe_cb(cb_data: str) -> str:
    """بازیابی مقدار اصلی از callback_data"""
    if not cb_data:
        return ""
    if cb_data in CALLBACK_DATA_MAP:
        return CALLBACK_DATA_MAP[cb_data]
    if "|" in cb_data:
        prefix, rest = cb_data.split("|", 1)
        if rest.startswith("h_") and cb_data in CALLBACK_DATA_MAP:
            return CALLBACK_DATA_MAP[cb_data]
        return rest
    return cb_data

ADMIN_IDS_FILE = "admin_ids.json"
OWNER_ID: int = 86900909

def is_owner(user_id: int) -> bool:
    """تشخیص ادمین اصلی و مالک ربات (شناسه 86900909)"""
    if not user_id:
        return False
    try:
        uid = int(user_id)
        if uid == OWNER_ID:
            return True
        # همچنین اگر اولین ادمین در ADMIN_IDS پیکربندی شده باشد
        if ADMIN_IDS and uid == int(ADMIN_IDS[0]):
            return True
    except Exception:
        pass
    return False

def get_all_admin_ids() -> set:
    """دریافت لیست تمام شناسه‌های ادمین (اصلی و فرعی)"""
    ids = set(int(x) for x in ADMIN_IDS if str(x).isdigit())
    ids.add(OWNER_ID)
    if os.path.exists(ADMIN_IDS_FILE):
        try:
            with open(ADMIN_IDS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    for item in saved:
                        if isinstance(item, dict) and "id" in item:
                            if str(item["id"]).isdigit():
                                ids.add(int(item["id"]))
                        elif str(item).isdigit():
                            ids.add(int(item))
                elif isinstance(saved, dict):
                    for k in saved.keys():
                        if str(k).isdigit():
                            ids.add(int(k))
        except Exception:
            pass
    return ids

def get_sub_admins_detailed() -> List[dict]:
    """دریافت لیست ادمین‌های فرعی همراه با نام و شناسه عددی"""
    detailed = []
    if os.path.exists(ADMIN_IDS_FILE):
        try:
            with open(ADMIN_IDS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    for item in saved:
                        if isinstance(item, dict) and "id" in item:
                            uid = int(item["id"])
                            name = str(item.get("name", "")).strip() or "همکار"
                            if not is_owner(uid):
                                detailed.append({"id": uid, "name": name})
                        elif str(item).isdigit():
                            uid = int(item)
                            if not is_owner(uid):
                                detailed.append({"id": uid, "name": "همکار"})
                elif isinstance(saved, dict):
                    for k, v in saved.items():
                        if str(k).isdigit():
                            uid = int(k)
                            name = str(v.get("name", "") if isinstance(v, dict) else v).strip() or "همکار"
                            if not is_owner(uid):
                                detailed.append({"id": uid, "name": name})
        except Exception:
            pass
    return detailed

def get_sub_admin_ids() -> List[int]:
    """دریافت لیست ادمین‌های فرعی ثبت‌شده (بدون ادمین اصلی)"""
    detailed = get_sub_admins_detailed()
    sub_ids = [item["id"] for item in detailed]
    # همچنین شناسه‌های متفرقه از get_all_admin_ids
    for uid in get_all_admin_ids():
        if not is_owner(uid) and uid not in sub_ids:
            sub_ids.append(uid)
    sub_ids.sort()
    return sub_ids

def add_admin_id(user_id: int, name: str = "") -> bool:
    """افزودن شناسه ادمین به همراه نام شخص به صورت دائمی در فایل محلی"""
    try:
        uid = int(user_id)
        if uid == OWNER_ID:
            return True
        name_clean = (name or "").strip() or "همکار"
        saved_list = []
        if os.path.exists(ADMIN_IDS_FILE):
            try:
                with open(ADMIN_IDS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "id" in item:
                                saved_list.append({"id": int(item["id"]), "name": str(item.get("name", "")).strip() or "همکار"})
                            elif str(item).isdigit():
                                saved_list.append({"id": int(item), "name": "همکار"})
                    elif isinstance(data, dict):
                        for k, v in data.items():
                            if str(k).isdigit():
                                nm = str(v.get("name", "") if isinstance(v, dict) else v).strip() or "همکار"
                                saved_list.append({"id": int(k), "name": nm})
            except Exception:
                saved_list = []
        
        # بررسی یا بروزرسانی نام در صورت وجود
        found = False
        for item in saved_list:
            if item["id"] == uid:
                item["name"] = name_clean
                found = True
                break
        if not found:
            saved_list.append({"id": uid, "name": name_clean})
            
        return atomic_save_json(ADMIN_IDS_FILE, saved_list, indent=2)
    except Exception:
        return False

def remove_admin_id(user_id: int) -> bool:
    """حذف شناسه ادمین فرعی از فایل محلی (ادمین اصلی هرگز حذف نمی‌شود)"""
    try:
        uid = int(user_id)
        if is_owner(uid):
            return False
        saved_list = []
        if os.path.exists(ADMIN_IDS_FILE):
            try:
                with open(ADMIN_IDS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "id" in item:
                                if int(item["id"]) != uid:
                                    saved_list.append(item)
                            elif str(item).isdigit():
                                if int(item) != uid:
                                    saved_list.append({"id": int(item), "name": "همکار"})
            except Exception:
                saved_list = []
        return atomic_save_json(ADMIN_IDS_FILE, saved_list, indent=2)
    except Exception:
        return False

def is_admin(user_id: int) -> bool:
    if not user_id:
        return False
    return user_id in get_all_admin_ids()

def get_orders_live_badge() -> str:
    """محاسبه فوری نشان زنده (Live Badge) برای سفارشات جدید و رسیدهای بررسی نشده"""
    try:
        import sqlite3
        db_file = os.getenv("DB_PATH", "bot_data.db")
        if not os.path.exists(db_file):
            for candidate in ["aikala_bot.db", "aikala.db"]:
                if os.path.exists(candidate):
                    db_file = candidate
                    break
        if not os.path.exists(db_file):
            return ""
        conn = sqlite3.connect(db_file, timeout=2.0)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM orders WHERE status = 'Receipt_Uploaded'")
        row = c.fetchone()
        conn.close()
        count = row[0] if row else 0
        if count > 0:
            return f" ({count} جدید 🔴)"
        return ""
    except Exception:
        return ""

# ─── کیبوردهای منوی اصلی ───

def main_menu_keyboard(is_adm: bool = False) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton("🔍 جستجوی کالا"), KeyboardButton("📂 دسته‌بندی‌ها")],
        [KeyboardButton("🧠 مشاور هوشمند خرید (جمینای)")],
        [KeyboardButton("📋 پیگیری سفارش"), KeyboardButton("ℹ️ راهنمای خرید و ضمانت")],
        [KeyboardButton("💰 نرخ زنده ارز و طلا"), KeyboardButton("📞 پشتیبانی و مشاوره")]
    ]
    if is_adm:
        badge = get_orders_live_badge()
        buttons.append([KeyboardButton(f"📋 سفارشات و رسید بانکی{badge}")])
        buttons.append([KeyboardButton("⚙️ پنل مدیریت ادمین")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# توابع کیبورد راهنمای خرید جهت سازگاری و تفکیک به guidbuy.py منتقل شده‌اند
from guidbuy import help_menu_keyboard, guide_section_keyboard

# ─── قالب‌بندی متن اشتراک‌گذاری کالا ───

def build_product_share_text(p: Optional[Dict[str, Any]], pid_str: str) -> str:
    """تولید متن کامل و شکیل مشخصات کالا جهت ارسال مستقیم به دوستان در تلگرام"""
    clean_pid = str(pid_str or (get_product_id(p) if p else "")).strip()
    deep_link = f"https://t.me/{BOT_USERNAME}?start=p_{clean_pid}" if clean_pid else f"https://t.me/{BOT_USERNAME}"
    if not p:
        return f"مشاهده مشخصات، عکس‌ها و خرید آنی در ربات هوشمند کالا:\n{deep_link}"

    name = get_product_name(p) or "کالای منتخب فروشگاه"
    brand = get_product_brand(p)
    category = get_product_category(p)
    subcategory = str(p.get("subcategory") or "").strip()
    cat_str = category
    if subcategory and subcategory != category:
        cat_str = f"{category} ({subcategory})"

    _, price_str = get_product_price(p)

    lines = [f"🌟 {name}"]

    meta_parts = []
    if brand:
        meta_parts.append(f"🏷 برند: {brand}")
    if cat_str:
        meta_parts.append(f"📂 دسته: {cat_str}")
    if meta_parts:
        lines.append(" | ".join(meta_parts))

    specs = get_product_specs(p)
    NON_SPEC_KEYS = {
        "زیرشاخه", "دسته‌بندی", "دسته", "امتیاز کیفی", "امتیاز",
        "ضمانت اصالت", "گارانتی", "گارانتی و مهلت تست", "مهلت تست و تعویض"
    }

    spec_items = []
    for k, v in specs.items():
        if v and k not in NON_SPEC_KEYS:
            spec_items.append(f"▫️ {k}: {v}")
        if len(spec_items) >= 4:
            break

    if spec_items:
        lines.append("\n📋 مشخصات اصلی:\n" + "\n".join(spec_items))

    if is_laptop_product(p):
        lines.append("\n🛡 گارانتی: یک هفته مهلت تست و تعویض بی‌قید و شرط")
    else:
        lines.append("\n🛡 ضمانت اصالت: ۱۰۰٪ اورجینال با تضمین کتبی\n🛡 گارانتی: ۱۸ ماه گارانتی شرکتی و ۵ سال خدمات پس از فروش")

    lines.append(f"\n💰 قیمت روز: {price_str}")
    lines.append(f"\n🛒 مشاهده مشخصات کامل و سفارش آنلاین در ربات:\n👉 {deep_link}")

    return "\n".join(lines)


# ─── قالب‌بندی پیام مشخصات کالا ───

def build_boxed_product_message(p: Dict[str, Any]) -> str:
    name = get_product_name(p) or "محصول بدون نام"
    brand = get_product_brand(p) or "اورجینال شرکتی"
    category = get_product_category(p) or "لوازم خانگی"
    subcategory = str(p.get("subcategory") or "").strip()
    score = str(p.get("score") or "").strip()

    cat_str = category
    if subcategory and subcategory != category:
        cat_str = f"{category} ({subcategory})"

    meta_parts = [f"🏷 <b>برند:</b> {brand}", f"📂 <b>دسته:</b> {cat_str}"]
    if score:
        meta_parts.append(f"⭐ <b>امتیاز:</b> {score}")
    meta_line = " | ".join(meta_parts)

    raw_price_num, price_str = get_product_price(p)
    specs = get_product_specs(p)

    NON_SPEC_KEYS = {
        "زیرشاخه", "دسته‌بندی", "دسته", "امتیاز کیفی", "امتیاز",
        "ضمانت اصالت", "گارانتی", "گارانتی و مهلت تست", "مهلت تست و تعویض"
    }

    specs_lines = []
    for k, v in specs.items():
        if v and str(v).strip() and k not in NON_SPEC_KEYS:
            val_str = str(v).strip()
            if val_str not in ["-", "--", "---"]:
                specs_lines.append(f"▫️ <b>{k}:</b> {val_str}")

    if not specs_lines:
        specs_lines.append("▫️ <i>مشخصات فنی در حال تکمیل توسط هوش مصنوعی و کارشناسان فنی...</i>")

    specs_quote_content = "\n".join(specs_lines)
    specs_section = (
        f"📋 <b>مشخصات فنی کالا:</b>\n"
        f"<blockquote>{specs_quote_content}</blockquote>"
    )

    if is_laptop_product(p):
        warranty_text = "🛡 <b>گارانتی و مهلت تست:</b> یک هفته ضمانت تست و تعویض"
    else:
        warranty_text = (
            "🛡 <b>ضمانت اصالت:</b> ۱۰۰٪ اورجینال با تضمین کتبی\n"
            "🛡 <b>گارانتی:</b> ۱۸ ماه گارانتی شرکتی و ۵ سال خدمات پس از فروش"
        )

    # بررسی توضیحات تکمیلی تایید شده توسط ادمین (کپشن پست محصول)
    extra_desc = p.get("extra_description") or ""
    if not extra_desc:
        try:
            from photo_service import get_verified_product_caption
            pid = p.get("product_id") or p.get("id")
            if pid:
                extra_desc = get_verified_product_caption(pid)
        except Exception:
            pass

    # بررسی توضیحات هوش مصنوعی یا توضیحات تکمیلی
    ai_desc = str(p.get("ai_generated_description") or "").strip()
    if not ai_desc and extra_desc:
        ai_desc = str(extra_desc).strip()

    extra_desc_block = ""
    if ai_desc:
        # پاکسازی و بهینه‌سازی خوانایی توضیحات تکمیلی
        desc_lines = []
        known_keys = [
            "توان مصرفی (وات)", "روش و محل نصب", "قابلیتهای تکمیلی", "قابلیت‌های تکمیلی",
            "جنس بدنه", "رنگ بدنه", "کشور سازنده", "مدل", "برند", "قطعات", "مونتاژ",
            "WiFi", "وای فای", "ظرفیت", "ابعاد", "وزن", "گارانتی", "رنگ درب"
        ]
        for raw_line in ai_desc.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.endswith(":-") or (line.endswith("-") and not any(c.isdigit() for c in line[-3:])):
                continue
            if ":" in line or "：" in line:
                parts = line.split(":", 1) if ":" in line else line.split("：", 1)
                k_part = parts[0].strip().lstrip("▫️ •-")
                v_part = parts[1].strip()
                desc_lines.append(f"▫️ <b>{html.escape(k_part)}:</b> {html.escape(v_part)}")
                continue
            matched = False
            for k in known_keys:
                if line.startswith(k) and len(line) > len(k):
                    val = line[len(k):].strip(" :-")
                    val = val.replace(",", "، ")
                    desc_lines.append(f"▫️ <b>{html.escape(k)}:</b> {html.escape(val)}")
                    matched = True
                    break
            if not matched:
                clean_l = line.lstrip("▫️ •-").strip()
                desc_lines.append(f"▫️ {html.escape(clean_l)}")

        if desc_lines:
            # ایجاد خط خالی بین هر خط داخل blockquote جهت خوانایی بی‌نظیر
            clean_desc = "\n\n".join(desc_lines)
            extra_desc_block = (
                f"📝 <b>توضیحات تکمیلی و قابلیت‌های کلیدی:</b>\n"
                f"<blockquote expandable>\n{clean_desc}\n</blockquote>"
            )

    clean_pid = str(p.get("product_id") or p.get("id") or "").strip()
    bot_deep_link = f"https://t.me/{BOT_USERNAME}?start=p_{clean_pid}" if clean_pid else f"https://t.me/{BOT_USERNAME}"

    deposit_line = ""
    try:
        if raw_price_num and int(raw_price_num) > 0:
            dep_pct = getattr(config, "DEPOSIT_PERCENT", 8) if config else 8
            dep_amount_raw = int(int(raw_price_num) * (dep_pct / 100.0))
            from config import round_deposit
            dep_amount = round_deposit(dep_amount_raw)
            if dep_amount > 0:
                deposit_line = f"\n✨ <i>تنها با پرداخت <b>{dep_amount:,} تومان</b> بیعانه کالا را خریداری و الباقی را درب منزل تسویه نمایید.</i>\n"
    except Exception:
        deposit_line = ""

    price_quote_block = (
        f"<blockquote>💰 <b>قیمت روز:</b> <code>{price_str}</code>\n"
        f"{deposit_line}"
        f"{PRICE_NOTE}</blockquote>"
    )

    # امضای کالا با ارجاع مستقیم به ربات بدون نمایش پیش‌نمایش وب
    bot_handle = f"@{BOT_USERNAME}"
    share_signature = f'👉 <a href="{bot_deep_link}">{bot_handle}</a>'

    # چیدمان منظم و بدون خطوط جداکننده شلوغ
    msg_parts = [
        f"🌟 <b>{name}</b>\n{meta_line}",
        specs_section
    ]

    # طبق دستور: دو بند ضمانت همیشه بعد از توضیحات تکمیلی بیاید (اگر توضیحات تکمیلی داشت)
    if extra_desc_block:
        msg_parts.append(extra_desc_block)
        msg_parts.append(warranty_text)
    else:
        msg_parts.append(warranty_text)

    msg_parts.append(price_quote_block)
    msg_parts.append(share_signature)

    msg = "\n\n".join(msg_parts)
    return msg

# ─── کیبورد زیر هر کارت کالا ───

def product_inline_keyboard(
    pid: str,
    context: Optional[ContextTypes.DEFAULT_TYPE] = None,
    show_photo_button: bool = True,
    is_admin: bool = False,
    view_as_customer: bool = False
) -> InlineKeyboardMarkup:
    """دکمه‌های اقدام زیر کارت کالا:
    - برای ادمین: کنسول اختصاصی درجا (تغییر عکس، حذف عکس، تنظیم قیمت، پنهان/نمایش، دریافت لینک سریع، مشاهده از دید مشتری)
    - برای مشتری: استعلام قیمت و کرایه، تصاویر محصول، تماس با پشتیبانی و اشتراک‌گذاری با دوستان
    """
    pid_str = str(pid if pid is not None else "").strip()

    # کنسول اختصاصی ادمین در زیر کارت کالا
    if is_admin and not view_as_customer:
        try:
            from search_engine import is_product_hidden
            is_hidden = is_product_hidden(pid_str)
        except Exception:
            is_hidden = False

        toggle_label = "🔴 کالا پنهان است (کلیک: فعال‌سازی)" if is_hidden else "👁‍🗨 پنهان‌سازی کالا"

        buttons = [
            [
                InlineKeyboardButton("🖼 تغییر عکس کالا", callback_data=make_safe_cb("adm_pimg", pid_str)),
                InlineKeyboardButton("🗑 حذف عکس فعلی", callback_data=make_safe_cb("adm_pimgdel", pid_str)),
            ],
            [
                InlineKeyboardButton("✏️ تنظیم دستی قیمت", callback_data=make_safe_cb("adm_pprice", pid_str)),
                InlineKeyboardButton("📝 تغییر مشخصات فنی", callback_data=make_safe_cb("adm_pspec", pid_str)),
            ],
            [
                InlineKeyboardButton("🤖 استخراج مجدد (AI)", callback_data=make_safe_cb("adm_paispec", pid_str)),
                InlineKeyboardButton(toggle_label, callback_data=make_safe_cb("adm_ptog", pid_str)),
            ],
            [
                InlineKeyboardButton("🔗 دریافت لینک برای مشتری", callback_data=make_safe_cb("adm_plink", pid_str)),
                InlineKeyboardButton("👥 مشاهده از دید مشتری", callback_data=make_safe_cb("adm_pcust", pid_str)),
            ]
        ]
        return InlineKeyboardMarkup(buttons)

    # محصولات لپ‌تاپ فاقد تصویر آلبومی هستند؛ دکمه تصاویر برای لپ‌تاپ نمایش داده نمی‌شود
    if pid_str.upper().startswith("LAP"):
        show_photo_button = False

    # دکمه مستقیم اشتراک‌گذاری با دوستان در تلگرام (همراه با متن کامل مشخصات و قیمت کالا)
    prod_data = find_product_by_id(pid_str) if pid_str else None

    deep_link = f"https://t.me/{BOT_USERNAME}?start=p_{pid_str}" if pid_str else f"https://t.me/{BOT_USERNAME}"
    share_text = build_product_share_text(prod_data, pid_str)
    share_url = f"https://t.me/share/url?url={urllib.parse.quote(deep_link)}&text={urllib.parse.quote(share_text)}"

    buttons = [
        [
            InlineKeyboardButton("💰 استعلام قیمت تمام‌شده و کرایه", callback_data=make_safe_cb("inq", pid_str))
        ],
        [
            InlineKeyboardButton("🧠 مشاور هوشمند خرید (جمینای)", callback_data=make_safe_cb("adv_prod", pid_str))
        ]
    ]

    # قرارگیری دکمه تصاویر محصول و اشتراک‌گذاری در یک ردیف
    media_and_share_row = []
    if show_photo_button:
        media_and_share_row.append(
            InlineKeyboardButton("📸 تصاویر محصول", callback_data=make_safe_cb("req_img", pid_str))
        )
    media_and_share_row.append(
        InlineKeyboardButton("📤 اشتراک‌گذاری", url=share_url)
    )
    buttons.append(media_and_share_row)

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت به نتایج جستجو", callback_data="back_to_search"),
        InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")
    ])

    # دکمه بازگشت به پنل مدیریت در صورت تست حالت مشتری توسط ادمین
    if is_admin and view_as_customer:
        buttons.append([
            InlineKeyboardButton("⚙️ بازگشت به ابزارهای مدیریت کالا", callback_data=make_safe_cb("adm_pback", pid_str))
        ])

    return InlineKeyboardMarkup(buttons)

def inquiry_quote_keyboard(pid: str, req_id: Any = None) -> InlineKeyboardMarkup:
    """کیبورد ارسالی به مشتری همراه با قیمت اعلامی ادمین شامل ثبت سفارش و صدور پیش‌فاکتور"""
    pid_str = str(pid if pid is not None else "").strip()
    payload = f"{pid_str}:{req_id}" if req_id is not None else pid_str
    buttons = [
        [
            InlineKeyboardButton("🛒 ثبت سفارش و صدور پیش‌فاکتور رسمی", callback_data=make_safe_cb("buy", payload))
        ],
        [
            InlineKeyboardButton("📞 پشتیبانی و مشاوره", callback_data="show_support"),
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

# ─── صفحه‌بندی نتایج جستجو ───

async def show_search_page(update: Update, context: ContextTypes.DEFAULT_TYPE, products: List[Dict[str, Any]], page: int = 0):
    context.user_data["search_page"] = page
    page_size = 5
    total = len(products)
    start = page * page_size
    end = start + page_size
    current_batch = products[start:end]

    buttons = []
    for p in current_batch:
        pid = str(p.get("product_id", "")).strip()
        if not pid:
            pid = str(clean_key(p.get("name", "")))[:20]
        name = str(p.get("name", "")).strip()[:38]
        cb = make_safe_cb("sel", pid)
        buttons.append([InlineKeyboardButton(f"🔹 {name}", callback_data=cb)])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"spage|{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"spage|{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")])

    kb = InlineKeyboardMarkup(buttons)
    text = f"🔍 <b>تعداد {total} محصول منطبق یافت شد:</b> (صفحه {page+1} از {((total-1)//page_size)+1})"

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
