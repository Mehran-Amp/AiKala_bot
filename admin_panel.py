"""
AiKala - Admin Panel & Photo Management Controller (admin_panel.py)
===================================================================
مدیریت و پایش کانال‌ها، تایید سفارشات و فیش‌ها، آمار فروشگاه
و دریافت هوشمند لینک‌های آلبوم عکس توسط ادمین با محافظت Debounce و وب‌پروبینگ.
"""
import json


import os
import io
import re
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

try:
    import config
except ImportError:
    config = None

ADMIN_IDS = getattr(config, "ADMIN_IDS", [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()] if os.getenv("ADMIN_IDS") else [])
PHOTOS_CHANNEL = getattr(config, "PHOTOS_CHANNEL", getattr(config, "PHOTO_CHANNEL", getattr(config, "IMAGE_CHANNEL", getattr(config, "IMAGES_CHANNEL", os.getenv("PHOTOS_CHANNEL", "@img_ai_amp")))))

from database import Database
from keyboards import (
    is_admin,
    is_owner,
    get_sub_admin_ids,
    get_sub_admins_detailed,
    get_all_admin_ids,
    add_admin_id,
    remove_admin_id,
    OWNER_ID,
    make_safe_cb,
    resolve_safe_cb
)
from search_engine import (
    atomic_save_json,
    find_product_by_id,
    get_product_id,
    get_product_name,
    get_product_brand,
    get_product_category,
    is_laptop_product
)
from sync_prices import get_last_price_sync_str, update_live_prices, get_sync_info_dict
from photo_service import (
    VERIFIED_PRODUCT_PHOTOS,
    PENDING_IMAGE_REQUESTS,
    CHANNEL_POSTS_METADATA,
    CHANNEL_PHOTOS_MAP,
    CHANNEL_MEDIA_GROUPS,
    load_channel_photos_map,
    save_verified_photos,
    save_verified_product_entry,
    find_matching_verified_photos,
    parse_telegram_post_link,
    probe_telegram_channel_album,
    probe_telegram_channel_album_and_caption,
    clean_channel_caption,
    send_verified_photos_to_user
)

logger = logging.getLogger(__name__)
db = Database()

# ─── دستورات پنل مدیریت ───

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """داشبورد اصلی و بهینه‌سازی‌شده مدیریت ربات فروشگاهی هوشمند کالا AiKala_bot"""
    user = update.effective_user
    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text(
                f"⛔️ <b>دسترسی محدود به مدیریت فروشگاه</b>\n\n"
                f"شناسه کاربری شما: <code>{user.id}</code>\n"
                f"جهت دسترسی به پنل مدیریت، این شناسه را در متغیر <code>ADMIN_IDS</code> در سرور اضافه فرمایید.",
                parse_mode="HTML"
            )
        return

    # پاکسازی وضعیت‌های موقت احتمالی ادمین
    context.user_data.pop("awaiting_broadcast_msg", None)

    stats = await db.get_stats()
    total_prods = stats.get('total_products', 0)
    try:
        from search_engine import JSON_PRODUCTS
        if len(JSON_PRODUCTS) > total_prods:
            total_prods = len(JSON_PRODUCTS)
    except Exception:
        pass

    pending_receipts = stats.get('pending_receipts', 0)
    approved_orders = stats.get('approved_orders', 0)
    delivered_orders = stats.get('delivered_orders', 0)
    rejected_orders = stats.get('rejected_orders', 0)
    badge_pending = f" ({pending_receipts} جدید 🔴)" if pending_receipts > 0 else f" ({stats.get('total_orders', 0)})"

    try:
        from category_pdf_service import load_category_products
        laptop_count = len(load_category_products("laptop"))
        audio_count = len(load_category_products("audio"))
    except Exception:
        laptop_count = 0
        audio_count = 0

    badge_laptop = f" ({laptop_count})" if laptop_count > 0 else ""
    badge_audio = f" ({audio_count})" if audio_count > 0 else ""
    agents_count = stats.get('active_support_agents', 0)
    badge_support = f" ({agents_count})" if agents_count > 0 else ""
    channels_count = stats.get('active_channels', 0)
    badge_channels = f" ({channels_count})" if channels_count > 0 else ""

    last_sync_time = get_last_price_sync_str()
    try:
        from sync_catalog import get_last_catalog_sync_str
        last_cat_sync = get_last_catalog_sync_str()
    except Exception:
        last_cat_sync = "در دسترس نیست"

    is_main_owner = is_owner(user.id)
    admin_title = "مدیر ارشد (مالک ربات) 👑" if is_main_owner else "همکار مدیریت فروشگاه"

    try:
        from freeze_service import is_bot_frozen
        is_frozen_active = is_bot_frozen()
    except Exception:
        is_frozen_active = False

    freeze_status_line = (
        "▫️ 🔴 <b>وضعیت فعالیت ربات:</b> <code>متوقف و فریز شده (Pause) ⏸</code>\n"
        if is_frozen_active else
        "▫️ 🟢 <b>وضعیت فعالیت ربات:</b> <code>فعال و در حال سرویس‌دهی ✅</code>\n"
    )

    text = (
        f"⚙️ <b>داشبورد مدیریت ربات فروشگاهی هوشمند کالا @AiKala_bot</b>\n"
        f"👤 <b>سمت:</b> {admin_title} (<code>{user.id}</code>)\n\n"
        f"<blockquote>⏱ <b>آخرین بروزرسانی قیمت‌ها:</b> <code>{last_sync_time}</code>\n"
        f"📦 <b>کاتالوگ و موجودی:</b> <code>{last_cat_sync}</code></blockquote>\n\n"
        f"<blockquote>📊 <b>وضعیت زنده فروشگاه (Live Badges):</b>\n"
        f"{freeze_status_line}"
        f"▫️ کل کالاهای فعال کاتالوگ: <b>{total_prods:,} کالا</b>\n"
        f"▫️ کل سفارشات ثبت‌شده: <b>{stats.get('total_orders', 0)} سفارش</b> (امروز: <b>{stats.get('today_orders', 0)}</b>)\n"
        f"▫️ 🟡 رسیدهای جدید (بررسی‌نشده): <b>{pending_receipts} عدد</b> {f'🔴 اقدام فوری' if pending_receipts > 0 else '✅'}\n"
        f"▫️ 🟢 در حال ارسال: <b>{approved_orders}</b> | 🏁 تحویل شده: <b>{delivered_orders}</b>\n"
        f"▫️ 🔴 رسیدهای رد / لغو شده: <b>{rejected_orders}</b></blockquote>\n\n"
        f"👇 <i>لطفاً بخش مورد نظر خود را انتخاب فرمایید:</i>"
    )

    buttons = [
        # ۱. کاتالوگ‌ها
        [
            InlineKeyboardButton(f"💻 کاتالوگ لپتاپ{badge_laptop}", callback_data="adm_laptop_hub"),
            InlineKeyboardButton(f"🔊 کاتالوگ سیستم صوتی{badge_audio}", callback_data="adm_audio_hub")
        ],

        # ۲. بروزرسانی‌ها
        [
            InlineKeyboardButton("🔄 بروزرسانی قیمت‌ها", callback_data="adm_sync_live_prices"),
            InlineKeyboardButton("📦 بروزرسانی جامع", callback_data="adm_sync_catalog_stock")
        ],

        # ۳. برندهای همکار و گزارش کاتالوگ
        [
            InlineKeyboardButton("⭐️ محصولات آاگ", callback_data="adm_sync_aeg"),
            InlineKeyboardButton("📊 گزارش کاتالوگ", callback_data="adm_catalog_report")
        ],
    ]

    # ۵ الی ۸. ابزارهای مدیریت، پشتیبانی، امنیت و دسترسی‌ها
    if is_main_owner:
        buttons.append([
            InlineKeyboardButton(f"👥 پشتیبانان{badge_support}", callback_data="adm_manage_support"),
            InlineKeyboardButton("📢 پیام همگانی", callback_data="adm_broadcast_ask")
        ])
        buttons.append([
            InlineKeyboardButton("💳 حساب و بیعانه", callback_data="adm_bank_settings"),
            InlineKeyboardButton(f"📡 پایش کانال‌ها{badge_channels}", callback_data="adm_channels")
        ])
        buttons.append([
            InlineKeyboardButton("📢 ارسال خودکار به کانال", callback_data="adm_autoposter"),
            InlineKeyboardButton("🤖 هوش مصنوعی (AI)", callback_data="adm_ai_settings")
        ])
        buttons.append([
            InlineKeyboardButton("💾 Restore / Backup DB", callback_data="adm_backup_menu"),
            InlineKeyboardButton("👥 ادمین‌ها", callback_data="adm_manage_admins")
        ])
        freeze_btn_label = "🔴 ربات فریز است (مدیریت) ⏸" if is_frozen_active else "⏸ فریز و توقف فعالیت ربات"
        buttons.append([
            InlineKeyboardButton(freeze_btn_label, callback_data="adm_freeze_menu")
        ])
        buttons.append([
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("📢 ارسال خودکار به کانال", callback_data="adm_autoposter"),
            InlineKeyboardButton("📢 پیام همگانی", callback_data="adm_broadcast_ask")
        ])
        buttons.append([
            InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")
        ])

    kb = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
            return
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

# ─── ساب‌منوهای اختصاصی و ماژولار پنل ادمین ───

# ─── مرکز جامع مدیریت سفارشات و فیش‌های بانکی با نشانگرهای زنده (Live Badges) ───

async def admin_orders_hub(update: Update, context: ContextTypes.DEFAULT_TYPE, filter_status: str = "all"):
    """
    مرکز جامع و پیشرفته مدیریت سفارشات و رسیدهای بانکی
    تفکیک لحظه‌ای:
    - رسیدهای جدید (بررسی نشده / تایید یا رد نشده)
    - رسیدهای تایید شده (در حال ارسال)
    - رسیدهای رد شده / لغو شده
    - محصولات تحویل داده شده و تسویه شده
    - در انتظار واریز بیعانه
    """
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data.pop("awaiting_order_search", None)

    stats = await db.get_stats()
    pending = stats.get("pending_receipts", 0)
    approved = stats.get("approved_orders", 0)
    rejected = stats.get("rejected_orders", 0)
    delivered = stats.get("delivered_orders", 0)
    awaiting = stats.get("awaiting_payment", 0)
    total = stats.get("total_orders", 0)

    badge_pending = f" ({pending} 🔴)" if pending > 0 else f" ({pending})"
    badge_approved = f" ({approved})"
    badge_rejected = f" ({rejected})"
    badge_delivered = f" ({delivered})"
    badge_awaiting = f" ({awaiting})"
    badge_total = f" ({total})"

    status_meta = {
        "Receipt_Uploaded": {
            "title": "🟡 <b>رسیدهای جدید بانکی (نیاز به تایید یا رد حسابداری)</b>",
            "empty": "✅ در حال حاضر هیچ فیش بررسی‌نشده‌ای وجود ندارد. کلیه فیش‌ها تعیین تکلیف شده‌اند."
        },
        "Approved": {
            "title": "🟢 <b>سفارشات تایید شده (تخصیص به باربری و در حال ارسال)</b>",
            "empty": "📦 در حال حاضر هیچ سفارشی در وضعیت در حال ارسال وجود ندارد."
        },
        "Delivered": {
            "title": "🏁 <b>محصولات تحویل داده شده (تسویه کامل نهایی)</b>",
            "empty": "تا کنون سفارشی با وضعیت تحویل داده شده ثبت نشده است."
        },
        "Rejected": {
            "title": "🔴 <b>رسیدهای رد شده و سفارشات لغو شده</b>",
            "empty": "هیچ سفارش رد شده یا لغو شده‌ای در سیستم ثبت نشده است."
        },
        "Awaiting_Payment": {
            "title": "⏳ <b>سفارشات در انتظار واریز بیعانه مشتری</b>",
            "empty": "هیچ سفارشی در انتظار پرداخت بیعانه وجود ندارد."
        },
        "all_list": {
            "title": "📋 <b>لیست جامع کلیه سفارشات سیستم</b>",
            "empty": "در حال حاضر هیچ سفارشی در سیستم ثبت نشده است."
        }
    }

    if filter_status == "all":
        text = (
            f"📋 <b>مرکز جامع مدیریت سفارشات و فیش‌های بانکی</b>\n\n"
            f"<blockquote>📊 <b>وضعیت زنده سفارشات (Live Badges):</b>\n"
            f"▫️ 🟡 رسیدهای جدید (بررسی‌نشده): <b>{pending} عدد</b> {f'🔴 اقدام فوری' if pending > 0 else '✅ بروز'}\n"
            f"▫️ 🟢 رسیدهای تایید شده (در حال ارسال): <b>{approved} سفارش</b>\n"
            f"▫️ 🏁 محصولات تحویل داده شده: <b>{delivered} سفارش</b>\n"
            f"▫️ 🔴 رسیدهای رد شده / لغو: <b>{rejected} سفارش</b>\n"
            f"▫️ ⏳ در انتظار پرداخت بیعانه: <b>{awaiting} سفارش</b>\n"
            f"▫️ 📦 کل سفارشات ثبت‌شده: <b>{total} سفارش</b></blockquote>\n\n"
            f"👇 <i>بخش مورد نظر خود را جهت مشاهده لیست سفارشات، تایید فیش‌ها یا تغییر وضعیت انتخاب فرمایید:</i>"
        )
        buttons = [
            [
                InlineKeyboardButton(f"🟡 رسیدهای جدید{badge_pending}", callback_data="adm_ord_flt|Receipt_Uploaded"),
                InlineKeyboardButton(f"🟢 تایید شده{badge_approved}", callback_data="adm_ord_flt|Approved")
            ],
            [
                InlineKeyboardButton(f"🏁 تحویل شده{badge_delivered}", callback_data="adm_ord_flt|Delivered"),
                InlineKeyboardButton(f"🔴 رد / لغو شده{badge_rejected}", callback_data="adm_ord_flt|Rejected")
            ],
            [
                InlineKeyboardButton(f"⏳ منتظر بیعانه{badge_awaiting}", callback_data="adm_ord_flt|Awaiting_Payment"),
                InlineKeyboardButton(f"📋 همه سفارشات{badge_total}", callback_data="adm_ord_flt|all_list")
            ],
            [
                InlineKeyboardButton("🔎 جستجوی سفارش", callback_data="adm_search_ord_ask"),
                InlineKeyboardButton("🔄 بروزرسانی زنده", callback_data="adm_manage_orders")
            ],
            [
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data="back_to_main"),
                InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")
            ]
        ]
        kb = InlineKeyboardMarkup(buttons)
    else:
        meta = status_meta.get(filter_status, status_meta["all_list"])
        if filter_status == "all_list":
            orders = await db.get_all_orders(limit=25)
        else:
            orders = await db.get_orders_by_status(filter_status, limit=25)

        if not orders:
            text = (
                f"{meta['title']}\n\n"
                f"<blockquote>{meta['empty']}</blockquote>"
            )
            buttons = [
                [InlineKeyboardButton("🔙 بازگشت به هاب سفارشات", callback_data="adm_manage_orders")],
                [InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="adm_back_panel")]
            ]
            kb = InlineKeyboardMarkup(buttons)
        else:
            text = (
                f"{meta['title']}\n\n"
                f"<blockquote>▫️ تعداد سفارشات در این بخش: <b>{len(orders)} مورد</b>\n"
                f"▫️ جهت بررسی، مشاهده فیش یا تغییر وضعیت روی سفارش کلیک فرمایید.</blockquote>"
            )
            buttons = []
            for o in orders:
                code = o.get("order_code")
                pname = (o.get("product_name") or "کالا")[:16]
                dep = o.get("deposit_amount") or o.get("total_price") or ""
                buyer = (o.get("full_name") or "مشتری")[:12]

                if filter_status == "Receipt_Uploaded":
                    lbl = f"📸 {code} | {buyer} | {dep} ت"
                elif filter_status == "Approved":
                    lbl = f"🚚 {code} | {pname} | {buyer}"
                elif filter_status == "Delivered":
                    lbl = f"✅ {code} | {pname} | {buyer}"
                elif filter_status == "Rejected":
                    lbl = f"❌ {code} | {pname} | {buyer}"
                else:
                    lbl = f"🏷 {code} | {pname} | {dep} ت"
                buttons.append([InlineKeyboardButton(lbl, callback_data=f"adm_view_ord|{code}")])

            buttons.append([
                InlineKeyboardButton("🔄 بروزرسانی این لیست", callback_data=f"adm_ord_flt|{filter_status}"),
                InlineKeyboardButton("🔙 بازگشت به هاب سفارشات", callback_data="adm_manage_orders")
            ])
            buttons.append([InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")])
            kb = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_view_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, order_code: str):
    """نمایش مشخصات تفصیلی سفارش به همراه اقدامات مدیریتی متناسب با وضعیت آن"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    order = await db.get_order_by_code(order_code)
    if not order:
        msg = f"❌ سفارش با کد <code>{order_code}</code> یافت نشد."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به سفارشات", callback_data="adm_manage_orders")]])
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
        elif update.message:
            await update.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
        return

    st = order.get("status", "Awaiting_Payment")
    status_fa = {
        "Awaiting_Payment": ("⏳ در انتظار بیعانه", "🟡"),
        "Receipt_Uploaded": ("📸 فیش ارسال شده (نیازمند تایید یا رد)", "🔴"),
        "Approved": ("🚚 تایید شده / در حال ارسال باربری", "🟢"),
        "Delivered": ("🏁 تسویه کامل و تحویل خریدار شد", "✅"),
        "Rejected": ("❌ فیش رد شده توسط حسابداری", "🔴"),
        "Cancelled": ("🚫 سفارش لغو شده", "⚫️")
    }
    st_title, st_indicator = status_fa.get(st, (st, "⚪️"))

    shipping_method = order.get("shipping_method", "freight")
    ship_label = "📮 پست پیشتاز (تسویه کامل)" if shipping_method == "post" else "🚚 ترابری باربری اختصاصی (پرداخت پس‌کرایه)"

    # فرمت‌بندی مبالغ به تومان با کاما و فونت مونو
    def _fmt_toman(val):
        try:
            cl = re.findall(r'\d+', str(val).replace(",", "").replace("،", ""))
            n = int("".join(cl)) if cl else 0
            return f"{n:,}" if n > 0 else str(val or "۰")
        except Exception:
            return str(val or "۰")

    deposit_str = _fmt_toman(order.get('deposit_amount'))
    total_str = _fmt_toman(order.get('total_price'))
    created_str = str(order.get('created_at', ''))[:16].replace('T', ' ')
    phone2_part = f" (تماس دوم: <code>{order.get('phone2')}</code>)" if order.get('phone2') else ""
    note_part = f"\n📝 <b>یادداشت ادمین:</b> <i>{order.get('admin_note')}</i>" if order.get("admin_note") else ""

    txt = (
        f"📦 <b>جزئیات سفارش <code>{order_code}</code></b> {st_indicator}\n\n"
        f"<blockquote>▫️ <b>وضعیت کنونی:</b> {st_title}\n"
        f"▫️ <b>نام کالا:</b> {order.get('product_name')}\n"
        f"👤 <b>نام خریدار:</b> {order.get('full_name')}\n"
        f"📱 <b>شماره تماس:</b> <code>{order.get('phone1')}</code>{phone2_part}\n"
        f"📍 <b>استان و شهر مقصد:</b> {order.get('province_city')}\n"
        f"🏠 <b>آدرس پستی:</b> {order.get('address')}\n"
        f"📮 <b>کد پستی:</b> <code>{order.get('postal_code') or '-'}</code>\n"
        f"🚚 <b>روش ارسال:</b> {ship_label}\n"
        f"💳 <b>مبلغ بیعانه / پرداختی:</b> <code>{deposit_str} تومان</code>\n"
        f"💵 <b>کل مبلغ فاکتور:</b> <code>{total_str} تومان</code>\n"
        f"📅 <b>تاریخ ثبت:</b> <code>{created_str}</code>{note_part}</blockquote>\n\n"
    )

    buttons = []

    # دکمه‌های اقدام متناسب با وضعیت فعلی
    if st == "Receipt_Uploaded":
        txt += "👇 <i>این فیش هنوز تعیین تکلیف نشده است؛ تایید یا رد فرمایید:</i>"
        buttons.append([
            InlineKeyboardButton("✅ تایید فیش و صدور فاکتور قطعی", callback_data=f"adm_ok|{order_code}"),
            InlineKeyboardButton("❌ رد فیش بانکی", callback_data=f"adm_no|{order_code}")
        ])
        buttons.append([
            InlineKeyboardButton("🚚 تغییر به: در حال ارسال", callback_data=f"adm_set_status|{order_code}|Approved"),
            InlineKeyboardButton("🏁 تغییر به: تحویل کامل", callback_data=f"adm_set_status|{order_code}|Delivered")
        ])
    elif st == "Approved":
        txt += "👇 <i>سفارش تایید شده است؛ تغییر به تحویل داده شده یا لغو:</i>"
        buttons.append([
            InlineKeyboardButton("🏁 تغییر به: تسویه و تحویل خریدار شد", callback_data=f"adm_set_status|{order_code}|Delivered"),
            InlineKeyboardButton("❌ لغو سفارش", callback_data=f"adm_set_status|{order_code}|Cancelled")
        ])
    elif st in ("Rejected", "Cancelled"):
        txt += "👇 <i>این سفارش رد یا لغو شده است؛ در صورت رفع مغایرت امکان تایید مجدد وجود دارد:</i>"
        buttons.append([
            InlineKeyboardButton("✅ بازنگری و تایید فیش بانکی", callback_data=f"adm_ok|{order_code}"),
            InlineKeyboardButton("🚫 لغو قطعی سفارش", callback_data=f"adm_set_status|{order_code}|Cancelled")
        ])
    elif st == "Delivered":
        txt += "✨ <i>این سفارش تسویه کامل شده و به خریدار تحویل گردیده است.</i>"
    elif st == "Awaiting_Payment":
        txt += "👇 <i>در انتظار واریز بیعانه خریدار؛ در صورت واریز حضوری یا کارت به کارت دستی:</i>"
        buttons.append([
            InlineKeyboardButton("✅ تایید دستی واریز بیعانه", callback_data=f"adm_ok|{order_code}"),
            InlineKeyboardButton("❌ لغو سفارش", callback_data=f"adm_set_status|{order_code}|Cancelled")
        ])

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت به هاب سفارشات", callback_data="adm_manage_orders"),
        InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="adm_back_panel")
    ])
    kb = InlineKeyboardMarkup(buttons)

    # ارسال تصویر فیش در صورتی که آپلود شده باشد
    if order.get("receipt_file_id"):
        try:
            chat_id = update.effective_chat.id
            caption = (
                f"📸 <b>تصویر فیش واریزی سفارش <code>{order_code}</code></b>\n\n"
                f"<blockquote>💳 <b>مبلغ پرداختی:</b> <code>{deposit_str} تومان</code>\n"
                f"👤 <b>خریدار:</b> {order.get('full_name')}</blockquote>"
            )
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=order.get("receipt_file_id"),
                caption=caption,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not send receipt photo: {e}")

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


async def admin_order_search_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست ورودی برای جستجوی کد سفارش یا مشخصات مشتری"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["awaiting_order_search"] = True
    txt = (
        "🔍 <b>جستجوی هوشمند در سفارشات و رسیدها</b>\n\n"
        "<blockquote>لطفاً <b>شماره سفارش</b> (مثلاً: <code>12345</code> یا <code>ORD-12345</code>)، <b>شماره موبایل خریدار</b>، "
        "<b>نام مشتری</b> یا <b>نام کالا</b> را ارسال فرمایید:</blockquote>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_manage_orders")]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


async def handle_admin_order_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """پردازش متن ورودی جستجوی سفارش ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return False

    q_text = (update.message.text or "").strip()
    context.user_data.pop("awaiting_order_search", None)

    if not q_text:
        await update.message.reply_text("⚠️ متن جستجو نمی‌تواند خالی باشد.")
        return True

    orders = await db.search_orders(q_text, limit=15)
    if not orders:
        txt = (
            f"❌ <b>نتیجه‌ای یافت نشد!</b>\n\n"
            f"هیچ سفارشی با مشخصات «<code>{q_text}</code>» در سیستم پیدا نشد."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 جستجوی مجدد", callback_data="adm_search_ord_ask")],
            [InlineKeyboardButton("🔙 بازگشت به هاب سفارشات", callback_data="adm_manage_orders")]
        ])
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
        return True

    if len(orders) == 1:
        await admin_view_order_detail(update, context, orders[0].get("order_code"))
        return True

    txt = (
        f"🔍 <b>نتایج جستجو برای: «{q_text}»</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"تعداد {len(orders)} سفارش منطبق یافت شد:\n"
    )
    buttons = []
    for o in orders:
        code = o.get("order_code")
        pname = (o.get("product_name") or "کالا")[:16]
        buyer = (o.get("full_name") or "مشتری")[:12]
        st = o.get("status")
        st_icon = "🟡" if st == "Receipt_Uploaded" else ("🟢" if st == "Approved" else ("🏁" if st == "Delivered" else "🏷"))
        buttons.append([InlineKeyboardButton(f"{st_icon} {code} | {buyer} | {pname}", callback_data=f"adm_view_ord|{code}")])

    buttons.append([InlineKeyboardButton("🔍 جستجوی جدید", callback_data="adm_search_ord_ask")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت به هاب سفارشات", callback_data="adm_manage_orders")])
    kb = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
    return True


async def admin_laptop_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مرکز مدیریت و استخراج قیمت و مشخصات لپ‌تاپ"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    # شمارش تعداد لپ‌تاپ‌های ذخیره شده
    laptop_count = 0
    try:
        from search_engine import JSON_PRODUCTS
        laptop_count = sum(1 for p in JSON_PRODUCTS if is_laptop_product(p))
    except Exception:
        pass

    text = (
        f"💻 <b>مرکز استخراج هوشمند و ثبت کاتالوگ لپ‌تاپ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ تعداد لپ‌تاپ‌های فعال در فروشگاه: <b>{laptop_count} مدل</b>\n"
        f"▫️ موتور استخراج: <b>تحلیل‌گر پیشرفته اکسل + هوش مصنوعی بینایی ماشین</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"روش ورود اطلاعات مورد نظر خود را انتخاب فرمایید:\n"
        f"📊 <b>ارسال فایل اکسل:</b> آپلود فایل جدول (.xlsx / .csv) به صورت مستقیم\n"
        f"📸 <b>ارسال عکس:</b> اسکرین‌شات یا عکس جدول چاپی/دیجیتال"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 دریافت PDF لیست قیمت لپ‌تاپ", callback_data="adm_laptop_download_pdf")],
        [
            InlineKeyboardButton("📊 ارسال فایل اکسل", callback_data="adm_upload_laptop_excel"),
            InlineKeyboardButton("📸 ارسال عکس جدول", callback_data="adm_upload_laptop_photo")
        ],
        [
            InlineKeyboardButton("🗑 پاکسازی لیست", callback_data="adm_clear_laptops_ask"),
            InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")
        ]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_audio_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مرکز مدیریت و کاتالوگ سیستم صوتی، اسپیکر و پارتی‌باکس"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    query = update.callback_query
    if query:
        await query.answer()

    audio_items = []
    try:
        from category_pdf_service import load_category_products
        audio_items = load_category_products("audio")
    except Exception:
        pass

    count_total = len(audio_items)
    brand_counts = {}
    for it in audio_items:
        b = it.get("brand") or "سایر"
        brand_counts[b] = brand_counts.get(b, 0) + 1

    brand_str = " | ".join([f"<b>{b}:</b> {c} مدل" for b, c in sorted(brand_counts.items(), key=lambda x: -x[1])]) if brand_counts else "—"

    text = (
        f"🔊 <b>مرکز کاتالوگ و مدیریت سیستم‌های صوتی (Audio Hub)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ تعداد کل محصولات فعال صوتی: <b>{count_total} مدل</b>\n"
        f"▫️ تفکیک برندها: {brand_str}\n"
        f"▫️ وضعیت ضمانت: ۱۰۰٪ اورجینال شرکتی با مهلت تست صدا و گارانتی\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"عملیات مورد نظر خود را انتخاب فرمایید:\n"
        f"📊 <b>ارسال فایل اکسل / CSV:</b> آپلود لیست جدید به صورت فایل جدول\n"
        f"📥 <b>دریافت فایل CSV / PDF:</b> خروجی کامل جهت ویرایش در اکسل یا اشتراک‌گذاری"
    )

    buttons = [
        [
            InlineKeyboardButton("📥 دریافت فایل اکسل (.csv)", callback_data="adm_audio_download_csv"),
            InlineKeyboardButton("📄 دریافت PDF لیست قیمت", callback_data="adm_audio_download_pdf")
        ],
        [
            InlineKeyboardButton("📊 ارسال فایل اکسل / CSV", callback_data="adm_upload_audio_excel"),
            InlineKeyboardButton("🔄 بازخوانی از فایل محلی", callback_data="adm_audio_reload")
        ],
        [
            InlineKeyboardButton("🗑 پاکسازی لیست صوتی", callback_data="adm_clear_audio_ask"),
            InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")
        ]
    ]

    kb = InlineKeyboardMarkup(buttons)
    if query and query.message:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_upload_audio_excel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای آپلود فایل اکسل یا CSV سیستم صوتی"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["awaiting_audio_excel"] = True
    context.user_data.pop("pending_extracted_audio", None)

    text = (
        "📊 <b>آپلود فایل اکسل / CSV کاتالوگ سیستم صوتی:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "لطفاً فایل اکسل خود با پسوند <b>.xlsx</b> یا <b>.csv</b> را به صورت فایل در همین چت ارسال (Upload) فرمایید.\n\n"
        "✨ <b>امکانات استخراج خودکار جدول سیستم صوتی:</b>\n"
        "▫️ پشتیبانی از تمام شیت‌های اکسل و فایل‌های CSV فارسی/انگلیسی\n"
        "▫️ تشخیص خودکار ستون‌ها: کد، برند (JBL, Sony, Harman Kardon...)، مدل، توان خروجی، مشخصات و قیمت\n"
        "🚫 <b>فیلتر خودکار ستون قیمت همکاری و شماره‌های تماس</b>\n"
        "▫️ امکان ادغام با لیست قبلی یا جایگزینی کامل\n\n"
        "👇 <i>همین حالا فایل را ارسال فرمایید (یا کلمه لغو را بنویسید):</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_audio_hub")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_audio_download_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال مستقیم فایل CSV کاتالوگ سیستم صوتی برای ادمین جهت دانلود و ویرایش در اکسل"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    query = update.callback_query
    chat_id = update.effective_chat.id
    if query:
        await query.answer("📊 در حال تولید فایل CSV کاتالوگ صوتی...")

    try:
        from audio_service import generate_audio_csv_file, load_audio_catalog
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
        csv_path = generate_audio_csv_file("AiKala_Audio_Catalog.csv")
        items = load_audio_catalog()
        caption = (
            f"📊 <b>فایل اکسل / CSV کاتالوگ سیستم‌های صوتی</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 تعداد مدل‌های موجود در فایل: <b>{len(items)} دستگاه</b>\n"
            f"▫️ فرمت: <b>UTF-8 with BOM</b> (سازگار کامل با اکسل و بدون بهم‌ریختگی حروف فارسی)\n"
            f"💡 می‌توانید این فایل را در اکسل ویرایش کرده و مجدداً در بخش «ارسال فایل اکسل / CSV» آپلود فرمایید.\n\n"
            f"https://t.me/Aikala_bot"
        )
        try:
            with open(csv_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename="AiKala_Audio_Catalog.csv",
                    caption=caption,
                    parse_mode="HTML"
                )
        finally:
            if csv_path and os.path.exists(csv_path):
                try:
                    os.remove(csv_path)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error sending audio CSV: {e}")
        if query and query.message:
            await query.message.reply_text(f"❌ خطا در تولید فایل CSV: <code>{e}</code>", parse_mode="HTML")


async def admin_clear_audio_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تاییدیه پاکسازی لیست سیستم‌های صوتی"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    text = (
        "⚠️ <b>هشدار پاکسازی کاتالوگ سیستم صوتی:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "آیا اطمینان دارید که می‌خواهید <b>کلیه مدل‌های سیستم صوتی ثبت‌شده</b> را حذف نمایید؟\n\n"
        "💡 <i>سایر کالاها و لپ‌تاپ‌ها بدون تغییر باقی خواهند ماند.</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 بله، کلیه سیستم‌های صوتی حذف شوند", callback_data="adm_clear_audio_do")],
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_audio_hub")]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_clear_audio_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اجرای پاکسازی فایل سیستم صوتی و بارگذاری مجدد کاتالوگ"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    from audio_service import save_audio_catalog
    from search_engine import load_json_products
    save_audio_catalog([])
    load_json_products()

    text = "✅ <b>لیست سیستم‌های صوتی با موفقیت پاکسازی شد.</b>"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منوی سیستم صوتی", callback_data="adm_audio_hub")],
        [InlineKeyboardButton("🔙 پنل مدیریت", callback_data="adm_back_panel")]
    ])
    if update.callback_query:
        await update.callback_query.answer("لیست صوتی پاکسازی شد", show_alert=True)
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_audio_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """همگام‌سازی و بارگذاری مجدد کاتالوگ صوتی از فایل CSV"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    query = update.callback_query
    if query:
        await query.answer("در حال بارگذاری مجدد کاتالوگ صوتی...", show_alert=False)

    try:
        from audio_service import load_audio_catalog
        from search_engine import load_json_products
        items = load_audio_catalog(force_reload=True)
        load_json_products()
        msg = (
            f"✅ <b>کاتالوگ صوتی با موفقیت بروزرسانی و بازخوانی شد!</b>\n"
            f"▫️ تعداد محصولات فعال صوتی: <b>{len(items)} مدل</b>\n"
            f"▫️ کش موتور جستجوی فروشگاه نیز مجدداً بارگذاری گردید."
        )
    except Exception as e:
        msg = f"❌ خطا در بازخوانی کاتالوگ صوتی: <code>{e}</code>"

    buttons = [
        [InlineKeyboardButton("🔙 بازگشت به منوی سیستم صوتی", callback_data="adm_audio_hub")],
        [InlineKeyboardButton("🔙 پنل مدیریت", callback_data="adm_back_panel")]
    ]
    kb = InlineKeyboardMarkup(buttons)
    if query and query.message:
        try:
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")


async def admin_audio_download_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال مستقیم فایل PDF لیست قیمت سیستم صوتی برای ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    query = update.callback_query
    chat_id = update.effective_chat.id
    if query:
        await query.answer("📄 در حال تولید PDF لیست قیمت سیستم صوتی...")

    try:
        from category_pdf_service import generate_category_pdf, load_category_products
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
        pdf_path = generate_category_pdf("audio", "AiKala_Audio_PriceList.pdf")
        items = load_category_products("audio")
        caption = (
            f"🔊 <b>لیست قیمت رسمی سیستم‌های صوتی و پارتی‌باکس</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 تعداد کل مدل‌های موجود: <b>{len(items)} دستگاه</b>\n"
            f"🛡 <b>ضمانت اصالت:</b> ۱۰۰٪ اورجینال با تضمین کتبی و تست صدا\n"
            f"📅 تاریخ صدور: <code>{datetime.now().strftime('%Y-%m-%d')}</code>\n\n"
            f"تولید شده توسط موتور هوشمند صدور لیست قیمت کالا\n"
            f"https://t.me/Aikala_bot"
        )
        try:
            with open(pdf_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename="AiKala_Audio_PriceList.pdf",
                    caption=caption,
                    parse_mode="HTML"
                )
        finally:
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass
    except Exception as e:
        if query and query.message:
            await query.message.reply_text(f"❌ خطا در تولید فایل PDF: <code>{e}</code>", parse_mode="HTML")


async def admin_laptop_download_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تولید و ارسال فایل PDF لیست قیمت لپ‌تاپ‌ها"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    chat_id = update.effective_chat.id
    query = update.callback_query
    if query:
        await query.answer("📄 در حال تولید PDF لیست قیمت لپ‌تاپ...")

    try:
        from category_pdf_service import generate_category_pdf, load_category_products
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
        pdf_path = generate_category_pdf("laptop", "AiKala_Laptops_PriceList.pdf")
        items = load_category_products("laptop")
        caption = (
            f"💻 <b>لیست قیمت رسمی لپ‌تاپ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 تعداد کل مدل‌های موجود: <b>{len(items)} دستگاه</b>\n"
            f"🛡 <b>ضمانت اصالت:</b> ۱۰۰٪ اورجینال با تضمین کتبی و گارانتی شرکتی\n"
            f"📅 تاریخ صدور: <code>{datetime.now().strftime('%Y-%m-%d')}</code>\n\n"
            f"تولید شده توسط موتور هوشمند صدور لیست قیمت کالا\n"
            f"https://t.me/Aikala_bot"
        )
        try:
            with open(pdf_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename="AiKala_Laptops_PriceList.pdf",
                    caption=caption,
                    parse_mode="HTML"
                )
        finally:
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except Exception:
                    pass
    except Exception as e:
        if query and query.message:
            await query.message.reply_text(f"❌ خطا در تولید فایل PDF: <code>{e}</code>", parse_mode="HTML")


async def admin_upload_laptop_excel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای آپلود مستقیم فایل اکسل کاتالوگ لپ‌تاپ"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["awaiting_laptop_photo"] = True
    context.user_data["awaiting_laptop_excel"] = True
    context.user_data.pop("pending_extracted_laptops", None)

    text = (
        "📊 <b>آپلود فایل اکسل لیست قیمت و موجودی لپ‌تاپ:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "لطفاً فایل اکسل خود با پسوند <b>.xlsx</b> یا <b>.csv</b> را به صورت فایل در همین چت ارسال (Upload) فرمایید.\n\n"
        "✨ <b>قابلیت‌های هوشمند سیستم استخراج اکسل:</b>\n"
        "▫️ پشتیبانی از تمام نسخه‌ها و شیت‌های اکسل (.xlsx و .csv)\n"
        "▫️ تشخیص خودکار ستون‌ها (کد، برند، مدل، پردازنده، رم، هارد، گرافیک، صفحه نمایش، گرید، قیمت)\n"
        "🚫 <b>فیلتر قطعی قیمت همکار</b> (ستون‌های همکاری و عمده به هیچ عنوان ثبت یا نمایش داده نمی‌شوند)\n"
        "🚫 <b>فیلتر خودکار اطلاعات تماس و تبلیغات</b>\n"
        "▫️ پیش‌نمایش سطرهای استخراج‌شده قبل از تایید نهایی و ثبت در فروشگاه\n\n"
        "👇 <i>همین حالا فایل اکسل را ارسال فرمایید (یا برای انصراف کلمه لغو را بفرستید):</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_laptop_hub")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def admin_text_laptop_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای پیست متن جدول قیمت لپ‌تاپ"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["awaiting_laptop_photo"] = True
    context.user_data.pop("pending_extracted_laptops", None)

    text = (
        "📋 <b>استخراج سریع از جدول اکسل یا پیام تلگرام:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>شما می‌توانید مستقیماً خود فایل اکسل (.xlsx / .csv) را در همین چت بفرستید</b> یا متن جدول را کپی و پیست فرمایید.\n\n"
        "✨ <b>قابلیت‌های هوشمند سیستم:</b>\n"
        "▫️ خواندن خودکار فایل‌های اکسل (.xlsx و .csv)\n"
        "▫️ پردازش آنی بدون معطلی\n"
        "🚫 حذف اتوماتیک ستون همکار و تبلیغات متفرقه\n"
        "▫️ دسته‌بندی بر اساس برند (Dell, HP, Lenovo, Asus, Apple و...)\n"
        "▫️ استخراج CPU، RAM، Storage، Graphic و گرید\n\n"
        "❌ <i>جهت انصراف، کلمه <code>لغو</code> را بفرستید.</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 ارسال فایل اکسل (.xlsx / .csv)", callback_data="adm_upload_laptop_excel")],
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_laptop_hub")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def admin_clear_laptops_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تاییدیه پاکسازی لیست لپ‌تاپ‌ها"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    text = (
        "⚠️ <b>هشدار پاکسازی کاتالوگ لپ‌تاپ‌ها:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "آیا اطمینان دارید که می‌خواهید <b>کلیه مدل‌های لپ‌تاپ ثبت‌شده</b> را حذف نمایید؟\n\n"
        "💡 <i>کالاهای لوازم خانگی بدون تغییر باقی خواهند ماند.</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 بله، کلیه لپ‌تاپ‌ها حذف شوند", callback_data="adm_clear_laptops_do")],
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_laptop_hub")]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def admin_clear_laptops_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اجرای پاکسازی فایل لپ‌تاپ‌ها و بارگذاری مجدد کاتالوگ"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    l_file = "laptops_catalog.json"
    if os.path.exists(l_file):
        atomic_save_json(l_file, [], indent=2)

    try:
        from bot import load_json_products
        load_json_products()
    except Exception:
        pass

    text = "✅ <b>لیست لپ‌تاپ‌ها با موفقیت پاکسازی شد.</b>"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منوی لپ‌تاپ", callback_data="adm_laptop_hub")],
        [InlineKeyboardButton("🔙 پنل مدیریت", callback_data="adm_back_panel")]
    ])
    if update.callback_query:
        await update.callback_query.answer("لیست لپ‌تاپ‌ها پاکسازی شد", show_alert=True)
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def admin_sync_live_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اجرای دستی و آنی بروزرسانی قیمت‌ها از ممتازکالا"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    query = update.callback_query
    if query:
        await query.answer("در حال دریافت قیمت‌های زنده...", show_alert=False)
        try:
            await query.edit_message_text(
                "⏳ <b>در حال برقراری ارتباط با سرور ممتازکالا و دریافت آخرین قیمت‌ها...</b>\n"
                "<i>لطفاً چند لحظه شکیبا باشید...</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    success = False
    try:
        success = update_live_prices()
        # اطمینان مضاعف از بارگذاری مجدد کش جستجوی موتور فروشگاه
        if success:
            try:
                from search_engine import load_json_products
                load_json_products()
            except Exception as e_reload:
                logger.warning(f"Note reloading search engine in admin panel: {e_reload}")
    except Exception as e:
        logger.error(f"Error during live sync: {e}")

    sync_info = get_sync_info_dict()
    new_sync_time = sync_info.get("persian_datetime") or get_last_price_sync_str()
    updated_cnt = sync_info.get("updated_count", 0)
    total_cnt = sync_info.get("total_items", 0)

    if success:
        update_detail = f"▫️ تعداد کالاهای بروزرسانی‌شده: <b>{updated_cnt:,} کالا</b>\n" if updated_cnt > 0 else "▫️ کلیه قیمت‌ها از قبل کاملاً منطبق و بروز بودند.\n"
        result_text = (
            f"✅ <b>قیمت‌ها و وضعیت موجودی با موفقیت بروزرسانی شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{update_detail}"
            f"⏱ <b>زمان ثبت آخرین بروزرسانی:</b>\n"
            f"📅 <code>{new_sync_time}</code>\n"
            f"🌐 منبع: <b>داده‌های زنده ممتازکالا ({total_cnt:,} قلم فعال)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ تمامی قیمت‌ها و وضعیت موجودی در دیتابیس، کاتالوگ و حافظه جستجوی زنده ربات بلافاصله اعمال گردید."
        )
    else:
        result_text = (
            f"⚠️ <b>بروزرسانی زنده با خطا مواجه شد.</b>\n"
            f"احتمالاً ارتباط موقت با سرور منبع با تاخیر مواجه شده است.\n"
            f"آخرین زمان معتبر ثبت‌شده: <code>{new_sync_time}</code>"
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تلاش مجدد", callback_data="adm_sync_live_prices")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])

    if query:
        try:
            await query.edit_message_text(result_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(result_text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(result_text, reply_markup=kb, parse_mode="HTML")

async def admin_sync_catalog_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اجرای دستی و آنی بروزرسانی موجودی محصولات و بازسازی درخت دسته‌بندی‌های جدید (معادل کار خودکار هفتگی)"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    query = update.callback_query
    if query:
        await query.answer("در حال شروع بازسازی کاتالوگ و دسته‌بندی‌ها...", show_alert=False)
        try:
            await query.edit_message_text(
                "⏳ <b>در حال استخراج کاتالوگ، بررسی موجودی و بازسازی درخت دسته‌بندی‌های جدید...</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "▫️ بررسی و دریافت ۶ دسته‌بندی اصلی لوازم خانگی\n"
                "▫️ استخراج مشخصات فنی کامل، امتیازات و موجودی دقیق\n"
                "▫️ بازسازی درخت دسته‌بندی‌های پویا در دیتابیس\n"
                "▫️ بروزرسانی آنی حافظه موتور جستجوی هوشمند ربات\n\n"
                "<i>(این فرآیند به صورت خودکار هفته‌ای یک‌بار انجام می‌شود و اجرای کامل آن حدود ۱۰ الی ۱۵ ثانیه زمان می‌برد. لطفاً شکیبا باشید...)</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        from sync_catalog import run_full_catalog_and_category_sync
        res = await asyncio.to_thread(run_full_catalog_and_category_sync)
    except Exception as e:
        res = {"success": False, "error": str(e)}

    if res.get("success"):
        total_p = res.get("total_products", 0)
        dur = res.get("duration_seconds", 0)
        sync_dt = res.get("persian_datetime", "")
        cats_cnt = res.get("categories_count", 6)

        result_text = (
            f"✅ <b>کاتالوگ، موجودی و دسته‌بندی‌های جدید با موفقیت بروزرسانی شدند!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>مجموع کالاهای فعال استخراج‌شده:</b> <b>{total_p:,} کالا</b>\n"
            f"🗂 <b>دسته‌بندی‌های پویا:</b> <b>{cats_cnt} دسته‌بندی اصلی و ده‌ها زیرشاخه</b>\n"
            f"⏱ <b>مدت زمان پردازش:</b> <b>{dur} ثانیه</b>\n"
            f"📅 <b>تاریخ و زمان ثبت:</b> <code>{sync_dt}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <b>اقدامات صورت‌گرفته:</b>\n"
            f"▫️ کاتالوگ و مشخصات فنی ۱۰ ستونه کلیه محصولات نوسازی شد.\n"
            f"▫️ آخرین وضعیت موجودی و استعلام تلفنی تطبیق داده شد.\n"
            f"▫️ درخت دسته‌بندی‌های جدید در دیتابیس ثبت و در منوی کاتالوگ بارگذاری شد.\n"
            f"▫️ حافظه موتور جستجوی زنده ربات بلافاصله رفرش گردید."
        )
    else:
        err_msg = res.get("error", "خطای ارتباطی")
        result_text = (
            f"⚠️ <b>بروزرسانی کاتالوگ و دسته‌بندی‌ها با خطا مواجه شد.</b>\n"
            f"پیام سیستم: <code>{err_msg}</code>\n\n"
            f"▫️ در صورت بروز خطای ارتباطی، اتصال اینترنت سرور را بررسی فرموده و مجدداً تلاش نمایید."
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 بروزرسانی مجدد کاتالوگ و دسته‌ها", callback_data="adm_sync_catalog_stock")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])

    if query:
        try:
            await query.edit_message_text(result_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(result_text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(result_text, reply_markup=kb, parse_mode="HTML")

async def admin_sync_aeg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """همگام‌سازی دستی و آنی محصولات آاگ از سایت aegkala.com"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    query = update.callback_query
    if query:
        await query.answer("در حال اتصال به وب‌سایت مرجع محصولات آاگ (aegkala.com)...", show_alert=False)
        try:
            await query.edit_message_text(
                "⏳ <b>در حال برقراری ارتباط با وب‌سایت رسمی aegkala.com و دریافت کالاهای آاگ...</b>\n"
                "<i>محصولات دارای قیمت در حال استخراج و دسته‌بندی هستند، لطفاً چند لحظه شکیبا باشید...</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        from aeg_service import sync_aeg_products_from_api
        total_raw, total_priced, msg = await asyncio.to_thread(sync_aeg_products_from_api)
        # رفرش کردن کش موتور جستجو
        try:
            from search_engine import load_json_products
            load_json_products()
        except Exception as e_reload:
            logger.warning(f"Error reloading search engine after AEG sync: {e_reload}")

        text = (
            f"⭐️ <b>گزارش همگام‌سازی محصولات آاگ (aegkala.com):</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 کل کالاهای بررسی‌شده در وب‌سایت: <b>{total_raw} محصول</b>\n"
            f"🏷 کالاهای دارای قیمت فعال و معتبر: <b>{total_priced} محصول</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ کلیه کالاهای دارای قیمت در زیرشاخه‌های تخصصی (یخچال، لباسشویی، ظرفشویی، فر و مایکرویو، جاروبرقی) دسته‌بندی شدند و در کاتالوگ و جستجوی هوشمند ربات فعال گردیدند."
        )
    except Exception as e:
        logger.error(f"Error syncing AEG products: {e}")
        text = f"⚠️ <b>خطا در همگام‌سازی با وب‌سایت:</b>\n<code>{html.escape(str(e))}</code>"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بروزرسانی مجدد آاگ", callback_data="adm_sync_aeg")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])

    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def admin_bank_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش و مدیریت مشخصات حساب بانکی، کارت، شبا و درصد بیعانه (فقط ادمین اصلی)"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها برای ادمین اصلی (مالک ربات) مجاز است.", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔️ دسترسی غیرمجاز! این بخش تنها در اختیارات ادمین اصلی می‌باشد.")
        return

    # پاکسازی حالت‌های انتظار ویرایش قبلی
    context.user_data.pop("awaiting_bank_edit_field", None)

    card_num = getattr(config, "CARD_NUMBER", "")
    card_holder = getattr(config, "CARD_HOLDER", "")
    shaba_html = getattr(config, "SHABA_HTML", "")
    deposit_pct = getattr(config, "DEPOSIT_PERCENT", 8)

    card_display = f"<code>{card_num}</code>" if card_num else "<i>(هنوز ثبت نشده است)</i>"
    shaba_display = shaba_html if shaba_html else "<i>(هنوز ثبت نشده است)</i>"
    holder_display = f"<b>{card_holder}</b>" if card_holder else "<i>(هنوز ثبت نشده است)</i>"

    text = (
        f"💳 <b>مدیریت حساب بانکی و بیعانه فروشگاه:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ شماره کارت: {card_display}\n"
        f"▫️ شماره شبا: {shaba_display}\n"
        f"▫️ به نام: {holder_display}\n"
        f"▫️ درصد بیعانه: <b>{deposit_pct}٪ کل مبلغ کالا</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 جهت ثبت یا تغییر هر کدام از موارد، روی دکمه مربوطه کلیک فرمایید:\n"
        f"<i>(تغییرات به صورت آنی در پیش‌فاکتورها، محاسبات مالی و فاکتورهای رسمی ذخیره و اعمال می‌شود)</i>"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ تغییر شماره کارت", callback_data="adm_edit_bank_card"),
            InlineKeyboardButton("✏️ تغییر شماره شبا", callback_data="adm_edit_bank_shaba")
        ],
        [
            InlineKeyboardButton("✏️ تغییر نام دارنده حساب", callback_data="adm_edit_bank_holder"),
            InlineKeyboardButton("✏️ تغییر درصد بیعانه", callback_data="adm_edit_bank_deposit")
        ],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def admin_prompt_bank_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, field_key: str):
    """درخواست ورودی متنی از ادمین برای ویرایش یک مشخصه بانکی"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["awaiting_bank_edit_field"] = field_key

    prompts = {
        "card": (
            "💳 <b>تغییر شماره کارت واریز بیعانه:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"شماره کارت فعلی: <code>{getattr(config, 'CARD_NUMBER', '')}</code>\n\n"
            "لطفاً شماره کارت جدید ۱۶ رقمی را در همین چت ارسال فرمایید:\n"
            "<i>(می‌توانید به صورت پیوسته یا خط تیره ۴ رقم ۴ رقم بفرستید)</i>"
        ),
        "shaba": (
            "🏦 <b>تغییر شماره شبا بانکی:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"شماره شبا فعلی: {getattr(config, 'SHABA_HTML', '')}\n\n"
            "لطفاً شماره شبا ۲۴ رقمی جدید را ارسال فرمایید:\n"
            "<i>(نیازی به نوشتن کلمه IR نیست، سیستم خودکار تنظیم می‌کند)</i>"
        ),
        "holder": (
            "👤 <b>تغییر نام دارنده حساب / کارت:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"نام فعلی: <b>{getattr(config, 'CARD_HOLDER', '')}</b>\n\n"
            "لطفاً نام و نام خانوادگی کامل یا نام تجاری حساب را ارسال فرمایید:"
        ),
        "deposit": (
            "📊 <b>تغییر درصد محاسبه بیعانه سفارشات:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"درصد فعلی: <b>{getattr(config, 'DEPOSIT_PERCENT', 8)}٪</b>\n\n"
            "لطفاً درصد جدید را به صورت یک عدد بین <b>۱ تا ۱۰۰</b> ارسال فرمایید:\n"
            "<i>(مثال: عدد 10 برای ۱۰٪، یا 5 برای ۵٪)</i>"
        )
    }

    prompt_text = prompts.get(field_key, "لطفاً مقدار جدید را ارسال فرمایید:")
    prompt_text += "\n\n❌ <i>جهت انصراف، کلمه <code>لغو</code> را ارسال نمایید.</i>"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_bank_settings")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(prompt_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(prompt_text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(prompt_text, reply_markup=kb, parse_mode="HTML")

async def handle_admin_bank_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دریافت مقدار جدید ارسالی ادمین برای فیلدهای بانکی و ذخیره قطعی آن"""
    field = context.user_data.get("awaiting_bank_edit_field")
    if not field:
        return False

    user = update.effective_user
    if not is_admin(user.id):
        return False

    val = update.message.text.strip() if update.message.text else ""
    if val in ["لغو", "/cancel", "انصراف", "بازگشت"]:
        context.user_data.pop("awaiting_bank_edit_field", None)
        await update.message.reply_text("❌ ویرایش مشخصات بانکی لغو گردید.")
        await admin_bank_settings(update, context)
        return True

    # نرمال‌سازی اعداد فارسی
    from search_engine import _normalize_digits
    val_norm = _normalize_digits(val)

    if field == "card":
        digits = "".join(re.findall(r'\d+', val_norm))
        if len(digits) != 16:
            await update.message.reply_text("⚠️ شماره کارت باید دقیقاً ۱۶ رقم باشد. لطفاً مجدداً شماره معتبر بفرستید یا کلمه «لغو» را ارسال فرمایید:")
            return True
        # قالب‌بندی با خط تیره
        formatted_card = f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"
        config.update_bank_settings(card_number=formatted_card)
        success_msg = f"✅ شماره کارت با موفقیت به <code>{formatted_card}</code> تغییر یافت."

    elif field == "shaba":
        digits = "".join(re.findall(r'\d+', val_norm))
        if len(digits) != 24:
            await update.message.reply_text("⚠️ شماره شبا باید دقیقاً ۲۴ رقم (بدون IR) باشد. لطفاً مجدداً با دقت بفرستید یا کلمه «لغو» را ارسال فرمایید:")
            return True
        new_shaba = f"IR {digits}"
        config.update_bank_settings(card_shaba=new_shaba)
        success_msg = f"✅ شماره شبا با موفقیت به IR <code>{digits}</code> تغییر یافت."

    elif field == "holder":
        if len(val) < 3:
            await update.message.reply_text("⚠️ نام وارد شده بیش از حد کوتاه است. لطفاً نام کامل دارنده حساب را وارد نمایید:")
            return True
        config.update_bank_settings(card_holder=val)
        success_msg = f"✅ نام دارنده حساب با موفقیت به <b>{val}</b> تغییر یافت."

    elif field == "deposit":
        digits = "".join(re.findall(r'\d+', val_norm))
        if not digits or int(digits) < 1 or int(digits) > 100:
            await update.message.reply_text("⚠️ درصد بیعانه باید عددی بین ۱ تا ۱۰۰ باشد (مثلاً 8 یا 10). لطفاً مجدداً ارسال فرمایید:")
            return True
        pct = int(digits)
        config.update_bank_settings(deposit_percent=pct)
        success_msg = f"✅ درصد محاسبه بیعانه با موفقیت به <b>{pct}٪</b> کل فاکتور تغییر یافت."

    else:
        context.user_data.pop("awaiting_bank_edit_field", None)
        return False

    context.user_data.pop("awaiting_bank_edit_field", None)
    await update.message.reply_text(success_msg, parse_mode="HTML")
    await admin_bank_settings(update, context)
    return True

async def admin_catalog_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """گزارش تفکیک‌شده کاتالوگ محصولات"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    home_count = 0
    laptop_count = 0
    aeg_count = 0
    brands = set()
    try:
        from search_engine import JSON_PRODUCTS
        for p in JSON_PRODUCTS:
            if p.get("category_key") == "laptop" or p.get("category_name") == "لپ‌تاپ":
                laptop_count += 1
            elif p.get("category_key") == "aeg" or str(p.get("product_id", "")).startswith("AEG_"):
                aeg_count += 1
            else:
                home_count += 1
            if p.get("brand"):
                brands.add(p.get("brand"))
    except Exception:
        pass

    total = home_count + laptop_count + aeg_count
    last_sync = get_last_price_sync_str()
    try:
        from sync_catalog import get_last_catalog_sync_str
        last_cat_sync = get_last_catalog_sync_str()
    except Exception:
        last_cat_sync = "در دسترس نیست"

    text = (
        f"📊 <b>گزارش و آمار جامع کاتالوگ فروشگاه:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 کل کالاهای موجود در کاتالوگ: <b>{total:,} کالا</b>\n"
        f"🏠 لوازم خانگی اصلی و عمومی: <b>{home_count:,} کالا</b>\n"
        f"⭐️ محصولات اختصاصی آاگ (aegkala.com): <b>{aeg_count} محصول</b>\n"
        f"💻 دسته‌بندی لپ‌تاپ: <b>{laptop_count} مدل</b>\n"
        f"🏷 تعداد برندهای پوشش‌داده‌شده: <b>{len(brands)} برند</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>آخرین بروزرسانی قیمت‌ها:</b> <code>{last_sync}</code>\n"
        f"📦 <b>آخرین بازسازی موجودی و دسته‌ها:</b> <code>{last_cat_sync}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ تمام محصولات قابلیت جستجوی هوشمند متنی و فیلتر بر اساس برند و دسته را دارند."
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 بروزرسانی زنده قیمت‌ها", callback_data="adm_sync_live_prices"),
            InlineKeyboardButton("⭐️ بروزرسانی محصولات آاگ", callback_data="adm_sync_aeg")
        ],
        [
            InlineKeyboardButton("📦 بروزرسانی موجودی و دسته‌ها", callback_data="adm_sync_catalog_stock")
        ],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def admin_broadcast_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست متن پیام همگانی از ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["awaiting_broadcast_msg"] = True

    active_users = await db.get_all_active_user_ids()
    count_users = len(active_users)

    text = (
        f"📢 <b>ارسال پیام همگانی به کاربران ربات:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 تعداد کاربران ثبت‌شده در سیستم: <b>{count_users} کاربر</b>\n\n"
        f"لطفاً متن اطلاعیه، تخفیف یا پیام مورد نظر خود را در همین چت ارسال فرمایید.\n"
        f"<i>(قبل از ارسال قطعی، یک پیش‌نمایش به همراه دکمه تایید نهایی به شما نمایش داده خواهد شد)</i>\n\n"
        f"❌ <i>جهت انصراف، کلمه <code>لغو</code> را ارسال فرمایید.</i>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انصراف و بازگشت به پنل", callback_data="adm_back_panel")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

async def handle_admin_broadcast_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دریافت متن ارسالی ادمین جهت برودکست و نمایش پیش‌نمایش"""
    if not context.user_data.get("awaiting_broadcast_msg"):
        return False

    user = update.effective_user
    if not is_admin(user.id):
        return False

    text = update.message.text.strip() if update.message.text else ""
    if text.startswith("/cancel") or text.lower() == "لغو":
        context.user_data.pop("awaiting_broadcast_msg", None)
        await update.message.reply_text("❌ ارسال پیام همگانی لغو گردید.")
        await admin_panel_command(update, context)
        return True

    context.user_data.pop("awaiting_broadcast_msg", None)
    context.user_data["pending_broadcast_text"] = text

    active_users = await db.get_all_active_user_ids()

    preview = (
        f"📢 <b>پیش‌نمایش پیام همگانی:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 این پیام برای <b>{len(active_users)} کاربر</b> ارسال خواهد شد.\n"
        f"آیا برای ارسال به کلیه کاربران اطمینان دارید؟"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ بله، همین الان ارسال شود", callback_data="adm_broadcast_do"),
            InlineKeyboardButton("❌ لغو", callback_data="adm_back_panel")
        ]
    ])
    await update.message.reply_text(preview, reply_markup=kb, parse_mode="HTML")
    return True

async def admin_broadcast_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال قطعی پیام همگانی به کلیه کاربران"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    text = context.user_data.pop("pending_broadcast_text", None)
    if not text:
        await update.callback_query.answer("پیامی برای ارسال یافت نشد.", show_alert=True)
        await admin_panel_command(update, context)
        return

    query = update.callback_query
    await query.answer("در حال ارسال همگانی...", show_alert=False)
    status_msg = await query.message.reply_text("⏳ <b>در حال ارسال پیام همگانی به کاربران...</b>", parse_mode="HTML")

    active_users = await db.get_all_active_user_ids()
    sent = 0
    failed = 0

    for uid in active_users:
        if uid == user.id:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)  # رعایت محدودیت نرخ تلگرام
        except Exception:
            failed += 1

    report = (
        f"🎉 <b>نتیجه ارسال پیام همگانی:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ ارسال موفق: <b>{sent} کاربر</b>\n"
        f"❌ ناموفق (مسدود یا غیرفعال): <b>{failed} کاربر</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])
    try:
        await status_msg.edit_text(report, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await query.message.reply_text(report, reply_markup=kb, parse_mode="HTML")

async def sync_photos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    load_channel_photos_map()
    total_posts = len(CHANNEL_POSTS_METADATA)
    total_keys = len(CHANNEL_PHOTOS_MAP)
    colors_detected = sum(1 for p in CHANNEL_POSTS_METADATA if p.get("color"))
    
    msg = (
        f"📸 <b>وضعیت گالری تصاویر محصولات:</b>\n\n"
        f"📦 تعداد کل پست‌های ایندکس‌شده: <b>{total_posts}</b>\n"
        f"🎨 پست‌های دارای رنگ تفکیک‌شده: <b>{colors_detected}</b>\n"
        f"🏷 کلیدهای مدل فعال: <b>{total_keys}</b>\n"
        f"📸 تصاویر تایید شده دستی: <b>{len(VERIFIED_PRODUCT_PHOTOS)}</b>\n\n"
        f"✨ سیستم تفکیک رنگ و تنزل هوشمند فعال است."
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode="HTML")
    else:
        await update.message.reply_text(msg, parse_mode="HTML")

async def setphoto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور مدیریت برای اتصال مستقیم و تایید عکس یا آلبوم برای هر کالا"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "📸 <b>راهنمای ثبت دستی تصویر کالا:</b>\n\n"
            "جهت ثبت تصویر یا آلبوم برای هر کالا، دستور را به صورت زیر وارد فرمایید:\n"
            "<code>/setphoto [کد_محصول]</code>\n\n"
            "مثال:\n"
            "<code>/setphoto 68798</code>\n\n"
            "سپس ربات منتظر دریافت عکس، فوروارد از کانال یا ارسال شماره پست می‌ماند.",
            parse_mode="HTML"
        )
        return

    pid = str(args[0]).strip()

    # بررسی نام محصول از کاتالوگ در صورت امکان
    prod = find_product_by_id(pid)
    pname = get_product_name(prod) if prod else f"کالای {pid}"

    context.user_data["awaiting_product_image_link"] = {
        "pid": pid,
        "target_uid": 0,
        "product_name": pname
    }

    await update.message.reply_text(
        f"📸 <b>ثبت تصاویر تایید شده برای محصول:</b>\n"
        f"🌟 <b>{pname}</b> (کد: <code>{pid}</code>)\n\n"
        f"لطفاً همین الان <b>عکس‌ها را ارسال فرمایید</b> یا <b>پست کانال را فوروارد کنید</b> یا <b>شماره پست کانال</b> (مانند <code>452</code>) را بفرستید.\n\n"
        f"❌ جهت انصراف: /cancel",
        parse_mode="HTML"
    )

async def clearphotos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور ادمین برای تایید و پاکسازی کامل لیست عکس‌های تستی"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ بله، تمامی عکس‌ها پاک شوند", callback_data="adm_clear_photos_do")
        ],
        [
            InlineKeyboardButton("🔙 انصراف و بازگشت به پنل", callback_data="adm_back_panel")
        ]
    ])
    msg = (
        "⚠️ <b>هشدار پاکسازی کل تصاویر و کش محصولات:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "آیا مایلید <b>تمامی عکس‌های تستی و آرشیو موجود</b> برای محصولات را حذف نمایید؟\n\n"
        "این عمل موارد زیر را پاکسازی می‌کند:\n"
        "▫️ کلیه تصاویر تایید شده دستی پیشین\n"
        "▫️ کش تصاویر و ارتباطات تستی قبلی\n\n"
        "🎯 <i>پس از پاکسازی، تنها تصاویری که از این به بعد در کانال رسمی عکس قرار دهید یا با دستور <code>/setphoto</code> اضافه کنید، برای محصولات نمایش داده می‌شوند.</i>"
    )
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")

# ─── پردازش ثبت لینک و عکس توسط ادمین ───

async def handle_admin_photo_link_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    req_data = context.user_data.get("awaiting_product_image_link")
    if not req_data:
        return

    pid = str(req_data.get("pid", "")).strip()
    pname = req_data.get("product_name", pid)
    target_uid = req_data.get("target_uid")

    text = update.message.text.strip() if update.message.text else ""
    if text.startswith("/cancel") or text.lower() in ["cancel", "لغو", "انصراف", "/انصراف"]:
        context.user_data.pop("awaiting_product_image_link", None)
        await update.message.reply_text("❌ فرآیند ثبت لینک تصویر لغو گردید.")
        return

    if "collected_msg_ids" not in req_data:
        req_data["collected_msg_ids"] = []
    if "collected_file_ids" not in req_data:
        req_data["collected_file_ids"] = []

    channel = PHOTOS_CHANNEL
    msg_ids = []
    file_ids = []
    post_link = ""
    detected_caption = (update.message.caption or "").strip()

    # ۱. آیا پیام از کانال عکس فوروارد شده است؟
    if getattr(update.message, 'forward_origin', None):
        origin = update.message.forward_origin
        if hasattr(origin, 'chat') and origin.chat:
            ch_uname = origin.chat.username or str(origin.chat.id)
            channel = f"@{ch_uname}" if not ch_uname.startswith("@") and not ch_uname.startswith("-") else ch_uname
        if hasattr(origin, 'message_id'):
            msg_ids.append(origin.message_id)
    elif getattr(update.message, 'forward_from_chat', None):
        f_chat = update.message.forward_from_chat
        ch_uname = f_chat.username or str(f_chat.id)
        channel = f"@{ch_uname}" if not ch_uname.startswith("@") and not ch_uname.startswith("-") else ch_uname
        if getattr(update.message, 'forward_from_message_id', None):
            msg_ids.append(update.message.forward_from_message_id)

    # ۲. آیا عکس مستقیماً در چت ارسال شده است؟
    if update.message.photo:
        file_ids.append(update.message.photo[-1].file_id)

    # ۳. آیا متن ارسال شده حاوی لینک یا شماره پیام است؟
    if text:
        parsed = parse_telegram_post_link(text)
        if parsed:
            ch_parsed, m_ids = parsed
            channel = ch_parsed
            msg_ids.extend(m_ids)
            if "t.me" in text:
                post_link = text
        elif "t.me" in text:
            post_link = text

    req_data["collected_msg_ids"].extend(msg_ids)
    req_data["collected_file_ids"].extend(file_ids)

    # مکانیزم هوشمند Debounce برای جلوگیری از قطعه‌قطعه شدن آلبوم فوروارد شده
    is_multi_candidate = bool(
        getattr(update.message, 'media_group_id', None) or 
        update.message.photo or 
        getattr(update.message, 'forward_origin', None) or 
        getattr(update.message, 'forward_from_chat', None)
    )

    if is_multi_candidate:
        req_data["last_update_time"] = time.time()
        await asyncio.sleep(0.8)
        if time.time() - req_data.get("last_update_time", 0) < 0.75:
            return
        if req_data.get("is_processing"):
            return
        req_data["is_processing"] = True

    final_msg_ids = sorted(list(set(req_data["collected_msg_ids"])))
    final_file_ids = list(dict.fromkeys(req_data["collected_file_ids"]))

    # ۱. تطبیق سریع با آلبوم‌های کش‌شده در CHANNEL_MEDIA_GROUPS
    matched_mg = False
    for mid in list(final_msg_ids):
        mid_str = str(mid)
        for mg_id, g_info in CHANNEL_MEDIA_GROUPS.items():
            g_mids = [str(x) for x in g_info.get("msg_ids", [])]
            if mid_str in g_mids:
                logger.info(f"🎯 [ALBUM MATCH] Found album {mg_id} in CHANNEL_MEDIA_GROUPS for msg {mid}: {g_mids}")
                final_msg_ids = sorted(list(set(final_msg_ids + [int(x) for x in g_mids if str(x).isdigit()])))
                final_file_ids = list(dict.fromkeys(final_file_ids + g_info.get("photos", [])))
                matched_mg = True
                break
        if matched_mg:
            break

    # ۲. تطبیق با متادیتای پست‌های ایندکس‌شده در CHANNEL_POSTS_METADATA
    if not matched_mg:
        for mid in list(final_msg_ids):
            mid_str = str(mid)
            for post in CHANNEL_POSTS_METADATA:
                post_mids = [str(x) for x in post.get("msg_ids", [])]
                if mid_str in post_mids or mid_str in [str(x) for x in post.get("photos", [])]:
                    logger.info(f"🎯 [METADATA MATCH] Found post in CHANNEL_POSTS_METADATA for msg {mid}: {post_mids}")
                    if post_mids:
                        final_msg_ids = sorted(list(set(final_msg_ids + [int(x) for x in post_mids if str(x).isdigit()])))
                    if post.get("photos"):
                        extra_fids = [p for p in post["photos"] if not str(p).isdigit()]
                        final_file_ids = list(dict.fromkeys(final_file_ids + extra_fids))
                    matched_mg = True
                    break
            if matched_mg:
                break

    # ۳. 🌐 پویش قطعی و همه‌جانبه وب ویجت تلگرام (Telegram Public Embed)
    if channel and final_msg_ids and (len(final_file_ids) <= 1 or len(final_msg_ids) <= 1):
        target_mid = final_msg_ids[0]
        ch_clean = str(channel).replace("@", "").strip()
        if not ch_clean.startswith("-"):
            logger.info(f"🌐 [ADMIN INPUT] Probing channel album & caption via public embed for {ch_clean}/{target_mid}...")
            scraped_photos, scraped_mids, scraped_caption = await probe_telegram_channel_album_and_caption(ch_clean, target_mid)
            if scraped_photos:
                logger.info(f"🎉 [ADMIN INPUT] Successfully extracted {len(scraped_photos)} album photos from embed!")
                for sp in scraped_photos:
                    if sp not in final_file_ids:
                        final_file_ids.append(sp)
                for sm in scraped_mids:
                    if sm not in final_msg_ids:
                        final_msg_ids.append(sm)
            if not detected_caption and scraped_caption:
                detected_caption = scraped_caption
                logger.info(f"📝 [ADMIN INPUT] Extracted caption from embed ({len(scraped_caption)} chars)")

    # ۴. پویش تکمیلی از طریق فوروارد با مدیریت ایمن خطا (جهت استخراج تمام عکس‌های آلبوم)
    if channel and final_msg_ids and len(final_file_ids) < max(len(final_msg_ids), 2):
        probed_msgs = []
        try:
            def get_msg_orig_date(msg):
                if getattr(msg, 'forward_origin', None) and hasattr(msg.forward_origin, 'date'):
                    return msg.forward_origin.date
                if getattr(msg, 'forward_date', None):
                    return msg.forward_date
                return None

            # الف) اگر چندین شماره پیام وارد شده باشد (مثلاً رنج 452-455)، عکس تک‌تک آن‌ها استخراج شود
            if len(final_msg_ids) > 1:
                logger.info(f"🔍 Fetching photos for specified message IDs {final_msg_ids} via forward...")
                for mid in final_msg_ids:
                    try:
                        fwd = await context.bot.forward_message(
                            chat_id=update.effective_chat.id,
                            from_chat_id=channel,
                            message_id=mid
                        )
                        probed_msgs.append(fwd.message_id)
                        if not detected_caption and (fwd.caption or fwd.text):
                            detected_caption = (fwd.caption or fwd.text or "").strip()
                        if fwd.photo:
                            tfid = fwd.photo[-1].file_id
                            if tfid not in final_file_ids:
                                final_file_ids.append(tfid)
                    except Exception as ex:
                        logger.debug(f"Could not forward msg {mid}: {ex}")

            # ب) اگر تک‌شماره وارد شده، پیام‌های مجاور (آلبوم چندتایی) پویش شوند
            elif len(final_msg_ids) == 1:
                target_mid = final_msg_ids[0]
                logger.info(f"🔍 Probing sequential album messages in {channel} around message {target_mid} bidirectionally...")
                fwd_target = await context.bot.forward_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=channel,
                    message_id=target_mid
                )
                probed_msgs.append(fwd_target.message_id)
                if not detected_caption and (fwd_target.caption or fwd_target.text):
                    detected_caption = (fwd_target.caption or fwd_target.text or "").strip()

                base_orig_date = get_msg_orig_date(fwd_target)
                base_mg_id = getattr(fwd_target, 'media_group_id', None)

                if fwd_target.photo:
                    tfid = fwd_target.photo[-1].file_id
                    if tfid not in final_file_ids:
                        final_file_ids.append(tfid)

                if fwd_target.photo:
                    # پویش عقب‌گرد پیام‌های قبلی آلبوم (target_mid - 1 تا target_mid - 10)
                    for prev_id in range(target_mid - 1, max(1, target_mid - 10), -1):
                        try:
                            prev_fwd = await context.bot.forward_message(
                                chat_id=update.effective_chat.id,
                                from_chat_id=channel,
                                message_id=prev_id
                            )
                            probed_msgs.append(prev_fwd.message_id)
                            prev_orig_date = get_msg_orig_date(prev_fwd)
                            prev_mg_id = getattr(prev_fwd, 'media_group_id', None)

                            is_album_match = False
                            if base_mg_id and prev_mg_id and base_mg_id == prev_mg_id:
                                is_album_match = True
                            elif prev_fwd.photo and prev_orig_date and base_orig_date and abs((prev_orig_date - base_orig_date).total_seconds()) <= 4:
                                is_album_match = True

                            if prev_fwd.photo and is_album_match:
                                logger.info(f"   ➕ Discovered album photo at previous msg_id {prev_id}")
                                if prev_id not in final_msg_ids:
                                    final_msg_ids.append(prev_id)
                                pfid = prev_fwd.photo[-1].file_id
                                if pfid not in final_file_ids:
                                    final_file_ids.append(pfid)
                            else:
                                break
                        except Exception:
                            break

                    # پویش پیش‌رو پیام‌های بعدی آلبوم (target_mid + 1 تا target_mid + 10)
                    for next_id in range(target_mid + 1, target_mid + 10):
                        try:
                            next_fwd = await context.bot.forward_message(
                                chat_id=update.effective_chat.id,
                                from_chat_id=channel,
                                message_id=next_id
                            )
                            probed_msgs.append(next_fwd.message_id)
                            next_orig_date = get_msg_orig_date(next_fwd)
                            next_mg_id = getattr(next_fwd, 'media_group_id', None)

                            is_album_match = False
                            if base_mg_id and next_mg_id and base_mg_id == next_mg_id:
                                is_album_match = True
                            elif next_fwd.photo and next_orig_date and base_orig_date and abs((next_orig_date - base_orig_date).total_seconds()) <= 4:
                                is_album_match = True

                            if next_fwd.photo and is_album_match:
                                logger.info(f"   ➕ Discovered album photo at next msg_id {next_id}")
                                if next_id not in final_msg_ids:
                                    final_msg_ids.append(next_id)
                                nfid = next_fwd.photo[-1].file_id
                                if nfid not in final_file_ids:
                                    final_file_ids.append(nfid)
                            else:
                                break
                        except Exception:
                            break

        except Exception as e:
            logger.info(f"Forward probe skipped or not supported for channel {channel}: {e}")
        finally:
            for p_mid in probed_msgs:
                try:
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=p_mid)
                except Exception:
                    pass

    if not final_msg_ids and not final_file_ids and not post_link:
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ انصراف و خروج", callback_data="adm_cancel_img")]
        ])
        await update.message.reply_text(
            "⚠️ <b>ورودی نامعتبر است!</b>\n\n"
            "لطفاً شماره پیام را وارد کنید (مثال: <code>452</code> یا رنج: <code>452-455</code>) "
            "یا پست را فوروارد نموده و یا عکس‌ها را مستقیماً ارسال فرمایید.\n\n"
            "❌ جهت انصراف: /cancel یا دکمه زیر:",
            reply_markup=cancel_kb,
            parse_mode="HTML"
        )
        return

    final_msg_ids = sorted(list(set(final_msg_ids)))
    if not post_link and final_msg_ids:
        ch_clean = channel.replace("@", "")
        post_link = f"https://t.me/{ch_clean}/{final_msg_ids[0]}"

    # ذخیره پایدار در کش تایید شده با اطلاعات کامل مدل
    prod_model = ""
    prod_brand = ""
    prod_cat = ""
    prod_obj = find_product_by_id(pid)
    if prod_obj:
        prod_model = str(prod_obj.get("model_number", ""))
        prod_brand = get_product_brand(prod_obj)
        prod_cat = get_product_category(prod_obj)

    clean_caption = clean_channel_caption(detected_caption) if detected_caption else ""
    if prod_obj:
        prod_obj["extra_description"] = clean_caption

    save_verified_product_entry(
        pid=pid,
        product_name=pname,
        channel=channel,
        message_ids=final_msg_ids,
        file_ids=final_file_ids,
        link=post_link,
        model_number=prod_model,
        brand=prod_brand,
        category=prod_cat,
        caption=clean_caption
    )
    context.user_data.pop("awaiting_product_image_link", None)

    # ارسال آنی برای کاربری که دکمه را زده بود و سایر کاربران در انتظار همین کالا
    recipients = set()
    if target_uid and target_uid != 0:
        recipients.add(target_uid)
    for uid in PENDING_IMAGE_REQUESTS.get(pid, []):
        recipients.add(uid)

    # پوشش تفاوت حروف کوچک/بزرگ کد کالا در صف انتظار
    clean_pid_key = str(pid).strip().lower()
    for p_k, u_list in list(PENDING_IMAGE_REQUESTS.items()):
        if str(p_k).strip().lower() == clean_pid_key:
            for u in u_list:
                recipients.add(u)
            PENDING_IMAGE_REQUESTS.pop(p_k, None)

    sent_count = 0
    for uid in recipients:
        try:
            await send_verified_photos_to_user(context.bot, uid, pid, pname)
            sent_count += 1
        except Exception as e:
            logger.error(f"Error sending verified photos to recipient {uid}: {e}")

    PENDING_IMAGE_REQUESTS.pop(pid, None)

    total_photos_detected = len(final_file_ids) if final_file_ids else len(final_msg_ids)
    desc_status = f"📝 <b>توضیحات تکمیلی:</b> {len(clean_caption)} کاراکتر استخراج و به مشخصات فنی کالا پیوست شد.\n" if clean_caption else ""
    await update.message.reply_text(
        f"✅ <b>تصاویر محصول با موفقیت تایید و ثبت شد!</b>\n\n"
        f"📦 <b>محصول:</b> {pname}\n"
        f"🖼 <b>تعداد تصاویر کشف شده آلبوم:</b> {total_photos_detected} عکس\n"
        f"🔗 <b>مرجع تصاویر:</b> <code>{post_link or final_msg_ids}</code>\n"
        f"{desc_status}"
        f"👥 <b>ارسال آنی برای کاربران در انتظار:</b> {sent_count} کاربر\n\n"
        f"✨ <i>از این لحظه، هر کاربری دکمه «📸 تصاویر محصول» این کالا یا مدل‌های مشابه آن را لمس کند، کل آلبوم {total_photos_detected} تایی به صورت خودکار برای او ارسال خواهد شد.</i>",
        parse_mode="HTML"
    )

# ═════════════════════════════════════════════════════════════════════
# 📡 مدیریت پایش خودکار کانال‌ها و ریپوست به @img_ai_amp
# ═════════════════════════════════════════════════════════════════════

async def admin_channel_monitor_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی مدیریت کانال‌های تحت پایش و وضعیت ریپوست به @img_ai_amp (فقط ادمین اصلی)"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها برای ادمین اصلی (مالک ربات) مجاز است.", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔️ دسترسی غیرمجاز! این بخش تنها در اختیارات ادمین اصلی می‌باشد.")
        return

    from channel_monitor import get_target_channels_list, TARGET_IMAGE_CHANNEL, MONITOR_STATUS

    # دریافت لیست کانال‌ها
    channels = await get_target_channels_list()

    # دریافت آمار پست‌های ریپوست شده
    total_reposted = 0
    stats_map = {}
    try:
        from channel_monitor import tracker as _tracker
        total_reposted = _tracker.get_total_count()
        stats_map = _tracker.get_stats()
    except Exception:
        pass

    try:
        _db = Database()
        db_total = await _db.get_channel_reposts_count()
        if db_total > total_reposted:
            total_reposted = db_total
        db_stats = await _db.get_all_repost_stats()
        for k, v in db_stats.items():
            stats_map[k] = max(stats_map.get(k, 0), v)
    except Exception:
        pass

    ch_lines = []
    if channels:
        for idx, ch in enumerate(channels, 1):
            cnt = stats_map.get(ch.lower(), 0)
            ch_lines.append(f"{idx}️⃣ <b>{ch}</b>: <code>{cnt} پست ریپوست‌شده</code>")
    else:
        ch_lines.append("<i>هیچ کانالی در حال حاضر متصل نیست.</i>")

    last_run_str = MONITOR_STATUS.get("last_run") or "در انتظار اولین اجرای شبانه"
    next_run_str = MONITOR_STATUS.get("next_run") or "ساعت ۰۲:۳۰ بامداد (به وقت تهران)"

    text = (
        f"📡 <b>مرکز پایش خودکار کانال‌ها و گالری تصاویر</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>کانال مقصد:</b> <code>{TARGET_IMAGE_CHANNEL}</code>\n"
        f"👑 <b>مالکیت پست‌ها:</b> متعلق به کانال {TARGET_IMAGE_CHANNEL} (امکان ویرایش دستی)\n"
        f"📸 <b>فیلتر محتوا:</b> فقط پست‌های حاوی عکس (تک‌عکس و آلبوم)\n"
        f"💎 <b>حفظ ساختار:</b> نگهداری ۱۰۰٪ متن، کپشن، مشخصات و چیدمان آلبوم\n"
        f"🚫 <b>جلوگیری از تکرار:</b> ممانعت قطعی از انتشار هرگونه پست تکراری\n"
        f"⏱ <b>زمان‌بندی پایش:</b> ۱ بار در ۲۴ ساعت (نصف‌شب بین ۰۲:۰۰ الی ۰۵:۰۰ بامداد به وقت تهران)\n"
        f"🚀 <b>سرعت ربات در طول روز:</b> ۱۰۰٪ آزاد و بدون بار پردازشی (حالت استندبای)\n"
        f"⏳ <b>محدوده بررسی اولیه:</b> ۴ ماه گذشته (۱۲۰ روز)\n"
        f"📊 <b>مجموع پست‌های ریپوست‌شده تاکنون:</b> <b>{total_reposted} پست</b>\n"
        f"🕒 <b>آخرین پویش:</b> {last_run_str}\n"
        f"⏰ <b>پویش بعدی:</b> {next_run_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>کانال‌های تحت پایش فعال:</b>\n" +
        "\n".join(ch_lines)
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ افزودن کانال جدید", callback_data="adm_add_channel"),
            InlineKeyboardButton("🔄 اجرای پایش فوری (۴ ماهه)", callback_data="adm_sync_channels_all")
        ],
        [
            InlineKeyboardButton("🗑 مدیریت و حذف کانال‌ها", callback_data="adm_list_channels_delete")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")
        ]
    ])

    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await (update.callback_query.message if update.callback_query else update.message).reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_add_channel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست نام کاربری یا شناسه کانال جدید از ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["awaiting_channel_add"] = True

    msg = (
        "➕ <b>افزودن کانال جدید به سیستم پایش هوشمند:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "لطفاً آیدی کانال مورد نظر را ارسال فرمایید.\n\n"
        "📌 <b>نمونه‌های معتبر:</b>\n"
        "▫️ <code>@my_channel</code>\n"
        "▫️ <code>https://t.me/my_channel</code>\n"
        "▫️ <code>my_channel</code>\n\n"
        "✨ <i>نکته: به محض ثبت کانال، ربات به طور خودکار پست‌های عکس‌دار ۴ ماه گذشته آن را استخراج و بدون حذف هیچ متنی با مالکیت @img_ai_amp منتشر می‌نماید.</i>\n\n"
        "❌ جهت انصراف: /cancel"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_channels")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(msg, reply_markup=kb, parse_mode="HTML")


async def handle_admin_channel_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دریافت آیدی کانال ارسالی توسط ادمین و آغاز پویش خودکار ۴ ماهه"""
    if not context.user_data.get("awaiting_channel_add"):
        return False

    user = update.effective_user
    if not is_admin(user.id):
        return False

    raw_text = (update.message.text or "").strip()
    if raw_text.startswith("/cancel"):
        context.user_data.pop("awaiting_channel_add", None)
        await update.message.reply_text("❌ افزودن کانال لغو گردید.")
        return True

    from channel_monitor import normalize_channel_username, sync_single_channel, TARGET_IMAGE_CHANNEL
    cid = normalize_channel_username(raw_text)

    if len(cid) < 3 or cid == "@":
        await update.message.reply_text("⚠️ فرمت آیدی کانال نامعتبر است. لطفاً به صورت <code>@username</code> ارسال فرمایید یا دستور /cancel را بزنید.", parse_mode="HTML")
        return True

    context.user_data.pop("awaiting_channel_add", None)

    # ثبت در دیتابیس
    try:
        from channel_monitor import tracker as _tracker
        _tracker.add_channel(cid)
    except Exception:
        pass

    try:
        _db = Database()
        await _db.add_monitored_channel(cid, channel_name=cid)
    except Exception as e:
        logger.error(f"Failed to add channel {cid} to DB: {e}")

    await update.message.reply_text(
        f"✅ <b>کانال <code>{cid}</code> با موفقیت افزوده شد!</b>\n\n"
        f"🚀 <b>پویش و استخراج پست‌های ۴ ماه گذشته آغاز گردید:</b>\n"
        f"▫️ فقط پست‌های حاوی عکس (تک‌عکس و آلبوم)\n"
        f"▫️ بدون حذف هیچ کلمه یا شماره‌ای از کپشن\n"
        f"▫️ انتشار مستقیم با مالکیت اختصاصی کانال <code>{TARGET_IMAGE_CHANNEL}</code>\n"
        f"▫️ بررسی مجدد خودکار: ۱ بار در ۲۴ ساعت (نصف‌شب بین ساعت ۲ الی ۵ بامداد)\n\n"
        f"<i>عملیات در پس‌زمینه در جریان است و نیازی به توقف یا انتظار نیست.</i>",
        parse_mode="HTML"
    )

    # اجرای غیرمسدودکننده در پس‌زمینه
    asyncio.create_task(sync_single_channel(cid, days=120))
    return True


async def admin_sync_channels_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اجرای دستی و آنی همگام‌سازی ۴ ماهه برای تمامی کانال‌ها"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    from channel_monitor import sync_all_monitored_channels, TARGET_IMAGE_CHANNEL

    if update.callback_query:
        await update.callback_query.answer("🚀 پایش و ریپوست ۴ ماهه آغاز شد...", show_alert=False)

    text = (
        f"🚀 <b>عملیات پایش و ریپوست ۴ ماهه آغاز شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 تمام کانال‌های تحت پایش در نوبت بررسی قرار گرفتند.\n"
        f"📸 پست‌های عکس‌دار (آلبوم‌ها و تک‌عکس‌ها) ۴ ماه گذشته استخراج و با مالکیت کامل کانال <code>{TARGET_IMAGE_CHANNEL}</code> ریپوست خواهند شد.\n"
        f"🚫 پست‌های تکراری به صورت هوشمند شناسایی و صرف‌نظر می‌شوند.\n"
        f"⏱ پایش خودکار شبانه: ۱ بار در شبانه‌روز (ساعت ۲ الی ۵ بامداد به وقت تهران)."
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به مرکز پایش کانال‌ها", callback_data="adm_channels")]
    ])

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            # آغاز پویش در پس‌زمینه
            asyncio.create_task(sync_all_monitored_channels(days=120))
            return
        except Exception:
            pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    asyncio.create_task(sync_all_monitored_channels(days=120))


async def admin_list_channels_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست کانال‌ها همراه با امکان حذف"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    from channel_monitor import get_target_channels_list
    channels = await get_target_channels_list()

    buttons = []
    if channels:
        for ch in channels:
            buttons.append([
                InlineKeyboardButton(f"❌ حذف {ch}", callback_data=f"adm_del_ch|{ch}")
            ])

    buttons.append([InlineKeyboardButton("🔙 بازگشت به مرکز پایش", callback_data="adm_channels")])
    kb = InlineKeyboardMarkup(buttons)

    msg = (
        "🗑 <b>مدیریت و حذف کانال‌های تحت پایش:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "جهت حذف هر کانال از پایش خودکار، دکمه حذف مربوط به آن را لمس فرمایید:"
    )

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(msg, reply_markup=kb, parse_mode="HTML")


async def admin_delete_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_to_del: str):
    """حذف کانال از پایش"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    try:
        from channel_monitor import tracker as _tracker
        _tracker.delete_channel(channel_to_del)
    except Exception:
        pass

    try:
        _db = Database()
        await _db.delete_monitored_channel(channel_to_del)
    except Exception as e:
        logger.error(f"Error deleting channel {channel_to_del}: {e}")

    # همچنین از monitor_state.json هم حذف شود
    try:
        from channel_monitor import load_monitor_state, save_monitor_state
        state = load_monitor_state()
        if channel_to_del in state:
            state.pop(channel_to_del, None)
            save_monitor_state(state)
    except Exception:
        pass

    if update.callback_query:
        await update.callback_query.answer(f"✅ کانال {channel_to_del} حذف گردید.", show_alert=True)

    # بازگشت به لیست
    await admin_list_channels_delete(update, context)


async def admin_ai_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی تنظیم و انتخاب موتور هوش مصنوعی برای استخراج مشخصات فنی کالا (فقط ادمین اصلی)"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها برای ادمین اصلی (مالک ربات) مجاز است.", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔️ دسترسی غیرمجاز! این بخش تنها در اختیارات ادمین اصلی می‌باشد.")
        return

    from gemini_enricher import (
        get_ai_settings,
        get_gemini_api_key,
        get_deepseek_api_key,
        get_active_provider_label,
        save_ai_api_key,
        test_ai_connection,
        get_batch_specs_counts,
        get_batch_enrichment_status,
        get_batch_description_counts,
        get_description_batch_status,
        stop_description_batch,
        run_gemini_description_batch
    )

    settings = get_ai_settings()
    active_provider = settings.get("provider", "gemini")

    gemini_key = get_gemini_api_key()
    deepseek_key = get_deepseek_api_key()

    def _mask(k: str) -> str:
        if not k:
            return "⚠️ ثبت‌نشده (فاقد کلید معتبر)"
        if len(k) > 10:
            return f"✅ فعال (<code>{k[:6]}...{k[-4:]}</code>)"
        return "✅ فعال"

    gemini_key_status = _mask(gemini_key)
    deepseek_key_status = _mask(deepseek_key)

    provider_title = get_active_provider_label()

    no_specs_count, under_3_count, total_catalog_count = get_batch_specs_counts()
    no_desc_count, _ = get_batch_description_counts()
    batch_status = get_batch_enrichment_status()
    desc_status = get_description_batch_status()

    batch_running_notice = ""
    if batch_status.get("is_running"):
        b_cur = batch_status.get("current", 0)
        b_tot = batch_status.get("total", 0)
        batch_running_notice = f"⏳ <b>یک عملیات تکمیل مشخصات فنی در حال اجرا است ({b_cur} از {b_tot}).</b>\n\n"
    elif desc_status.get("is_running"):
        d_cur = desc_status.get("current", 0)
        d_tot = desc_status.get("total", 0)
        batch_running_notice = f"✨ <b>یک عملیات تولید توضیحات تکمیلی در حال اجرا است ({d_cur} از {d_tot}).</b>\n\n"

    text = (
        f"🤖 <b>تنظیمات هوش مصنوعی و تکمیل مشخصات/توضیحات:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>نحوه کارکرد سامانه:</b>\n"
        f"استخراج مشخصات و تولید توضیحات هم به‌صورت <b>تقاضامحور (On-Demand)</b> هنگام کلیک روی محصول، و هم به‌صورت <b>تکمیل گروهی خودکار کاتالوگ</b> با گوگل جمینای انجام می‌شود.\n\n"
        f"▫️ <b>موتور فعال پیش‌فرض:</b>\n"
        f"<b>{provider_title}</b>\n\n"
        f"📊 <b>وضعیت کاتالوگ، مشخصات و توضیحات:</b>\n"
        f"▫️ کل کالاهای کاتالوگ: <b>{total_catalog_count} کالا</b>\n"
        f"▫️ کالاهای فاقد مشخصات فنی: <b>{no_specs_count} کالا</b>\n"
        f"▫️ کالاهای با مشخصات ناقص (۳ مورد و کمتر): <b>{under_3_count} کالا</b>\n"
        f"▫️ کالاهای فاقد توضیحات تکمیلی AI: <b>{no_desc_count} کالا</b>\n\n"
        f"{batch_running_notice}"
        f"🔑 <b>وضعیت کلیدهای API هوش مصنوعی:</b>\n"
        f"▫️ کلید جمینای (Gemini): {gemini_key_status}\n"
        f"▫️ کلید دیپ‌سیک (DeepSeek): {deepseek_key_status}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 برای انتخاب موتور، تکمیل مشخصات یا تولید توضیحات تکمیلی با جمینای، دکمه‌های زیر را انتخاب نمایید:"
    )

    btn_gemini = InlineKeyboardButton(
        "✅ گوگل جمینای ♊️ (فعال)" if active_provider == "gemini" else "فعالسازی گوگل جمینای ♊️",
        callback_data="adm_ai_set_gemini"
    )
    btn_deepseek = InlineKeyboardButton(
        "✅ دیپ‌سیک 🤖 (فعال)" if active_provider == "deepseek" else "فعالسازی دیپ‌سیک 🤖",
        callback_data="adm_ai_set_deepseek"
    )
    btn_off = InlineKeyboardButton(
        "✅ هوش مصنوعی خاموش است 🛑" if active_provider in ["off", "disabled"] else "🛑 خاموش کردن هوش مصنوعی",
        callback_data="adm_ai_set_off"
    )

    btn_batch_desc = InlineKeyboardButton(
        "✨ تکمیل توضیحات تکمیلی محصولات",
        callback_data="adm_ai_batch_desc"
    )
    btn_batch_no_specs = InlineKeyboardButton(
        f"⚡️ تکمیل کالاهای بدون مشخصات ({no_specs_count})",
        callback_data="adm_ai_batch_no_specs"
    )
    btn_batch_under_3 = InlineKeyboardButton(
        f"🔍 تکمیل کالاهای ناقص / تا ۳ مشخصه ({under_3_count})",
        callback_data="adm_ai_batch_under_3"
    )

    btn_key_gemini = InlineKeyboardButton("🔑 ثبت / ویرایش کلید Gemini", callback_data="adm_ai_key_gemini")
    btn_key_deepseek = InlineKeyboardButton("🔑 ثبت / ویرایش کلید DeepSeek", callback_data="adm_ai_key_deepseek")
    btn_test_ai = InlineKeyboardButton("🧪 تست زنده ارتباط با هوش مصنوعی", callback_data="adm_ai_test")

    kb_rows = [
        [btn_gemini],
        [btn_deepseek],
        [btn_off],
        [btn_batch_desc],
        [btn_batch_no_specs],
        [btn_batch_under_3]
    ]

    if batch_status.get("is_running"):
        kb_rows.insert(4, [InlineKeyboardButton("⏳ مشاهده وضعیت عملیات مشخصات / توقف", callback_data="adm_ai_batch_status")])
    elif desc_status.get("is_running"):
        kb_rows.insert(4, [InlineKeyboardButton("⏳ مشاهده وضعیت تولید توضیحات / توقف", callback_data="adm_ai_desc_status")])

    kb_rows.extend([
        [btn_key_gemini, btn_key_deepseek],
        [btn_test_ai],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])
    kb = InlineKeyboardMarkup(kb_rows)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_ai_set_provider_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, target_provider: str):
    """مدیریت سوییچ موتور هوش مصنوعی توسط ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    from gemini_enricher import set_ai_provider

    set_ai_provider(target_provider)
    if update.callback_query:
        if target_provider == "gemini":
            msg = "✅ موتور هوش مصنوعی بر روی Google Gemini تنظیم شد."
        elif target_provider == "deepseek":
            msg = "✅ موتور هوش مصنوعی بر روی DeepSeek تنظیم شد."
        else:
            msg = "🛑 استخراج هوش مصنوعی با موفقیت خاموش گردید."
        try:
            await update.callback_query.answer(msg, show_alert=True)
        except Exception:
            pass

    await admin_ai_settings_menu(update, context)


async def admin_ai_key_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, provider: str):
    """درخواست ارسال کلید API جدید از ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    clean_provider = provider.lower().strip()
    provider_title = "Google Gemini (جمینای)" if clean_provider == "gemini" else "DeepSeek (دیپ‌سیک)"

    context.user_data["awaiting_ai_key_provider"] = clean_provider

    text = (
        f"🔑 <b>ثبت / تغییر کلید API برای {provider_title}:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"لطفاً کلید اختصاصی API خود را به عنوان پیام متنی در همین ربات ارسال نمایید.\n\n"
        f"💡 <i>نکته: کلید شما فوراً ذخیره شده و پس از ثبت، سامانه به طور خودکار آماده دریافت مشخصات فنی دقیق محصولات خواهد بود.</i>\n\n"
        f"جهت انصراف روی دکمه زیر کلیک کنید:"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_ai_settings")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def handle_admin_ai_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دریافت و ذخیره‌سازی کلید ارسالی توسط ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return False

    provider = context.user_data.get("awaiting_ai_key_provider")
    if not provider:
        return False

    raw_text = (update.message.text or "").strip()

    if raw_text.lower() in ["انصراف", "لغو", "cancel", "/cancel"]:
        context.user_data.pop("awaiting_ai_key_provider", None)
        await update.message.reply_text("❌ عملیات ثبت کلید API لغو گردید.")
        await admin_ai_settings_menu(update, context)
        return True

    clean_key = raw_text.strip().strip('"').strip("'")
    if len(clean_key) < 15:
        await update.message.reply_text(
            "⚠️ کلید وارد شده بسیار کوتاه به نظر می‌رسد و احتمالاً نامعتبر است.\n"
            "لطفاً کلید معتبر را با دقت کپی کرده و ارسال فرمایید، یا کلمه «انصراف» را ارسال کنید."
        )
        return True

    from gemini_enricher import save_ai_api_key, set_ai_provider

    context.user_data.pop("awaiting_ai_key_provider", None)
    ok = save_ai_api_key(provider, clean_key)

    if ok:
        set_ai_provider(provider)
        provider_name = "Google Gemini" if provider == "gemini" else "DeepSeek"
        await update.message.reply_text(
            f"✅ <b>کلید API با موفقیت ثبت شد!</b>\n\n"
            f"موتور <b>{provider_name}</b> نیز به عنوان ارائه‌دهنده فعال تنظیم گردید.\n"
            f"اکنون می‌توانید از دکمه «تست زنده ارتباط» صحت ارتباط را آزمایش نمایید.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ متأسفانه در ذخیره کلید خطایی رخ داد. لطفاً مجدداً امتحان کنید.")

    await admin_ai_settings_menu(update, context)
    return True


async def admin_ai_test_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تست زنده اتصال به هوش مصنوعی و نمایش نتیجه به ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    if update.callback_query:
        await update.callback_query.answer("در حال تست اتصال به هوش مصنوعی... لطفاً چند ثانیه شکیبا باشید.")

    from gemini_enricher import test_ai_connection, get_active_provider_label

    provider_label = get_active_provider_label()
    wait_msg = None
    if update.callback_query:
        try:
            wait_msg = await update.callback_query.message.reply_text(
                f"⏳ <b>در حال برقراری ارتباط زنده با {provider_label}...</b>\nلطفاً شکیبا باشید.",
                parse_mode="HTML"
            )
        except Exception:
            pass

    success, msg, elapsed = test_ai_connection()

    if wait_msg:
        try:
            await wait_msg.delete()
        except Exception:
            pass

    if success:
        result_text = (
            f"✅ <b>ارتباط با موفقیت برقرار شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{msg}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 هوش مصنوعی آماده دریافت و تکمیل خودکار مشخصات کالاها می‌باشد."
        )
    else:
        result_text = (
            f"❌ <b>خطا در برقراری ارتباط با هوش مصنوعی:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{msg}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 راهنما: لطفاً از دکمه‌های ثبت کلید، کلید API معتبر خود را وارد نمایید."
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تست مجدد", callback_data="adm_ai_test")],
        [InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]
    ])

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(result_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(result_text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(result_text, reply_markup=kb, parse_mode="HTML")


async def admin_ai_batch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """مدیریت فرآیند تکمیل گروهی مشخصات فنی کالاها با هوش مصنوعی گوگل جمینای"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی می‌باشد.", show_alert=True)
        return

    query = update.callback_query
    if query:
        await query.answer()

    from gemini_enricher import (
        get_ai_settings,
        set_ai_provider,
        get_gemini_api_key,
        get_batch_specs_counts,
        get_batch_enrichment_status,
        stop_gemini_batch_enrichment,
        run_gemini_batch_enrichment,
        get_batch_description_counts,
        get_description_batch_status,
        stop_description_batch,
        run_gemini_description_batch
    )

    # ─── توقف عملیات توضیحات تکمیلی ───
    if data == "adm_ai_desc_stop":
        stopped = stop_description_batch()
        if stopped:
            try:
                await query.answer("🛑 دستور توقف تولید توضیحات صادر شد.", show_alert=True)
            except Exception:
                pass
        else:
            try:
                await query.answer("عملیاتی در حال اجرا نیست.", show_alert=True)
            except Exception:
                pass
        return

    # ─── مشاهده وضعیت لحظه‌ای تولید توضیحات ───
    if data == "adm_ai_desc_status":
        d_status = get_description_batch_status()
        if not d_status.get("is_running"):
            await admin_ai_settings_menu(update, context)
            return

        current = d_status.get("current", 0)
        total = d_status.get("total", 0)
        success = d_status.get("success", 0)
        failed = d_status.get("failed", 0)
        pname = d_status.get("current_product", "")
        pct = int((current / total) * 100) if total > 0 else 0

        filled_bars = min(10, pct // 10)
        progress_bar = "▓" * filled_bars + "░" * (10 - filled_bars)

        text = (
            f"✨ <b>وضعیت زنده تولید توضیحات تکمیلی با Google Gemini:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"▫️ صف پردازش: <b>Rate Limit استاندارد (۱۵ درخواست در دقیقه)</b>\n"
            f"▫️ پیشرفت: <b>{current} از {total}</b> ({pct}%)\n"
            f"<code>[{progress_bar}]</code>\n\n"
            f"▫️ کالای در حال پردازش: <code>{pname[:40]}</code>\n"
            f"▫️ ✅ تولید و ثبت موفق: <b>{success}</b> | ⏭ ناموفق: <b>{failed}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"برای توقف عملیات از دکمه زیر استفاده فرمایید:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 توقف عملیات", callback_data="adm_ai_desc_stop")],
            [InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]
        ])
        if query:
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
        return

    # ─── شروع اجرای تولید توضیحات تکمیلی ───
    if data.startswith("adm_ai_run_desc:"):
        mode = data.split(":")[1] if ":" in data else "missing"
        d_status = get_description_batch_status()
        if d_status.get("is_running"):
            try:
                await query.answer("⚠️ عملیات دیگری در حال حاضر در حال اجرا است.", show_alert=True)
            except Exception:
                pass
            return

        start_text = (
            f"🚀 <b>آغاز تولید توضیحات تکمیلی با Google Gemini (نرخ ۱۵ در دقیقه)...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"سیستم در حال ارسال درخواست‌ها و تولید محتوای تخصصی می‌باشد.\n"
            f"نوار پیشرفت تا لحظاتی دیگر در همین پیام نمایش داده خواهد شد..."
        )
        msg = None
        if query:
            try:
                msg = await query.edit_message_text(start_text, parse_mode="HTML")
            except Exception:
                msg = await query.message.reply_text(start_text, parse_mode="HTML")
        elif update.message:
            msg = await update.message.reply_text(start_text, parse_mode="HTML")

        chat_id = update.effective_chat.id
        message_id = msg.message_id if msg else 0

        asyncio.create_task(run_gemini_description_batch(context.bot, chat_id, message_id, only_missing=(mode == "missing")))
        return

    # ─── درخواست اولیه تولید توضیحات تکمیلی (کلیک روی دکمه منو) ───
    if data == "adm_ai_batch_desc":
        gemini_key = get_gemini_api_key()
        if not gemini_key:
            err_text = (
                f"❌ <b>کلید اختصاصی Google Gemini ثبت نشده است!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"تولید خودکار توضیحات تکمیلی کالاها نیازمند کلید معتبر Google Gemini است.\n\n"
                f"💡 لطفاً ابتدا از منوی هوش مصنوعی گزینه «🔑 ثبت / ویرایش کلید Gemini» را انتخاب کرده و کلید خود را وارد نمایید."
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 ثبت کلید Gemini", callback_data="adm_ai_key_gemini")],
                [InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]
            ])
            if query:
                try:
                    await query.edit_message_text(err_text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass
            return

        d_status = get_description_batch_status()
        if d_status.get("is_running"):
            try:
                await query.answer("⚠️ عملیات تولید توضیحات تکمیلی در حال اجرا است.", show_alert=True)
            except Exception:
                pass
            return

        no_desc_cnt, total_cnt = get_batch_description_counts()

        confirm_desc_text = (
            f"✨ <b>تایید شروع تکمیل توضیحات تکمیلی محصولات با Google Gemini</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"▫️ کل محصولات کاتالوگ: <b>{total_cnt} کالا</b>\n"
            f"▫️ کالاهای فاقد توضیحات تکمیلی: <b>{no_desc_cnt} کالا</b>\n"
            f"▫️ موتور هوش مصنوعی: <b>Google Gemini (Gemini Flash ♊️)</b>\n"
            f"▫️ صف پردازش ایمن: <b>Rate Limit کنترل‌شده (۱۵ درخواست در دقیقه)</b>\n"
            f"▫️ ذخیره‌سازی: <b>فیلد اختصاصی <code>ai_generated_description</code></b>\n"
            f"▫️ نحوه نمایش در تلگرام: <b>کشویی با تگ <code>&lt;blockquote expandable&gt;</code> و خطوط مجزا</b>\n\n"
            f"💡 <i>سایر بخش‌های کارت کالا (مشخصات، گارانتی، قیمت و اشتراک) همواره باز باقی می‌مانند.</i>\n\n"
            f"لطفاً نحوه اجرای عملیات را انتخاب فرمایید:"
        )

        rows = []
        if no_desc_cnt > 0:
            rows.append([InlineKeyboardButton(f"⚡️ فقط کالاهای فاقد توضیحات ({no_desc_cnt})", callback_data="adm_ai_run_desc:missing")])
        rows.append([InlineKeyboardButton("🚀 تولید و جایگزینی برای تمام کالاها", callback_data="adm_ai_run_desc:all")])
        rows.append([InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_ai_settings")])

        if query:
            try:
                await query.edit_message_text(confirm_desc_text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
            except Exception:
                pass
        return

    # ۱. درخواست توقف عملیات جاری
    if data == "adm_ai_batch_stop":
        stopped = stop_gemini_batch_enrichment()
        if stopped:
            try:
                await query.answer("🛑 دستور توقف صادر شد. فرآیند به زودی متوقف می‌شود.", show_alert=True)
            except Exception:
                pass
        else:
            try:
                await query.answer("عملیاتی در حال اجرا نیست.", show_alert=True)
            except Exception:
                pass
        return

    # ۲. مشاهده وضعیت لحظه‌ای عملیات
    if data == "adm_ai_batch_status":
        status = get_batch_enrichment_status()
        if not status.get("is_running"):
            await admin_ai_settings_menu(update, context)
            return

        mode_title = (
            "کالاهای کاملاً فاقد مشخصات"
            if status.get("mode") == "no_specs"
            else "کالاهای با مشخصات ناقص (۳ مشخصه و کمتر)"
        )
        current = status.get("current", 0)
        total = status.get("total", 0)
        success = status.get("success", 0)
        failed = status.get("failed", 0)
        pname = status.get("current_product", "")
        pct = int((current / total) * 100) if total > 0 else 0

        text = (
            f"⚙️ <b>وضعیت زنده عملیات تکمیل مشخصات فنی:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"▫️ حالت: <b>{mode_title}</b>\n"
            f"▫️ پیشرفت: <b>{current} از {total}</b> ({pct}%)\n"
            f"▫️ کالای در حال پردازش: <code>{pname[:40]}</code>\n"
            f"▫️ ✅ ثبت موفق: <b>{success}</b> | ⏭ نامشخص: <b>{failed}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"برای توقف عملیات از دکمه زیر استفاده فرمایید:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 توقف عملیات", callback_data="adm_ai_batch_stop")],
            [InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]
        ])
        if query:
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
        return

    # ۳. شروع اجرای عملیات پس از تایید توسط ادمین
    if data.startswith("adm_ai_run_batch:"):
        parts = data.split(":")
        mode = parts[1] if len(parts) > 1 else "no_specs"
        action = parts[2] if len(parts) > 2 else "start"

        status = get_batch_enrichment_status()
        if status.get("is_running"):
            try:
                await query.answer("⚠️ یک فرآیند دیگر در حال حاضر در حال اجرا است.", show_alert=True)
            except Exception:
                pass
            return

        if action == "switch_default":
            set_ai_provider("gemini")

        start_text = (
            f"🚀 <b>آغاز فرآیند استخراج و تکمیل مشخصات با Google Gemini...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"سیستم در حال آماده‌سازی اقلام و برقراری ارتباط با مدل هوش مصنوعی می‌باشد.\n"
            f"گزارش پیشرفت زنده تا لحظاتی دیگر در همین پیام نمایش داده خواهد شد..."
        )
        msg = None
        if query:
            try:
                msg = await query.edit_message_text(start_text, parse_mode="HTML")
            except Exception:
                msg = await query.message.reply_text(start_text, parse_mode="HTML")
        elif update.message:
            msg = await update.message.reply_text(start_text, parse_mode="HTML")

        chat_id = update.effective_chat.id
        message_id = msg.message_id if msg else 0

        asyncio.create_task(run_gemini_batch_enrichment(mode, context.bot, chat_id, message_id))
        return

    # ۴. درخواست اولیه تکمیل (کلیک روی یکی از دکمه‌های منو)
    mode = "no_specs" if data == "adm_ai_batch_no_specs" else "under_3"
    mode_title = (
        "کالاهای کاملاً فاقد مشخصات فنی (۰ مشخصه)"
        if mode == "no_specs"
        else "کالاهای با مشخصات ناقص (۳ مشخصه و کمتر)"
    )

    # الف) بررسی وجود کلید API جمینای
    gemini_key = get_gemini_api_key()
    if not gemini_key:
        err_text = (
            f"❌ <b>کلید اختصاصی Google Gemini ثبت نشده است!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"عملیات استخراج و تکمیل گروهی مشخصات کالاها منحصراً با <b>Google Gemini</b> انجام می‌شود و نیازمند کلید معتبر است.\n\n"
            f"💡 لطفاً ابتدا از منوی هوش مصنوعی گزینه «🔑 ثبت / ویرایش کلید Gemini» را انتخاب کرده و کلید خود را وارد نمایید."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 ثبت کلید Gemini", callback_data="adm_ai_key_gemini")],
            [InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]
        ])
        if query:
            try:
                await query.edit_message_text(err_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
        return

    # ب) بررسی اینکه آیا عملیاتی در حال حاضر در حال اجرا است
    status = get_batch_enrichment_status()
    if status.get("is_running"):
        try:
            await query.answer("⚠️ یک فرآیند تکمیل مشخصات در حال حاضر در حال اجرا است.", show_alert=True)
        except Exception:
            pass
        return

    no_specs_cnt, under_3_cnt, total_cnt = get_batch_specs_counts()
    target_count = no_specs_cnt if mode == "no_specs" else under_3_cnt

    if target_count == 0:
        empty_text = (
            f"🎉 <b>تمامی کالاهای کاتالوگ دارای مشخصات کامل هستند!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"▫️ دسته بررسی: <b>{mode_title}</b>\n"
            f"▫️ هیچ کالایی نیازمند تکمیل مشخصات نیست."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به تنظیمات هوش مصنوعی", callback_data="adm_ai_settings")]
        ])
        if query:
            try:
                await query.edit_message_text(empty_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
        return

    # ج) بررسی موتور پیش‌فرض هوش مصنوعی (در صورت انتخاب دیپ‌سیک یا خاموش بودن، هشدار داده می‌شود)
    settings = get_ai_settings()
    active_provider = settings.get("provider", "gemini")

    if active_provider != "gemini":
        provider_name = "دیپ‌سیک (DeepSeek) 🤖" if active_provider == "deepseek" else "خاموش 🛑"
        warn_text = (
            f"⚠️ <b>هشدار انتخاب موتور هوش مصنوعی</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"قابلیت تکمیل گروهی مشخصات به دلیل سرعت پردازش بالا، تطابق قطعی با دیتاشیت‌های کاتالوگ و جلوگیری سخت‌گیرانه از اطلاعات نادرست، <b>منحصراً توسط Google Gemini</b> انجام می‌شود.\n\n"
            f"▫️ موتور فعال فعلی ربات: <b>{provider_name}</b>\n"
            f"▫️ حالت انتخابی: <b>{mode_title}</b>\n"
            f"▫️ تعداد اقلام واجد شرایط: <b>{target_count} کالا</b>\n\n"
            f"لطفاً نحوه ادامه عملیات را مشخص فرمایید:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تغییر پیش‌فرض به جمینای و شروع", callback_data=f"adm_ai_run_batch:{mode}:switch_default")],
            [InlineKeyboardButton("⚡️ ادامه با جمینای (بدون تغییر پیش‌فرض)", callback_data=f"adm_ai_run_batch:{mode}:keep_default")],
            [InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_ai_settings")]
        ])
        if query:
            try:
                await query.edit_message_text(warn_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
        return

    # د) در صورت فعال بودن جمینای، نمایش صفحه تایید نهایی
    confirm_text = (
        f"⚡️ <b>تایید شروع تکمیل خودکار مشخصات فنی با Google Gemini</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ حالت انتخابی: <b>{mode_title}</b>\n"
        f"▫️ تعداد کالاهای واجد شرایط: <b>{target_count} کالا</b> (از کل {total_cnt})\n"
        f"▫️ موتور هوش مصنوعی: <b>گوگل جمینای (Gemini Flash ♊️)</b>\n\n"
        f"⚠️ <b>استانداردها و الزامات فنی:</b>\n"
        f"۱. مشخصات فنی ۱۰۰٪ مستند و منحصراً بر اساس کد مدل دقیق کارخانه استخراج می‌شوند تا هیچ اطلاعات اشتباهی به مشتری داده نشود.\n"
        f"۲. هرگونه رنگ یا تنوع رنگی محصول به‌طور کامل حذف می‌گردد.\n"
        f"۳. مقادیر دارای واحدهای رسمی (وات، لیتر، هرتز، کیلوگرم، نوع موتور و...) هستند.\n"
        f"۴. مشخصات جدید پس از استخراج، به‌صورت دائمی در کاتالوگ و پایگاه داده ثبت خواهند شد.\n\n"
        f"آیا برای آغاز عملیات اطمینان دارید؟"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 شروع عملیات تکمیل مشخصات", callback_data=f"adm_ai_run_batch:{mode}:start")],
        [InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_ai_settings")]
    ])
    if query:
        try:
            await query.edit_message_text(confirm_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass


# =====================================================================
# 💾 منوی اختصاصی پشتیبان‌گیری و بازگردانی (Backup & Restore)
# =====================================================================

async def admin_backup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی پشتیبان‌گیری و بازگردانی اطلاعات سیستم (فقط ادمین اصلی)"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها برای ادمین اصلی (مالک ربات) مجاز است.", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔️ دسترسی غیرمجاز! این بخش تنها در اختیارات ادمین اصلی می‌باشد.")
        return

    from backup_service import load_backup_settings, _collect_database_summary

    settings = load_backup_settings()
    auto_enabled = settings.get("auto_backup_enabled", False)
    interval_h = settings.get("interval_hours", 24)
    last_auto = settings.get("last_auto_backup") or "تاکنون انجام نشده"

    db_stats = _collect_database_summary("bot_data.db")
    orders_cnt = db_stats.get("orders", 0)
    channels_cnt = db_stats.get("monitored_channels", 0)

    # کاتالوگ و عکس‌ها
    cat_cnt = 0
    if os.path.exists("catalog_products.json"):
        try:
            with open("catalog_products.json", "r", encoding="utf-8") as f:
                cat_cnt = len(json.load(f))
        except Exception:
            pass

    audio_cnt = 0
    if os.path.exists("audio_catalog.json"):
        try:
            with open("audio_catalog.json", "r", encoding="utf-8") as f:
                audio_cnt = len(json.load(f))
        except Exception:
            pass

    aeg_cnt = 0
    if os.path.exists("aeg_products.json"):
        try:
            with open("aeg_products.json", "r", encoding="utf-8") as f:
                aeg_cnt = len(json.load(f))
        except Exception:
            pass

    photos_cnt = 0
    if os.path.exists("verified_photos.json"):
        try:
            with open("verified_photos.json", "r", encoding="utf-8") as f:
                photos_cnt = len(json.load(f))
        except Exception:
            pass

    sub_admins_cnt = 0
    if os.path.exists("admin_ids.json"):
        try:
            with open("admin_ids.json", "r", encoding="utf-8") as f:
                adm_d = json.load(f)
                sub_admins_cnt = len(adm_d) if isinstance(adm_d, list) else len(adm_d.keys())
        except Exception:
            pass

    auto_status_text = "✅ فعال (ارسال فایل هر ۲۴ ساعت به پیوی مدیر)" if auto_enabled else "🛑 غیرفعال (فقط دستی)"

    text = (
        f"💾 <b>مدیریت پشتیبان‌گیری و بازگردانی داده‌ها (Backup / Restore):</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>وضعیت داده‌های کنونی سیستم:</b>\n"
        f"▫️ سفارش‌ها و خریدهای ثبت‌شده: <b>{orders_cnt:,}</b> سفارش\n"
        f"▫️ کاتالوگ اصلی محصولات: <b>{cat_cnt:,}</b> کالا\n"
        f"▫️ کاتالوگ صوتی و پارتی‌باکس: <b>{audio_cnt:,}</b> دستگاه\n"
        f"▫️ محصولات تخصصی آاگ: <b>{aeg_cnt:,}</b> کالا\n"
        f"▫️ تصاویر اختصاصی متصل‌شده: <b>{photos_cnt:,}</b> کالا\n"
        f"▫️ ادمین‌های فرعی ثبت‌شده: <b>{sub_admins_cnt}</b> نفر\n"
        f"▫️ کانال‌های متصل و تحت پایش: <b>{channels_cnt}</b> کانال\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <b>وضعیت بک‌آپ‌گیری خودکار ۲۴ ساعته:</b>\n"
        f"▫️ وضعیت: <b>{auto_status_text}</b>\n"
        f"▫️ آخرین بک‌آپ خودکار: <code>{last_auto}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 جهت عملیات مورد نظر، یکی از گزینه‌های زیر را انتخاب فرمایید:"
    )

    toggle_btn_text = "🛑 غیرفعال‌سازی بک‌آپ خودکار" if auto_enabled else "⏰ فعال‌سازی بک‌آپ خودکار ۲۴ ساعته"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 دانلود فوری فایل پشتیبان (Full Backup .zip)", callback_data="adm_backup_download")],
        [InlineKeyboardButton(toggle_btn_text, callback_data="adm_backup_toggle_auto")],
        [InlineKeyboardButton("♻️ بازگردانی یا ادغام فایل بک‌آپ (Upload)", callback_data="adm_backup_upload_prompt")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_backup_download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ایجاد و ارسال فایل زیپ بک‌آپ به پیوی ادمین در تلگرام"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    if update.callback_query:
        await update.callback_query.answer("⏳ در حال ساخت پکیج پشتیبان...", show_alert=False)

    status_msg = await update.effective_message.reply_text(
        "⏳ <b>در حال ایجاد فایل فشرده پشتیبان کلی (.zip)...</b>\n"
        "▫️ فشرده‌سازی دیتابیس سفارش‌ها، فاکتورها، عکس‌ها، کاتالوگ و تنظیمات",
        parse_mode="HTML"
    )

    from backup_service import create_full_backup_zip
    zip_path, manifest = create_full_backup_zip()

    file_size_kb = round(os.path.getsize(zip_path) / 1024, 1)

    audio_and_aeg = manifest.get("audio_catalog_count", 0) + manifest.get("aeg_products_count", 0)
    caption = (
        f"📦 <b>پکیج پشتیبان جامع سیستم (Full Backup)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 نام فایل: <code>{manifest['backup_name']}</code>\n"
        f"📅 تاریخ و ساعت: <b>{manifest['created_at']}</b>\n"
        f"⚖️ حجم فایل: <b>{file_size_kb} کیلوبایت</b>\n\n"
        f"📋 <b>محتویات داخل پکیج:</b>\n"
        f"▫️ سفارش‌ها و فاکتورها: <b>{manifest['orders_count']}</b> مورد\n"
        f"▫️ کاتالوگ اصلی کالاها: <b>{manifest['products_catalog_count']}</b> محصول\n"
        f"▫️ سیستم‌های صوتی و AEG: <b>{audio_and_aeg}</b> محصول\n"
        f"▫️ ارتباط تصاویر و آلبوم‌ها: <b>{manifest['verified_photos_count']}</b> مورد\n"
        f"▫️ لیست ادمین‌های فرعی: <b>{manifest.get('sub_admins_count', 0)}</b> نفر\n"
        f"▫️ دیتابیس SQLite، تنظیمات بانکی، هوش مصنوعی، نرخ‌ها و وضعیت کانال‌ها\n\n"
        f"💡 <i>این فایل را در جای امن نگهداری فرمایید. در صورت نیاز به بازگردانی، می‌توانید همین فایل زیپ را برای ربات ارسال فرمایید.</i>"
    )

    try:
        with open(zip_path, "rb") as f_zip:
            await context.bot.send_document(
                chat_id=user.id,
                document=f_zip,
                filename=manifest["backup_name"],
                caption=caption,
                parse_mode="HTML"
            )
        try:
            await status_msg.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error sending backup zip: {e}")
        await status_msg.edit_text(f"❌ خطا در ارسال فایل پشتیبان: {e}")


async def admin_backup_toggle_auto_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سوییچ فعال یا غیرفعال بودن بک‌آپ خودکار ۲۴ ساعته"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    from backup_service import load_backup_settings, set_auto_backup_state

    curr = load_backup_settings()
    new_state = not curr.get("auto_backup_enabled", False)
    set_auto_backup_state(new_state)

    state_msg = "✅ پشتیبان‌گیری خودکار ۲۴ ساعته فعال شد. هر ۲۴ ساعت یک فایل کامل به تلگرام شما ارسال می‌شود." if new_state else "🛑 پشتیبان‌گیری خودکار غیرفعال گردید."
    if update.callback_query:
        try:
            await update.callback_query.answer(state_msg, show_alert=True)
        except Exception:
            pass

    await admin_backup_menu(update, context)


async def admin_backup_upload_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای آپلود فایل زیپ بک‌آپ توسط ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    context.user_data["awaiting_backup_zip_file"] = True

    text = (
        f"📥 <b>ارسال فایل پشتیبان جهت بازگردانی یا ادغام:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"لطفاً فایل پشتیبان با پسوند <b>.zip</b> (که قبلاً از سیستم دریافت کرده‌اید) را در همین چت <b>ارسال (یا فوروارد)</b> فرمایید.\n\n"
        f"✨ <b>پس از ارسال فایل:</b>\n"
        f"ربات محتویات را بررسی کرده و به شما ۲ گزینه ارائه می‌دهد:\n"
        f"۱️⃣ <b>ادغام هوشمند (Smart Merge):</b> اضافه کردن سفارش‌ها و عکس‌های جدید بدون حذف داده‌های فعلی.\n"
        f"۲️⃣ <b>بازگردانی کامل (Replace All):</b> جایگزینی ۱۰۰٪ سیستم با فایل بک‌آپ (همراه با اسنپ‌شات ایمنی).\n\n"
        f"❌ جهت انصراف: /cancel"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منوی پشتیبان", callback_data="adm_backup_menu")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


# =====================================================================
# 👥 مدیریت ادمین‌ها و سطوح دسترسی (فقط ادمین اصلی - مالک ربات)
# =====================================================================

async def admin_manage_admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی مدیریت ادمین‌ها و دسترسی‌ها (مخصوص ادمین اصلی 86900909)"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها برای ادمین اصلی (مالک ربات) مجاز است.", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔️ دسترسی غیرمجاز! این بخش تنها در اختیارات ادمین اصلی می‌باشد.")
        return

    # پاکسازی وضعیت‌های در حال انتظار ادمین
    context.user_data.pop("awaiting_new_admin_id", None)
    context.user_data.pop("pending_admin_id", None)

    sub_admins_detailed = get_sub_admins_detailed()
    sub_admin_ids = get_sub_admin_ids()

    # ایجاد مپ id -> name
    name_map = {item["id"]: item.get("name", "همکار") for item in sub_admins_detailed}

    text = (
        f"👥 <b>مرکز مدیریت ادمین‌ها و سطوح دسترسی</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>ادمین اصلی (مالک ربات):</b>\n"
        f"▫️ نام: <b>مهران امین‌پور</b>\n"
        f"▫️ شناسه عددی: <code>{OWNER_ID}</code> (دارای دسترسی کامل و غیرقابل حذف)\n\n"
        f"👥 <b>لیست ادمین‌های فرعی ثبت‌شده:</b>\n"
    )

    if not sub_admin_ids:
        text += "▫️ <i>در حال حاضر هیچ ادمین فرعی در سیستم ثبت نشده است.</i>\n"
    else:
        for idx, aid in enumerate(sub_admin_ids, start=1):
            adm_name = name_map.get(aid, "همکار")
            text += f"▫️ <b>{idx}. {adm_name}:</b> شناسه عددی <code>{aid}</code>\n"

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🔒 <b>محدودیت‌های ادمین‌های فرعی:</b>\n"
        f"❌ عدم دسترسی به افزودن/حذف ادمین‌ها\n"
        f"❌ عدم دسترسی به کارشناسان پشتیبانی\n"
        f"❌ عدم دسترسی به مشخصات بانکی و بیعانه\n"
        f"❌ عدم دسترسی به پایش کانال‌ها و آلبوم‌ها\n"
        f"❌ عدم دسترسی به تنظیمات هوش مصنوعی\n"
        f"❌ عدم دسترسی به پشتیبان‌گیری و بازگردانی\n\n"
        f"👇 جهت افزودن ادمین جدید یا حذف ادمین‌های فعلی گزینه‌های زیر را انتخاب فرمایید:"
    )

    buttons = []
    # دکمه‌های حذف ادمین‌های فرعی به همراه نام
    for aid in sub_admin_ids:
        adm_name = name_map.get(aid, "همکار")
        buttons.append([
            InlineKeyboardButton(f"❌ حذف دسترسی: {adm_name} ({aid})", callback_data=f"adm_del_admin|{aid}")
        ])

    buttons.append([
        InlineKeyboardButton("➕ افزودن ادمین جدید (با آیدی و نام)", callback_data="adm_add_admin_prompt")
    ])
    buttons.append([
        InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")
    ])

    kb = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_add_admin_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست ارسال آیدی عددی تلگرام و نام شخص جهت ثبت ادمین جدید"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها برای ادمین اصلی مجاز است.", show_alert=True)
        return

    context.user_data["awaiting_new_admin_id"] = True
    context.user_data.pop("pending_admin_id", None)

    text = (
        f"➕ <b>افزودن ادمین فرعی جدید:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"برای ثبت دقیق، می‌توانید آیدی عددی و نام شخص را به یکی از دو روش زیر ارسال فرمایید:\n\n"
        f"<b>روش ۱ (تک‌مرحله‌ای - پیشنهادی):</b>\n"
        f"ارسال آیدی عددی به همراه نام با خط فاصله یا فاصله:\n"
        f"▫️ مثال: <code>123456789 - علی رضایی</code>\n"
        f"▫️ مثال: <code>123456789 محمد</code>\n\n"
        f"<b>روش ۲ (دو مرحله‌ای):</b>\n"
        f"ابتدا فقط آیدی عددی (مانند <code>123456789</code>) را ارسال فرمایید تا ربات در پیام بعد نام او را از شما بپرسد.\n\n"
        f"💡 <i>راهنما:</i> همکار شما می‌تواند با ارسال دستور <code>/id</code> در همین ربات، آیدی عددی تلگرام خود را دریافت و برای شما بفرستد.\n\n"
        f"❌ جهت انصراف: /cancel یا دکمه زیر:"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_manage_admins")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_delete_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, target_uid_str: str):
    """حذف ادمین فرعی توسط ادمین اصلی"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها برای ادمین اصلی مجاز است.", show_alert=True)
        return

    try:
        target_uid = int(str(target_uid_str).strip())
    except ValueError:
        if update.callback_query:
            await update.callback_query.answer("شناسه نامعتبر است.", show_alert=True)
        return

    if is_owner(target_uid):
        if update.callback_query:
            await update.callback_query.answer("⚠️ ادمین اصلی (مالک ربات) قابل حذف نیست.", show_alert=True)
        return

    success = remove_admin_id(target_uid)
    if success:
        if update.callback_query:
            await update.callback_query.answer(f"✅ دسترسی ادمین {target_uid} لغو و از سیستم حذف شد.", show_alert=True)
    else:
        if update.callback_query:
            await update.callback_query.answer("خطا در حذف ادمین.", show_alert=True)

    await admin_manage_admins_menu(update, context)


async def handle_admin_add_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """پردازش پیام متنی حاوی آیدی عددی و نام برای ثبت ادمین جدید"""
    if not context.user_data.get("awaiting_new_admin_id"):
        return False

    user = update.effective_user
    if not is_owner(user.id):
        context.user_data.pop("awaiting_new_admin_id", None)
        context.user_data.pop("pending_admin_id", None)
        return False

    raw_text = (update.message.text or "").strip()
    if raw_text.startswith("/cancel") or raw_text.lower() in ["cancel", "لغو", "انصراف", "/انصراف"]:
        context.user_data.pop("awaiting_new_admin_id", None)
        context.user_data.pop("pending_admin_id", None)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به مدیریت ادمین‌ها", callback_data="adm_manage_admins")]
        ])
        await update.message.reply_text("❌ عملیات افزودن ادمین جدید لغو گردید.", reply_markup=kb)
        return True

    from search_engine import _normalize_digits

    # بررسی اگر در مرحله دوم (انتظار برای نام) هستیم
    pending_uid = context.user_data.get("pending_admin_id")
    if pending_uid:
        admin_name = raw_text.strip() or "همکار"
        success = add_admin_id(pending_uid, name=admin_name)
        context.user_data.pop("awaiting_new_admin_id", None)
        context.user_data.pop("pending_admin_id", None)

        if success:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 مشاهده لیست ادمین‌ها", callback_data="adm_manage_admins")],
                [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
            ])
            await update.message.reply_text(
                f"✅ <b>ادمین جدید با موفقیت ثبت شد!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 نام همکار: <b>{admin_name}</b>\n"
                f"▫️ شناسه عددی: <code>{pending_uid}</code>\n"
                f"▫️ سطح دسترسی: <b>ادمین فرعی (محدود)</b>\n\n"
                f"این همکار هم‌اکنون با ارسال دستور /admin یا دکمه پنل مدیریت، می‌تواند به بخش‌های مجاز دسترسی داشته باشد.",
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به مدیریت ادمین‌ها", callback_data="adm_manage_admins")]
            ])
            await update.message.reply_text("❌ خطا در ذخیره‌سازی ادمین جدید.", reply_markup=kb)
        return True

    # بررسی ورودی تک‌مرحله‌ای (آیدی + نام) یا تک‌مقداری (فقط آیدی)
    import re
    norm_text = _normalize_digits(raw_text)

    # جداسازی عدد اول متن
    match = re.match(r"^(\d{4,15})[\s\-:|,]+(.+)$", norm_text, re.DOTALL)
    if match:
        new_uid_str, admin_name = match.group(1), match.group(2).strip()
    else:
        # شاید فقط عدد ارسال شده
        clean_num = norm_text.replace(" ", "").replace("\n", "").strip()
        if clean_num.isdigit() and len(clean_num) >= 4:
            new_uid_str = clean_num
            admin_name = None
        else:
            cancel_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_manage_admins")]
            ])
            await update.message.reply_text(
                "⚠️ <b>ورودی نامعتبر است!</b>\n\n"
                "لطفاً آیدی عددی تلگرام را به همراه نام وارد فرمایید.\n"
                "▫️ مثال: <code>123456789 - علی احمدی</code>\n"
                "▫️ یا فقط عدد: <code>123456789</code>\n\n"
                "❌ جهت انصراف: /cancel",
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )
            return True

    new_uid = int(new_uid_str)

    if is_owner(new_uid):
        context.user_data.pop("awaiting_new_admin_id", None)
        context.user_data.pop("pending_admin_id", None)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به مدیریت ادمین‌ها", callback_data="adm_manage_admins")]
        ])
        await update.message.reply_text(
            f"ℹ️ شناسه <code>{new_uid}</code> متعلق به ادمین اصلی (مالک ربات) است و از قبل به تمام بخش‌ها دسترسی کامل دارد.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return True

    if new_uid in get_sub_admin_ids() and not admin_name:
        context.user_data.pop("awaiting_new_admin_id", None)
        context.user_data.pop("pending_admin_id", None)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به مدیریت ادمین‌ها", callback_data="adm_manage_admins")]
        ])
        await update.message.reply_text(
            f"⚠️ همکار با شناسه <code>{new_uid}</code> در حال حاضر در لیست ادمین‌های فرعی ثبت شده است.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return True

    # اگر نام وارد نشده بود، در مرحله بعد نام را بپرس
    if not admin_name:
        context.user_data["pending_admin_id"] = new_uid
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="adm_manage_admins")]
        ])
        await update.message.reply_text(
            f"✅ شناسه عددی <code>{new_uid}</code> دریافت شد.\n\n"
            f"👤 اکنون لطفاً <b>نام یا عنوان این همکار</b> را ارسال فرمایید تا مشخص باشد این آیدی متعلق به کیست:\n"
            f"▫️ (مثال: <code>علی رضایی - بخش ارسال</code> یا <code>رضا احمدی</code>)",
            reply_markup=cancel_kb,
            parse_mode="HTML"
        )
        return True

    # اگر نام هم همراه آیدی بود، مستقیماً ذخیره کن
    success = add_admin_id(new_uid, name=admin_name)
    context.user_data.pop("awaiting_new_admin_id", None)
    context.user_data.pop("pending_admin_id", None)

    if success:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 مشاهده لیست ادمین‌ها", callback_data="adm_manage_admins")],
            [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
        ])
        await update.message.reply_text(
            f"✅ <b>ادمین جدید با موفقیت ثبت شد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 نام همکار: <b>{admin_name}</b>\n"
            f"▫️ شناسه عددی: <code>{new_uid}</code>\n"
            f"▫️ سطح دسترسی: <b>ادمین فرعی (محدود)</b>\n\n"
            f"🔒 <b>دسترسی‌های فعال این ادمین:</b>\n"
            f"✔️ مدیریت سفارشات و فیش‌ها\n"
            f"✔️ کاتالوگ و بروزرسانی قیمت‌ها و موجودی\n"
            f"✔️ مدیریت کاتالوگ لپ‌تاپ\n"
            f"✔️ ارسال پیام همگانی و گزارش کاتالوگ\n"
            f"✔️ تنظیم عکس و قیمت دستی کالاها\n\n"
            f"🚫 <b>دسترسی‌های مسدود و پنهان:</b>\n"
            f"⛔️ عدم دسترسی به افزودن/حذف ادمین\n"
            f"⛔️ عدم دسترسی به کارشناسان پشتیبانی\n"
            f"⛔️ عدم دسترسی به مشخصات بانکی و بیعانه\n"
            f"⛔️ عدم دسترسی به پایش کانال‌ها و آلبوم‌ها\n"
            f"⛔️ عدم دسترسی به تنظیمات هوش مصنوعی\n"
            f"⛔️ عدم دسترسی به پشتیبان‌گیری و بازیابی\n\n"
            f"این همکار هم‌اکنون می‌تواند با ارسال دستور /admin وارد پنل مدیریت شود.",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به مدیریت ادمین‌ها", callback_data="adm_manage_admins")]
        ])
        await update.message.reply_text("❌ خطا در ذخیره‌سازی ادمین جدید.", reply_markup=kb)

    return True


# ─── سامانه ارسال خودکار و زمان‌بندی‌شده به کانال تلگرام (Auto-Poster) ───

async def admin_autoposter_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی مدیریت و تنظیمات ارسال خودکار محصولات به کانال فروشگاه"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    from auto_poster import load_poster_settings
    st = load_poster_settings()

    ch = st.get("channel_username", "@AiKala_Khanegi")
    enabled = st.get("enabled", True)
    status_icon = "🟢 فعال (در حال ارسال منظم)" if enabled else "🔴 متوقف (غیرفعال)"
    toggle_text = "⏸ توقف ارسال خودکار" if enabled else "▶️ فعال‌سازی ارسال خودکار"
    mode = st.get("interval_mode", "random")
    interval = st.get("interval_minutes", 30)
    next_int = st.get("next_interval_minutes", 25)
    total_posted = st.get("total_posted", 0)
    last_prod = st.get("last_product_name") or "هنوز پستی ارسال نشده"
    last_time = st.get("last_post_time") or "—"
    start_h = st.get("active_hours_start", 8)
    end_h = st.get("active_hours_end", 23)

    if mode == "random":
        interval_desc = f"🎲 <b>تصادفی هوشمند (ضد اسپم)</b>\n▫️ <b>الگوی زمان‌بندی:</b> نوسانی بین ۱۵، ۲۰، ۳۰، ۴۵ الی ۶۰ دقیقه\n▫️ <b>تخمین ارسال بعدی:</b> حدوداً <b>{next_int} دقیقه</b> دیگر"
    else:
        interval_desc = f"ثابت (هر <b>{interval} دقیقه</b> یکبار)"

    text = (
        f"📢 <b>سیستم ارسال خودکار و سئو کانال هوشمند کالا</b>\n\n"
        f"<blockquote>▫️ <b>کانال هدف:</b> <code>{ch}</code>\n"
        f"▫️ <b>وضعیت کنونی:</b> {status_icon}\n"
        f"▫️ <b>فاصله زمانی بین پست‌ها:</b> {interval_desc}\n"
        f"▫️ <b>ساعات مجاز ارسال:</b> از ساعت {start_h}:00 الی {end_h}:00\n"
        f"▫️ <b>کل پست‌های ارسال‌شده:</b> <b>{total_posted} کالا</b>\n"
        f"▫️ <b>آخرین محصول ارسالی:</b> <b>{last_prod}</b> (<code>{last_time}</code>)</blockquote>\n\n"
        f"🛡 <b>مزیت حالت تصادفی ضد اسپم:</b> فواصل نامنظم (یکبار ۱۵ دقیقه، یکبار ۳۰ دقیقه، یکبار ۱ ساعت) دقیقاً مانند ادمین انسانی عمل می‌کند و مانع از حساسیت، اسپم و بن شدن کانال توسط تلگرام می‌گردد.\n\n"
        f"💡 <i>پست‌ها همراه تصویر، مشخصات فنی، ضمانت کتبی، هشتگ‌های سئو و <b>دکمه شیشه‌ای خرید در ربات</b> ارسال می‌شوند.</i>\n\n"
        f"⚠️ <b>پیش‌نیاز مهم:</b> لطفاً اطمینان حاصل فرمایید ربات @AiKala_bot در کانال <code>{ch}</code> به عنوان <b>ادمین با دسترسی ارسال پیام (Post Messages)</b> عضو باشد."
    )

    buttons = [
        [
            InlineKeyboardButton("🚀 ارسال فوری یک پست به کانال (تست)", callback_data="adm_post_now")
        ],
        [
            InlineKeyboardButton(toggle_text, callback_data="adm_post_toggle")
        ],
        [
            InlineKeyboardButton(f"{'🔘 ' if mode == 'random' else ''}🎲 حالت تصادفی ضد اسپم (۱۵ تا ۶۰ دقیقه)", callback_data="adm_post_int|random")
        ],
        [
            InlineKeyboardButton(f"{'🔘 ' if mode == 'fixed' and interval == 15 else ''}⏱ ۱۵ دقیقه", callback_data="adm_post_int|15"),
            InlineKeyboardButton(f"{'🔘 ' if mode == 'fixed' and interval == 30 else ''}⏱ ۳۰ دقیقه", callback_data="adm_post_int|30"),
            InlineKeyboardButton(f"{'🔘 ' if mode == 'fixed' and interval == 60 else ''}⏱ ۱ ساعت", callback_data="adm_post_int|60")
        ],
        [
            InlineKeyboardButton("✏️ تغییر آیدی کانال مقصد", callback_data="adm_post_set_channel_ask"),
            InlineKeyboardButton("🔄 بروزرسانی وضعیت", callback_data="adm_autoposter")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")
        ]
    ]

    kb = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_autoposter_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغییر وضعیت روشن/خاموش ارسال خودکار"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    from auto_poster import toggle_poster_enabled
    new_state = toggle_poster_enabled()
    state_str = "فعال شد 🟢" if new_state else "متوقف گردید 🔴"
    if update.callback_query:
        await update.callback_query.answer(f"ارسال خودکار به کانال {state_str}", show_alert=False)
    await admin_autoposter_menu(update, context)


async def admin_autoposter_set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE, val: str):
    """تنظیم بازه زمانی انتشار پست در کانال"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    from auto_poster import set_poster_interval
    mode, next_mins = set_poster_interval(val)
    if update.callback_query:
        if mode == "random":
            await update.callback_query.answer(f"🎲 حالت تصادفی ضد اسپم فعال شد.\nارسال بعدی حدوداً {next_mins} دقیقه دیگر.", show_alert=True)
        else:
            await update.callback_query.answer(f"⏱ فاصله ارسال روی زمان ثابت هر {val} دقیقه تنظیم گردید.", show_alert=False)
    await admin_autoposter_menu(update, context)


async def admin_autoposter_post_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال فوری و دستی یک پست به کانال جهت تست یا انتشار آنی"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    # پاسخ تک‌مرحله‌ای و بدون ریسک انقضا به کلیک شیشه‌ای
    if update.callback_query:
        try:
            await update.callback_query.answer("⏳ در حال پردازش و ارسال محصول به کانال...", show_alert=False)
        except Exception:
            pass

    from auto_poster import publish_product_to_channel, load_poster_settings
    st = load_poster_settings()
    ch = st.get("channel_username", "@AiKala_Khanegi")

    status_msg = None
    try:
        if update.callback_query and update.callback_query.message:
            status_msg = await update.callback_query.message.reply_text(
                f"⏳ <b>در حال انتخاب کالا و انتشار در کانال <code>{ch}</code>...</b>\nلطفاً چند لحظه شکیبا باشید.",
                parse_mode="HTML"
            )
        elif update.message:
            status_msg = await update.message.reply_text(
                f"⏳ <b>در حال انتخاب کالا و انتشار در کانال <code>{ch}</code>...</b>\nلطفاً چند لحظه شکیبا باشید.",
                parse_mode="HTML"
            )
    except Exception as e_st:
        logger.warning(f"Could not send poster status message: {e_st}")

    try:
        success, msg = await publish_product_to_channel(context.bot)
    except Exception as e_pub:
        logger.error(f"Error calling publish_product_to_channel: {e_pub}", exc_info=True)
        success = False
        msg = f"خطای سیستمی: {e_pub}"

    if success:
        last_prod = load_poster_settings().get("last_product_name", "کالا")
        success_text = (
            f"✅ <b>پست با موفقیت در کانال منتشر گردید!</b>\n\n"
            f"<blockquote>▫️ <b>کالای منتشرشده:</b> {last_prod}\n"
            f"▫️ <b>کانال مقصد:</b> <code>{ch}</code></blockquote>\n\n"
            f"🔗 می‌توانید هم‌اکنون پست جدید را در کانال بررسی فرمایید."
        )
        try:
            if status_msg:
                await status_msg.edit_text(success_text, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=user.id, text=success_text, parse_mode="HTML")
        except Exception:
            pass
    else:
        fail_text = (
            f"❌ <b>خطا در انتشار پست در کانال:</b>\n\n"
            f"<blockquote>{msg}</blockquote>\n\n"
            f"<b>راهنمای حل مشکل:</b>\n"
            f"۱. وارد کانال <code>{ch}</code> شوید.\n"
            f"۲. از منوی تنظیمات کانال وارد <b>Administrators (مدیران)</b> شوید.\n"
            f"۳. ربات <b>@AiKala_bot</b> را به عنوان ادمین اضافه کنید.\n"
            f"۴. تیک دسترسی <b>Post Messages (ارسال پیام)</b> را برای ربات فعال کنید.\n"
            f"۵. اگر آدرس کانال متفاوت است، از دکمه «✏️ تغییر آیدی کانال مقصد» استفاده نمایید."
        )
        try:
            if status_msg:
                await status_msg.edit_text(fail_text, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=user.id, text=fail_text, parse_mode="HTML")
        except Exception:
            pass

    await admin_autoposter_menu(update, context)


async def admin_autoposter_set_channel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست آیدی جدید کانال از ادمین"""
    user = update.effective_user
    if not is_admin(user.id):
        return

    if update.callback_query:
        await update.callback_query.answer()

    context.user_data["awaiting_poster_channel_set"] = True

    txt = (
        "✏️ <b>تنظیم آدرس یا آیدی کانال مقصد جهت ارسال خودکار محصولات:</b>\n\n"
        "<blockquote>▫️ نمونه صحیح: <code>@AiKala_Khanegi</code>\n"
        "▫️ یا لینک عمومی: <code>https://t.me/AiKala_Khanegi</code></blockquote>\n\n"
        "👇 لطفاً نام کاربری جدید کانال را ارسال فرمایید:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_autoposter")]
    ])
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


async def handle_admin_poster_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دریافت و ذخیره آیدی جدید کانال ارسالی توسط ادمین"""
    if not context.user_data.get("awaiting_poster_channel_set"):
        return False

    context.user_data.pop("awaiting_poster_channel_set", None)
    raw = update.message.text.strip()
    clean = raw.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "").replace("@", "").strip()

    if not clean:
        await update.message.reply_text("❌ آیدی وارد شده نامعتبر است.")
        await admin_autoposter_menu(update, context)
        return True

    new_ch = f"@{clean}"
    from auto_poster import set_poster_channel
    set_poster_channel(new_ch)

    await update.message.reply_text(f"✅ کانال مقصد با موفقیت به <code>{new_ch}</code> تغییر یافت.", parse_mode="HTML")
    await admin_autoposter_menu(update, context)
    return True


# ─── مرکز کنترل وضعیت و فریز کلی ربات (ویژه ادمین اصلی) ───

async def admin_freeze_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اختصاصی مدیریت وضعیت و فریز کلی ربات (ویژه ادمین اصلی)"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش منحصراً در اختیارات مدیر ارشد (مالک ربات) می‌باشد.", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔️ این بخش منحصراً در اختیارات مدیر ارشد (مالک ربات) می‌باشد.")
        return

    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass

    context.user_data.pop("awaiting_freeze_custom_message", None)

    from freeze_service import get_freeze_status_summary
    summary = get_freeze_status_summary()
    is_frozen = summary["is_frozen"]
    curr_msg = summary["message"]
    updated_at = summary["updated_at"] or "ثبت‌نشده"

    if is_frozen:
        status_header = "🔴 <b>وضعیت کنونی ربات: متوقف و فریز شده (Paused) ⏸</b>"
        status_desc = (
            "⚠️ <b>توجه:</b> ربات در حالت تعلیق قرار دارد.\n"
            "▫️ کاربران عادی به هیچ دستوری پاسخ دریافت نمی‌کنند و با پیام زیر روبرو می‌شوند.\n"
            "▫️ پنل مدیریت برای ادمین‌ها در دسترس و فعال است."
        )
    else:
        status_header = "🟢 <b>وضعیت کنونی ربات: فعال و عادی (Active) ✅</b>"
        status_desc = (
            "▫️ تمامی سرویس‌های ربات، کاتالوگ‌ها، جستجو و ثبت سفارش برای عموم کاربران فعال هستند."
        )

    text = (
        f"⏸ <b>مرکز کنترل وضعیت و فریز کلی ربات (Maintenance & Freeze)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_header}\n\n"
        f"{status_desc}\n\n"
        f"💬 <b>پیام فعال هنگام فریز:</b>\n"
        f"<blockquote>{curr_msg}</blockquote>\n\n"
        f"⏱ <b>آخرین تغییر وضعیت:</b> <code>{updated_at}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 <i>جهت تغییر وضعیت یا ویرایش پیام، گزینه مورد نظر را انتخاب فرمایید:</i>"
    )

    buttons = []
    if is_frozen:
        buttons.append([
            InlineKeyboardButton("▶️ خروج از فریز و فعال‌سازی فوری ربات", callback_data="adm_unfreeze_do")
        ])
        buttons.append([
            InlineKeyboardButton("✏️ ویرایش پیام نمایش داده شده", callback_data="adm_freeze_custom_prompt")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("⚡ فریز سریع (با پیام جاری)", callback_data="adm_freeze_quick")
        ])
        buttons.append([
            InlineKeyboardButton("✍️ فریز با پیام دلخواه جدید", callback_data="adm_freeze_custom_prompt")
        ])

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")
    ])

    kb = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    if update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_freeze_quick_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فریز سریع ربات توسط ادمین اصلی با پیام جاری یا پیش‌فرض"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ دسترسی غیرمجاز.", show_alert=True)
        return

    from freeze_service import freeze_bot
    ok, msg = freeze_bot(user.id)
    if update.callback_query:
        await update.callback_query.answer("⏸ ربات با موفقیت فریز گردید.", show_alert=True)
    await admin_freeze_menu(update, context)


async def admin_unfreeze_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج ربات از فریز و فعال‌سازی مجدد توسط ادمین اصلی"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ دسترسی غیرمجاز.", show_alert=True)
        return

    from freeze_service import unfreeze_bot
    ok, msg = unfreeze_bot(user.id)
    if update.callback_query:
        await update.callback_query.answer("▶️ ربات مجدداً فعال و آنلاین شد.", show_alert=True)
    await admin_freeze_menu(update, context)


async def admin_freeze_custom_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست پیام دلخواه فریز از ادمین اصلی"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ دسترسی غیرمجاز.", show_alert=True)
        return

    if update.callback_query:
        await update.callback_query.answer()

    context.user_data["awaiting_freeze_custom_message"] = True

    txt = (
        "✍️ <b>تنظیم پیام اختصاصی توقف و فریز ربات:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "لطفاً متنی را که مایلید در هنگام فریز بودن ربات، به کاربران عادی نمایش داده شود ارسال فرمایید.\n\n"
        "▫️ می‌توانید از متن‌های چندخطی و ایموجی استفاده فرمایید.\n"
        "▫️ پس از ارسال پیام، ربات بلافاصله با این پیام به حالت فریز درخواهد آمد.\n\n"
        "👇 <i>متن مورد نظرتان را تایپ و ارسال کنید (یا دکمه انصراف را لمس نمایید):</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="adm_freeze_menu")]
    ])

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    if update.message:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


async def handle_admin_freeze_custom_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """دریافت پیام سفارشی فریز و اعمال آن توسط ادمین اصلی"""
    if not context.user_data.get("awaiting_freeze_custom_message"):
        return False

    user = update.effective_user
    if not is_owner(user.id):
        context.user_data.pop("awaiting_freeze_custom_message", None)
        return False

    raw_text = (update.message.text or "").strip()
    if raw_text.startswith("/cancel"):
        context.user_data.pop("awaiting_freeze_custom_message", None)
        await update.message.reply_text("❌ تنظیم پیام فریز لغو گردید.")
        await admin_freeze_menu(update, context)
        return True

    if not raw_text:
        await update.message.reply_text("⚠️ متن پیام نمی‌تواند خالی باشد. لطفاً پیام را تایپ نمایید یا /cancel را ارسال فرمایید:")
        return True

    context.user_data.pop("awaiting_freeze_custom_message", None)

    from freeze_service import freeze_bot
    ok, msg = freeze_bot(user.id, custom_message=raw_text)

    confirm_txt = (
        "✅ <b>فعالیت ربات با موفقیت فریز (متوقف) شد.</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💬 <b>پیام تنظیم‌شده برای کاربران:</b>\n"
        f"<blockquote>{raw_text}</blockquote>\n\n"
        "▫️ از این لحظه هر کاربر عادی که ربات را استارت بزند یا دستوری بفرستد با این پیام مواجه خواهد شد.\n"
        "▫️ جهت فعال‌سازی مجدد، از دکمه زیر یا دستور <code>/unfreeze</code> استفاده فرمایید."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ خروج از فریز و فعال‌سازی فوری", callback_data="adm_unfreeze_do")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")]
    ])
    await update.message.reply_text(confirm_txt, reply_markup=kb, parse_mode="HTML")
    return True


async def admin_freeze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور مستقیم /freeze برای ادمین اصلی"""
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("⛔️ این دستور فقط در اختیارات مدیر ارشد (مالک ربات) می‌باشد.")
        return
    await admin_freeze_menu(update, context)


async def admin_unfreeze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور مستقیم /unfreeze برای فعال‌سازی فوری ربات"""
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("⛔️ این دستور فقط در اختیارات مدیر ارشد (مالک ربات) می‌باشد.")
        return
    await admin_unfreeze_handler(update, context)





