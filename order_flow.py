"""
AiKala - Order Flow & Proforma Invoice Generator (order_flow.py)
================================================================
فرآیند چندمرحله‌ای صدور پیش‌فاکتور رسمی، اخذ بیعانه و آپلود فیش بانکی.
"""
import time


import os
import io
import re
import json
import random
import logging
import asyncio
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

try:
    import config
except ImportError:
    config = None

CARD_NUMBER = getattr(config, "CARD_NUMBER", getattr(config, "CARD_NO", ""))
CARD_HOLDER = getattr(config, "CARD_HOLDER", getattr(config, "CARD_NAME", ""))
CARD_SHABA = getattr(config, "CARD_SHABA", "")
SHABA_HTML = getattr(config, "SHABA_HTML", "")
DEPOSIT_AMOUNT = getattr(config, "DEPOSIT_AMOUNT", "")
SUPPORT_USERNAME = getattr(config, "SUPPORT_USERNAME", "@AiKala_Admin")
ADMIN_IDS = getattr(config, "ADMIN_IDS", [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()] if os.getenv("ADMIN_IDS") else [])

from database import Database
from search_engine import JSON_PRODUCTS, _normalize_digits
from keyboards import resolve_safe_cb, main_menu_keyboard, is_admin
from invoice_service import generate_invoice_png, build_invoice_data_from_order, to_fa_digits

logger = logging.getLogger(__name__)
db = Database()

def is_cancel_text(text: str) -> bool:
    """بررسی ارسال عبارات انصراف توسط کاربر در هر یک از مراحل متنی"""
    if not text:
        return False
    t = text.strip().lower()
    return t in [
        "/cancel", "لغو", "انصراف", "❌ لغو سفارش", "❌ انصراف از خرید",
        "لغو سفارش", "انصراف از خرید", "انصراف", "cancel", "خروج"
    ]

def normalize_iran_phone(raw_phone: str) -> str:
    """استانداردسازی شماره موبایل ارسالی تلگرام یا دستی به فرمت ۰۹۱۲۳۴۵۶۷۸۹"""
    if not raw_phone:
        return ""
    cleaned = re.sub(r'[^0-9]', '', _normalize_digits(raw_phone))
    if cleaned.startswith("0098"):
        cleaned = "0" + cleaned[4:]
    elif cleaned.startswith("98") and len(cleaned) == 12:
        cleaned = "0" + cleaned[2:]
    elif len(cleaned) == 10 and cleaned.startswith("9"):
        cleaned = "0" + cleaned
    return cleaned

def reverse_geocode(lat: float, lon: float) -> Dict[str, str]:
    """تبدیل مختصات جغرافیایی به آدرس متنی فارسی با استفاده از سرویس نقشه‌باز اوپن‌استریت‌مپ"""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1&accept-language=fa"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AiKalaBot/1.0 (contact: admin@aikala.ir)"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            addr = data.get("address", {})
            province = addr.get("state", "")
            city = addr.get("city") or addr.get("town") or addr.get("county") or addr.get("municipality", "")
            suburb = addr.get("suburb") or addr.get("neighbourhood") or addr.get("quarter", "")
            road = addr.get("road") or addr.get("pedestrian") or addr.get("amenity", "")
            postcode = addr.get("postcode", "")

            parts = []
            if province:
                parts.append(province)
            if city and city != province:
                parts.append(city)
            if suburb:
                parts.append(suburb)
            if road:
                parts.append(road)

            readable = "، ".join(parts) if parts else data.get("display_name", "")
            return {
                "province": province,
                "city": city,
                "suburb": suburb,
                "road": road,
                "postcode": postcode,
                "readable_address": readable,
                "display_name": data.get("display_name", "")
            }
    except Exception as e:
        logger.warning(f"Reverse geocoding warning: {e}")
        return {}

# ─── متغیرهای استیت کانوِرسیشن ───
ORDER_NAME, ORDER_PHONE1, ORDER_PHONE2, ORDER_CITY, ORDER_ADDRESS, ORDER_POSTAL, ORDER_CONFIRM = range(7)
RECEIPT_FILE = 20

# ─── مراحل گفتگوی ثبت سفارش ───

async def start_order_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    raw_payload = resolve_safe_cb(query.data)

    req_id = None
    if ":" in raw_payload:
        pid, req_id_str = raw_payload.split(":", 1)
        if req_id_str.isdigit():
            req_id = int(req_id_str)
    else:
        pid = raw_payload

    user_id = update.effective_user.id if update.effective_user else 0

    product = None
    for p in JSON_PRODUCTS:
        if str(p.get("product_id")) == str(pid):
            product = p
            break

    if not product:
        product = await db.get_product_by_id(pid)

    if not product:
        product = context.user_data.get("last_viewed_product") or context.user_data.get("current_product")

    if not product:
        product = {
            "product_id": pid or "CUSTOM",
            "name": f"کالای انتخابی هوشمند کالا (کد {pid})",
            "brand": "اورجینال شرکتی",
            "price": "طبق استعلام روز"
        }

    # استخراج قیمت قطعی اعلامی توسط ادمین (مبنای اصلی) یا قیمت کاتالوگ
    inq = None
    if req_id:
        inq = await db.get_price_inquiry(req_id)
    if not inq and user_id:
        inq = await db.get_latest_user_inquiry(user_id, pid)

    shipping_method = (inq.get("shipping_method") if inq else "") or "freight"

    total_price = 0
    if inq:
        p_raw = str(inq.get("final_price") or inq.get("admin_response") or "")
        clean_p = _normalize_digits(p_raw).replace(",", "").replace("،", "").strip()
        digits = re.findall(r'\d+', clean_p)
        if digits:
            try:
                total_price = int("".join(digits))
            except Exception:
                total_price = 0

    if total_price == 0 and product and product.get("price"):
        clean_p = _normalize_digits(str(product.get("price"))).replace(",", "").replace("،", "").strip()
        digits = re.findall(r'\d+', clean_p)
        if digits:
            try:
                total_price = int("".join(digits))
            except Exception:
                total_price = 0

    # محاسبه بیعانه رند شده به عنوان پیش‌پرداخت بر اساس شیوه ارسال
    deposit = 0
    if total_price > 0:
        if shipping_method == "post":
            deposit = total_price
        else:
            dep_pct = getattr(config, "DEPOSIT_PERCENT", 8)
            deposit = int(round((total_price * (dep_pct / 100.0)) / 10000)) * 10000
            if deposit == 0:
                deposit = int(round((total_price * (dep_pct / 100.0)) / 1000)) * 1000

    context.user_data["order_shipping_method"] = shipping_method
    context.user_data["order_total_price"] = total_price
    context.user_data["order_deposit"] = deposit
    context.user_data["order_inquiry_id"] = req_id or (inq.get("id") if inq else None)
    if total_price > 0:
        product["price"] = str(total_price)

    context.user_data["order_product"] = product
    start_kb = ReplyKeyboardMarkup([
        [KeyboardButton("❌ انصراف از خرید")]
    ], resize_keyboard=True)
    await query.message.reply_text(
        f"📝 <b>مرحله ۱ از ۵:</b>\n"
        f"شما در حال ثبت سفارش برای <b>{product.get('name')}</b> هستید.\n\n"
        f"👤 لطفاً <b>نام و نام‌خانوادگی</b> تحویل‌گیرنده را ارسال فرمایید:\n"
        f"<i>(جهت انصراف کلمه «لغو» را ارسال نمایید)</i>",
        reply_markup=start_kb,
        parse_mode="HTML"
    )
    return ORDER_NAME

async def order_name_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message.text else ""
    if is_cancel_text(text):
        return await cancel_conversation(update, context)

    context.user_data["order_name"] = text

    contact_kb = ReplyKeyboardMarkup([
        [KeyboardButton("📱 ارسال خودکار شماره موبایل من", request_contact=True)],
        [KeyboardButton("❌ انصراف از خرید")]
    ], resize_keyboard=True)

    await update.message.reply_text(
        "📱 <b>مرحله ۲ از ۵:</b>\n"
        "لطفاً <b>شماره موبایل اصلی</b> جهت هماهنگی ارسال را وارد کنید:\n\n"
        "💡 <i>می‌توانید دکمه «📱 ارسال خودکار شماره موبایل من» در پایین صفحه را لمس کنید، یا شماره را به صورت متنی تایپ نمایید (مثال: 09123456789).</i>",
        reply_markup=contact_kb,
        parse_mode="HTML"
    )
    return ORDER_PHONE1

async def order_phone1_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = ""
    if update.message.contact:
        raw_phone = update.message.contact.phone_number
        phone = normalize_iran_phone(raw_phone)
    elif update.message.text:
        text = update.message.text.strip()
        if is_cancel_text(text):
            return await cancel_conversation(update, context)
        phone = normalize_iran_phone(text)

    if not re.search(r'^09\d{9}$', phone):
        contact_retry_kb = ReplyKeyboardMarkup([
            [KeyboardButton("📱 ارسال خودکار شماره موبایل من", request_contact=True)],
            [KeyboardButton("❌ انصراف از خرید")]
        ], resize_keyboard=True)
        await update.message.reply_text(
            "❌ لطفاً یک شماره موبایل معتبر ۱۱ رقمی (مثال: 09123456789) وارد فرمایید یا دکمه <b>«📱 ارسال خودکار شماره موبایل من»</b> را لمس کنید:",
            reply_markup=contact_retry_kb,
            parse_mode="HTML"
        )
        return ORDER_PHONE1

    context.user_data["order_phone1"] = phone

    phone2_kb = ReplyKeyboardMarkup([
        [KeyboardButton("ندارم")],
        [KeyboardButton("❌ انصراف از خرید")]
    ], resize_keyboard=True)

    await update.message.reply_text(
        "📞 <b>مرحله ۳ از ۵:</b>\n"
        "لطفاً <b>شماره تماس دوم یا اضطراری</b> را ارسال فرمایید:\n\n"
        "💡 <i>در صورت عدم تمایل دکمه «ندارم» را لمس کنید یا بنویسید «ندارم».</i>",
        reply_markup=phone2_kb,
        parse_mode="HTML"
    )
    return ORDER_PHONE2

async def order_phone2_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message.text else ""
    if is_cancel_text(text):
        return await cancel_conversation(update, context)

    context.user_data["order_phone2"] = text

    loc_city_kb = ReplyKeyboardMarkup([
        [KeyboardButton("📍 ارسال لوکیشن (تعیین خودکار استان و شهر)", request_location=True)],
        [KeyboardButton("❌ انصراف از خرید")]
    ], resize_keyboard=True)

    await update.message.reply_text(
        "📍 <b>مرحله ۴ از ۵:</b>\n"
        "لطفاً <b>استان و شهر</b> مقصد را وارد فرمایید (مثال: تهران - تهران):\n\n"
        "💡 <i>همچنین می‌توانید با لمس دکمه زیر، لوکیشن نقشه خود را بفرستید تا استان و شهر به صورت خودکار شناسایی شوند.</i>",
        reply_markup=loc_city_kb,
        parse_mode="HTML"
    )
    return ORDER_CITY

async def order_city_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        maps_url = f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"
        context.user_data["order_location_url"] = maps_url
        context.user_data["order_lat"] = lat
        context.user_data["order_lon"] = lon

        geo_info = await asyncio.to_thread(reverse_geocode, lat, lon)
        city = geo_info.get("city") or geo_info.get("province") or "مشخص‌شده با لوکیشن"
        prov = geo_info.get("province") or ""
        city_display = f"{prov} - {city}" if prov and city != prov else (city or "مشخص‌شده با لوکیشن")
        context.user_data["order_city"] = city_display

        addr_parts = []
        if geo_info.get("readable_address"):
            addr_parts.append(f"📌 نشانی تقریبی: {geo_info['readable_address']}")
        addr_parts.append(f"📍 موقعیت نقشه: {maps_url}")
        resolved_address = "\n".join(addr_parts)
        context.user_data["order_address"] = resolved_address

        if geo_info.get("postcode"):
            clean_postcode = geo_info["postcode"].replace("-", "")
            if len(clean_postcode) == 10:
                context.user_data["order_postal"] = clean_postcode

        addr_kb = ReplyKeyboardMarkup([
            [KeyboardButton("تایید همین آدرس لوکیشن")],
            [KeyboardButton("📍 ارسال مجدد لوکیشن", request_location=True)],
            [KeyboardButton("❌ انصراف از خرید")]
        ], resize_keyboard=True)

        await update.message.reply_text(
            f"✅ <b>موقعیت مکانی شما با موفقیت شناسایی شد:</b>\n"
            f"📍 شهر و استان: <b>{city_display}</b>\n"
            f"🏠 نشانی اولیه: <b>{geo_info.get('readable_address', 'ثبت‌شده با مختصات GPS')}</b>\n\n"
            f"🏢 لطفاً <b>پلاک، واحد یا جزئیات دقیق آدرس</b> را بنویسید (یا اگر همین نشانی کافی است، دکمه «تایید همین آدرس لوکیشن» را بزنید):",
            reply_markup=addr_kb,
            parse_mode="HTML"
        )
        return ORDER_ADDRESS

    text = update.message.text.strip() if update.message.text else ""
    if is_cancel_text(text):
        return await cancel_conversation(update, context)

    context.user_data["order_city"] = text

    addr_kb = ReplyKeyboardMarkup([
        [KeyboardButton("📍 ارسال موقعیت مکانی (لوکیشن نقشه)", request_location=True)],
        [KeyboardButton("❌ انصراف از خرید")]
    ], resize_keyboard=True)

    await update.message.reply_text(
        "🏠 <b>مرحله ۵ از ۵:</b>\n"
        "لطفاً <b>آدرس دقیق پستی</b> (شامل خیابان، کوچه، پلاک و واحد) را ارسال فرمایید:\n\n"
        "💡 <i>می‌توانید آدرس را تایپ کنید، یا با لمس دکمه زیر لوکیشن نقشه ارسال کنید تا تحویل درب منزل سریع‌تر انجام گیرد.</i>",
        reply_markup=addr_kb,
        parse_mode="HTML"
    )
    return ORDER_ADDRESS

async def order_address_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        maps_url = f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"
        context.user_data["order_location_url"] = maps_url
        context.user_data["order_lat"] = lat
        context.user_data["order_lon"] = lon

        geo_info = await asyncio.to_thread(reverse_geocode, lat, lon)
        readable = geo_info.get("readable_address", "")
        if not context.user_data.get("order_city") and (geo_info.get("city") or geo_info.get("province")):
            p = geo_info.get("province", "")
            c = geo_info.get("city", "")
            context.user_data["order_city"] = f"{p} - {c}".strip(" -")

        existing_addr = context.user_data.get("order_address", "")
        if existing_addr and "لوکیشن" not in existing_addr:
            combined = f"{existing_addr}\n📍 لوکیشن نقشه: {maps_url}"
            if readable:
                combined += f"\n📌 محدوده نقشه: {readable}"
            context.user_data["order_address"] = combined
        else:
            context.user_data["order_address"] = f"📍 لوکیشن نقشه: {maps_url}\n📌 نشانی: {readable}" if readable else f"📍 لوکیشن نقشه: {maps_url}"

        if geo_info.get("postcode") and not context.user_data.get("order_postal"):
            clean_code = geo_info["postcode"].replace("-", "")
            if len(clean_code) == 10:
                context.user_data["order_postal"] = clean_code

        postal_kb = ReplyKeyboardMarkup([
            [KeyboardButton("ندارم")],
            [KeyboardButton("❌ انصراف از خرید")]
        ], resize_keyboard=True)

        await update.message.reply_text(
            f"✅ <b>موقعیت مکانی شما با موفقیت دریافت گردید.</b>\n"
            f"🗺 <a href=\"{maps_url}\">مشاهده موقعیت روی نقشه گوگل</a>\n"
            f"📌 نشانی نقشه: {readable or 'مختصات GPS ثبت شد'}\n\n"
            f"📮 لطفاً <b>کد پستی ۱۰ رقمی</b> را ارسال فرمایید (یا در صورت نداشتن دکمه «ندارم» را بزنید):",
            reply_markup=postal_kb,
            parse_mode="HTML"
        )
        return ORDER_POSTAL

    text = update.message.text.strip() if update.message.text else ""
    if is_cancel_text(text):
        return await cancel_conversation(update, context)

    if text == "تایید همین آدرس لوکیشن":
        if not context.user_data.get("order_address"):
            context.user_data["order_address"] = "ثبت‌شده از طریق موقعیت مکانی (لوکیشن)"
    else:
        loc_url = context.user_data.get("order_location_url", "")
        if loc_url and "لوکیشن" not in text:
            context.user_data["order_address"] = f"{text}\n📍 لوکیشن نقشه: {loc_url}"
        else:
            context.user_data["order_address"] = text

    postal_kb = ReplyKeyboardMarkup([
        [KeyboardButton("ندارم")],
        [KeyboardButton("❌ انصراف از خرید")]
    ], resize_keyboard=True)

    await update.message.reply_text(
        "📮 لطفاً <b>کد پستی ۱۰ رقمی</b> را ارسال فرمایید (یا در صورت نداشتن دکمه «ندارم» را بزنید):\n"
        "<i>(جهت انصراف کلمه «لغو» را ارسال نمایید)</i>",
        reply_markup=postal_kb,
        parse_mode="HTML"
    )
    return ORDER_POSTAL

async def order_postal_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message.text else ""
    if is_cancel_text(text):
        return await cancel_conversation(update, context)

    context.user_data["order_postal"] = text
    return await show_order_confirmation(update, context)

async def show_order_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش مشخصات ثبت‌شده به کاربر و درخواست تایید، اصلاح یا لغو سفارش"""
    prod = context.user_data.get("order_product", {})
    total_price = context.user_data.get("order_total_price", 0)
    deposit = context.user_data.get("order_deposit", 0)
    shipping_method = context.user_data.get("order_shipping_method", "freight")
    is_post = (shipping_method == "post")
    dep_pct = getattr(config, "DEPOSIT_PERCENT", 8)

    if total_price == 0 or deposit == 0:
        clean_p = _normalize_digits(str(prod.get("price", "0"))).replace(",", "").replace("،", "").strip()
        digits = re.findall(r'\d+', clean_p)
        if digits:
            try:
                total_price = int("".join(digits))
                if is_post:
                    deposit = total_price
                else:
                    deposit = int(round((total_price * (dep_pct / 100.0)) / 10000)) * 10000
                    if deposit == 0:
                        deposit = int(round((total_price * (dep_pct / 100.0)) / 1000)) * 1000
            except Exception:
                pass

    if is_post:
        deposit = total_price
        remaining = 0
    else:
        remaining = max(0, total_price - deposit)

    f_total_price = to_fa_digits(f"{total_price:,}")
    f_deposit = to_fa_digits(f"{deposit:,}")
    f_remaining = to_fa_digits(f"{remaining:,}")

    # ارسال کیبورد منوی اصلی جهت پایداری همیشگی دکمه‌های ربات
    user_id = update.effective_user.id if update.effective_user else 0
    if update.message:
        try:
            await update.message.reply_text(
                "📋 <i>در حال آماده‌سازی پیش‌نمایش نهایی سفارش...</i>",
                reply_markup=main_menu_keyboard(is_admin(user_id)),
                parse_mode="HTML"
            )
        except Exception:
            pass

    name = context.user_data.get("order_name", "-")
    phone1 = context.user_data.get("order_phone1", "-")
    phone2 = context.user_data.get("order_phone2", "-")
    city = context.user_data.get("order_city", "-")
    address = context.user_data.get("order_address", "-")
    postal = context.user_data.get("order_postal", "-")
    loc_url = context.user_data.get("order_location_url", "")
    loc_display = f"\n▫️ <b>موقعیت روی نقشه:</b> <a href=\"{loc_url}\">مشاهده در نقشه</a>" if loc_url else ""

    if is_post:
        method_badge = "📮 پست پیشتاز (تسویه ۱۰۰٪ کامل - بدون بیعانه)"
        deposit_line = f"💳 <b>مبلغ قابل واریز (تسویه کامل):</b> <code>{f_total_price} تومان</code>\n"
        remaining_line = "▫️ <b>مانده در محل:</b> <code>۰ تومان (تسویه کامل قبل از ارسال)</code>\n"
        confirm_step_text = "صدور پیش‌فاکتور رسمی و دریافت مشخصات حساب بانکی جهت تسویه کامل وجه"
    else:
        method_badge = f"🚚 باربری / پیک (بیعانه {dep_pct}٪ + تسویه در محل)"
        deposit_line = f"💳 <b>مبلغ بیعانه پیش‌پرداخت ({dep_pct}٪):</b> <code>{f_deposit} تومان</code>\n"
        remaining_line = f"▫️ <b>مانده تسویه در محل:</b> <code>{f_remaining} تومان</code>\n"
        confirm_step_text = "صدور پیش‌فاکتور رسمی و دریافت مشخصات حساب بانکی جهت واریز بیعانه"

    phone2_val = f"<code>{phone2}</code>" if phone2 and phone2 != "ندارم" else (phone2 or "ندارم")

    confirm_msg = (
        "📋 <b>پیش‌نمایش و بررسی نهایی مشخصات سفارش:</b>\n\n"
        f"<blockquote>📦 <b>کالای انتخابی:</b> {prod.get('name', 'کالای سفارشی')}\n"
        f"🛵 <b>نحوه ارسال:</b> {method_badge}\n"
        f"💰 <b>مبلغ کل کالا:</b> <code>{f_total_price} تومان</code>\n"
        f"{deposit_line}"
        f"{remaining_line[:-1]}</blockquote>\n\n"
        f"<blockquote>👤 <b>مشخصات تحویل‌گیرنده:</b> {name}\n"
        f"📱 <b>شماره موبایل اصلی:</b> <code>{phone1}</code>\n"
        f"▫️ <b>شماره تماس دوم / اضطراری:</b> {phone2_val}\n"
        f"📍 <b>استان و شهر مقصد:</b> {city}\n"
        f"🏠 <b>نشانی دقیق پستی:</b> {address}{loc_display}\n"
        f"📮 <b>کد پستی:</b> <code>{postal}</code></blockquote>\n\n"
        "❓ <b>خریدار گرامی، آیا اطلاعات واردشده فوق را تایید می‌فرمایید؟</b>\n\n"
        f"▫️ <b>✅ تایید و ثبت نهایی:</b> {confirm_step_text}\n"
        "▫️ <b>✏️ اصلاح مشخصات:</b> ویرایش مجدد اطلاعات وارد شده\n"
        "▫️ <b>❌ لغو کامل سفارش:</b> انصراف کامل از خرید و بازگشت به منو"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و ثبت نهایی سفارش", callback_data="ord_confirm_final")],
        [
            InlineKeyboardButton("✏️ اصلاح مشخصات", callback_data="ord_edit_info"),
            InlineKeyboardButton("❌ لغو کامل سفارش", callback_data="ord_cancel_flow")
        ]
    ])

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(confirm_msg, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(confirm_msg, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(confirm_msg, reply_markup=kb, parse_mode="HTML")

    return ORDER_CONFIRM

async def order_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دکمه‌های تایید، اصلاح و لغو در صفحه بررسی نهایی سفارش"""
    query = update.callback_query
    data = query.data

    if data == "ord_confirm_final":
        return await finalize_order(update, context)

    elif data == "ord_edit_info":
        await query.answer("ویرایش مشخصات...")
        edit_kb = ReplyKeyboardMarkup([
            [KeyboardButton("❌ انصراف از خرید")]
        ], resize_keyboard=True)
        await query.message.reply_text(
            "✏️ <b>اصلاح مشخصات خریدار:</b>\n"
            "لطفاً <b>نام و نام‌خانوادگی</b> جدید تحویل‌گیرنده را ارسال فرمایید:\n"
            "<i>(جهت انصراف کلمه «لغو» را ارسال فرمایید)</i>",
            reply_markup=edit_kb,
            parse_mode="HTML"
        )
        return ORDER_NAME

    elif data == "ord_cancel_flow":
        await query.answer("سفارش لغو شد.")
        for key in [
            "order_name", "order_phone1", "order_phone2", "order_city",
            "order_address", "order_postal", "order_product", "order_total_price",
            "order_deposit", "order_inquiry_id", "order_location_url",
            "order_lat", "order_lon"
        ]:
            context.user_data.pop(key, None)

        user_id = update.effective_user.id if update.effective_user else 0
        cancel_text = (
            "❌ <b>ثبت سفارش با موفقیت لغو گردید.</b>\n\n"
            "▫️ هیچ اطلاعاتی ثبت یا ذخیره نشد.\n"
            "▫️ در هر زمان می‌توانید از طریق منوی اصلی کاتالوگ فروشگاه را مشاهده یا سفارش جدیدی ثبت فرمایید."
        )
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 منوی اصلی فروشگاه", callback_data="back_to_main")]
        ])
        try:
            await query.edit_message_text(cancel_text, reply_markup=cancel_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(cancel_text, reply_markup=cancel_kb, parse_mode="HTML")

        try:
            await query.message.reply_text(
                "📋 <i>دکمه‌های منوی اصلی در پایین صفحه:</i>",
                reply_markup=main_menu_keyboard(is_admin(user_id)),
                parse_mode="HTML"
            )
        except Exception:
            pass

        return ConversationHandler.END

    return ORDER_CONFIRM

async def order_confirm_text_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر ورودی متنی در وضعیت تایید سفارش"""
    text = update.message.text.strip() if update.message.text else ""
    if is_cancel_text(text):
        return await cancel_conversation(update, context)
    return await show_order_confirmation(update, context)

async def finalize_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت نهایی سفارش در دیتابیس و صدور پیش‌فاکتور رسمی"""
    query = update.callback_query
    if query:
        await query.answer("در حال ثبت سفارش و صدور پیش‌فاکتور...", show_alert=False)

    user = update.effective_user
    prod = context.user_data.get("order_product", {})
    
    order_code = f"AK-{int(datetime.now().timestamp())%1000000:06d}"
    
    total_price = context.user_data.get("order_total_price", 0)
    deposit = context.user_data.get("order_deposit", 0)

    shipping_method = context.user_data.get("order_shipping_method", "freight")
    is_post = (shipping_method == "post")
    dep_pct = getattr(config, "DEPOSIT_PERCENT", 8)

    if total_price == 0 or deposit == 0:
        clean_p = _normalize_digits(str(prod.get("price", "0"))).replace(",", "").replace("،", "").strip()
        digits = re.findall(r'\d+', clean_p)
        if digits:
            try:
                total_price = int("".join(digits))
                if is_post:
                    deposit = total_price
                else:
                    deposit = int(round((total_price * (dep_pct / 100.0)) / 10000)) * 10000
                    if deposit == 0:
                        deposit = int(round((total_price * (dep_pct / 100.0)) / 1000)) * 1000
            except Exception:
                pass

    if is_post:
        deposit = total_price
        remaining = 0
    else:
        remaining = max(0, total_price - deposit)

    order_data = {
        "order_code": order_code,
        "user_id": user.id,
        "username": f"@{user.username}" if user.username else "",
        "product_id": prod.get("product_id", ""),
        "product_name": prod.get("name", ""),
        "full_name": context.user_data.get("order_name"),
        "phone1": context.user_data.get("order_phone1"),
        "phone2": context.user_data.get("order_phone2"),
        "province_city": context.user_data.get("order_city"),
        "address": context.user_data.get("order_address"),
        "postal_code": context.user_data.get("order_postal"),
        "total_price": str(total_price),
        "deposit_amount": str(deposit),
        "shipping_method": shipping_method,
        "status": "Awaiting_Payment"
    }

    await db.create_order(order_data)

    # ۱. تولید پیش‌فاکتور رسمی دیجیتال (Ultra HD PNG) با برچسب متناسب شیوه ارسال
    invoice_path = None
    out_png = f"invoices/pre_invoice_{order_code}.png"
    try:
        inv_data = build_invoice_data_from_order(order_data, prod)
        os.makedirs("invoices", exist_ok=True)
        invoice_path = await asyncio.to_thread(generate_invoice_png, inv_data, output_path=out_png, is_pre_invoice=True)
    except Exception as e:
        logger.error(f"Async pre-invoice generation failed: {e}")

    # فال‌بک تولید مستقیم سنکرون در صورت عدم موفقیت در ترد
    if not invoice_path or not os.path.exists(invoice_path):
        try:
            inv_data = build_invoice_data_from_order(order_data, prod)
            invoice_path = generate_invoice_png(inv_data, output_path=out_png, is_pre_invoice=True)
        except Exception as e2:
            logger.error(f"Sync fallback pre-invoice generation error: {e2}")

    f_total_price = to_fa_digits(f"{total_price:,}")
    f_deposit = to_fa_digits(f"{deposit:,}")
    f_remaining = to_fa_digits(f"{remaining:,}")

    # خواندن پویای مشخصات حساب بانکی تنظیم‌شده توسط ادمین
    card_number = getattr(config, "CARD_NUMBER", "")
    card_holder = getattr(config, "CARD_HOLDER", "")
    shaba_html = getattr(config, "SHABA_HTML", "")

    bank_lines = []
    if card_number:
        card_lbl = "▫️ شماره کارت جهت تسویه حساب کامل سفارش:" if is_post else "▫️ شماره کارت واریز بیعانه:"
        bank_lines.append(f"{card_lbl} <code>{card_number}</code>")
    if shaba_html:
        bank_lines.append(f"▫️ شماره شبا بانکی: {shaba_html}")
    if card_holder:
        bank_lines.append(f"▫️ به نام: <b>{card_holder}</b>")

    if not bank_lines:
        bank_block = "▫️ <b>اطلاعات حساب بانکی:</b> متعاقباً توسط واحد فروش و حسابداری اعلام می‌گردد."
    else:
        bank_block = "\n".join(bank_lines)

    if is_post:
        doc_status = "پیش‌فاکتور رسمی (در انتظار تسویه کامل وجه)"
        pay_amount_line = f"💳 <b>مبلغ قابل واریز (تسویه کامل):</b> <code>{f_total_price} تومان</code>"
        rem_amount_line = "▫️ <b>مانده در محل:</b> <code>۰ تومان (تسویه کامل قبل از ارسال)</code>"
        shipping_desc_line = "📮 <b>نحوه ارسال:</b> پست پیشتاز (ارسال مستقیم به سراسر کشور)"
        note_text = f"⚠️ <i>نکته مهم: این سفارش با پست پیشتاز ارسال می‌گردد. لطفاً مبلغ ({f_total_price} تومان) را واریز و عکس فیش را ارسال فرمایید تا مرسوله با بیمه کامل سلامت تحویل پست گردد.</i>"
    else:
        doc_status = "پیش‌فاکتور رسمی (در انتظار واریز بیعانه)"
        pay_amount_line = f"💳 <b>مبلغ بیعانه پیش‌پرداخت ({dep_pct}٪):</b> <code>{f_deposit} تومان</code>"
        rem_amount_line = f"▫️ <b>مانده تسویه پس از تحویل و تست سلامت:</b> <code>{f_remaining} تومان</code>"
        shipping_desc_line = f"🚚 <b>نحوه ارسال:</b> باربری اختصاصی (تحویل درب منزل با بیعانه {dep_pct}٪)"
        note_text = f"⚠️ <i>نکته مهم: جهت قطعی شدن سفارش و صدور فاکتور نهایی فروش با مهر شرکتی، لطفاً بیعانه ({f_deposit} تومان) را واریز و عکس فیش را ارسال فرمایید.</i>"

    invoice_msg = (
        f"🧾 <b>پیش‌فاکتور رسمی سفارش @AiKala_bot هوشمند کالا</b>\n\n"
        f"<blockquote>🔖 <b>شماره سفارش:</b> <code>{order_code}</code>\n"
        f"📦 <b>کالای انتخابی:</b> {prod.get('name', 'کالای سفارشی')}\n"
        f"👤 <b>تحویل‌گیرنده:</b> {order_data['full_name']}\n"
        f"📱 <b>شماره تماس:</b> <code>{order_data['phone1']}</code>\n"
        f"📍 <b>مقصد تحویل:</b> {order_data['province_city']} - {order_data['address']}\n"
        f"{shipping_desc_line}</blockquote>\n\n"
        f"<blockquote>⏳ <b>وضعیت سند:</b> {doc_status}\n"
        f"💰 <b>قیمت قطعی روز کالا:</b> <code>{f_total_price} تومان</code>\n"
        f"{pay_amount_line}\n"
        f"{rem_amount_line}</blockquote>\n\n"
        f"<blockquote>{bank_block}\n"
        f"⏱ <b>مهلت اعتبار رزرو انبار:</b> <code>۵ ساعت کاری</code></blockquote>\n\n"
        f"{note_text}"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 ارسال تصویر فیش واریزی", callback_data=f"uprec|{order_code}")],
        [InlineKeyboardButton("🔄 پیگیری لحظه‌ای وضعیت سفارش", callback_data=f"track_ord|{order_code}")],
        [InlineKeyboardButton("📞 پشتیبانی و مشاوره", callback_data="show_support")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]
    ])

    chat_id = update.effective_chat.id if update.effective_chat else update.effective_user.id

    if invoice_path and os.path.exists(invoice_path):
        if is_post:
            photo_caption = (
                f"🧾 <b>تصویر پیش‌فاکتور رسمی سفارش @AiKala_bot</b>\n\n"
                f"<blockquote>🔖 <b>شماره سفارش:</b> <code>{order_code}</code>\n"
                f"📦 <b>کالا:</b> {prod.get('name', 'کالای سفارشی')}\n"
                f"📮 <b>نحوه ارسال:</b> پست پیشتاز (تسویه کامل)\n"
                f"💰 <b>مبلغ کل:</b> <code>{f_total_price} تومان</code>\n"
                f"💳 <b>مبلغ قابل واریز:</b> <code>{f_total_price} تومان</code>\n"
                f"▫️ <b>مانده در محل:</b> <code>۰ تومان</code>\n"
                f"⏳ <b>وضعیت:</b> در انتظار تسویه کامل سفارش</blockquote>"
            )
        else:
            photo_caption = (
                f"🧾 <b>تصویر پیش‌فاکتور رسمی سفارش @AiKala_bot</b>\n\n"
                f"<blockquote>🔖 <b>شماره سفارش:</b> <code>{order_code}</code>\n"
                f"📦 <b>کالا:</b> {prod.get('name', 'کالای سفارشی')}\n"
                f"🚚 <b>نحوه ارسال:</b> باربری اختصاصی / تحویل در محل\n"
                f"💰 <b>قیمت کل:</b> <code>{f_total_price} تومان</code>\n"
                f"💳 <b>بیعانه پیش‌پرداخت ({dep_pct}٪):</b> <code>{f_deposit} تومان</code>\n"
                f"▫️ <b>مانده تسویه در محل:</b> <code>{f_remaining} تومان</code>\n"
                f"⏳ <b>وضعیت:</b> در انتظار واریز بیعانه</blockquote>"
            )

        try:
            with open(invoice_path, "rb") as f_img:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=f_img,
                    caption=photo_caption,
                    parse_mode="HTML",
                    read_timeout=60.0,
                    write_timeout=90.0,
                    connect_timeout=30.0
                )
        except Exception as e_photo:
            logger.warning(f"send_photo failed ({e_photo}), trying send_document fallback...")
            try:
                with open(invoice_path, "rb") as f_doc:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f_doc,
                        filename=f"pre_invoice_{order_code}.png",
                        caption=photo_caption,
                        parse_mode="HTML",
                        read_timeout=60.0,
                        write_timeout=90.0,
                        connect_timeout=30.0
                    )
            except Exception as e_doc:
                logger.error(f"send_document fallback failed: {e_doc}")

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=invoice_msg,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as ex_msg:
        logger.error(f"Error sending invoice text message: {ex_msg}")
        if update.message:
            await update.message.reply_text(invoice_msg, reply_markup=kb, parse_mode="HTML")

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🏠 <i>دکمه‌های منوی اصلی فروشگاه در دسترس شما قرار دارد:</i>",
            reply_markup=main_menu_keyboard(is_admin(chat_id)),
            parse_mode="HTML"
        )
    except Exception:
        pass

    # اطلاع‌رسانی ثبت سفارش جدید به ادمین‌ها به همراه موقعیت مکانی و شیوه ارسال
    loc_url = context.user_data.get("order_location_url", "")
    loc_info = f"\n🗺 <b>لوکیشن نقشه:</b> {loc_url}" if loc_url else ""
    order_lat = context.user_data.get("order_lat")
    order_lon = context.user_data.get("order_lon")

    admin_shipping_text = "📮 پست پیشتاز (تسویه کامل - بدون بیعانه)" if is_post else f"🚚 باربری (بیعانه {dep_pct}٪ + مانده در محل)"
    admin_fin_text = f"💰 <b>مبلغ کل (تسویه ۱۰۰٪):</b> <code>{f_total_price} تومان</code>" if is_post else f"💰 <b>مبلغ کل:</b> <code>{f_total_price} تومان</code>\n💳 <b>بیعانه ({dep_pct}٪):</b> <code>{f_deposit} تومان</code>"

    for adm_id in ADMIN_IDS:
        try:
            admin_note = ""
            if not card_number:
                admin_note = "\n⚠️ <i>توجه ادمین: شماره کارت فروشگاه در پنل هنوز ثبت نشده است. لطفاً از بخش تنظیمات بانکی آن را ثبت فرمایید.</i>"
            await context.bot.send_message(
                chat_id=adm_id,
                text=(
                    f"🛒 <b>سفارش جدید ثبت گردید!</b>\n\n"
                    f"<blockquote>🔖 <b>کد سفارش:</b> <code>{order_code}</code>\n"
                    f"👤 <b>خریدار:</b> {order_data['full_name']} (<code>{order_data['phone1']}</code>)\n"
                    f"📦 <b>کالا:</b> {prod.get('name')}\n"
                    f"🛵 <b>نحوه ارسال:</b> {admin_shipping_text}\n"
                    f"{admin_fin_text}\n"
                    f"📍 <b>مقصد:</b> {order_data['province_city']}\n"
                    f"🏠 <b>نشانی:</b> {order_data['address']}{loc_info}</blockquote>{admin_note}"
                ),
                parse_mode="HTML"
            )
            if order_lat and order_lon:
                try:
                    await context.bot.send_location(
                        chat_id=adm_id,
                        latitude=order_lat,
                        longitude=order_lon
                    )
                except Exception as e_pin:
                    logger.warning(f"Could not send location pin to admin {adm_id}: {e_pin}")
        except Exception as e_adm:
            logger.error(f"Error notifying admin {adm_id} about new order: {e_adm}")

    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for key in [
        "order_name", "order_phone1", "order_phone2", "order_city",
        "order_address", "order_postal", "order_product", "order_total_price",
        "order_deposit", "order_shipping_method", "order_inquiry_id", "order_location_url",
        "order_lat", "order_lon"
    ]:
        context.user_data.pop(key, None)
    user_id = update.effective_user.id if update.effective_user else 0
    await update.message.reply_text("❌ عملیات ثبت سفارش لغو گردید.", reply_markup=main_menu_keyboard(is_admin(user_id)))
    return ConversationHandler.END

async def cancel_and_handle_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج ایمن از کانوِرسیشن و پردازش آنی دکمه‌های ناوبری شیشه‌ای"""
    for key in [
        "order_name", "order_phone1", "order_phone2", "order_city",
        "order_address", "order_postal", "order_product", "order_total_price",
        "order_deposit", "order_shipping_method", "order_inquiry_id", "order_location_url",
        "order_lat", "order_lon"
    ]:
        context.user_data.pop(key, None)
    query = update.callback_query
    if query:
        data = query.data
        try:
            await query.answer()
        except Exception:
            pass

        if data == "back_to_main":
            user_id = query.from_user.id
            await query.message.reply_text("🏠 بازگشت به منوی اصلی:", reply_markup=main_menu_keyboard(is_admin(user_id)))
        elif data in ["track_order_list", "track_refresh_list"]:
            from order_tracking import show_order_tracking
            await show_order_tracking(update, context)
        elif data.startswith("track_ord|"):
            from order_tracking import order_tracking_callback_handler
            await order_tracking_callback_handler(update, context)
        elif data == "show_support":
            from support_service import show_support_menu
            await show_support_menu(update, context)
        elif data.startswith("uprec|"):
            order_code = data.split("|")[1]
            context.user_data["upload_order_code"] = order_code
            await query.message.reply_text(
                f"📸 لطفاً <b>عکس فیش واریزی</b> مربوط به سفارش <code>{order_code}</code> را ارسال نمایید:",
                parse_mode="HTML"
            )
            return RECEIPT_FILE

    return ConversationHandler.END

# ─── مراحل ارسال فیش واریزی ───

async def start_receipt_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_code = query.data.split("|")[1]
    context.user_data["upload_order_code"] = order_code

    await query.message.reply_text(
        f"📸 لطفاً <b>عکس فیش واریزی</b> مربوط به سفارش <code>{order_code}</code> را ارسال نمایید:",
        parse_mode="HTML"
    )
    return RECEIPT_FILE

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_code = context.user_data.get("upload_order_code")
    photo = update.message.photo[-1]
    file_id = photo.file_id

    await db.update_order_status(order_code, status="Receipt_Uploaded", receipt_file_id=file_id)

    order = await db.get_order_by_code(order_code)
    shipping_method = order.get("shipping_method", "freight") if order else "freight"
    is_post = (shipping_method == "post")

    reply_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 پیگیری لحظه‌ای وضعیت سفارش", callback_data=f"track_ord|{order_code}")],
        [InlineKeyboardButton("📞 پشتیبانی و پیگیری مالی", callback_data="show_support")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]
    ])

    await update.message.reply_text(
        f"✅ <b>فیش واریزی شما با موفقیت در سامانه ثبت شد!</b>\n\n"
        f"<blockquote>🔖 <b>شماره سفارش:</b> <code>{order_code}</code>\n"
        f"⏳ <b>وضعیت بررسی:</b> واحد حسابداری حداکثر ظرف ۳۰ دقیقه فیش شما را تایید نموده و <b>فاکتور قطعی و نهایی فروش</b> به صورت خودکار صادر خواهد شد.</blockquote>",
        reply_markup=reply_kb,
        parse_mode="HTML"
    )

    try:
        user_id = update.effective_user.id if update.effective_user else 0
        await update.message.reply_text(
            "🏠 <i>دکمه‌های منوی اصلی فروشگاه در دسترس شما قرار دارد:</i>",
            reply_markup=main_menu_keyboard(is_admin(user_id)),
            parse_mode="HTML"
        )
    except Exception:
        pass

    method_title = "📮 پست پیشتاز (تسویه کامل - بدون بیعانه)" if is_post else "🚚 باربری (بیعانه + مانده در محل)"
    amt_paid = order.get("total_price", "0") if is_post else order.get("deposit_amount", "0") if order else "0"
    try:
        f_amt = f"{int(amt_paid):,} تومان"
    except Exception:
        f_amt = f"{amt_paid} تومان"

    for adm_id in ADMIN_IDS:
        try:
            adm_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ تایید فیش و صدور فاکتور قطعی", callback_data=f"adm_ok|{order_code}"),
                    InlineKeyboardButton("❌ رد فیش", callback_data=f"adm_no|{order_code}")
                ]
            ])
            username_str = f"@{update.effective_user.username}" if update.effective_user and update.effective_user.username else "نامشخص"
            await context.bot.send_photo(
                chat_id=adm_id,
                photo=file_id,
                caption=(
                    f"🔔 <b>فیش واریزی جدید دریافت شد!</b>\n\n"
                    f"<blockquote>🔖 <b>کد سفارش:</b> <code>{order_code}</code>\n"
                    f"🛵 <b>شیوه ارسال:</b> {method_title}\n"
                    f"💳 <b>مبلغ واریزی مورد انتظار:</b> <code>{f_amt}</code>\n"
                    f"👤 <b>کاربر:</b> {username_str}</blockquote>"
                ),
                reply_markup=adm_kb,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error notifying admin {adm_id}: {e}")

    return ConversationHandler.END

# ─── توابع تولید هندلرها برای bot.py ───

def get_order_conversation_handler() -> ConversationHandler:
    nav_pattern = r"^(back_to_main|track_order_list|track_refresh_list|track_ord\||show_support|guide_main|close_window)"
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order_flow, pattern=r"^buy\|")],
        states={
            ORDER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_name_step),
                CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
            ],
            ORDER_PHONE1: [
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), order_phone1_step),
                CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
            ],
            ORDER_PHONE2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone2_step),
                CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
            ],
            ORDER_CITY: [
                MessageHandler(filters.LOCATION | (filters.TEXT & ~filters.COMMAND), order_city_step),
                CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
            ],
            ORDER_ADDRESS: [
                MessageHandler(filters.LOCATION | (filters.TEXT & ~filters.COMMAND), order_address_step),
                CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
            ],
            ORDER_POSTAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_postal_step),
                CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
            ],
            ORDER_CONFIRM: [
                CallbackQueryHandler(order_confirm_callback, pattern=r"^ord_(confirm_final|edit_info|cancel_flow)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_confirm_text_step),
                CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
        ],
        per_message=False
    )

def get_receipt_conversation_handler() -> ConversationHandler:
    nav_pattern = r"^(back_to_main|track_order_list|track_refresh_list|track_ord\||show_support|guide_main|close_window)"
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_receipt_upload, pattern=r"^uprec\|")],
        states={
            RECEIPT_FILE: [
                MessageHandler(filters.PHOTO, handle_receipt_photo),
                CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_and_handle_nav_callback, pattern=nav_pattern)
        ],
        per_message=False
    )
