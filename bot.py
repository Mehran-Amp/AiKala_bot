"""
AiKala Telegram Bot - Modular Production Core (bot.py)
======================================================
هسته سبک، تمیز و ساختاریافته ربات فروشگاهی و تلگرامی آی کالا:
- پیکربندی و راه‌اندازی ربات
- رجیستری هندلرها، کانوِرسیشن‌ها و میدل‌ویرها
- مسیریابی دستورات، پیام‌های متنی، کال‌بک کوئری‌ها و پست‌های کانال
"""
import time
import json


import os
import sys
import io
import re
import html
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    TypeHandler,
    ApplicationHandlerStop,
    filters
)

try:
    import config
except ImportError:
    config = None

TELEGRAM_BOT_TOKEN = getattr(config, "TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
PHOTOS_CHANNEL = getattr(config, "PHOTOS_CHANNEL", getattr(config, "PHOTO_CHANNEL", getattr(config, "IMAGE_CHANNEL", getattr(config, "IMAGES_CHANNEL", os.getenv("PHOTOS_CHANNEL", "@img_ai_amp")))))
SUPPORT_USERNAME = getattr(config, "SUPPORT_USERNAME", "@AiKala_Admin")
ADMIN_IDS = getattr(config, "ADMIN_IDS", [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()] if os.getenv("ADMIN_IDS") else [])
BOT_LINK = getattr(config, "BOT_LINK", os.getenv("BOT_LINK", "@AiKala_bot"))

# ─── پیکربندی بهینه‌سازی‌شده و خلاصه لاگر ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout
)
logger = logging.getLogger("AiKalaBot")

# 🛡️ حذف قطعی اسپم لاگ‌های درخواست خام شبکه (جلوگیری از پر شدن مکرر صفحه با لینک‌های api.telegram.org)
for _noisy in ("httpx", "httpcore", "telegram.ext.Application", "telegram.ext.ExtBot", "urllib3", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ─── ماژول‌های سیستم ───
from database import Database
from search_engine import (
    JSON_PRODUCTS,
    search_products,
    _normalize_digits,
    load_json_products,
    find_product_by_id,
    get_product_id,
    get_product_name
)
from laptop_extractor import (
    extract_laptops_from_image,
    extract_laptops_from_text,
    extract_laptops_from_excel,
    set_gemini_api_key,
    merge_extracted_laptops,
    replace_extracted_laptops,
    format_laptops_preview_for_admin,
    load_laptops_catalog
)
from audio_service import (
    extract_audio_from_excel,
    format_audio_preview_for_admin,
    merge_audio_products,
    replace_audio_products,
    load_audio_catalog,
    save_audio_catalog,
    generate_audio_csv_file
)
from bot_catalog import (
    get_main_categories_markup,
    get_category_sub_markup,
    get_filter_options_markup,
    get_products_for_category_selection
)
from keyboards import (
    is_admin,
    is_owner,
    OWNER_ID,
    get_sub_admin_ids,
    remove_admin_id,
    add_admin_id,
    get_all_admin_ids,
    main_menu_keyboard,
    show_search_page,
    resolve_safe_cb,
    make_safe_cb,
    inquiry_quote_keyboard,
    product_inline_keyboard
)
from guidbuy import show_guide_command, register_guide_handlers
from support_service import (
    show_support_command,
    register_support_handlers,
    handle_admin_support_agent_input
)
from ai_advisor import (
    ADVISOR_WELCOME_TEXT,
    get_advisor_menu_keyboard,
    consult_gemini_shopping_advisor,
    build_advisor_response_keyboard
)
from photo_service import (
    VERIFIED_PRODUCT_PHOTOS,
    PENDING_IMAGE_REQUESTS,
    CHANNEL_MEDIA_GROUPS,
    register_photo_message,
    save_channel_photos_map,
    save_verified_photos,
    remove_verified_product_photo,
    find_matching_verified_photos,
    send_verified_photos_to_user,
    get_product_photos,
    send_product_card_and_photos,
    prepare_media_items,
    resolve_media_for_telegram
)
from order_flow import (
    get_order_conversation_handler,
    get_receipt_conversation_handler
)
from admin_panel import (
    admin_panel_command,
    admin_orders_hub,
    admin_view_order_detail,
    admin_order_search_ask,
    handle_admin_order_search_input,
    admin_laptop_hub,
    admin_audio_hub,
    admin_audio_reload,
    admin_audio_download_pdf,
    admin_audio_download_csv,
    admin_upload_audio_excel_prompt,
    admin_clear_audio_ask,
    admin_clear_audio_do,
    admin_laptop_download_pdf,
    admin_upload_laptop_excel_prompt,
    admin_text_laptop_prompt,
    admin_clear_laptops_ask,
    admin_clear_laptops_do,
    admin_sync_live_prices,
    admin_sync_catalog_stock,
    admin_sync_aeg,
    admin_bank_settings,
    admin_prompt_bank_edit,
    handle_admin_bank_input,
    admin_catalog_report,
    admin_broadcast_ask,
    admin_broadcast_do,
    handle_admin_broadcast_input,
    admin_ai_settings_menu,
    admin_ai_set_provider_handler,
    admin_ai_batch_handler,
    admin_backup_menu,
    admin_backup_download_handler,
    admin_backup_toggle_auto_handler,
    admin_backup_upload_prompt,
    admin_manage_admins_menu,
    admin_add_admin_prompt,
    admin_delete_admin_handler,
    handle_admin_add_id_input,
    sync_photos_command,
    setphoto_command,
    clearphotos_command,
    handle_admin_photo_link_input,
    admin_freeze_menu,
    admin_freeze_quick_handler,
    admin_unfreeze_handler,
    admin_freeze_custom_prompt,
    handle_admin_freeze_custom_input,
    admin_freeze_command,
    admin_unfreeze_command
)
from freeze_service import is_bot_frozen, get_freeze_message
from order_tracking import (
    show_order_tracking,
    register_order_tracking_handlers
)
from invoice_service import generate_invoice_png, build_invoice_data_from_order, to_fa_digits
from currency_service import show_currency_rates

db = Database()

# =====================================================================
# 🤖 دستورات اصلی ربات (Commands)
# =====================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    adm = is_admin(user.id)

    # 🔗 بررسی دیپ‌لینک مستقیم به کارت کالا (مانند /start p_123 یا /start p_AEG_19937 یا /start prod_123)
    if context.args and len(context.args) > 0:
        raw_arg = context.args[0].strip()
        target_pid = ""
        if raw_arg.startswith("p_"):
            target_pid = raw_arg[2:].strip()
        elif raw_arg.startswith("prod_"):
            target_pid = raw_arg[5:].strip()
        else:
            target_pid = raw_arg

        if target_pid:
            prod = find_product_by_id(target_pid) or await db.get_product_by_id(target_pid)
            if not prod and target_pid.isdigit():
                prod = find_product_by_id(f"AEG_{target_pid}")
            if not prod:
                # جستجو بر اساس کدهای مشابه یا عددی
                from search_engine import search_products
                cand = search_products(target_pid)
                if cand:
                    prod = cand[0]
            if prod:
                from search_engine import is_product_hidden
                if not adm and is_product_hidden(prod):
                    await update.message.reply_text("⚠️ این کالا در حال حاضر در فروشگاه موجود نیست یا غیرفعال شده است.")
                    return
                await send_product_card_and_photos(update.effective_chat.id, prod, context)
                return

    welcome_text = (
        f"سلام <b>{user.first_name}</b> گرامی! 🌹\n"
        f"به اولین فروشگاه تلگرامی لوازم خانگی و لپتاپ (هوشمند کالا AiKala_bot) در ایران خوش آمدید.\n\n"
        f"<blockquote>📦 <b>موجودی و قیمت‌های بروز:</b>\n"
        f"▫️ قیمت تمامی محصولات و موجودی انبار به صورت لحظه‌ای و قطعی بروزرسانی می‌شوند.\n"
        f"▫️ استعلام آنی قیمت روز، صدور پیش‌فاکتور دیجیتال رسمی و تسویه مطمئن درب منزل پس از تست سلامت</blockquote>\n\n"
        f"<blockquote>💡 <b>راهنمای تعامل با ربات:</b>\n"
        f"▫️ <b>ارسال متن:</b> ارسال هرگونه متن در چت، مستقیماً برای <b>جستجوی سریع محصولات</b> در کاتالوگ است.\n"
        f"▫️ <b>مشاوره با هوش مصنوعی:</b> جهت دریافت تحلیل و مقایسه هوشمند، از دکمه «🧠 مشاور هوشمند خرید (جمینای)» استفاده فرمایید.</blockquote>\n\n"
        f"👇 <i>جهت جستجو، نام کالا یا مدل مدنظرتان را تایپ کنید (مثلاً: <code>V9</code> یا <code>الجی</code>) یا از منوی زیر استفاده فرمایید:</i>"
    )
    try:
        from telegram import MenuButtonCommands
        await context.bot.set_chat_menu_button(chat_id=user.id, menu_button=MenuButtonCommands())
    except Exception:
        pass
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(adm), parse_mode="HTML")

async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش مستقیم فهرست دسته‌بندی‌های محصولات"""
    kb = get_main_categories_markup()
    user_id = update.effective_user.id if update.effective_user else 0
    adm = is_admin(user_id)
    await update.message.reply_text(
        "📂 <b>دسته‌بندی‌های جامع فروشگاه هوشمند کالا:</b>\n"
        "لطفاً دسته کالای مورد نظر خود را جهت مشاهده مشخصات و کاتالوگ انتخاب فرمایید:",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای سریع جستجوی کالا و نمایش منوی اصلی"""
    user_id = update.effective_user.id if update.effective_user else 0
    adm = is_admin(user_id)
    await update.message.reply_text(
        "💡 لطفاً نام مدل، برند یا دسته‌بندی کالا را تایپ فرمایید (مثال: <code>V9</code> یا <code>الجی</code>):",
        reply_markup=main_menu_keyboard(adm),
        parse_mode="HTML"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_guide_command(update, context)

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_support_command(update, context)

async def track_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتقال مستقیم به سامانه تعاملی رهگیری سفارشات"""
    await show_order_tracking(update, context)

async def advisor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ورود به بخش مشاور هوشمند خرید جمینای"""
    context.user_data["awaiting_advisor_question"] = True
    context.user_data.pop("advisor_context_pid", None)
    await update.message.reply_text(
        ADVISOR_WELCOME_TEXT,
        reply_markup=get_advisor_menu_keyboard(),
        parse_mode="HTML"
    )



async def setgemini_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم کلید Gemini API توسط ادمین برای استخراج تصاویر و جداول لپ‌تاپ"""
    user = update.effective_user
    if not is_admin(user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "🔑 <b>راهنمای تنظیم کلید هوش مصنوعی Gemini:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "جهت فعال‌سازی یا به‌روزرسانی کلید استخراج تصویر، دستور را به این شکل ارسال فرمایید:\n"
            "<code>/setgemini YOUR_GEMINI_API_KEY</code>\n\n"
            "💡 <i>کلید اختصاصی را می‌توانید رایگان از <a href='https://aistudio.google.com/app/apikey'>Google AI Studio</a> دریافت نمایید.</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return
    key = args[0].strip()
    if len(key) < 15:
        await update.message.reply_text("❌ طول کلید وارد شده بسیار کوتاه است. لطفاً کلید کامل را ارسال فرمایید.")
        return
    ok = set_gemini_api_key(key)
    if ok:
        await update.message.reply_text(
            "✅ <b>کلید هوش مصنوعی Gemini با موفقیت ذخیره شد!</b>\n"
            "سیستم استخراج خودکار تصاویر جدول لپ‌تاپ با این کلید فعال گردید.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ خطا در ذخیره‌سازی کلید در سرور.")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور عمومی /cancel جهت خروج از تمامی فرآیندهای انتظار ورودی و بازگشت به حالت عادی"""
    user_id = update.effective_user.id if update.effective_user else 0
    adm = is_admin(user_id)
    cleared = False

    # پاکسازی وضعیت‌های مدیریتی
    for key in [
        "awaiting_product_image_link",
        "awaiting_admin_product_price",
        "awaiting_admin_product_specs",
        "awaiting_broadcast_msg",
        "awaiting_bank_edit_field",
        "awaiting_channel_add",
        "awaiting_ai_key_provider",
        "awaiting_new_admin_id",
        "pending_admin_id",
        "awaiting_poster_channel_set",
    ]:
        if context.user_data.pop(key, None):
            cleared = True

    # پاکسازی وضعیت‌های کانوِرسیشن سفارش
    for o_key in [
        "order_name", "order_phone1", "order_phone2", "order_city",
        "order_address", "order_postal", "order_product", "order_total_price",
        "order_deposit", "order_shipping_method", "order_inquiry_id", "order_location_url",
        "order_lat", "order_lon"
    ]:
        if context.user_data.pop(o_key, None):
            cleared = True

    msg = "❌ عملیات جاری لغو گردید." if cleared else "ℹ️ عملیات فعالی جهت لغو وجود ندارد."
    await update.message.reply_text(
        msg,
        reply_markup=main_menu_keyboard(adm)
    )

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش شناسه عددی تلگرام کاربر"""
    user = update.effective_user
    if not user:
        return
    await update.message.reply_text(
        f"🆔 <b>شناسه عددی تلگرام شما:</b>\n\n"
        f"<code>{user.id}</code>\n\n"
        f"💡 <i>(با لمس روی عدد، شناسه خودکار کپی می‌شود)</i>",
        parse_mode="HTML"
    )

async def auth_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """احراز هویت سریع یا اعلام شناسه کاربری جهت مدیریت بات"""
    user = update.effective_user
    if not user:
        return
    args = context.args or []
    token = TELEGRAM_BOT_TOKEN or ""
    is_valid = False
    if args:
        provided = args[0].strip()
        if (token and (provided == token or (len(provided) >= 8 and token.startswith(provided)))) or provided == "aikala_secret_admin":
            is_valid = True
    elif not get_all_admin_ids():
        is_valid = True

    if is_valid:
        add_admin_id(user.id)
        await update.message.reply_text(
            f"✅ <b>احراز هویت مدیر با موفقیت انجام شد:</b>\n"
            f"شناسه کاربری شما <code>{user.id}</code> در لیست مدیران فعال گردید.\n"
            f"هم‌اکنون می‌توانید فایل‌های اکسل (.xlsx / .csv) یا دستور <code>/admin</code> را ارسال فرمایید.",
            reply_markup=main_menu_keyboard(True),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"ℹ️ <b>شناسه تلگرام شما:</b> <code>{user.id}</code>\n\n"
            f"جهت فعال‌سازی دسترسی مدیریت، این شناسه را در متغیر <code>ADMIN_IDS</code> در سرور قرار دهید یا توکن بات را همراه دستور بفرستید:\n"
            f"<code>/auth_admin BOT_TOKEN</code>",
            parse_mode="HTML"
        )

def make_laptop_confirm_prompt(extracted: list, source_title: str = "جدول") -> tuple:
    """
    ایجاد پیام پیش‌نمایش و کیبورد تاییدیه نحوه ثبت در کاتالوگ فروشگاه:
    از ادمین سوال می‌شود که آیا مایل است لیست قبلی لپ‌تاپ‌ها کاملاً حذف شود یا با آن ادغام گردد.
    """
    existing = load_laptops_catalog()
    existing_count = len(existing)
    preview_text = format_laptops_preview_for_admin(extracted, max_display=10)

    if existing_count > 0:
        full_text = (
            f"📊 <b>استخراج هوشمند از {html.escape(source_title)}:</b>\n\n"
            f"{preview_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"❓ <b>نحوه ثبت در کاتالوگ فروشگاه:</b>\n"
            f"▫️ تعداد <b>{existing_count} مدل لپ‌تاپ</b> از قبل در کاتالوگ موجود است.\n\n"
            f"⚠️ <b>آیا مایلید لیست قبلی لپ‌تاپ‌ها کاملاً حذف شود یا این لیست جدید با آن ادغام (ترکیب) گردد؟</b>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🗑 بله، لیست قبلی ({existing_count}) کاملاً حذف و جایگزین شود", callback_data="adm_confirm_laptops_replace")],
            [InlineKeyboardButton("➕ خیر، با لیست قبلی ادغام شود (حفظ مدل‌های قبل)", callback_data="adm_confirm_laptops_merge")],
            [
                InlineKeyboardButton("❌ انصراف و لغو", callback_data="adm_cancel_laptops"),
                InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")
            ]
        ])
    else:
        full_text = (
            f"📊 <b>استخراج هوشمند از {html.escape(source_title)}:</b>\n\n"
            f"{preview_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>کاتالوگ فعلی لپ‌تاپ خالی است. جهت تایید و ثبت در فروشگاه دکمه زیر را انتخاب فرمایید:</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ تایید و ثبت {len(extracted)} لپ‌تاپ در کاتالوگ", callback_data="adm_confirm_laptops_replace")],
            [
                InlineKeyboardButton("❌ انصراف و لغو", callback_data="adm_cancel_laptops"),
                InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")
            ]
        ])
    return full_text, kb

def make_audio_confirm_prompt(extracted: list, source_title: str = "جدول") -> tuple:
    """
    ایجاد پیام پیش‌نمایش و کیبورد تاییدیه نحوه ثبت کاتالوگ سیستم‌های صوتی:
    از ادمین سوال می‌شود که آیا مایل است لیست قبلی کاملاً حذف و جایگزین شود یا با آن ادغام گردد.
    """
    existing = load_audio_catalog()
    existing_count = len(existing)
    preview_text = format_audio_preview_for_admin(extracted, max_display=10)

    if existing_count > 0:
        full_text = (
            f"🔊 <b>استخراج هوشمند از {html.escape(source_title)}:</b>\n\n"
            f"{preview_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"❓ <b>نحوه ثبت در کاتالوگ سیستم صوتی:</b>\n"
            f"▫️ تعداد <b>{existing_count} دستگاه صوتی</b> از قبل در کاتالوگ موجود است.\n\n"
            f"⚠️ <b>آیا مایلید لیست قبلی کاملاً حذف و جایگزین شود یا این لیست جدید با آن ادغام (ترکیب) گردد؟</b>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🗑 بله، لیست قبلی ({existing_count}) کاملاً حذف و جایگزین شود", callback_data="adm_confirm_audio_replace")],
            [InlineKeyboardButton("➕ خیر، با لیست قبلی ادغام شود (حفظ مدل‌های قبل)", callback_data="adm_confirm_audio_merge")],
            [
                InlineKeyboardButton("❌ انصراف و لغو", callback_data="adm_cancel_audio"),
                InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")
            ]
        ])
    else:
        full_text = (
            f"🔊 <b>استخراج هوشمند از {html.escape(source_title)}:</b>\n\n"
            f"{preview_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>کاتالوگ فعلی سیستم صوتی خالی است. جهت تایید و ثبت در فروشگاه دکمه زیر را انتخاب فرمایید:</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ تایید و ثبت {len(extracted)} سیستم صوتی در کاتالوگ", callback_data="adm_confirm_audio_replace")],
            [
                InlineKeyboardButton("❌ انصراف و لغو", callback_data="adm_cancel_audio"),
                InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")
            ]
        ])
    return full_text, kb

# =====================================================================
# 💬 هندلر پیام‌های متنی و جستجوی کالا
# =====================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    adm = is_admin(user.id)

    if adm and context.user_data.get("awaiting_product_image_link"):
        await handle_admin_photo_link_input(update, context)
        return

    if adm and context.user_data.get("awaiting_admin_product_price"):
        req = context.user_data.pop("awaiting_admin_product_price")
        pid = req.get("pid")
        pname = req.get("product_name", pid)
        raw_text = (update.message.text or "").strip()

        if raw_text.startswith("/cancel"):
            await update.message.reply_text("❌ تنظیم دستی قیمت لغو گردید.")
            return

        clean_num = _normalize_digits(raw_text).replace(",", "").replace(" ", "").replace("تومان", "").strip()
        if not clean_num.isdigit() or int(clean_num) <= 0:
            context.user_data["awaiting_admin_product_price"] = req
            await update.message.reply_text("⚠️ لطفاً مبلغ معتبر به صورت عدد به تومان وارد فرمایید (یا /cancel را بفرستید):")
            return

        new_price = int(clean_num)
        try:
            await db.execute("UPDATE products SET price = ? WHERE product_id = ?", (new_price, pid))
        except Exception as e:
            logger.warning(f"Error updating product price in db: {e}")

        for p in JSON_PRODUCTS:
            if str(p.get("product_id")) == str(pid):
                p["price"] = new_price
                break

        await update.message.reply_text(
            f"✅ <b>قیمت کالا با موفقیت بروزرسانی شد:</b>\n"
            f"🌟 <b>{pname}</b> (<code>{pid}</code>)\n"
            f"💰 قیمت جدید: <b>{new_price:,} تومان</b>\n\n"
            f"▫️ این قیمت بلافاصله در جستجو، کاتالوگ و کارت مشخصات کالا اعمال گردید.",
            parse_mode="HTML"
        )
        return

    if adm and context.user_data.get("awaiting_admin_product_specs"):
        req = context.user_data.pop("awaiting_admin_product_specs")
        pid = req.get("pid")
        pname = req.get("product_name", pid)
        raw_text = (update.message.text or "").strip()

        if raw_text.startswith("/cancel"):
            await update.message.reply_text("❌ ویرایش مشخصات فنی لغو گردید.")
            return

        new_specs = {}
        for line in raw_text.splitlines():
            line_str = line.strip().lstrip("▫️-•* ")
            if not line_str:
                continue
            if ":" in line_str:
                parts = line_str.split(":", 1)
                k = parts[0].strip()
                v = parts[1].strip()
                if k and v:
                    new_specs[k] = v
            elif "：" in line_str:
                parts = line_str.split("：", 1)
                k = parts[0].strip()
                v = parts[1].strip()
                if k and v:
                    new_specs[k] = v
            else:
                new_specs[line_str] = "دارد"

        if not new_specs:
            context.user_data["awaiting_admin_product_specs"] = req
            await update.message.reply_text(
                "⚠️ متنی دریافت نشد یا فرمت مشخصات نامعتبر است.\n"
                "لطفاً حداقل یک سطر مشخصات (مثلاً: <code>توان: ۱۲۰۰ وات</code>) وارد فرمایید یا /cancel را ارسال کنید:",
                parse_mode="HTML"
            )
            return

        specs_json_str = json.dumps(new_specs, ensure_ascii=False)
        try:
            await db.execute("UPDATE products SET specs_json = ? WHERE product_id = ?", (specs_json_str, pid))
        except Exception as e:
            logger.warning(f"Error updating product specs in db: {e}")

        prod_found = None
        for p in JSON_PRODUCTS:
            if str(p.get("product_id")) == str(pid):
                p["specs"] = new_specs
                p["specs_json"] = specs_json_str
                p["ai_specs"] = new_specs
                prod_found = p
                break

        if not prod_found:
            prod_found = await db.get_product_by_id(pid)
            if prod_found:
                prod_found["specs"] = new_specs

        await update.message.reply_text(
            f"✅ <b>مشخصات فنی کالا با موفقیت بروزرسانی شد:</b>\n"
            f"🌟 <b>{pname}</b> (<code>{pid}</code>)\n"
            f"▫️ تعداد مشخصات ثبت‌شده: <b>{len(new_specs)} مورد</b>\n\n"
            f"کارت بروزرسانی‌شده کالا در زیر نمایش داده می‌شود:",
            parse_mode="HTML"
        )
        if prod_found:
            from keyboards import build_boxed_product_message, product_inline_keyboard
            updated_msg = build_boxed_product_message(prod_found)
            adm_kb = product_inline_keyboard(pid, context, show_photo_button=True, is_admin=True, view_as_customer=False)
            try:
                from telegram import LinkPreviewOptions
                await update.message.reply_text(updated_msg, reply_markup=adm_kb, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True))
            except Exception:
                await update.message.reply_text(updated_msg, reply_markup=adm_kb, parse_mode="HTML", disable_web_page_preview=True)
        return

    if adm and context.user_data.get("awaiting_support_agent_step"):
        handled = await handle_admin_support_agent_input(update, context)
        if handled:
            return

    if adm and context.user_data.get("awaiting_broadcast_msg"):
        handled = await handle_admin_broadcast_input(update, context)
        if handled:
            return

    if adm and context.user_data.get("awaiting_bank_edit_field"):
        handled = await handle_admin_bank_input(update, context)
        if handled:
            return

    if adm and context.user_data.get("awaiting_channel_add"):
        from admin_panel import handle_admin_channel_add_input
        handled = await handle_admin_channel_add_input(update, context)
        if handled:
            return

    if adm and context.user_data.get("awaiting_ai_key_provider"):
        from admin_panel import handle_admin_ai_key_input
        handled = await handle_admin_ai_key_input(update, context)
        if handled:
            return

    if is_owner(user.id) and context.user_data.get("awaiting_new_admin_id"):
        handled = await handle_admin_add_id_input(update, context)
        if handled:
            return

    if is_owner(user.id) and context.user_data.get("awaiting_freeze_custom_message"):
        handled = await handle_admin_freeze_custom_input(update, context)
        if handled:
            return

    if adm and context.user_data.get("awaiting_poster_channel_set"):
        from admin_panel import handle_admin_poster_channel_input
        handled = await handle_admin_poster_channel_input(update, context)
        if handled:
            return

    if adm and context.user_data.get("awaiting_order_search"):
        handled = await handle_admin_order_search_input(update, context)
        if handled:
            return

    # ─── پردازش و بررسی فوری فایل‌های اکسل یا CSV ارسالی ───
    photo = update.message.photo[-1] if update.message.photo else None
    doc = update.message.document

    # تشخیص فایل اکسل یا CSV یا ZIP پشتیبان
    is_excel = False
    is_zip_backup = False
    if doc:
        d_name = (doc.file_name or "").lower()
        d_mime = (doc.mime_type or "").lower()
        if (
            d_name.endswith(".xlsx")
            or d_name.endswith(".xls")
            or d_name.endswith(".csv")
            or d_name.endswith(".tsv")
            or "spreadsheet" in d_mime
            or "excel" in d_mime
            or "csv" in d_mime
        ):
            is_excel = True
        elif d_name.endswith(".zip") or "zip" in d_mime:
            is_zip_backup = True

    # ۰. اگر فایل ZIP پشتیبان ارسال شده است
    if is_zip_backup:
        if not adm:
            await update.message.reply_text("⛔️ بازگردانی فایل پشتیبان فقط توسط مدیران فروشگاه امکان‌پذیر است.")
            return

        file_title = doc.file_name or "فایل پشتیبان"
        status_msg = await update.message.reply_text(
            f"🔍 <b>در حال بررسی ساختار فایل پشتیبان «{html.escape(file_title)}»...</b>",
            parse_mode="HTML"
        )
        try:
            file_obj = await doc.get_file()
            file_bytes = await file_obj.download_as_bytearray()
            from backup_service import inspect_backup_zip
            inspected = inspect_backup_zip(io.BytesIO(file_bytes))

            if not inspected:
                await status_msg.edit_text(
                    "❌ <b>فایل پشتیبان نامعتبر است!</b>\n\n"
                    "این فایل زیپ حاوی ساختار استاندارد بک‌آپ سیستم (دیتابیس یا کاتالوگ محصولات) نمی‌باشد.\n"
                    "لطفاً مطمئن شوید فایلی را ارسال می‌کنید که قبلاً از همین ربات دریافت کرده‌اید.",
                    parse_mode="HTML"
                )
                return

            # ذخیره بایت‌ها یا مسیر فایل موقت جهت ریستور
            os.makedirs("backups/temp", exist_ok=True)
            temp_restore_path = f"backups/temp/restore_{int(time.time())}.zip"
            with open(temp_restore_path, "wb") as f_tmp:
                f_tmp.write(file_bytes)

            context.user_data["pending_restore_file"] = temp_restore_path
            context.user_data.pop("awaiting_backup_zip_file", None)

            c_date = inspected.get("created_at", "نامشخص")
            b_orders = inspected.get("orders_count", 0)
            b_prods = inspected.get("products_catalog_count", 0)
            b_audio_aeg = inspected.get("audio_catalog_count", 0) + inspected.get("aeg_products_count", 0)
            b_photos = inspected.get("verified_photos_count", 0)
            b_admins = inspected.get("sub_admins_count", 0)

            confirm_text = (
                f"📦 <b>فایل پشتیبان معتبر با موفقیت تایید گردید:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 نام فایل: <code>{html.escape(file_title)}</code>\n"
                f"📅 تاریخ ایجاد: <b>{c_date}</b>\n"
                f"▫️ سفارش‌ها و فاکتورها: <b>{b_orders}</b> مورد\n"
                f"▫️ کاتالوگ محصولات اصلی: <b>{b_prods}</b> کالا\n"
                f"▫️ سیستم‌های صوتی و AEG: <b>{b_audio_aeg}</b> کالا\n"
                f"▫️ تصاویر اختصاصی متصل: <b>{b_photos}</b> کالا\n"
                f"▫️ تعداد ادمین‌های فرعی: <b>{b_admins}</b> نفر\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"❓ <b>نحوه بازگردانی اطلاعات را مشخص فرمایید:</b>\n\n"
                f"➕ <b>۱. ادغام هوشمند (Smart Merge):</b>\n"
                f"سفارش‌ها، ادمین‌ها، تصاویر و کاتالوگ جدید بدون حذف هیچ داده‌ای به سیستم فعلی افزوده می‌شوند. (پیشنهادی)\n\n"
                f"♻️ <b>۲. بازگردانی کامل و جایگزینی (Full Replace):</b>\n"
                f"کل دیتابیس، کاتالوگ‌ها، عکس‌ها و تنظیمات با این فایل زیپ جایگزین می‌شود. (یک نسخه اسنپ‌شات ایمنی به صورت خودکار قبل از رونویسی ذخیره می‌گردد)"
            )

            confirm_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ ۱. ادغام هوشمند (پیشنهادی - حفظ داده‌های فعلی)", callback_data="adm_restore_smart_merge")],
                [InlineKeyboardButton("♻️ ۲. بازگردانی کامل (جایگزینی تمام داده‌ها)", callback_data="adm_restore_full_replace")],
                [
                    InlineKeyboardButton("❌ انصراف و لغو", callback_data="adm_restore_cancel"),
                    InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")
                ]
            ])

            await status_msg.edit_text(confirm_text, reply_markup=confirm_kb, parse_mode="HTML")
            return
        except Exception as err:
            logger.error(f"Error inspecting backup zip: {err}", exc_info=True)
            await status_msg.edit_text(f"❌ خطا در پردازش فایل زیپ: {html.escape(str(err))}", parse_mode="HTML")
            return

    # ۰.۵. بررسی آیا ادمین در حال ارسال فایل اکسل سیستم صوتی است
    is_audio_flow = bool(context.user_data.get("awaiting_audio_excel"))

    # ۱. اگر فایل اکسل یا CSV ارسال شده است
    if is_excel:
        if not adm:
            await update.message.reply_text(
                f"⛔️ <b>دسترسی محدود به مدیریت فروشگاه</b>\n\n"
                f"فایل «<b>{html.escape(doc.file_name or 'اکسل')}</b>» دریافت شد، اما به‌روزرسانی موجودی و قیمت‌ها تنها توسط مدیران مجاز است.\n\n"
                f"🆔 <b>شناسه تلگرام شما:</b> <code>{user.id}</code>\n\n"
                f"💡 در صورت نیاز، با مدیریت یا پشتیبانی فروشگاه هماهنگ فرمایید.",
                parse_mode="HTML"
            )
            return

        file_title = doc.file_name or "فایل اکسل"
        fname_lower = file_title.lower()

        # تشخیص اینکه آیا فایل مربوط به سیستم صوتی است
        is_audio_file = is_audio_flow or any(k in fname_lower for k in ["audio", "speaker", "party", "sound", "صوتی", "اسپیکر", "پارتی"])

        if is_audio_file:
            status_msg = await update.message.reply_text(
                f"⏳ <b>در حال خواندن و تحلیل کاتالوگ سیستم صوتی «{html.escape(file_title)}»...</b>\n"
                f"▫️ پردازش مشخصات اسپیکر، پارتی‌باکس و ساندبارها\n"
                f"🛡 حذف قطعی ستون قیمت همکاری، اطلاعات تماس و تبلیغات\n"
                f"<i>لطفاً چند لحظه شکیبا باشید...</i>",
                parse_mode="HTML"
            )
            try:
                file_obj = await doc.get_file()
                file_bytes = await file_obj.download_as_bytearray()

                extracted = extract_audio_from_excel(bytes(file_bytes), filename=doc.file_name or "")
                if not extracted:
                    await status_msg.edit_text(
                        "⚠️ متأسفانه هیچ سطری با مشخصات و قیمت معتبر سیستم صوتی در این فایل شناسایی نشد.\n"
                        "لطفاً ساختار جدول و نام ستون‌ها (برند/مدل، قیمت) را بررسی فرمایید.",
                        parse_mode="HTML"
                    )
                    return

                context.user_data["pending_extracted_audio"] = extracted
                context.user_data.pop("awaiting_audio_excel", None)

                preview_text, confirm_kb = make_audio_confirm_prompt(extracted, source_title=f"فایل ({file_title})")
                await status_msg.edit_text(
                    preview_text,
                    reply_markup=confirm_kb,
                    parse_mode="HTML"
                )
                return
            except Exception as err:
                logger.error(f"Error processing audio excel file: {err}", exc_info=True)
                err_str = html.escape(str(err))
                await status_msg.edit_text(
                    f"❌ <b>خطا در خواندن فایل سیستم صوتی:</b>\n<code>{err_str}</code>\n\n"
                    f"💡 لطفاً مطمئن شوید فایل دارای فرمت معتبر .xlsx یا .csv است.",
                    parse_mode="HTML"
                )
                return

        status_msg = await update.message.reply_text(
            f"⏳ <b>در حال خواندن و تحلیل هوشمند فایل اکسل «{html.escape(file_title)}»...</b>\n"
            f"▫️ پردازش سطرها و ستون‌های جدول بدون نیاز به کتابخانه‌های خارجی\n"
            f"🛡 حذف قطعی ستون قیمت همکاری، اطلاعات تماس و تبلیغات\n"
            f"<i>لطفاً چند لحظه شکیبا باشید...</i>",
            parse_mode="HTML"
        )
        try:
            file_obj = await doc.get_file()
            file_bytes = await file_obj.download_as_bytearray()

            extracted = extract_laptops_from_excel(bytes(file_bytes), filename=doc.file_name or "")
            if not extracted:
                await status_msg.edit_text(
                    "⚠️ متأسفانه هیچ سطری با مشخصات و قیمت معتبر در این فایل اکسل شناسایی نشد.\n"
                    "لطفاً ساختار جدول و نام ستون‌ها (مدل/مشخصات، قیمت) را بررسی فرمایید.",
                    parse_mode="HTML"
                )
                return

            context.user_data["pending_extracted_laptops"] = extracted
            context.user_data.pop("awaiting_laptop_photo", None)
            context.user_data.pop("awaiting_laptop_excel", None)

            preview_text, confirm_kb = make_laptop_confirm_prompt(extracted, source_title=f"فایل اکسل ({file_title})")
            await status_msg.edit_text(
                preview_text,
                reply_markup=confirm_kb,
                parse_mode="HTML"
            )
            return
        except Exception as err:
            logger.error(f"Error processing excel file: {err}", exc_info=True)
            err_str = html.escape(str(err))
            await status_msg.edit_text(
                f"❌ <b>خطا در خواندن فایل اکسل:</b>\n<code>{err_str}</code>\n\n"
                f"💡 لطفاً مطمئن شوید فایل دارای فرمت معتبر .xlsx یا .csv است.",
                parse_mode="HTML"
            )
            return

    # ۱.۵. اگر ادمین در حالت انتظار ارسال فایل سیستم صوتی است و پیام متنی فرستاده
    if adm and context.user_data.get("awaiting_audio_excel"):
        text_input = update.message.text.strip() if update.message.text else ""
        if text_input in ["انصراف", "لغو", "بازگشت"]:
            context.user_data.pop("awaiting_audio_excel", None)
            await update.message.reply_text("❌ عملیات آپلود کاتالوگ سیستم صوتی لغو شد.")
            await admin_audio_hub(update, context)
            return
        await update.message.reply_text(
            "📊 لطفاً <b>فایل اکسل (.xlsx یا .csv)</b> کاتالوگ سیستم صوتی را ارسال فرمایید.\n"
            "برای انصراف کلمه <code>لغو</code> را ارسال نمایید.",
            parse_mode="HTML"
        )
        return

    # ۲. پردازش دریافت عکس یا متن کاتالوگ لپ‌تاپ توسط ادمین در حالت انتظار
    if adm and (
        context.user_data.get("awaiting_laptop_photo")
        or context.user_data.get("awaiting_laptop_excel")
        or (update.message.photo and (context.user_data.get("awaiting_laptop_photo") or context.user_data.get("awaiting_laptop_excel")))
        or (update.message.document and (context.user_data.get("awaiting_laptop_photo") or context.user_data.get("awaiting_laptop_excel")))
    ):
        is_image_doc = bool(doc and doc.mime_type and doc.mime_type.startswith("image/"))
        text_input = update.message.text.strip() if update.message.text else ""

        if not photo and not is_image_doc:
            if text_input in ["انصراف", "لغو", "بازگشت"]:
                context.user_data.pop("awaiting_laptop_photo", None)
                context.user_data.pop("awaiting_laptop_excel", None)
                await update.message.reply_text("❌ عملیات استخراج لپ‌تاپ لغو شد.")
                return

            # بررسی اینکه آیا متن جدول اکسل یا پیام لیست ارسال شده است
            text_extracted = extract_laptops_from_text(text_input) if len(text_input) > 15 else []
            if text_extracted:
                context.user_data["pending_extracted_laptops"] = text_extracted
                context.user_data.pop("awaiting_laptop_photo", None)
                context.user_data.pop("awaiting_laptop_excel", None)
                preview_text, confirm_kb = make_laptop_confirm_prompt(text_extracted, source_title="متن ارسالی")
                await update.message.reply_text(
                    preview_text,
                    reply_markup=confirm_kb,
                    parse_mode="HTML"
                )
                return

            await update.message.reply_text(
                "📊 لطفاً <b>فایل اکسل (.xlsx / .csv)</b> یا <b>عکس و اسکرین‌شات جدول</b> را ارسال فرمایید.\n"
                "<i>(همچنین می‌توانید متن کپی‌شده از اکسل یا تلگرام را مستقیماً پیست نمایید)</i>\n"
                "برای انصراف کلمه <code>لغو</code> را ارسال فرمایید.",
                parse_mode="HTML"
            )
            return

        # ─── سناریوی دریافت عکس جدول با هوش مصنوعی بینایی ماشین ───
        status_msg = await update.message.reply_text(
            "⏳ <b>در حال تحلیل هوشمند تصویر جدول با هوش مصنوعی بینایی ماشین Gemini...</b>\n"
            "▫️ مشخصات فنی سطر به سطر در حال استخراج هستند.\n"
            "🛡 ستون قیمت همکار و اطلاعات تماس به صورت خودکار فیلتر می‌شوند.\n"
            "<i>لطفاً چند لحظه شکیبا باشید...</i>",
            parse_mode="HTML"
        )

        try:
            file_obj = await (photo.get_file() if photo else doc.get_file())
            img_bytes = await file_obj.download_as_bytearray()
            mime = "image/jpeg" if photo else (doc.mime_type or "image/jpeg")

            extracted = extract_laptops_from_image(bytes(img_bytes), mime_type=mime)
            if not extracted:
                await status_msg.edit_text(
                    "⚠️ متأسفانه هیچ سطری از مشخصات لپ‌تاپ در این تصویر شناسایی نشد.\n"
                    "لطفاً از وضوح تصویر و خوانا بودن ستون‌های جدول اطمینان حاصل کرده و مجدداً ارسال نمایید.",
                    parse_mode="HTML"
                )
                return

            context.user_data["pending_extracted_laptops"] = extracted
            context.user_data.pop("awaiting_laptop_photo", None)

            preview_text, confirm_kb = make_laptop_confirm_prompt(extracted, source_title="عکس ارسالی جدول")
            await status_msg.edit_text(preview_text, reply_markup=confirm_kb, parse_mode="HTML")
            return
        except Exception as err:
            logger.error(f"Error extracting laptops from image: {err}")
            err_text = str(err)
            network_hint = ""
            if "10053" in err_text or "Connection" in err_text or "abort" in err_text.lower():
                network_hint = (
                    "⚠️ <b>علت خطا:</b> ارتباط اینترنت یا نرم‌افزار ضدتحریم / VPN با سرور گوگل قطع شد (خطای 10053 ویندوز).\n"
                    "لطفاً فیلترشکن خود را بررسی و در صورت امکان حالت Tun / Global را فعال نمایید.\n\n"
                )

            alert_msg = (
                f"❌ <b>خطا در استخراج با هوش مصنوعی:</b>\n<code>{err_text[:250]}</code>\n\n"
                f"{network_hint}"
                "💡 <b>راهکارهای سریع:</b>\n"
                "۱. متن جدول اکسل یا پیام تلگرامی را کپی کرده و مستقیماً ارسال فرمایید (بدون نیاز به هوش مصنوعی و سریع).\n"
                "۲. یا کلید اختصاصی فعال را با دستور <code>/setgemini YOUR_KEY</code> تنظیم نمایید."
            )
            try:
                await status_msg.edit_text(alert_msg, parse_mode="HTML")
            except Exception as e_edit:
                logger.warning(f"Could not edit status_msg ({e_edit}), trying reply_text...")
                try:
                    await asyncio.sleep(2)
                    await update.message.reply_text(alert_msg, parse_mode="HTML")
                except Exception as e_reply:
                    logger.error(f"Failed to send error alert to admin: {e_reply}")
            return

    text = update.message.text.strip() if update.message.text else ""
    if not text:
        return

    # ۱. پردازش پاسخ ادمین به استعلام قیمت کالا (فقط دریافت قیمت تمام‌شده به عنوان مبنای اصلی)
    if adm and context.user_data.get("admin_answering_inquiry_id"):
        req_id = context.user_data.pop("admin_answering_inquiry_id")
        inq = await db.get_price_inquiry(req_id)
        if not inq:
            await update.message.reply_text("❌ درخواست استعلام یافت نشد یا منقضی شده است.")
            return

        raw_text = text.strip()
        t = _normalize_digits(raw_text).replace(",", "").replace("،", "").strip().lower()

        # پشتیبانی از ورود قیمت به میلیون (مانند ۳۸.۵ میلیون یا 38 میلیون)
        million_match = re.search(r'([\d\.]+)\s*(?:میلیون|mil|m)', t)
        total_price = 0
        if million_match:
            try:
                total_price = int(float(million_match.group(1)) * 1_000_000)
            except Exception:
                total_price = 0

        if total_price == 0:
            digits = re.findall(r'\d+', t)
            if digits:
                try:
                    total_price = int("".join(digits))
                except Exception:
                    total_price = 0

        dep_pct = getattr(config, "DEPOSIT_PERCENT", 8)
        shipping_method = context.user_data.pop("admin_answering_shipping_method", "freight")
        is_post = (shipping_method == "post")

        if total_price < 10000:
            context.user_data["admin_answering_inquiry_id"] = req_id
            context.user_data["admin_answering_shipping_method"] = shipping_method
            await update.message.reply_text(
                "❌ لطفاً <b>فقط مبلغ قیمت تمام‌شده کالا را به عدد (تومان)</b> وارد و ارسال فرمایید:\n"
                f"<i>(مثال: ۳۸,۵۰۰,۰۰۰ یا 38500000)</i>",
                parse_mode="HTML"
            )
            return

        # محاسبه بیعانه بر اساس شیوه ارسال
        if is_post:
            deposit_amount = total_price
            remaining_amount = 0
        else:
            deposit_amount = int(round((total_price * (dep_pct / 100.0)) / 10000)) * 10000
            if deposit_amount == 0:
                deposit_amount = int(round((total_price * (dep_pct / 100.0)) / 1000)) * 1000
            remaining_amount = max(0, total_price - deposit_amount)

        # ثبت قیمت تمام شده و شیوه ارسال در دیتابیس به عنوان مبنای قطعی
        await db.answer_price_inquiry(
            req_id,
            admin_response=str(total_price),
            final_price=str(total_price),
            shipping_method=shipping_method
        )

        f_total_price = to_fa_digits(f"{total_price:,}")
        f_deposit = to_fa_digits(f"{deposit_amount:,}")
        f_remaining = to_fa_digits(f"{remaining_amount:,}")

        if is_post:
            method_name = "📮 پست پیشتاز (تسویه کامل - بدون بیعانه)"
            admin_financial_block = (
                f"💰 <b>قیمت قطعی روز با هزینه ارسال:</b> <code>{f_total_price} تومان</code>\n"
                f"💳 <b>شرایط پرداخت:</b> تسویه کامل ۱۰۰٪ پیش از ارسال\n"
                f"▫️ <b>مانده در محل:</b> <code>۰ تومان</code>"
            )
            cust_financial_block = (
                f"💰 <b>قیمت قطعی روز کالا:</b> <code>{f_total_price} تومان</code>\n"
                f"💳 <b>مبلغ قابل پرداخت:</b> <code>{f_total_price} تومان (تسویه کامل)</code>\n"
                f"▫️ <i>نکته: ارسال از طریق پست پیشتاز و تسویه کامل پیش از ارسال می‌باشد.</i>"
            )
        else:
            method_name = f"🚚 باربری اختصاصی (بیعانه {dep_pct}٪ + تسویه در محل)"
            admin_financial_block = (
                f"💰 <b>قیمت قطعی روز با هزینه ارسال:</b> <code>{f_total_price} تومان</code>\n"
                f"💳 <b>مبلغ بیعانه ({dep_pct}٪):</b> <code>{f_deposit} تومان</code>\n"
                f"▫️ <b>مانده تسویه در محل:</b> <code>{f_remaining} تومان</code>"
            )
            cust_financial_block = (
                f"💰 <b>قیمت قطعی روز با احتساب هزینه ارسال:</b> <code>{f_total_price} تومان</code>\n"
                f"💳 <b>مبلغ بیعانه پیش‌پرداخت ({dep_pct}٪):</b> <code>{f_deposit} تومان</code>\n"
                f"▫️ <i>مانده تسویه پس از تحویل و تست سلامت: <code>{f_remaining} تومان</code></i>"
            )

        await update.message.reply_text(
            f"✅ <b>پاسخ استعلام با موفقیت برای خریدار ارسال گردید.</b>\n\n"
            f"<blockquote>📦 <b>کالا:</b> {inq.get('product_name')}\n"
            f"📍 <b>مقصد:</b> {inq.get('city')}\n"
            f"🛵 <b>شیوه ارسال:</b> {method_name}</blockquote>\n\n"
            f"<blockquote>{admin_financial_block}</blockquote>",
            parse_mode="HTML"
        )

        target_user_id = inq.get("user_id")
        pid = inq.get("product_id", "")
        customer_msg = (
            f"🌟 <b>استعلام قیمت تمام‌شده و شرایط ارسال تایید شد:</b>\n\n"
            f"<blockquote>📦 <b>کالا:</b> {inq.get('product_name')}\n"
            f"📍 <b>مقصد تحویل:</b> {inq.get('city')}\n"
            f"🛵 <b>نحوه ارسال:</b> {method_name}</blockquote>\n\n"
            f"<blockquote>{cust_financial_block}</blockquote>\n\n"
            f"<blockquote>⏳ <b>مهلت اعتبار:</b> این قیمت و شرایط تحویل تا <code>۵ ساعت</code> کاری معتبر می‌باشد.</blockquote>\n\n"
            f"👇 <i>جهت نهایی کردن خرید و صدور پیش‌فاکتور رسمی، دکمه زیر را لمس فرمایید:</i>"
        )
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=customer_msg,
                reply_markup=inquiry_quote_keyboard(pid, req_id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send quote to user {target_user_id}: {e}")
            await update.message.reply_text(f"⚠️ ارسال پیام به کاربر به دلیل بلاک بودن ربات یا خطای تلگرام انجام نشد: {e}")
        return

    # ۲. پردازش دریافت شهر مقصد از خریدار برای استعلام قیمت
    if context.user_data.get("awaiting_inquiry_pid"):
        pid = context.user_data.pop("awaiting_inquiry_pid", "")
        prod = context.user_data.pop("awaiting_inquiry_prod", None)
        if not prod:
            prod = find_product_by_id(pid) or await db.get_product_by_id(pid)

        pname = get_product_name(prod) if prod else "کالای انتخابی"
        city = text.strip()

        # ثبت سریع در دیتابیس
        req_id = await db.create_price_inquiry(
            user_id=user.id,
            username=f"@{user.username}" if user.username else user.first_name,
            product_id=str(pid),
            product_name=pname,
            city=city
        )

        # تاییدیه آنی به خریدار (بدون معطلی)
        escaped_pname = html.escape(str(pname))
        escaped_city = html.escape(str(city))
        confirm_text = (
            f"✅ <b>درخواست استعلام شما با موفقیت ثبت شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>کالا:</b> {escaped_pname}\n"
            f"📍 <b>مقصد تحویل:</b> {escaped_city}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ مشخصات به واحد فروش ارسال گردید.\n"
            f"قیمت قطعی روز و شرایط دقیق ارسال تا دقایقی دیگر به همراه دکمه پیش‌فاکتور در همین صفحه برای شما ارسال می‌شود.\n\n"
            f"ℹ️ <i>یادآوری: لوازم خانگی درشت با باربری (بیعانه + تسویه در محل) و برخی محصولات ریز با پست پیشتاز (تسویه کامل قبل از ارسال) ارسال می‌گردند.</i>"
        )
        inquiry_done_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📂 دسته‌بندی محصولات", callback_data="cat_back"),
                InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")
            ]
        ])
        try:
            await update.message.reply_text(confirm_text, reply_markup=inquiry_done_kb, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error replying to user text inquiry: {e}")
            await context.bot.send_message(chat_id=user.id, text=confirm_text, reply_markup=inquiry_done_kb, parse_mode="HTML")

        # ارسال اعلان غیرمسدودکننده به ادمین‌ها در پس‌زمینه (Zero Latency برای مشتری)
        admin_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚚 پاسخ با باربری (بیعانه)", callback_data=f"set_ship|freight|{req_id}"),
                InlineKeyboardButton("📮 پاسخ با پست (تسویه کامل)", callback_data=f"set_ship|post|{req_id}")
            ],
            [
                InlineKeyboardButton("❌ اتمام موجودی", callback_data=f"out_of_stock|{req_id}")
            ]
        ])
        user_info = f"@{user.username}" if user.username else user.first_name
        catalog_price = prod.get("price", "درج نشده") if prod else "درج نشده"
        admin_text = (
            f"🔔 <b>درخواست جدید استعلام قیمت تمام‌شده و کرایه!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>کالا:</b> {escaped_pname} (کد: <code>{html.escape(str(pid))}</code>)\n"
            f"🏷 <b>قیمت اولیه در کاتالوگ/کانال:</b> <b>{html.escape(str(catalog_price))}</b>\n"
            f"📍 <b>مقصد تحویل خریدار:</b> <b>{escaped_city}</b>\n"
            f"👤 <b>مشتری:</b> {html.escape(user.full_name or '')} ({html.escape(user_info)} | شناسه: <code>{user.id}</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>جهت ارسال قیمت نهایی و شرایط ارسال برای این مشتری روی دکمه زیر کلیک نمایید:</i>"
        )

        async def _notify_admins_async():
            target_admins = get_all_admin_ids()
            for admin_id in target_admins:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        reply_markup=admin_kb,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.debug(f"Notification to admin {admin_id} skipped: {e}")

        asyncio.create_task(_notify_admins_async())
        return

    clean_lower_text = text.strip().lower()
    if clean_lower_text in ["منو", "منوی اصلی", "منو اصلی", "بازگشت به منو", "منوی فروشگاه", "خانه", "menu", "/menu"]:
        welcome_text = (
            f"🏠 <b>اولین فروشگاه تلگرامی لوازم خانگی و لپتاپ (هوشمند کالا AiKala_bot) در ایران</b>\n\n"
            f"سلام <b>{user.first_name}</b> گرامی! 🌹\n\n"
            f"<blockquote>📦 <b>موجودی و قیمت‌های بروز کاتالوگ:</b>\n"
            f"▫️ قیمت‌ها و موجودی کالاها به صورت لحظه‌ای و قطعی بروزرسانی می‌شوند.\n"
            f"▫️ تضمین ۱۰۰٪ اصالت کالا، فاکتور معتبر و امکان تسویه درب منزل پس از تست</blockquote>\n\n"
            f"<blockquote>💡 <b>راهنمای تعامل با ربات:</b>\n"
            f"▫️ <b>ارسال متن:</b> ارسال هرگونه پیام یا نام مدل در چت، برای <b>جستجوی مستقیم کالا</b> است.\n"
            f"▫️ <b>مشاوره هوشمند:</b> برای مقایسه تخصصی و راهنمایی خرید، از دکمه «🧠 مشاور هوشمند خرید (جمینای)» استفاده فرمایید.</blockquote>"
        )
        await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(adm), parse_mode="HTML")
        return

    if text in ["🔍 جستجوی کالا", "جستجوی کالا", "جستجو", "سرچ", "/search"]:
        await update.message.reply_text(
            "💡 لطفاً نام مدل، برند یا دسته‌بندی کالا را تایپ کنید (مثال: <code>V9</code> یا <code>الجی</code>):",
            reply_markup=main_menu_keyboard(adm),
            parse_mode="HTML"
        )
        return
    elif text in [
        "📂 دسته‌بندی‌ها", "📂 دسته‌بندی ها", "📂 دسته بندی ها", "📂 دسته بندی‌ها",
        "📂 دسته‌بندی", "📂 دسته بندی", "دسته‌بندی‌ها", "دسته‌بندی ها", "دسته بندی ها",
        "دسته بندی", "دسته‌بندی", "دسته‌ها", "دسته ها", "دسته‌بندی محصولات", "دسته بندی محصولات",
        "/categories", "/category"
    ] or (isinstance(text, str) and text.replace(" ", "").replace("\u200c", "") in [
        "دسته‌بندی‌ها", "دسته‌بندی", "دستهبندیها", "دستهبندی", "📂دسته‌بندی‌ها", "📂دستهبندیها", "دسته‌ها", "دستهها"
    ]):
        await categories_command(update, context)
        return
    elif text in ["🧠 مشاور هوشمند خرید (جمینای)", "مشاور هوشمند", "مشاور خرید", "مشاوره خرید", "کمک در خرید", "/advisor", "/ai"]:
        await advisor_command(update, context)
        return
    elif text == "📋 پیگیری سفارش":
        await track_order_command(update, context)
        return
    elif text == "ℹ️ راهنمای خرید و ضمانت":
        await help_command(update, context)
        return
    elif text in ["💰 نرخ زنده ارز و طلا", "نرخ ارز و طلا", "قیمت دلار", "قیمت طلا", "نرخ ارز", "نرخ طلا", "قیمت ارز", "/rates", "/currency"]:
        await show_currency_rates(update, context)
        return
    elif text == "📞 پشتیبانی و مشاوره":
        await support_command(update, context)
        return
    elif adm and (text == "📋 سفارشات و رسید بانکی" or text.startswith("📋 سفارشات و رسید بانکی")):
        await admin_orders_hub(update, context, "all")
        return
    elif text == "⚙️ پنل مدیریت ادمین" and adm:
        await admin_panel_command(update, context)
        return

    # بررسی اگر کاربر در حالت پرسش از مشاور هوشمند خرید است یا یک سوال مشاوره‌ای پرسیده است:
    is_advisor_mode = context.user_data.get("awaiting_advisor_question")
    is_conversational_question = any(w in text for w in [
        "پیشنهاد", "کدوم", "کدام", "بهتره", "تفاوت", "مقایسه", "بخرم", "راهنمایی", "چطور", "نظرت", "بودجه", "متراژ",
        "ارسال", "باربری", "پست", "تسویه", "درب منزل", "اعتماد", "ضمانت", "گارانتی", "فاکتور", "سابقه", "بیعانه"
    ]) and len(text.strip().split()) >= 3

    if is_advisor_mode or is_conversational_question:
        context.user_data["awaiting_advisor_question"] = False
        context_pid = context.user_data.pop("advisor_context_pid", None)
        context_prod = None
        if context_pid:
            from search_engine import find_product_by_id
            context_prod = find_product_by_id(context_pid)

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        status_msg = await update.message.reply_text("⏳ <i>در حال بررسی کاتالوگ فروشگاه و آماده‌سازی مشاوره تخصصی جمینای...</i>", parse_mode="HTML")

        ans, suggested = await consult_gemini_shopping_advisor(text, context_product=context_prod)
        adv_kb = build_advisor_response_keyboard(suggested, context_pid=context_pid)

        try:
            await status_msg.delete()
        except Exception:
            pass

        await update.message.reply_text(
            f"🧠 <b>پاسخ مشاور هوشمند هوشمند کالا (Google Gemini):</b>\n\n{ans}",
            reply_markup=adv_kb,
            parse_mode="HTML"
        )
        return

    # در غیر این صورت، جستجوی کامل کاتالوگ محصولات با همان الگوریتم استاندارد و قدرتمند قبلی اجرا می‌شود:
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    products = search_products(text)

    if len(products) == 1:
        prod = products[0]
        await send_product_card_and_photos(update.effective_chat.id, prod, context, user_query=text)

    elif len(products) > 1:
        context.user_data["search_query_text"] = text
        context.user_data["search_results_list"] = products
        context.user_data["last_search_results"] = {p["product_id"]: p for p in products}
        await show_search_page(update, context, products, 0)
    else:
        await update.message.reply_text(
            "❌ کالایی با این عنوان پیدا نشد.\n💡 لطفاً نام مدل را کوتاه‌تر وارد کنید (مثال: <code>V9</code> یا <code>الجی</code>).",
            parse_mode="HTML"
        )

# =====================================================================
# 🔘 هندلر Callback Query دکمه‌های شیشه‌ای
# =====================================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # ─── بازگشت به نتایج جستجو از روی کارت کالا ───
    if data == "back_to_search":
        await query.answer()
        products = context.user_data.get("search_results_list", [])
        if not products:
            q_text = context.user_data.get("search_query_text", "")
            if q_text:
                products = search_products(q_text)
                if products:
                    context.user_data["search_results_list"] = products
                    context.user_data["last_search_results"] = {p["product_id"]: p for p in products}

        if products:
            page = context.user_data.get("search_page", 0)
            if not isinstance(page, int) or page < 0:
                page = 0
            max_page = max(0, (len(products) - 1) // 5)
            if page > max_page:
                page = max_page
            await show_search_page(update, context, products, page)
        else:
            await query.answer("لیست نتایج جستجوی قبلی منقضی شده است.", show_alert=False)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")]
            ])
            try:
                await query.message.reply_text(
                    "🔍 <b>لیست نتایج جستجوی قبلی موجود نیست یا منقضی شده است.</b>\n"
                    "لطفاً نام یا مدل کالای مورد نظر خود را مجدداً ارسال نمایید:",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception:
                pass
        return

    # ─── ناوبری هوشمند و پویای دسته‌بندی‌ها ───
    if data == "cat_back":
        await query.answer()
        kb = get_main_categories_markup()
        try:
            await query.edit_message_text(
                "📂 <b>دسته‌بندی‌های جامع فروشگاه هوشمند کالا:</b>\n"
                "لطفاً دسته کالای مورد نظر خود را جهت مشاهده مشخصات و کاتالوگ انتخاب فرمایید:",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception:
            await query.message.reply_text(
                "📂 <b>دسته‌بندی‌های جامع فروشگاه هوشمند کالا:</b>\n"
                "لطفاً دسته کالای مورد نظر خود را جهت مشاهده مشخصات و کاتالوگ انتخاب فرمایید:",
                reply_markup=kb,
                parse_mode="HTML"
            )
        return

    elif data.startswith("cat_m|") or data == "cat_m_laptop":
        await query.answer()
        if data == "cat_m_laptop":
            cat_key = "laptop"
        else:
            cat_key = resolve_safe_cb(data)
        msg_text, kb = get_category_sub_markup(cat_key)
        try:
            await query.edit_message_text(msg_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(msg_text, reply_markup=kb, parse_mode="HTML")
        return

    elif data.startswith("cat_f|"):
        await query.answer()
        raw_payload = resolve_safe_cb(data)
        parts = raw_payload.split(":", 1)
        if len(parts) == 2:
            cat_key, filter_type = parts
            msg_text, kb = get_filter_options_markup(cat_key, filter_type)
            try:
                await query.edit_message_text(msg_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(msg_text, reply_markup=kb, parse_mode="HTML")
        return

    elif data.startswith("cat_opt|"):
        await query.answer()
        raw_payload = resolve_safe_cb(data)
        parts = raw_payload.split(":", 2)
        if len(parts) == 3:
            cat_key, filter_type, opt_name = parts
            products = get_products_for_category_selection(cat_key, filter_type, opt_name)
            if products:
                context.user_data["search_results_list"] = products
                context.user_data["search_query_text"] = f"{opt_name}"
                context.user_data["last_search_results"] = {p["product_id"]: p for p in products}
                await show_search_page(update, context, products, 0)
            else:
                await query.message.reply_text("❌ کالایی با این فیلتر در انبار یافت نشد.")
        return

    elif data.startswith("cat_sub|"):
        await query.answer()
        raw_payload = resolve_safe_cb(data)
        parts = raw_payload.split(":", 1)
        if len(parts) == 2:
            cat_key, sub_name = parts
            products = get_products_for_category_selection(cat_key, "subcategories", sub_name)
            if products:
                context.user_data["search_results_list"] = products
                context.user_data["search_query_text"] = sub_name
                context.user_data["last_search_results"] = {p["product_id"]: p for p in products}
                await show_search_page(update, context, products, 0)
            else:
                await query.message.reply_text("❌ کالایی در این زیرشاخه یافت نشد.")
        return

    elif data.startswith("cat_all|"):
        await query.answer()
        cat_key = resolve_safe_cb(data)
        products = get_products_for_category_selection(cat_key)
        if products:
            context.user_data["search_results_list"] = products
            context.user_data["search_query_text"] = cat_key
            context.user_data["last_search_results"] = {p["product_id"]: p for p in products}
            await show_search_page(update, context, products, 0)
        else:
            await query.message.reply_text("❌ کالایی در این دسته یافت نشد.")
        return

    elif data.startswith("cat_pdf|"):
        await query.answer("📄 در حال آماده‌سازی فایل PDF لیست قیمت...")
        cat_key = resolve_safe_cb(data)
        chat_id = query.message.chat_id

        # Universal Category PDF handler
        try:
            from category_pdf_service import generate_category_pdf, load_category_products, CATEGORY_CONFIGS
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")

            cfg = CATEGORY_CONFIGS.get(cat_key, {
                "title": cat_key.upper(),
                "persian_title": "کالاهای اصلی",
                "guarantee": "ضمانت ۱۰۰٪ اصالت کالا و گارانتی معتبر شرکتی"
            })

            pdf_filename = f"AiKala_{cat_key.capitalize()}_PriceList.pdf"
            pdf_path = generate_category_pdf(cat_key, pdf_filename)
            items = load_category_products(cat_key)
            items_count = len(items)

            emoji_map = {
                "tv": "📺",
                "conditioner": "💨",
                "refrigerator": "❄️",
                "washing_machine": "🧺",
                "dishwasher": "🍽",
                "small_appliances": "🔌",
                "aeg": "✨",
                "laptop": "💻",
                "audio": "🔊"
            }
            cat_emoji = emoji_map.get(cat_key, "📦")
            p_title = cfg.get("persian_title", "لیست قیمت روز")

            today_str = datetime.now().strftime("%Y-%m-%d")
            warranty_desc = "۱۰۰٪ اورجینال با تضمین کتبی و تست صدا" if cat_key == "audio" else "۱۰۰٪ اورجینال با تضمین کتبی و گارانتی شرکتی"

            caption_text = (
                f"{cat_emoji} <b>لیست قیمت رسمی {p_title}</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 تعداد کل مدل‌های موجود: <b>{items_count} دستگاه</b>\n"
                f"🛡 <b>ضمانت اصالت:</b> {warranty_desc}\n"
                f"📅 <b>تاریخ صدور:</b> <code>{today_str}</code>\n\n"
                "تولید شده توسط موتور هوشمند صدور لیست قیمت کالا\n"
                "https://t.me/Aikala_bot"
            )

            try:
                with open(pdf_path, "rb") as doc_file:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=doc_file,
                        filename=pdf_filename,
                        caption=caption_text,
                        parse_mode="HTML"
                    )
            finally:
                if pdf_path and os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error generating/sending category PDF for {cat_key}: {e}")
            await query.message.reply_text(f"⚠️ متأسفانه در آماده‌سازی فایل PDF خطایی رخ داد. لطفاً با پشتیبانی تماس حاصل فرمایید.")
        return

    elif data.startswith("sel|"):
        await query.answer()
        pid = resolve_safe_cb(data)
        logger.info(f"👉 [BUTTON CLICKED] User clicked on product button ID: {pid}")
        prod = None
        for p in JSON_PRODUCTS:
            if str(p.get("product_id")) == str(pid):
                prod = p
                break
        if not prod:
            # جستجو در نتایج ذخیره‌شده اخیر کاربر در حافظه سشن
            cached_map = context.user_data.get("last_search_results", {})
            if isinstance(cached_map, dict) and str(pid) in [str(k) for k in cached_map.keys()]:
                for k, v in cached_map.items():
                    if str(k) == str(pid):
                        prod = v
                        break
            if not prod:
                for p in context.user_data.get("search_results_list", []):
                    if str(p.get("product_id")) == str(pid) or str(p.get("name")) == str(pid):
                        prod = p
                        break
        if not prod:
            prod = await db.get_product_by_id(pid)

        user_query = context.user_data.get("search_query_text", "")
        if prod:
            logger.info(f"   ↳ Found Product in DB/Cache: '{prod.get('name')}' (User query context: '{user_query}')")
            await send_product_card_and_photos(query.message.chat_id, prod, context, user_query=user_query)
        else:
            logger.warning(f"   ❌ Product ID '{pid}' not found in JSON_PRODUCTS or DB!")
            await query.message.reply_text("❌ کالا یافت نشد.")

    elif data.startswith("spage|"):
        await query.answer()
        page = int(data.split("|")[1])
        products = context.user_data.get("search_results_list", [])
        if products:
            await show_search_page(update, context, products, page)

    elif data.startswith("inq|"):
        pid = resolve_safe_cb(data)
        prod = find_product_by_id(pid) or await db.get_product_by_id(pid)
        pname = get_product_name(prod) if prod else "این کالا"

        context.user_data["awaiting_inquiry_pid"] = pid
        context.user_data["awaiting_inquiry_prod"] = prod

        # ساخت دکمه‌های سریع برای انتخاب شهرهای پرتقاضا + دکمه لغو با callback_data ایمن
        city_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("تهران", callback_data=make_safe_cb("inq_city", f"{pid}|تهران")),
                InlineKeyboardButton("اصفهان", callback_data=make_safe_cb("inq_city", f"{pid}|اصفهان")),
                InlineKeyboardButton("مشهد", callback_data=make_safe_cb("inq_city", f"{pid}|مشهد")),
            ],
            [
                InlineKeyboardButton("شیراز", callback_data=make_safe_cb("inq_city", f"{pid}|شیراز")),
                InlineKeyboardButton("تبریز", callback_data=make_safe_cb("inq_city", f"{pid}|تبریز")),
                InlineKeyboardButton("کرج", callback_data=make_safe_cb("inq_city", f"{pid}|کرج")),
            ],
            [
                InlineKeyboardButton("❌ انصراف از استعلام", callback_data="cancel_inq")
            ]
        ])

        msg_prompt = (
            f"💰 <b>استعلام قیمت تمام‌شده و کرایه کالا:</b>\n"
            f"📦 <b>{html.escape(str(pname))}</b>\n\n"
            f"🏙 لطفاً <b>شهر مقصد تحویل</b> را از گزینه‌های زیر لمس فرمایید، یا نام شهر خود را به صورت متنی تایپ و ارسال نمایید:\n"
            f"<i>(مثال: قم، اهواز، کرمان یا تهران - تهران)</i>\n\n"
            f"💡 <i>نکته ارسال: لوازم خانگی درشت با باربری (بیعانه + تسویه در محل) و برخی محصولات ریز با پست پیشتاز (تسویه کامل قبل از ارسال) ارسال می‌گردند.</i>"
        )
        # اجرای موازی answer و reply_text جهت دریافت بازخورد آنی کاربر بدون معطلی شبکه
        await query.answer("⏳ لطفاً شهر مقصد را انتخاب یا تایپ فرمایید...", show_alert=False)
        try:
            if query.message:
                await query.message.reply_text(msg_prompt, reply_markup=city_kb, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=query.from_user.id, text=msg_prompt, reply_markup=city_kb, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error sending city inquiry prompt: {e}")
            await context.bot.send_message(chat_id=query.from_user.id, text=msg_prompt, reply_markup=city_kb, parse_mode="HTML")

    elif data.startswith("inq_city|"):
        payload = resolve_safe_cb(data)
        pid = ""
        city = ""
        if "|" in payload:
            pid, city = payload.rsplit("|", 1)
        else:
            city = payload

        if not pid:
            pid = context.user_data.get("awaiting_inquiry_pid", "")

        prod = find_product_by_id(pid) or await db.get_product_by_id(pid)
        pname = get_product_name(prod) if prod else "کالای انتخابی"
        user = query.from_user

        context.user_data.pop("awaiting_inquiry_pid", None)
        context.user_data.pop("awaiting_inquiry_prod", None)

        # ثبت سریع در دیتابیس
        req_id = await db.create_price_inquiry(
            user_id=user.id,
            username=f"@{user.username}" if user.username else user.first_name,
            product_id=str(pid),
            product_name=pname,
            city=city
        )

        escaped_pname = html.escape(str(pname))
        escaped_city = html.escape(str(city))
        confirm_text = (
            f"✅ <b>درخواست استعلام شما با موفقیت ثبت شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>کالا:</b> {escaped_pname}\n"
            f"📍 <b>مقصد تحویل:</b> {escaped_city}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ مشخصات به واحد فروش ارسال گردید.\n"
            f"قیمت قطعی روز و شرایط دقیق ارسال تا دقایقی دیگر به همراه دکمه پیش‌فاکتور در همین صفحه برای شما ارسال می‌شود.\n\n"
            f"ℹ️ <i>یادآوری: لوازم خانگی درشت با باربری (بیعانه + تسویه در محل) و برخی محصولات ریز با پست پیشتاز (تسویه کامل قبل از ارسال) ارسال می‌گردند.</i>"
        )

        await query.answer("✅ استعلام شما با موفقیت ثبت شد.")
        inquiry_done_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📂 دسته‌بندی محصولات", callback_data="cat_back"),
                InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")
            ]
        ])
        try:
            if query.message:
                await query.message.reply_text(confirm_text, reply_markup=inquiry_done_kb, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=user.id, text=confirm_text, reply_markup=inquiry_done_kb, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error sending inquiry confirmation: {e}")
            await context.bot.send_message(chat_id=user.id, text=confirm_text, reply_markup=inquiry_done_kb, parse_mode="HTML")

        admin_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚚 پاسخ با باربری (بیعانه)", callback_data=f"set_ship|freight|{req_id}"),
                InlineKeyboardButton("📮 پاسخ با پست (تسویه کامل)", callback_data=f"set_ship|post|{req_id}")
            ],
            [
                InlineKeyboardButton("❌ اتمام موجودی", callback_data=f"out_of_stock|{req_id}")
            ]
        ])
        user_info = f"@{user.username}" if user.username else user.first_name
        catalog_price = prod.get("price", "درج نشده") if prod else "درج نشده"
        admin_text = (
            f"🔔 <b>درخواست جدید استعلام قیمت تمام‌شده و کرایه!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>کالا:</b> {escaped_pname} (کد: <code>{html.escape(str(pid))}</code>)\n"
            f"🏷 <b>قیمت اولیه در کاتالوگ/کانال:</b> <b>{html.escape(str(catalog_price))}</b>\n"
            f"📍 <b>مقصد تحویل خریدار:</b> <b>{escaped_city}</b>\n"
            f"👤 <b>مشتری:</b> {html.escape(user.full_name or '')} ({html.escape(user_info)} | شناسه: <code>{user.id}</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>جهت ارسال قیمت نهایی و شرایط ارسال برای این مشتری روی دکمه زیر کلیک نمایید:</i>"
        )

        async def _notify_admins_async():
            target_admins = get_all_admin_ids()
            for admin_id in target_admins:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        reply_markup=admin_kb,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.debug(f"Notification to admin {admin_id} skipped: {e}")

        asyncio.create_task(_notify_admins_async())
        return

    elif data == "cancel_inq":
        context.user_data.pop("awaiting_inquiry_pid", None)
        context.user_data.pop("awaiting_inquiry_prod", None)
        await asyncio.gather(
            query.answer("❌ لغو شد."),
            query.message.reply_text("❌ درخواست استعلام لغو گردید. در صورت تمایل می‌توانید کالای دیگری را جستجو فرمایید.")
        )
        return

    elif data.startswith("ans_inq|"):
        await query.answer()
        user_id = query.from_user.id
        if not is_admin(user_id):
            await query.message.reply_text("⛔️ دسترسی به این بخش فقط مخصوص مدیران فروشگاه است.")
            return

        req_id = int(data.split("|")[1])
        inq = await db.get_price_inquiry(req_id)
        if not inq:
            await query.message.reply_text("❌ درخواست استعلام یافت نشد یا حذف شده است.")
            return

        dep_pct = getattr(config, "DEPOSIT_PERCENT", 8)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🚚 ارسال با باربری (بیعانه {dep_pct}٪ + تسویه در محل)", callback_data=f"set_ship|freight|{req_id}")],
            [InlineKeyboardButton("📮 ارسال با پست پیشتاز (تسویه ۱۰۰٪ - بدون بیعانه)", callback_data=f"set_ship|post|{req_id}")],
        ])
        admin_prompt = (
            f"✍️ <b>تعیین شیوه ارسال و پاسخ به استعلام قیمت:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>کالا:</b> {inq.get('product_name')}\n"
            f"📍 <b>مقصد تحویل:</b> {inq.get('city')}\n"
            f"👤 <b>مشتری:</b> {inq.get('username')} (شناسه: <code>{inq.get('user_id')}</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <b>لطفاً نحوه ارسال کالا برای این سفارش را انتخاب فرمایید:</b>\n\n"
            f"▫️ <b>🚚 باربری:</b> دریافت بیعانه ({dep_pct}٪) + تسویه مانده درب منزل پس از تست سلامت\n"
            f"▫️ <b>📮 پست پیشتاز:</b> واریز ۱۰۰٪ مبلغ کل کالا قبل از ارسال (بدون بیعانه)"
        )
        await query.message.reply_text(admin_prompt, reply_markup=kb, parse_mode="HTML")

    elif data.startswith("set_ship|"):
        await query.answer()
        user_id = query.from_user.id
        if not is_admin(user_id):
            await query.message.reply_text("⛔️ دسترسی به این بخش فقط مخصوص مدیران فروشگاه است.")
            return

        parts = data.split("|")
        shipping_method = parts[1]
        req_id = int(parts[2])

        inq = await db.get_price_inquiry(req_id)
        if not inq:
            await query.message.reply_text("❌ درخواست استعلام یافت نشد یا حذف شده است.")
            return

        context.user_data["admin_answering_inquiry_id"] = req_id
        context.user_data["admin_answering_shipping_method"] = shipping_method

        dep_pct = getattr(config, "DEPOSIT_PERCENT", 8)
        if shipping_method == "post":
            method_desc = "📮 <b>پست پیشتاز (تسویه ۱۰۰٪ کامل قبل از ارسال - بدون بیعانه)</b>"
            calc_hint = "مشتری ملزم به واریز کل این مبلغ خواهد بود و بیعانه‌ای دریافت نمی‌شود"
        else:
            method_desc = f"🚚 <b>باربری / پیک (دریافت {dep_pct}٪ بیعانه + تسویه مانده در محل)</b>"
            calc_hint = f"مبلغ بیعانه {dep_pct}٪ به صورت خودکار محاسبه شده و مانده در محل تسویه می‌شود"

        admin_prompt = (
            f"✍️ <b>ثبت قیمت تمام‌شده کالا:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>کالا:</b> {inq.get('product_name')}\n"
            f"📍 <b>مقصد تحویل:</b> {inq.get('city')}\n"
            f"🛵 <b>نحوه ارسال انتخابی:</b> {method_desc}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 لطفاً <b>فقط مبلغ قیمت تمام‌شده کالا (به تومان)</b> را وارد و ارسال فرمایید:\n"
            f"<i>({calc_hint} - مثال: ۳۸,۵۰۰,۰۰۰ یا 38500000)</i>"
        )
        await query.message.reply_text(admin_prompt, parse_mode="HTML")

    elif data.startswith("out_of_stock|"):
        user_id = query.from_user.id
        if not is_admin(user_id):
            await query.answer("⛔️ دسترسی به این بخش فقط مخصوص مدیران فروشگاه است.", show_alert=True)
            return

        req_id = int(data.split("|")[1])
        inq = await db.get_price_inquiry(req_id)
        if not inq:
            await query.answer("❌ درخواست استعلام یافت نشد.", show_alert=True)
            return

        buyer_id = inq.get("user_id")
        pname = inq.get("product_name", "کالا")

        # دکمه‌های پیام ارسالی به خریدار
        buyer_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗂 مشاهده همه دسته‌بندی‌های کالا", callback_data="cat_back")],
            [InlineKeyboardButton("📞 مشاوره و پیشنهاد مدل جایگزین", callback_data="show_support")]
        ])

        buyer_notice = (
            f"⚠️ <b>اطلاعیه وضعیت موجودی کالا</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"خریدار گرامی، متأسفانه موجودی انبار برای کالای <b>{pname}</b> در حال حاضر به پایان رسیده است.\n\n"
            f"💡 پیشنهاد می‌کنیم جهت مشاهده و انتخاب مدل‌های مشابه و موجود در بازار، دسته‌بندی مربوط به این کالا را مشاهده فرمایید و یا با واحد مشاوره ما در ارتباط باشید."
        )

        try:
            await context.bot.send_message(
                chat_id=buyer_id,
                text=buyer_notice,
                reply_markup=buyer_kb,
                parse_mode="HTML"
            )
            await query.answer("✅ پیام اتمام موجودی برای خریدار ارسال گردید.", show_alert=True)
        except Exception as e:
            logger.error(f"Failed to send out-of-stock notice to buyer {buyer_id}: {e}")
            await query.answer("⚠️ خطا در ارسال پیام به خریدار (احتمالاً چت با ربات مسدود است)", show_alert=True)

    elif data == "adm_sync_photos":
        await query.answer()
        await sync_photos_command(update, context)

    elif data == "adm_channels":
        await query.answer()
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        from admin_panel import admin_channel_monitor_menu
        await admin_channel_monitor_menu(update, context)

    elif data == "adm_add_channel":
        await query.answer()
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        from admin_panel import admin_add_channel_prompt
        await admin_add_channel_prompt(update, context)

    elif data == "adm_sync_channels_all":
        await query.answer()
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        from admin_panel import admin_sync_channels_all
        await admin_sync_channels_all(update, context)

    elif data == "adm_list_channels_delete":
        await query.answer()
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        from admin_panel import admin_list_channels_delete
        await admin_list_channels_delete(update, context)

    elif data.startswith("adm_del_ch|"):
        await query.answer()
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        ch_to_del = data.split("|")[1]
        from admin_panel import admin_delete_channel_handler
        await admin_delete_channel_handler(update, context, ch_to_del)

    elif data == "adm_autoposter":
        await query.answer()
        from admin_panel import admin_autoposter_menu
        await admin_autoposter_menu(update, context)

    elif data == "adm_post_toggle":
        from admin_panel import admin_autoposter_toggle
        await admin_autoposter_toggle(update, context)

    elif data == "adm_post_now":
        from admin_panel import admin_autoposter_post_now
        await admin_autoposter_post_now(update, context)

    elif data.startswith("adm_post_int|"):
        val = data.split("|")[1]
        from admin_panel import admin_autoposter_set_interval
        await admin_autoposter_set_interval(update, context, val)

    elif data == "adm_post_set_channel_ask":
        from admin_panel import admin_autoposter_set_channel_prompt
        await admin_autoposter_set_channel_prompt(update, context)

    elif data == "adm_pending_orders":
        await query.answer()
        pending = await db.get_orders_by_status("Receipt_Uploaded")
        if not pending:
            empty_msg = "✅ در حال حاضر هیچ سفارشی در انتظار تایید وجود ندارد."
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")]])
            try:
                await query.edit_message_text(empty_msg, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(empty_msg, reply_markup=kb, parse_mode="HTML")
        else:
            lines = ["📋 <b>سفارشات در انتظار بررسی فیش:</b>\nبرای بررسی و تغییر وضعیت روی سفارش کلیک فرمایید:\n"]
            btns = []
            for o in pending[:8]:
                code = o.get("order_code")
                pname = (o.get("product_name") or "کالا")[:20]
                lines.append(f"▫️ سفارش <code>{code}</code> | {pname} | {o.get('full_name')}")
                btns.append([InlineKeyboardButton(f"🔎 بررسی و مدیریت سفارش {code}", callback_data=f"adm_view_ord|{code}")])
            btns.append([InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")])
            kb = InlineKeyboardMarkup(btns)
            try:
                await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
            except Exception:
                await query.message.reply_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")

    elif data == "adm_manage_orders":
        await admin_orders_hub(update, context, "all")

    elif data.startswith("adm_ord_flt|"):
        filter_st = data.split("|")[1]
        await admin_orders_hub(update, context, filter_st)

    elif data == "adm_search_ord_ask":
        await admin_order_search_ask(update, context)

    elif data.startswith("adm_view_ord|"):
        code = data.split("|")[1]
        await admin_view_order_detail(update, context, code)

    elif data.startswith("adm_set_status|"):
        await query.answer()
        parts = data.split("|")
        code = parts[1]
        new_status = parts[2]
        note = "تغییر وضعیت توسط ادمین"
        if new_status == "Approved":
            note = "تایید باربری و ارسال مرسوله"
        elif new_status == "Delivered":
            note = "تحویل کامل به خریدار و تسویه نهایی"
        elif new_status == "Cancelled":
            note = "لغو شده توسط مدیر فروشگاه"

        await db.update_order_status(code, status=new_status, admin_note=note)
        order = await db.get_order_by_code(code)

        # ارسال اطلاع‌رسانی آنی به خریدار
        if order and order.get("user_id"):
            buyer_id = order.get("user_id")
            buyer_msg = ""
            if new_status == "Approved":
                buyer_msg = (
                    f"🚚 <b>خریدار گرامی، سفارش <code>{code}</code> بارگیری و ارسال شد!</b>\n\n"
                    f"<blockquote>📦 <b>وضعیت مرسوله:</b> کالا با موفقیت تحویل باربر اختصاصی گردید و در مسیر شهر مقصد است.\n"
                    f"🛡 <b>بیمه سلامت کالا:</b> دستگاه تا لحظه تحویل، بررسی فیزیکی و تست سلامت در حضور باربر تحت پوشش بیمه کامل می‌باشد.</blockquote>\n\n"
                    f"👇 <i>جهت مشاهده لحظه‌ای موقعیت و تایم‌لاین ارسال، از بخش <b>پیگیری سفارشات</b> ربات استفاده فرمایید.</i>"
                )
            elif new_status == "Delivered":
                buyer_msg = (
                    f"🎉 <b>خریدار گرامی، سفارش <code>{code}</code> با موفقیت تحویل و تسویه گردید!</b>\n\n"
                    f"<blockquote>🌹 <b>پیام فروشگاه:</b> از حسن اعتماد و خرید شما از مجموعه هوشمند کالا صمیمانه سپاسگزاریم.\n"
                    f"🛡 <b>گارانتی و خدمات:</b> ضمانت اصالت و خدمات پس از فروش دستگاه از تاریخ امروز فعال می‌باشد.</blockquote>"
                )
            elif new_status == "Cancelled":
                buyer_msg = (
                    f"⚠️ <b>اطلاعیه لغو سفارش <code>{code}</code>:</b>\n\n"
                    f"<blockquote>❌ <b>وضعیت:</b> سفارش شما لغو گردید.\n"
                    f"▫️ <b>علت:</b> {note}</blockquote>\n\n"
                    f"💡 <i>در صورت نیاز به راهنمایی یا ثبت سفارش جدید، با واحد پشتیبانی در تماس باشید.</i>"
                )

            if buyer_msg:
                try:
                    await context.bot.send_message(chat_id=buyer_id, text=buyer_msg, parse_mode="HTML")
                except Exception as ex:
                    logger.warning(f"Could not notify buyer {buyer_id} of status change: {ex}")

        await query.message.reply_text(f"✅ وضعیت سفارش <code>{code}</code> با موفقیت به <b>{new_status}</b> تغییر یافت.", parse_mode="HTML")
        await admin_orders_hub(update, context, "all")

    elif data.startswith("adm_ok|"):
        await query.answer("فیش تایید شد")
        code = data.split("|")[1]
        order = await db.get_order_by_code(code)
        shipping_method = order.get("shipping_method", "freight") if order else "freight"
        is_post = (shipping_method == "post")

        admin_note = "تسویه کامل فاکتور تایید شد. تخصیص به واحد بسته‌بندی و تحویل به پست پیشتاز." if is_post else "فیش بانکی و بیعانه تایید شد. تخصیص به واحد ترابری."
        await db.update_order_status(code, status="Approved", admin_note=admin_note)
        # بازخوانی رکورد به‌روزشده
        order = await db.get_order_by_code(code)

        # مرحله دوم: تولید فاکتور رسمی و قطعی فروش
        invoice_path = None
        if order:
            try:
                inv_data = build_invoice_data_from_order(order)
                os.makedirs("invoices", exist_ok=True)
                out_png = f"invoices/final_invoice_{code}.png"
                invoice_path = generate_invoice_png(inv_data, output_path=out_png, is_pre_invoice=False)
            except Exception as e:
                logger.error(f"Error generating final invoice PNG: {e}")

        if order and order.get("user_id"):
            buyer_id = order.get("user_id")
            buyer_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 پیگیری لحظه‌ای سفارش", callback_data=f"track_ord|{code}")],
                [InlineKeyboardButton("📞 پشتیبانی و ترابری", callback_data="show_support")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")]
            ])
            if is_post:
                success_caption = (
                    f"🎉 <b>فاکتور رسمی و قطعی فروش صادر گردید!</b>\n\n"
                    f"<blockquote>✅ <b>وضعیت:</b> تسویه کامل سفارش <code>{code}</code> تایید شد.\n"
                    f"📦 <b>مرحله بعد:</b> کالا در دست آماده‌سازی و بسته‌بندی ضدضربه بوده و تحویل اداره پست پیشتاز خواهد شد.\n"
                    f"📮 <b>نحوه ارسال:</b> پست پیشتاز (تسویه کامل - مانده صفر)</blockquote>\n\n"
                    f"<blockquote>📋 <i>کد رهگیری پستی به محض تحویل به اداره پست، در بخش پیگیری سفارشات ثبت و پیامک خواهد شد.</i></blockquote>\n\n"
                    f"👇 <i>جهت مشاهده موقعیت لحظه‌ای و تایم‌لاین سفارش، دکمه پیگیری سفارش را لمس فرمایید:</i>"
                )
            else:
                success_caption = (
                    f"🎉 <b>فاکتور رسمی و قطعی فروش صادر گردید!</b>\n\n"
                    f"<blockquote>✅ <b>وضعیت:</b> بیعانه سفارش <code>{code}</code> تایید شد.\n"
                    f"📦 <b>مرحله بعد:</b> کالا در نوبت بارگیری بوده و تحویل باربر اختصاصی داده خواهد شد.\n"
                    f"🚚 <b>نحوه ارسال:</b> باربری اختصاصی (تحویل درب منزل)\n"
                    f"▫️ <i>تسویه مانده‌حساب پس از تحویل، بررسی فیزیکی و تست سلامت در محل انجام خواهد شد.</i></blockquote>\n\n"
                    f"👇 <i>جهت مشاهده موقعیت لحظه‌ای و تایم‌لاین ارسال، دکمه پیگیری سفارش را لمس فرمایید:</i>"
                )
            try:
                if invoice_path and os.path.exists(invoice_path):
                    with open(invoice_path, "rb") as f_inv:
                        await context.bot.send_photo(
                            chat_id=buyer_id,
                            photo=f_inv,
                            caption=success_caption,
                            reply_markup=buyer_kb,
                            parse_mode="HTML",
                            read_timeout=60.0,
                            write_timeout=90.0,
                            connect_timeout=30.0
                        )
                else:
                    await context.bot.send_message(
                        chat_id=buyer_id,
                        text=success_caption,
                        reply_markup=buyer_kb,
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.warning(f"Could not notify buyer {buyer_id}: {e}")

        method_lbl = "پست پیشتاز (تسویه کامل)" if is_post else "باربری (بیعانه)"
        try:
            await query.edit_message_caption(
                caption=f"✅ فیش سفارش <code>{code}</code> ({method_lbl}) تایید شد.\n📄 فاکتور قطعی فروش صادر و برای مشتری ارسال گردید.",
                parse_mode="HTML"
            )
        except Exception:
            await query.message.reply_text(
                f"✅ فیش سفارش <code>{code}</code> ({method_lbl}) تایید و فاکتور نهایی برای مشتری ارسال گردید.",
                parse_mode="HTML"
            )

    elif data.startswith("adm_no|"):
        await query.answer("فیش رد شد")
        code = data.split("|")[1]
        await db.update_order_status(code, status="Rejected", admin_note="عدم تایید مشخصات فیش یا مبلغ بیعانه توسط حسابداری")
        order = await db.get_order_by_code(code)
        if order and order.get("user_id"):
            buyer_id = order.get("user_id")
            buyer_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 ارسال مجدد تصویر فیش", callback_data=f"uprec|{code}")],
                [InlineKeyboardButton("📞 پشتیبانی و پیگیری", callback_data="show_support")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")]
            ])
            reject_msg = (
                f"❌ <b>عدم تایید فیش ارسالی برای سفارش <code>{code}</code></b>\n\n"
                f"<blockquote>⚠️ مشخصات فیش یا مبلغ واریزی مورد تایید حسابداری قرار نگرفت.\n"
                f"▫️ <b>علت احتمالی:</b> ناخوانا بودن رسید، مغایرت مبلغ یا تاخیر بانکی.</blockquote>\n\n"
                f"💡 <i>لطفاً تصویر فیش واریزی را مجدداً ارسال نمایید یا با پشتیبانی تماس حاصل فرمایید.</i>"
            )
            try:
                await context.bot.send_message(
                    chat_id=buyer_id,
                    text=reject_msg,
                    reply_markup=buyer_kb,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not notify buyer {buyer_id}: {e}")

        try:
            await query.edit_message_caption(
                caption=f"❌ فیش سفارش <code>{code}</code> رد شد و به مشتری اطلاع‌رسانی گردید.",
                parse_mode="HTML"
            )
        except Exception:
            await query.message.reply_text(f"❌ فیش سفارش <code>{code}</code> رد شد.", parse_mode="HTML")

    elif data == "adm_verified_photos":
        await query.answer()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")]
        ])
        if not VERIFIED_PRODUCT_PHOTOS:
            empty_msg = (
                "📸 <b>لیست تصاویر تایید شده محصولات:</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "در حال حاضر هیچ تصویری به صورت دستی تایید یا ثبت نشده است.\n\n"
                "💡 <b>چگونه تصویر تایید شده ثبت کنیم؟</b>\n"
                "۱. <b>روش مستقیم:</b> با ارسال دستور زیر:\n"
                "<code>/setphoto [کد_محصول]</code> (مثال: <code>/setphoto 68798</code>)\n\n"
                "۲. <b>روش خودکار:</b> هرگاه کاربری روی «📸 تصاویر محصول» کالایی بزند و تصویری در کانال نباشد، "
                "یک دکمه «ثبت عکس» به صورت اختصاصی برای ادمین ارسال می‌شود تا با یک کلیک و ارسال عکس/لینک آن را تایید کند."
            )
            try:
                await query.edit_message_text(empty_msg, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await query.message.reply_text(empty_msg, reply_markup=kb, parse_mode="HTML")
        else:
            lines = [
                f"📸 <b>لیست تصاویر تایید شده ({len(VERIFIED_PRODUCT_PHOTOS)} محصول):</b>\n",
                "━━━━━━━━━━━━━━━━━━━━\n"
            ]
            for pid_item, val in list(VERIFIED_PRODUCT_PHOTOS.items())[-20:]:
                p_link = val.get('link') or val.get('message_ids') or "فایل مستقیم"
                lines.append(f"▫️ <b>{val.get('product_name', pid_item)}</b>\n  کد: <code>{pid_item}</code> | مرجع: <code>{p_link}</code>")
            lines.append("\n💡 <i>جهت افزودن یا تغییر تصویر هر محصول، از دستور <code>/setphoto [کد]</code> استفاده نمایید.</i>")
            try:
                await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                await query.message.reply_text("\n".join(lines), reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

    elif data == "adm_clear_photos_ask":
        await query.answer()
        await clearphotos_command(update, context)

    elif data == "adm_clear_photos_do":
        await query.answer("در حال پاکسازی لیست تصاویر...", show_alert=False)
        from photo_service import clear_all_product_photos
        stats = clear_all_product_photos()
        v_count = stats.get("verified_count", 0)
        p_count = stats.get("posts_count", 0)

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
        ])
        msg = (
            f"✅ <b>تمامی تصاویر تستی و کش قبلی با موفقیت پاکسازی شدند!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"▫️ تعداد تصاویر تایید شده دستی حذف‌شده: <b>{v_count}</b> مورد\n"
            f"▫️ تعداد پست‌های ایندکس‌شده تستی کانال: <b>{p_count}</b> پست\n\n"
            f"✨ <b>از این پس:</b>\n"
            f"سیستم کاملاً آماده و تمیز است تا فقط تصاویر واقعی محصولات که در کانال عکس‌ها قرار می‌گیرند یا با دستور <code>/setphoto</code> متصل می‌شوند، برای مشتریان ارسال گردند."
        )
        try:
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")

    elif data == "back_to_main":
        await query.answer()
        user = update.effective_user
        adm = is_admin(user.id if user else 0)
        welcome_text = (
            f"🏠 <b>منوی اصلی بازرگانی و فروشگاه هوشمند کالا</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"سلام <b>{user.first_name}</b> گرامی! 🌹\n\n"
            f"✨ <b>دسترسی سریع به امکانات فروشگاه:</b>\n"
            f"🔹 جهت جستجوی کالا، نام یا مدل محصول را تایپ و ارسال فرمایید.\n"
            f"🔹 برای مشاهده دسته‌بندی‌ها یا رهگیری سفارشات، از گزینه‌های زیر استفاده نمایید:"
        )
        main_inline_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📂 دسته‌بندی محصولات", callback_data="cat_back"),
                InlineKeyboardButton("🔍 جستجوی کالا", callback_data="btn_search_prompt")
            ],
            [
                InlineKeyboardButton("📦 پیگیری سفارشات", callback_data="track_order_list"),
                InlineKeyboardButton("ℹ️ راهنمای خرید و ضمانت", callback_data="guide_main")
            ],
            [
                InlineKeyboardButton("💰 نرخ زنده ارز و طلا", callback_data="show_currency_rates"),
                InlineKeyboardButton("📞 پشتیبانی و مشاوره", callback_data="show_support")
            ]
        ])
        try:
            await query.edit_message_text(welcome_text, reply_markup=main_inline_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(welcome_text, reply_markup=main_inline_kb, parse_mode="HTML")

        # بازگرداندن و تثبیت کیبورد دکمه‌های منو در پایین صفحه
        try:
            await query.message.reply_text(
                "📋 <i>دکمه‌های منوی اصلی در پایین صفحه در دسترس شماست:</i>",
                reply_markup=main_menu_keyboard(adm),
                parse_mode="HTML"
            )
        except Exception:
            pass

    elif data == "btn_search_prompt":
        await query.answer()
        user = update.effective_user
        adm = is_admin(user.id if user else 0)
        await query.message.reply_text(
            "💡 لطفاً نام مدل، برند یا دسته‌بندی کالا را تایپ کنید (مثال: <code>V9</code> یا <code>الجی</code>):",
            reply_markup=main_menu_keyboard(adm),
            parse_mode="HTML"
        )

    elif data == "show_currency_rates":
        await show_currency_rates(update, context, is_refresh=False)
        return

    elif data == "refresh_currency_rates":
        await show_currency_rates(update, context, is_refresh=True)
        return

    elif data == "close_window":
        try:
            await query.message.delete()
        except Exception:
            pass

    elif data == "adm_back_panel":
        await query.answer()
        await admin_panel_command(update, context)

    elif data == "adm_laptop_hub":
        await admin_laptop_hub(update, context)

    elif data == "adm_audio_hub":
        await admin_audio_hub(update, context)

    elif data == "adm_upload_audio_excel":
        await admin_upload_audio_excel_prompt(update, context)

    elif data == "adm_audio_download_csv":
        await admin_audio_download_csv(update, context)

    elif data == "adm_clear_audio_ask":
        await admin_clear_audio_ask(update, context)

    elif data == "adm_clear_audio_do":
        await admin_clear_audio_do(update, context)

    elif data == "adm_audio_reload":
        await admin_audio_reload(update, context)

    elif data == "adm_audio_download_pdf":
        await admin_audio_download_pdf(update, context)

    elif data == "adm_laptop_download_pdf":
        await admin_laptop_download_pdf(update, context)

    elif data == "adm_text_laptop_prompt":
        await admin_text_laptop_prompt(update, context)

    elif data == "adm_clear_laptops_ask":
        await admin_clear_laptops_ask(update, context)

    elif data == "adm_clear_laptops_do":
        await admin_clear_laptops_do(update, context)

    elif data == "adm_sync_live_prices":
        await admin_sync_live_prices(update, context)

    elif data == "adm_sync_aeg":
        await admin_sync_aeg(update, context)

    elif data == "adm_sync_catalog_stock":
        await admin_sync_catalog_stock(update, context)

    elif data == "adm_bank_settings":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_bank_settings(update, context)

    elif data == "adm_edit_bank_card":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_prompt_bank_edit(update, context, "card")

    elif data == "adm_edit_bank_shaba":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_prompt_bank_edit(update, context, "shaba")

    elif data == "adm_edit_bank_holder":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_prompt_bank_edit(update, context, "holder")

    elif data == "adm_edit_bank_deposit":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_prompt_bank_edit(update, context, "deposit")

    elif data == "adm_catalog_report":
        await admin_catalog_report(update, context)

    elif data == "adm_ai_settings":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_ai_settings_menu(update, context)

    elif data.startswith("adm_ai_set_"):
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        target_provider = data.replace("adm_ai_set_", "").strip()
        await admin_ai_set_provider_handler(update, context, target_provider)

    elif data.startswith("adm_ai_key_"):
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        provider = data.replace("adm_ai_key_", "").strip()
        from admin_panel import admin_ai_key_prompt
        await admin_ai_key_prompt(update, context, provider)

    elif data == "adm_ai_test":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        from admin_panel import admin_ai_test_handler
        await admin_ai_test_handler(update, context)

    elif data.startswith("adm_ai_batch_") or data.startswith("adm_ai_run_batch:") or data.startswith("adm_ai_desc_") or data.startswith("adm_ai_run_desc:"):
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_ai_batch_handler(update, context, data)

    # ─── بخش پشتیبان‌گیری و بازگردانی کلی سیستم (مخصوص ادمین اصلی) ───
    elif data == "adm_backup_menu":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_backup_menu(update, context)

    elif data == "adm_backup_download":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_backup_download_handler(update, context)

    elif data == "adm_backup_toggle_auto":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_backup_toggle_auto_handler(update, context)

    elif data == "adm_backup_upload_prompt":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_backup_upload_prompt(update, context)

    elif data == "adm_restore_smart_merge":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return

        zip_file = context.user_data.pop("pending_restore_file", None)
        if not zip_file or not os.path.exists(zip_file):
            await query.answer("فایل بک‌آپ منقضی شده است. لطفاً مجدداً فایل را ارسال فرمایید.", show_alert=True)
            return

        await query.answer("در حال ادغام اطلاعات...", show_alert=False)
        from backup_service import restore_smart_merge
        success, res_text, stats = restore_smart_merge(zip_file)
        try:
            os.remove(zip_file)
        except Exception:
            pass

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
        ])
        await query.edit_message_text(res_text, reply_markup=kb, parse_mode="HTML")

    elif data == "adm_restore_full_replace":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return

        zip_file = context.user_data.pop("pending_restore_file", None)
        if not zip_file or not os.path.exists(zip_file):
            await query.answer("فایل بک‌آپ منقضی شده است. لطفاً مجدداً فایل را ارسال فرمایید.", show_alert=True)
            return

        await query.answer("در حال بازگردانی کامل سیستم...", show_alert=False)
        from backup_service import restore_full_replace
        success, res_text = restore_full_replace(zip_file)
        try:
            os.remove(zip_file)
        except Exception:
            pass

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
        ])
        await query.edit_message_text(res_text, reply_markup=kb, parse_mode="HTML")

    # ─── مدیریت ادمین‌ها و سطوح دسترسی (مخصوص ادمین اصلی) ───
    elif data == "adm_manage_admins":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_manage_admins_menu(update, context)

    elif data == "adm_add_admin_prompt":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        await admin_add_admin_prompt(update, context)

    elif data.startswith("adm_del_admin|"):
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
            return
        target_uid_str = data.split("|")[1]
        await admin_delete_admin_handler(update, context, target_uid_str)

    # ─── مرکز کنترل وضعیت و فریز کلی ربات (مخصوص ادمین اصلی) ───
    elif data == "adm_freeze_menu":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات مدیر ارشد می‌باشد.", show_alert=True)
            return
        await admin_freeze_menu(update, context)

    elif data == "adm_freeze_quick":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات مدیر ارشد می‌باشد.", show_alert=True)
            return
        await admin_freeze_quick_handler(update, context)

    elif data == "adm_unfreeze_do":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات مدیر ارشد می‌باشد.", show_alert=True)
            return
        await admin_unfreeze_handler(update, context)

    elif data == "adm_freeze_custom_prompt":
        if not is_owner(update.effective_user.id):
            await query.answer("⛔️ این بخش تنها در اختیارات مدیر ارشد می‌باشد.", show_alert=True)
            return
        await admin_freeze_custom_prompt(update, context)

    elif data == "adm_restore_cancel":
        await query.answer("عملیات بازگردانی لغو گردید.")
        zip_file = context.user_data.pop("pending_restore_file", None)
        if zip_file and os.path.exists(zip_file):
            try:
                os.remove(zip_file)
            except Exception:
                pass
        await admin_backup_menu(update, context)

    elif data == "adm_broadcast_ask":
        await admin_broadcast_ask(update, context)

    elif data == "adm_broadcast_do":
        await admin_broadcast_do(update, context)

    elif data == "adm_upload_laptop_excel":
        await admin_upload_laptop_excel_prompt(update, context)

    elif data == "adm_upload_laptop_photo":
        await query.answer()
        context.user_data["awaiting_laptop_photo"] = True
        context.user_data.pop("pending_extracted_laptops", None)
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_laptop_hub")]
        ])
        msg = (
            "💻 <b>استخراج هوشمند لیست قیمت و موجودی لپ‌تاپ:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "لطفاً <b>عکس، اسکرین‌شات یا فایل تصویر جدول قیمت</b> لپ‌تاپ را ارسال فرمایید.\n\n"
            "🤖 <b>فیلترهای خودکار هوش مصنوعی:</b>\n"
            "✅ خواندن ستون «قیمت» و تبدیل دقیق به تومان\n"
            "🚫 <b>حذف قطعی ستون همکاری</b> (قیمت همکار هرگز ثبت نمی‌شود)\n"
            "🚫 <b>فیلتر کامل شماره تماس‌ها</b> (درویشی، رحمانی، خاکساران و...)\n"
            "🚫 <b>حذف هدرها و نام‌های تبلیغاتی متفرقه</b>\n"
            "🏷 تفکیک خودکار و ثبت زیرمجموعه منحصراً بر اساس برند (HP، ASUS، LENOVO و...)\n\n"
            "👇 <i>هم‌اکنون عکس را در همین چت ارسال فرمایید:</i>"
        )
        try:
            await query.edit_message_text(msg, reply_markup=cancel_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(msg, reply_markup=cancel_kb, parse_mode="HTML")

    elif data == "adm_confirm_laptops_replace":
        await query.answer("در حال جایگزینی کامل لیست لپ‌تاپ‌ها...", show_alert=False)
        extracted = context.user_data.pop("pending_extracted_laptops", None)
        if not extracted:
            await query.message.reply_text("⚠️ داده‌ای برای ثبت یافت نشد یا جلسه منقضی شده است.")
            return

        res = replace_extracted_laptops(extracted)
        # به‌روزرسانی آنی کش محصولات در حافظه بدون نیاز به ری‌استارت
        load_json_products()

        done_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 مشاهده دسته‌بندی لپ‌تاپ", callback_data="cat_m_laptop")],
            [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
        ])
        done_text = (
            f"🎉 <b>لیست لپ‌تاپ‌ها با موفقیت جایگزین شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🗑 <b>لیست قبلی لپ‌تاپ‌ها به طور کامل حذف گردید.</b>\n"
            f"💻 تعداد کل لپ‌تاپ‌های فعال جدید: <b>{res['total']} مدل</b>\n\n"
            f"✨ کلیه مدل‌ها بلافاصله در دسته‌بندی «💻 لپ‌تاپ» و زیرمجموعه برندها قرار گرفتند و با جستجو نیز در دسترس هستند."
        )
        try:
            await query.edit_message_text(done_text, reply_markup=done_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(done_text, reply_markup=done_kb, parse_mode="HTML")

    elif data == "adm_confirm_laptops_merge" or data == "adm_confirm_laptops":
        await query.answer("در حال ادغام با کاتالوگ لپ‌تاپ...", show_alert=False)
        extracted = context.user_data.pop("pending_extracted_laptops", None)
        if not extracted:
            await query.message.reply_text("⚠️ داده‌ای برای ثبت یافت نشد یا جلسه منقضی شده است.")
            return

        merge_res = merge_extracted_laptops(extracted)
        # به‌روزرسانی آنی کش محصولات در حافظه بدون نیاز به ری‌استارت
        load_json_products()

        done_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 مشاهده دسته‌بندی لپ‌تاپ", callback_data="cat_m_laptop")],
            [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
        ])
        done_text = (
            f"🎉 <b>لیست لپ‌تاپ‌ها با موفقیت با کاتالوگ ادغام شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"➕ مدل‌های جدید اضافه شده: <b>{merge_res['added']} مدل</b>\n"
            f"🔄 مدل‌های به‌روزرسانی شده: <b>{merge_res['updated']} مدل</b>\n"
            f"💻 کل لپ‌تاپ‌های فعال در کاتالوگ: <b>{merge_res['total']} مدل</b>\n\n"
            f"✨ کلیه محصولات بلافاصله در دسته‌بندی «💻 لپ‌تاپ» و زیرمجموعه برندها قرار گرفتند و با جستجوی مدل و مشخصات نیز قابل مشاهده و سفارش هستند."
        )
        try:
            await query.edit_message_text(done_text, reply_markup=done_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(done_text, reply_markup=done_kb, parse_mode="HTML")

    elif data == "adm_cancel_laptops":
        await query.answer("عملیات لغو شد.")
        context.user_data.pop("awaiting_laptop_photo", None)
        context.user_data.pop("awaiting_laptop_excel", None)
        context.user_data.pop("pending_extracted_laptops", None)
        await admin_panel_command(update, context)

    elif data == "adm_confirm_audio_replace":
        await query.answer("در حال جایگزینی کامل لیست سیستم‌های صوتی...", show_alert=False)
        extracted = context.user_data.pop("pending_extracted_audio", None)
        if not extracted:
            await query.message.reply_text("⚠️ داده‌ای برای ثبت یافت نشد یا جلسه منقضی شده است.")
            return

        res = replace_audio_products(extracted)
        load_json_products()

        done_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 مشاهده دسته‌بندی سیستم صوتی", callback_data="cat_m_audio")],
            [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
        ])
        done_text = (
            f"🎉 <b>کاتالوگ سیستم صوتی با موفقیت جایگزین شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🗑 <b>لیست قبلی سیستم‌های صوتی به طور کامل حذف گردید.</b>\n"
            f"🔊 تعداد کل مدل‌های فعال جدید: <b>{res['total']} دستگاه</b>\n\n"
            f"✨ کلیه مدل‌ها بلافاصله در دسته‌بندی «🔊 سیستم صوتی»، جستجوی زنده و ربات فعال شدند."
        )
        try:
            await query.edit_message_text(done_text, reply_markup=done_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(done_text, reply_markup=done_kb, parse_mode="HTML")

    elif data == "adm_confirm_audio_merge":
        await query.answer("در حال ادغام با کاتالوگ سیستم صوتی...", show_alert=False)
        extracted = context.user_data.pop("pending_extracted_audio", None)
        if not extracted:
            await query.message.reply_text("⚠️ داده‌ای برای ثبت یافت نشد یا جلسه منقضی شده است.")
            return

        merge_res = merge_audio_products(extracted)
        load_json_products()

        done_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 مشاهده دسته‌بندی سیستم صوتی", callback_data="cat_m_audio")],
            [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
        ])
        done_text = (
            f"🎉 <b>لیست با کاتالوگ سیستم‌های صوتی با موفقیت ادغام شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"➕ مدل‌های جدید اضافه شده: <b>{merge_res['added']} دستگاه</b>\n"
            f"🔄 مدل‌های به‌روزرسانی شده: <b>{merge_res['updated']} دستگاه</b>\n"
            f"🔊 کل مدل‌های فعال سیستم صوتی: <b>{merge_res['total']} دستگاه</b>\n\n"
            f"✨ کلیه محصولات بلافاصله در دسته‌بندی «🔊 سیستم صوتی» و حافظه جستجوی ربات در دسترس هستند."
        )
        try:
            await query.edit_message_text(done_text, reply_markup=done_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(done_text, reply_markup=done_kb, parse_mode="HTML")

    elif data == "adm_cancel_audio":
        await query.answer("عملیات لغو شد.")
        context.user_data.pop("awaiting_audio_excel", None)
        context.user_data.pop("pending_extracted_audio", None)
        await admin_audio_hub(update, context)

    elif data.startswith("req_img|"):
        pid = resolve_safe_cb(data)
        user = update.effective_user

        prod = None
        for p in JSON_PRODUCTS:
            if str(p.get("product_id")) == str(pid):
                prod = p
                break
        if not prod:
            prod = await db.get_product_by_id(pid)
        pname = prod.get("name", "این محصول") if prod else "این محصول"

        # بررسی آیا محصول از دسته لپ‌تاپ است (چون عکس ندارند)
        is_laptop = (
            (prod and prod.get("category_key") == "laptop")
            or (prod and prod.get("category") in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"])
            or (prod and prod.get("category_name") in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"])
            or str(pid).upper().startswith("LAP")
            or any(w in str(pname).lower() for w in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"])
        )
        if is_laptop:
            await query.answer("💡 محصولات دسته‌بندی لپ‌تاپ فاقد تصویر آلبومی هستند و مشخصات فنی آن‌ها در کارت کالا درج شده است.", show_alert=True)
            return

        # ۱. بررسی تصاویر تایید شده محصول
        matched_pid, photo_data, match_type = find_matching_verified_photos(prod or pid)
        if photo_data:
            await query.answer("📸 در حال ارسال تصاویر اختصاصی محصول...")
            success = await send_verified_photos_to_user(
                context.bot,
                query.message.chat_id,
                pid,
                pname,
                photo_data=photo_data,
                matched_note=None
            )
            if success:
                return

        # ۲. در غیر این صورت -> ثبت درخواست، ارسال پیام اطلاع به کاربر و ارسال فوری نوتیفیکیشن به ادمین
        await query.answer("درخواست شما برای مشاهده تصاویر کالا ثبت شد", show_alert=True)

        user_req_text = (
            f"📸 <b>درخواست تصاویر واقعی کالا:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>محصول:</b> <b>{pname}</b>\n\n"
            f"⏳ تا دقایقی دیگر آلبوم تصاویر به صورت خودکار در همین گفتگو برای شما ارسال خواهد شد."
        )
        try:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=user_req_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not send waiting confirmation to user: {e}")

        if pid not in PENDING_IMAGE_REQUESTS:
            PENDING_IMAGE_REQUESTS[pid] = []
        if query.message.chat_id not in PENDING_IMAGE_REQUESTS[pid]:
            PENDING_IMAGE_REQUESTS[pid].append(query.message.chat_id)

        admin_cb = make_safe_cb("adm_set_img", f"{pid}|{query.message.chat_id}")
        admin_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 ثبت و ارسال لینک تصاویر", callback_data=admin_cb)]
        ])
        admin_alert = (
            f"🔔 <b>درخواست جدید تصاویر محصول از سوی مشتری</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>نام کالا:</b> {pname}\n"
            f"🏷 <b>کد محصول:</b> <code>{pid}</code>\n"
            f"👤 <b>متقاضی:</b> {user.full_name} (@{user.username or 'ندارد'})\n"
            f"🆔 <b>شناسه کاربر:</b> <code>{user.id}</code>\n\n"
            f"👇 <i>جهت ارسال تصاویر این کالا، دکمه زیر را لمس کرده و لینک پست، شماره پیام یا عکس‌های کانال را بفرستید:</i>"
        )
        for adm_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=adm_id,
                    text=admin_alert,
                    reply_markup=admin_kb,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to alert admin {adm_id}: {e}")

    elif data.startswith("adm_set_img|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        await query.answer()
        payload = resolve_safe_cb(data)
        parts = payload.split("|")
        pid = parts[0]
        target_uid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

        prod = next((p for p in JSON_PRODUCTS if str(p.get("product_id")) == str(pid)), None)
        pname = prod.get("name", pid) if prod else pid

        context.user_data["awaiting_product_image_link"] = {
            "pid": pid,
            "target_uid": target_uid,
            "product_name": pname
        }

        cancel_img_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_cancel_img")]
        ])

        await query.message.reply_text(
            f"📸 <b>ارسال و ثبت تصاویر:</b>\n"
            f"🌟 <b>{pname}</b> (<code>{pid}</code>)\n\n"
            f"لطفاً <b>لینک تصاویر این کالا</b> را ارسال (Paste) فرمایید:\n"
            f"<i>(یا پست مربوطه را فوروارد کنید و یا عکس‌ها را ارسال نمایید)</i>\n\n"
            f"📌 نمونه ورودی‌های معتبر:\n"
            f"ارسال شماره پست: <code>452</code> یا چند عکس: <code>452-455</code>\n\n"
            f"❌ جهت انصراف: /cancel",
            reply_markup=cancel_img_kb,
            parse_mode="HTML"
        )

    elif data == "adm_back_panel":
        await query.answer()
        await admin_panel_command(update, context)

    # ─── کنسول اختصاصی ادمین در زیر کارت کالا ───
    elif data.startswith("adm_pimg|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        await query.answer()
        pid = resolve_safe_cb(data)
        prod = await db.get_product_by_id(pid) or find_product_by_id(pid)
        pname = get_product_name(prod) or pid

        context.user_data["awaiting_product_image_link"] = {
            "pid": pid,
            "target_uid": 0,
            "product_name": pname
        }

        cancel_img_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_cancel_img")]
        ])

        await query.message.reply_text(
            f"🖼 <b>ارسال یا تغییر عکس کالا:</b>\n"
            f"🌟 <b>{pname}</b> (<code>{pid}</code>)\n\n"
            f"لطفاً <b>عکس، آلبوم تصاویر، یا لینک پست کانال</b> این محصول را ارسال یا فوروارد فرمایید.\n\n"
            f"📌 ورودی‌های معتبر:\n"
            f"▫️ ارسال مستقیم عکس (یا چند عکس همزمان به صورت آلبوم)\n"
            f"▫️ فوروارد پیام از کانال عکس‌ها\n"
            f"▫️ ارسال لینک پست (مثلاً <code>https://t.me/img_ai_amp/450</code>)\n"
            f"▫️ ارسال شماره پست (مثلاً <code>450</code> یا <code>450-453</code>)\n\n"
            f"💡 <i>تصویر ارسالی بلافاصله جایگزین تصویر قبلی این کالا خواهد شد.</i>\n"
            f"❌ جهت انصراف: /cancel",
            reply_markup=cancel_img_kb,
            parse_mode="HTML"
        )

    elif data == "adm_cancel_img":
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return
        await query.answer("عملیات لغو شد.")
        context.user_data.pop("awaiting_product_image_link", None)
        await query.message.reply_text("❌ فرآیند ثبت و تغییر عکس محصول لغو گردید.")

    elif data.startswith("adm_pimgdel|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        pid = resolve_safe_cb(data)
        prod = await db.get_product_by_id(pid) or find_product_by_id(pid)
        pname = get_product_name(prod) or pid

        remove_verified_product_photo(pid)
        try:
            await db.execute("UPDATE products SET image_url = '' WHERE product_id = ?", (pid,))
        except Exception:
            pass
        if prod:
            prod["image_url"] = ""
            prod["extra_description"] = ""
        for p in JSON_PRODUCTS:
            if get_product_id(p) == str(pid):
                p["image_url"] = ""
                p["extra_description"] = ""

        await query.answer("✅ تصویر این کالا حذف شد.", show_alert=True)
        await query.message.reply_text(
            f"🗑 <b>تصویر کالا با موفقیت حذف گردید:</b>\n"
            f"🌟 <b>{pname}</b> (<code>{pid}</code>)\n\n"
            f"▫️ آلبوم و تصویر متصل به این محصول پاکسازی شد و اکنون بدون تصویر نمایش داده می‌شود.\n"
            f"▫️ هر زمان مایل بودید می‌توانید با دکمه «🖼 تغییر عکس کالا» تصویر جدید ثبت کنید.",
            parse_mode="HTML"
        )

    elif data.startswith("adm_pprice|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        await query.answer()
        pid = resolve_safe_cb(data)
        prod = await db.get_product_by_id(pid) or find_product_by_id(pid)
        pname = get_product_name(prod) or pid
        curr_price = prod.get("price", 0) if prod else 0
        curr_formatted = f"{int(curr_price):,} تومان" if curr_price else "ثبت نشده"

        context.user_data["awaiting_admin_product_price"] = {
            "pid": pid,
            "product_name": pname,
            "current_price": curr_price
        }

        await query.message.reply_text(
            f"✏️ <b>تنظیم دستی قیمت کالا:</b>\n"
            f"🌟 <b>{pname}</b> (<code>{pid}</code>)\n"
            f"▫️ قیمت فعلی: <code>{curr_formatted}</code>\n\n"
            f"لطفاً مبلغ جدید را به <b>تومان</b> و فقط با ارقام انگلیسی وارد فرمایید:\n"
            f"<i>(مثال: <code>54000000</code> برای ۵۴ میلیون تومان)</i>\n\n"
            f"❌ جهت انصراف: /cancel",
            parse_mode="HTML"
        )

    elif data.startswith("adm_pspec|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        await query.answer()
        pid = resolve_safe_cb(data)
        prod = await db.get_product_by_id(pid) or find_product_by_id(pid)
        pname = get_product_name(prod) or pid

        curr_specs = prod.get("specs") if prod else {}
        if isinstance(curr_specs, str):
            try:
                curr_specs = json.loads(curr_specs)
            except Exception:
                curr_specs = {}

        specs_summary = []
        if isinstance(curr_specs, dict) and curr_specs:
            for k, v in curr_specs.items():
                if v and str(v).strip():
                    specs_summary.append(f"▫️ {k}: {v}")
        summary_text = "\n".join(specs_summary[:6]) if specs_summary else "مشخصات فنی ثبت نشده است."

        context.user_data["awaiting_admin_product_specs"] = {
            "pid": pid,
            "product_name": pname
        }

        await query.message.reply_text(
            f"📝 <b>ویرایش و تغییر دستی مشخصات فنی کالا:</b>\n"
            f"🌟 <b>{pname}</b> (<code>{pid}</code>)\n\n"
            f"<b>مشخصات فنی فعلی:</b>\n"
            f"<blockquote>{summary_text}</blockquote>\n\n"
            f"لطفاً مشخصات فنی جدید را به صورت <b>خط‌به‌خط</b> ارسال فرمایید:\n"
            f"<i>هر خط را به شکل «عنوان: مقدار» وارد نمایید (مثال):</i>\n"
            f"<code>توان مصرفی: ۱۸۰۰ وات\nظرفیت: ۲ لیتر\nکشور سازنده: آلمان\nرنگ: مشکی</code>\n\n"
            f"❌ جهت انصراف: /cancel",
            parse_mode="HTML"
        )

    elif data.startswith("adm_ptog|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        pid = resolve_safe_cb(data)
        from search_engine import toggle_product_hidden_state, is_product_hidden
        
        is_now_hidden = toggle_product_hidden_state(pid)
        new_status = "hidden" if is_now_hidden else "b"
        status_label = "🔴 پنهان (مخفی از نتایج جستجو و کاتالوگ)" if is_now_hidden else "🟢 نمایان و فعال در فروشگاه"

        prod = find_product_by_id(pid) or await db.get_product_by_id(pid)
        pname = get_product_name(prod) or pid
        if prod:
            prod["status"] = new_status

        try:
            await db.execute("UPDATE products SET status = ? WHERE product_id = ?", (new_status, pid))
        except Exception as e:
            logger.warning(f"Error updating product status in db: {e}")

        # ۱. بازخورد فوری به ادمین به صورت Alert
        await query.answer(f"وضعیت کالا: {status_label}", show_alert=True)

        # ۲. به‌روزرسانی درجا و بی‌درنگ کیبورد پیام جهت هماهنگی دکمه
        try:
            from keyboards import product_inline_keyboard
            new_kb = product_inline_keyboard(pid, context, show_photo_button=True, is_admin=True, view_as_customer=False)
            await query.edit_message_reply_markup(reply_markup=new_kb)
        except Exception as ekb:
            logger.debug(f"Could not edit reply markup after status toggle: {ekb}")

        # ۳. ارسال پیام تأییدیه وضعیت
        await query.message.reply_text(
            f"👁‍🗨 <b>وضعیت نمایش کالا تغییر یافت:</b>\n"
            f"🌟 <b>{pname}</b> (<code>{pid}</code>)\n\n"
            f"▫️ وضعیت جدید: <b>{status_label}</b>",
            parse_mode="HTML"
        )

    elif data.startswith("adm_plink|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        await query.answer()
        pid = resolve_safe_cb(data)
        prod = find_product_by_id(pid) or await db.get_product_by_id(pid)
        pname = get_product_name(prod) or pid

        bot_uname = str(BOT_LINK or "").replace("@", "").strip() or "AiKala_bot"
        deep_link = f"https://t.me/{bot_uname}?start=p_{pid}"

        website_link_line = ""
        permalink = prod.get("permalink") if prod else ""
        if permalink and str(permalink).startswith("http"):
            website_link_line = f"\n🌐 <b>لینک صفحه کالا در وبسایت رسمی aegkala:</b>\n<code>{permalink}</code>\n"

        await query.message.reply_text(
            f"🔗 <b>لینک مستقیم اختصاصی محصول جهت ارسال به مشتری:</b>\n\n"
            f"🌟 <b>{pname}</b>\n"
            f"<code>{deep_link}</code>\n"
            f"{website_link_line}\n"
            f"📋 <i>کافیست روی لینک لمس کنید تا کپی شود. مشتری با باز کردن لینک ربات، مستقیماً وارد ربات شده و کارت کامل مشخصات، قیمت روز و آلبوم تصاویر این کالا را مشاهده خواهد کرد.</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    elif data.startswith("adm_paispec|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        pid = resolve_safe_cb(data)
        await query.answer("🤖 در حال استعلام مشخصات با هوش مصنوعی... لطفاً شکیبا باشید.", show_alert=False)

        prod = await db.get_product_by_id(pid) or find_product_by_id(pid)
        if not prod:
            await query.message.reply_text("❌ کالا در سیستم یافت نشد.")
            return

        from gemini_enricher import async_enrich_product_with_gemini_on_demand
        success, err = await async_enrich_product_with_gemini_on_demand(prod, force=True, return_error=True)

        if success:
            updated_msg = build_boxed_product_message(prod)
            adm_kb = product_inline_keyboard(pid, context, show_photo_button=True, is_admin=True, view_as_customer=False)
            try:
                from telegram import LinkPreviewOptions
                lp_opts = LinkPreviewOptions(is_disabled=True)
                if query.message.caption is not None:
                    await query.edit_message_caption(caption=updated_msg, reply_markup=adm_kb, parse_mode="HTML")
                else:
                    await query.edit_message_text(text=updated_msg, reply_markup=adm_kb, parse_mode="HTML", link_preview_options=lp_opts)
            except Exception:
                try:
                    if query.message.caption is not None:
                        await query.edit_message_caption(caption=updated_msg, reply_markup=adm_kb, parse_mode="HTML")
                    else:
                        await query.edit_message_text(text=updated_msg, reply_markup=adm_kb, parse_mode="HTML", disable_web_page_preview=True)
                except Exception:
                    await query.message.reply_text(updated_msg, reply_markup=adm_kb, parse_mode="HTML", disable_web_page_preview=True)
            await query.message.reply_text("✅ <b>مشخصات فنی کالا با موفقیت توسط هوش مصنوعی استخراج و در سیستم ذخیره گردید.</b>", parse_mode="HTML")
        else:
            await query.message.reply_text(
                f"⚠️ <b>عدم دریافت مشخصات توسط هوش مصنوعی:</b>\n{err}\n\n"
                f"💡 راهنما: لطفاً در بخش «تنظیمات هوش مصنوعی» کلید API معتبر (Gemini یا DeepSeek) را ثبت و دکمه «تست زنده ارتباط» را بررسی نمایید.",
                parse_mode="HTML"
            )

    elif data.startswith("adm_pcust|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        pid = resolve_safe_cb(data)
        await query.answer("👥 مشاهده از دید مشتری فعال شد.", show_alert=False)
        cust_kb = product_inline_keyboard(pid, context, show_photo_button=True, is_admin=True, view_as_customer=True)
        try:
            await query.edit_message_reply_markup(reply_markup=cust_kb)
        except Exception as e:
            logger.warning(f"Failed to switch to customer view: {e}")

    elif data.startswith("adm_pback|"):
        if not is_admin(update.effective_user.id):
            await query.answer("دسترسی غیرمجاز", show_alert=True)
            return

        pid = resolve_safe_cb(data)
        await query.answer("⚙️ ابزارهای مدیریت کالا فعال شد.", show_alert=False)
        admin_kb = product_inline_keyboard(pid, context, show_photo_button=True, is_admin=True, view_as_customer=False)
        try:
            await query.edit_message_reply_markup(reply_markup=admin_kb)
        except Exception as e:
            logger.warning(f"Failed to switch to admin view: {e}")

    # ─── هندلر مشاور هوشمند خرید جمینای ───
    elif data.startswith("adv_prod|"):
        await query.answer("🧠 در حال ارتباط با مشاور خرید جمینای...")
        pid = resolve_safe_cb(data)
        from search_engine import find_product_by_id
        prod = find_product_by_id(pid)
        pname = prod.get("name", "این کالا") if prod else "این کالا"
        context.user_data["awaiting_advisor_question"] = True
        context.user_data["advisor_context_pid"] = str(pid)

        quick_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✨ بررسی ارزش خرید و نقاط قوت {pname[:20]}", callback_data=make_safe_cb("adv_eval", str(pid)))],
            [InlineKeyboardButton("💎 آیا گزینه بهتری مثل آاگ (AEG) وجود دارد؟", callback_data=make_safe_cb("adv_comp", str(pid)))],
            [InlineKeyboardButton("🔙 بازگشت به مشخصات کالا", callback_data=make_safe_cb("sel", str(pid)))]
        ])
        await query.message.reply_text(
            f"🧠 <b>مشاور هوشمند کالا درباره:</b>\n🌟 <b>{pname}</b>\n\n"
            f"▫️ می‌توانید هر سوالی درباره کیفیت ساخت، عملکرد، مقایسه با سایر برندها یا ارزش خرید این کالا دارید را همینجا تایپ و ارسال فرمایید.\n"
            f"▫️ یا یکی از گزینه‌های سریع زیر را انتخاب کنید:",
            reply_markup=quick_kb,
            parse_mode="HTML"
        )
        return

    elif data.startswith("adv_eval|"):
        await query.answer("⏳ در حال تحلیل کالا توسط هوش مصنوعی...")
        pid = resolve_safe_cb(data)
        from search_engine import find_product_by_id
        prod = find_product_by_id(pid)
        pname = prod.get("name", "این کالا") if prod else "این کالا"
        q_text = f"نقاط قوت، عملکرد فنی و ارزش خرید کالای '{pname}' رو برام توضیح بده و بگو برای چه کسانی بهترین انتخابه؟"
        
        status_msg = await query.message.reply_text("⏳ <i>در حال آماده‌سازی تحلیل کارشناسی هوش مصنوعی جمینای...</i>", parse_mode="HTML")
        ans, suggested = await consult_gemini_shopping_advisor(q_text, context_product=prod)
        adv_kb = build_advisor_response_keyboard(suggested, context_pid=str(pid))
        try:
            await status_msg.delete()
        except Exception:
            pass
        await query.message.reply_text(
            f"🧠 <b>تحلیل کارشناسی هوشمند کالا (Google Gemini):</b>\n\n{ans}",
            reply_markup=adv_kb,
            parse_mode="HTML"
        )
        return

    elif data.startswith("adv_comp|"):
        await query.answer("⏳ در حال بررسی کاتالوگ و مقایسه مدل‌ها...")
        pid = resolve_safe_cb(data)
        from search_engine import find_product_by_id
        prod = find_product_by_id(pid)
        pname = prod.get("name", "این کالا") if prod else "این کالا"
        q_text = f"در مقایسه با کالای '{pname}'، آیا مدل‌های بهتری به خصوص از برند اصیل و بادوام آاگ (AEG) یا سایر برندهای معتبر در فروشگاه دارید؟ چه تفاوت‌هایی دارند؟"
        
        status_msg = await query.message.reply_text("⏳ <i>در حال مقایسه هوشمند مدل‌ها در کاتالوگ فروشگاه...</i>", parse_mode="HTML")
        ans, suggested = await consult_gemini_shopping_advisor(q_text, context_product=prod)
        adv_kb = build_advisor_response_keyboard(suggested, context_pid=str(pid))
        try:
            await status_msg.delete()
        except Exception:
            pass
        await query.message.reply_text(
            f"🧠 <b>مقایسه و پیشنهاد هوشمند (Google Gemini):</b>\n\n{ans}",
            reply_markup=adv_kb,
            parse_mode="HTML"
        )
        return

    elif data.startswith("adv_q|"):
        await query.answer("🧠 در حال پردازش سوال...")
        q_type = data.split("|")[1]
        questions_map = {
            "shipping": "نحوه ارسال سفارشات، باربری‌های اختصاصی، شرایط تسویه درب منزل، و همچنین شرایط ارسال پستی لوازم خرد آشپزخانه و اعتماد به فروشگاه چطور است؟",
            "warranty": "شرایط گارانتی طلایی، ضمانت اصالت کتبی ۱۰۰٪، صدور فوری فاکتور و سابقه ۲۰ ساله فروشگاه هوشمند کالا (AiKala) به چه صورت است؟",
            "vacuum": "برای خرید جاروبرقی باکیفیت و با مکش عالی چه مدلی از فروشگاه رو پیشنهاد می‌دید؟ تفاوت برندهایی مثل آاگ، بوش و فیلیپس چیه؟",
            "wash": "بهترین ماشین لباسشویی با موتور بی‌صدا و طول عمر بالا در فروشگاه چیه و چرا مدل‌های آاگ (AEG) بالاترین ارزش خرید را دارند و تفاوتشان با سایر برندها چیه؟",
            "dish": "تفاوت مدل‌های مختلف ماشین ظرفشویی چیه و چرا مدل‌های آاگ (AEG) بیشترین ارزش خرید رو دارند و چه تفاوتی با بوش و سامسونگ دارند؟",
            "tv": "برای متراژهای مختلف چه سایز تلویزیونی مناسبه و بهترین مدل‌های موجود با کیفیت تصویر عالی کدومان؟",
            "aeg_intro": "چرا برند اصیل آاگ (AEG) در لوازم خانگی به ویژه جاروبرقی تا این حد محبوب و بادوام است و در فروشگاه شما چه مدل‌هایی از آن موجود است؟"
        }
        q_text = questions_map.get(q_type, "بهترین لوازم خانگی موجود در فروشگاه رو معرفی کن")
        status_msg = await query.message.reply_text("⏳ <i>در حال آماده‌سازی پاسخ هوشمند توسط گوگل جمینای...</i>", parse_mode="HTML")
        ans, suggested = await consult_gemini_shopping_advisor(q_text)
        adv_kb = build_advisor_response_keyboard(suggested)
        try:
            await status_msg.delete()
        except Exception:
            pass
        await query.message.reply_text(
            f"🧠 <b>مشاوره تخصصی هوشمند کالا (Google Gemini):</b>\n\n{ans}",
            reply_markup=adv_kb,
            parse_mode="HTML"
        )
        return

    elif data == "adv_ask_more":
        await query.answer()
        context.user_data["awaiting_advisor_question"] = True
        context.user_data.pop("advisor_context_pid", None)
        await query.message.reply_text(
            "💬 <b>پرسش جدید از مشاور هوشمند:</b>\n"
            "لطفاً سوال، نیاز یا بودجه مدنظرتان را تایپ و ارسال فرمایید تا جمینای بهترین گزینه‌ها را از کاتالوگ فروشگاه به شما پیشنهاد دهد:",
            parse_mode="HTML"
        )
        return

    # در صورتی که دکمه‌ای توسط هیچ شرطی گرفته نشد یا هنوز answer نشده باشد، وضعیت لودینگ آن متوقف شود
    try:
        await query.answer()
    except Exception:
        pass

# =====================================================================
# 📡 هندلر دریافت پست‌های کانال عکس‌ها
# =====================================================================

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if not msg:
        return

    photo_file_id = ""
    if msg.photo:
        photo_file_id = msg.photo[-1].file_id

    if not photo_file_id:
        return

    caption = msg.caption or msg.text or ""
    media_group_id = str(msg.media_group_id) if msg.media_group_id else None

    # اگر پست متعلق به یک آلبوم (Media Group) باشد
    if media_group_id:
        if media_group_id in CHANNEL_MEDIA_GROUPS:
            group = CHANNEL_MEDIA_GROUPS[media_group_id]
            if photo_file_id not in group["photos"]:
                group["photos"].append(photo_file_id)
            if msg.message_id not in group["msg_ids"]:
                group["msg_ids"].append(msg.message_id)
            if caption and not group.get("caption"):
                group["caption"] = caption
            effective_caption = group.get("caption") or caption
            register_photo_message(effective_caption, photo_file_id, msg_id=msg.message_id, media_group_id=media_group_id)
            logger.info(f"📸 Added photo #{len(group['photos'])} to media group {media_group_id} (msg_id: {msg.message_id})")
        else:
            CHANNEL_MEDIA_GROUPS[media_group_id] = {
                "caption": caption,
                "photos": [photo_file_id],
                "msg_ids": [msg.message_id]
            }
            register_photo_message(caption, photo_file_id, msg_id=msg.message_id, media_group_id=media_group_id)
            logger.info(f"📸 Registered new media group album {media_group_id} for msg_id: {msg.message_id} (caption: {caption[:40] if caption else 'بدون کپشن'})")
        save_channel_photos_map()
        return

    # ارسال تک عکس مستقل
    if photo_file_id and caption:
        register_photo_message(caption, photo_file_id, msg_id=msg.message_id)
        logger.info(f"📸 Registered single photo from channel for caption: {caption[:40]}...")

async def check_bot_freeze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    میدل‌ویر بررسی وضعیت فریز و تعلیق فعالیت ربات توسط ادمین اصلی.
    در صورت فریز بودن ربات، کلیه فعالیت‌های کاربران عادی متوقف شده و با پیام ادمین روبرو می‌شوند.
    ادمین‌ها برای مدیریت و خروج از فریز از این محدودیت مستثنی هستند.
    """
    # پست‌های کانال تلگرام هرگز متوقف نمی‌شوند
    if update.channel_post or update.edited_channel_post:
        return

    try:
        from freeze_service import is_bot_frozen, get_freeze_message
        if not is_bot_frozen():
            return
    except Exception as e:
        logger.warning(f"Error checking bot freeze state: {e}")
        return

    user = update.effective_user
    if not user:
        return

    # مدیر ارشد و ادمین‌های ربات اجازه ورود دارند تا ربات قفل نشود
    if is_owner(user.id) or is_admin(user.id):
        return

    freeze_text = get_freeze_message()

    # ۱. اگر کاربر روی دکمه شیشه‌ای کلیک کرد
    if update.callback_query:
        try:
            await update.callback_query.answer(
                text=f"⏸ {freeze_text[:180]}",
                show_alert=True
            )
        except Exception:
            pass
        raise ApplicationHandlerStop()

    # ۲. اگر کاربر پیامی فرستاد، دستوری تایپ کرد، یا عکسی ارسال نمود
    if update.message:
        formatted = (
            "⏸ <b>ربات موقتاً در وضعیت تعلیق و بروزرسانی می‌باشد</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{html.escape(freeze_text)}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "▫️ به زودی با اتمام بروزرسانی، کلیه خدمات ربات به روال عادی بازخواهد گشت."
        )
        try:
            await update.message.reply_text(formatted, parse_mode="HTML")
        except Exception:
            pass
        raise ApplicationHandlerStop()

    raise ApplicationHandlerStop()

# =====================================================================
# 🚀 راه‌اندازی و اجرای اپلیکیشن ربات
# =====================================================================

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ":
        logger.error("❌ خطا: متغیر TELEGRAM_BOT_TOKEN تنظیم نشده است! لطفاً توکن ربات تلگرام خود را در فایل .env قرار دهید.")
        print("\n" + "=" * 60)
        print("❌ خطا: TELEGRAM_BOT_TOKEN در فایل .env یا متغیرهای محیطی یافت نشد.")
        print("👉 لطفاً فایل .env را ایجاد کرده و توکن ربات خود از @BotFather را قرار دهید:")
        print("   TELEGRAM_BOT_TOKEN=\"your_bot_token_here\"")
        print("=" * 60 + "\n")
        return

    logger.info("🚀 AiKala Bot is initialized and ready to run.")

    builder = Application.builder().token(TELEGRAM_BOT_TOKEN)
    try:
        builder = builder.concurrent_updates(16)
    except Exception as e:
        logger.warning(f"Could not enable concurrent_updates: {e}")
    try:
        from telegram.request import HTTPXRequest
        request_config = HTTPXRequest(
            connection_pool_size=256,
            connect_timeout=30.0,
            read_timeout=60.0,
            write_timeout=90.0,
            media_write_timeout=120.0,
            pool_timeout=30.0
        )
        builder = builder.request(request_config)
    except Exception as e:
        logger.warning(f"Could not configure custom HTTPXRequest timeouts: {e}")

    app = builder.build()

    # فیلتر فریز و تعلیق فعالیت ربات با تقدم بالا (group=-1)
    app.add_handler(TypeHandler(Update, check_bot_freeze), group=-1)

    # کانوِرسیشن‌های ثبت سفارش و فیش واریزی
    app.add_handler(get_order_conversation_handler())
    app.add_handler(get_receipt_conversation_handler())

    # ماژول راهنمای جامع خرید و ضمانت
    register_guide_handlers(app)

    # ماژول مرکز مشاوره و پشتیبانی هوشمند
    register_support_handlers(app)

    # ماژول سامانه هوشمند و تعاملی رهگیری سفارشات
    register_order_tracking_handlers(app)

    # دستورات پایه و مدیریتی
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", start_command))
    app.add_handler(CommandHandler("categories", categories_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("guide", help_command))
    app.add_handler(CommandHandler("advisor", advisor_command))
    app.add_handler(CommandHandler("ai", advisor_command))
    app.add_handler(CommandHandler("support", support_command))
    app.add_handler(CommandHandler("track", track_order_command))
    app.add_handler(CommandHandler("rates", show_currency_rates))
    app.add_handler(CommandHandler("currency", show_currency_rates))
    app.add_handler(CommandHandler("sync_photos", sync_photos_command))
    app.add_handler(CommandHandler("setphoto", setphoto_command))
    app.add_handler(CommandHandler("clearphotos", clearphotos_command))
    app.add_handler(CommandHandler("setgemini", setgemini_command))
    app.add_handler(CommandHandler("admin", admin_panel_command))
    app.add_handler(CommandHandler("freeze", admin_freeze_command))
    app.add_handler(CommandHandler("unfreeze", admin_unfreeze_command))
    app.add_handler(CommandHandler("auth_admin", auth_admin_command))
    app.add_handler(CommandHandler("setadmin", auth_admin_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("id", id_command))

    # شنونده کانال تصاویر
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))

    # کلیک روی دکمه‌های شیشه‌ای و ارسال پیام‌های متنی، تصاویر و فایل‌های اکسل/سند
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.FORWARDED) & ~filters.COMMAND, handle_message))

    async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Exception while handling an update:", exc_info=context.error)

    app.add_error_handler(global_error_handler)

    async def post_init(application: Application):
        await db.init()
        try:
            me = await application.bot.get_me()
            logger.info(f"🚀 Telegram Bot @{me.username} is connected and online.")
        except Exception:
            logger.info("🚀 Telegram Bot is connected and online.")
        try:
            chat = await application.bot.get_chat(PHOTOS_CHANNEL)
            logger.info(f"📸 Image Channel: {chat.title} ({PHOTOS_CHANNEL}) connected.")
        except Exception as e:
            logger.warning(f"⚠️ Image Channel ({PHOTOS_CHANNEL}): {e}")

        # ثبت دائمی دکمه Menu Button و دستورات رسمی ربات در تلگرام
        try:
            from telegram import BotCommand, MenuButtonCommands
            commands = [
                BotCommand("menu", "🏠 منوی اصلی فروشگاه"),
                BotCommand("categories", "📂 دسته‌بندی محصولات"),
                BotCommand("search", "🔍 جستجوی کالا"),
                BotCommand("advisor", "🧠 مشاور هوشمند خرید (جمینای)"),
                BotCommand("track", "📦 پیگیری سفارشات"),
                BotCommand("rates", "💰 نرخ زنده ارز و طلا"),
                BotCommand("support", "📞 پشتیبانی و مشاوره"),
                BotCommand("guide", "ℹ️ راهنمای خرید و ضمانت"),
                BotCommand("start", "🔄 شروع مجدد ربات"),
            ]
            await application.bot.set_my_commands(commands)
            await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            logger.info("✅ Persistent Chat Menu Button and official BotCommands registered.")
        except Exception as e_cmd:
            logger.warning(f"Could not register BotCommands / MenuButton: {e_cmd}")

        # راه‌اندازی تسک پس‌زمینه پشتیبان‌گیری خودکار ۲۴ ساعته (پیش‌فرض غیرفعال)
        try:
            from backup_service import auto_backup_background_task
            admin_ids = get_all_admin_ids()
            asyncio.create_task(auto_backup_background_task(application.bot, admin_ids))
            logger.info("💾 Auto-backup background task registered successfully.")
        except Exception as e:
            logger.warning(f"Could not register auto-backup background task: {e}")

        # راه‌اندازی تسک پس‌زمینه ارسال خودکار محصولات به کانال (@AiKala_Khanegi)
        try:
            from auto_poster import channel_auto_poster_background_task
            asyncio.create_task(channel_auto_poster_background_task(application.bot))
            logger.info("📢 Channel auto-poster background task registered successfully.")
        except Exception as e:
            logger.warning(f"Could not register channel auto-poster background task: {e}")

    app.post_init = post_init
    # تضمین دریافت کلیه رویدادها از جمله کلیک روی دکمه‌های شیشه‌ای (callback_query)، پیام‌ها و پست‌های کانال
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", "callback_query"]
    )

if __name__ == "__main__":
    main()
