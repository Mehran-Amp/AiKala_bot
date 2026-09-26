"""
AiKala - Interactive Order Tracking Room (order_tracking.py)
============================================================
سامانه پیشرفته و تعاملی رهگیری سفارشات و تایم‌لاین مراحل بارگیری و تحویل مرسوله.
طراحی شده بر اساس الگوی ناوبری اتاقی و بدون شلوغی چت (Single-Message Room).
پشتیبانی از لغو خودکار پس از ۵ ساعت در صورت عدم پرداخت بیعانه.
"""
import time


import re
import logging
from datetime import datetime
from typing import Dict, Any, List

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
except ImportError:
    Update = InlineKeyboardButton = InlineKeyboardMarkup = object
    class MockObj:
        DEFAULT_TYPE = object
    ContextTypes = MockObj
    CallbackQueryHandler = CommandHandler = object

from database import Database

logger = logging.getLogger(__name__)
db = Database()


STATUS_MAP = {
    "Awaiting_Payment": "⏳ در انتظار بیعانه",
    "Receipt_Uploaded": "🔎 بررسی فیش",
    "Approved": "🚚 در حال ارسال",
    "Delivered": "✅ تسویه و تحویل شد",
    "Cancelled": "❌ لغو (عدم واریز بیعانه)",
    "Rejected": "❌ سفارش رد شد"
}


def get_product_icon(product_name: str) -> str:
    """تشخیص آیکون مناسب بر اساس عنوان کالا"""
    p = (product_name or "").lower()
    if any(w in p for w in ["تلویزیون", "tv", "oled", "qled", "سونی", "سامسونگ", "الجی"]):
        if any(w in p for w in ["یخچال", "ساید", "لباسشویی", "ظرفشویی"]):
            pass
        else:
            return "📺"
    if any(w in p for w in ["یخچال", "ساید", "فریزر", "دوقلو", "fridge"]):
        return "❄️"
    if any(w in p for w in ["لباسشویی", "لباس شویی", "washer"]):
        return "🧺"
    if any(w in p for w in ["ظرفشویی", "ظرف شویی", "dishwasher"]):
        return "🍽"
    if any(w in p for w in ["کولر", "اسپلیت", "اسپیلت", "کولرگازی"]):
        return "❄️"
    if any(w in p for w in ["جارو", "جاروبرقی", "vacuum"]):
        return "🧹"
    if any(w in p for w in ["مایکرو", "مایکروفر", "ماکروویو", "سولاردام"]):
        return "♨️"
    if any(w in p for w in ["اسپیکر", "ساندبار", "speaker", "soundbar"]):
        return "🔊"
    if any(w in p for w in ["قهوه", "اسپرسو", "سرخ", "هواپز"]):
        return "☕️"
    return "📦"


def format_order_list_message(orders: List[Dict[str, Any]]) -> str:
    """تولید کادر شیک با هدر جذاب و خلاصه وضعیت سفارشات خریدار"""
    if not orders:
        return (
            "📦 <b>مرکز هوشمند رهگیری و مدیریت سفارشات هوشمند کالا</b>\n\n"
            "<blockquote>📋 <b>خلاصه وضعیت:</b> شما در حال حاضر هیچ سفارش فعالی در سامانه ثبت نکرده‌اید.</blockquote>\n\n"
            "💡 <i>به محض استعلام قیمت کالا و ثبت پیش‌فاکتور دیجیتال، اطلاعات کامل مرسوله، وضعیت فیش، تایم‌لاین ارسال و تحویل راننده در این بخش به صورت لحظه‌ای قابل رهگیری خواهد بود.</i>"
        )

    # محاسبه آمار وضعیت‌ها
    active_in_transit = sum(1 for o in orders if o.get("status") == "Approved")
    awaiting_deposit = sum(1 for o in orders if o.get("status") == "Awaiting_Payment")
    under_review = sum(1 for o in orders if o.get("status") == "Receipt_Uploaded")
    delivered_count = sum(1 for o in orders if o.get("status") == "Delivered")

    summary_parts = []
    if active_in_transit:
        summary_parts.append(f"🚚 <b>{active_in_transit} سفارش در حال ارسال</b>")
    if awaiting_deposit:
        summary_parts.append(f"⏳ <b>{awaiting_deposit} در انتظار بیعانه</b>")
    if under_review:
        summary_parts.append(f"🔎 <b>{under_review} در حال بررسی حسابداری</b>")
    if delivered_count:
        summary_parts.append(f"✅ <b>{delivered_count} تحویل‌شده</b>")

    summary_str = " | ".join(summary_parts) if summary_parts else "سفارشات شما در سامانه ثبت شده است."

    return (
        "📦 <b>مرکز هوشمند رهگیری و وضعیت مرسولات</b>\n\n"
        f"<blockquote>📊 <b>خلاصه وضعیت سفارشات:</b> {summary_str}</blockquote>\n\n"
        "👇 <b>جهت رهگیری گام‌به‌گام و مشاهده فاکتور دیجیتال، سفارش مورد نظر را انتخاب فرمایید:</b>"
    )


def order_list_keyboard(orders: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """کیبورد دکمه‌های شیشه‌ای مجزا برای هر سفارش دقیقاً با استایل درخواستی:
    [ 🏷 سفارش AK-7391 | 📺 تلویزیون ۶۵ اینچ سونی | 🚚 در حال ارسال ]
    """
    buttons = []

    if not orders:
        buttons.append([InlineKeyboardButton("🛒 راهنمای مراحل خرید و تسویه", callback_data="guide_steps")])
        buttons.append([InlineKeyboardButton("📞 پشتیبانی و مشاوره", callback_data="show_support")])
        buttons.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")])
        return InlineKeyboardMarkup(buttons)

    # افزودن دکمه شیشه‌ای مجزا برای هر سفارش
    for o in orders[:8]:
        st = o.get("status", "Awaiting_Payment")
        st_fa = STATUS_MAP.get(st, st)
        code = o.get("order_code", "")
        raw_name = o.get("product_name") or "کالای سفارشی"
        p_icon = get_product_icon(raw_name)
        short_name = raw_name[:20].strip()

        # فرمت درخواستی: [ 🏷 سفارش AK-7391 | 📺 تلویزیون ۶۵ اینچ سونی | 🚚 در حال ارسال ]
        btn_label = f"🏷 سفارش {code} | {p_icon} {short_name} | {st_fa}"
        buttons.append([
            InlineKeyboardButton(btn_label, callback_data=f"track_ord|{code}")
        ])

    buttons.append([InlineKeyboardButton("🔄 به‌روزرسانی لیست سفارشات", callback_data="track_refresh_list")])
    buttons.append([InlineKeyboardButton("📞 پشتیبانی و مشاوره", callback_data="show_support")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")])
    return InlineKeyboardMarkup(buttons)


def format_order_detail_message(order: Dict[str, Any]) -> str:
    """تولید شناسنامه کامل و تایم‌لاین ۵ مرحله‌ای مرسوله با کنترل مهلت ۵ ساعته"""
    code = order.get("order_code", "")
    product_name = order.get("product_name", "نامشخص")
    full_name = order.get("full_name") or order.get("customer_name") or "نامشخص"
    phone1 = order.get("phone1") or order.get("customer_phone") or order.get("phone") or "-"
    phone2 = order.get("phone2", "")
    phone_display = f"{phone1} / {phone2}" if phone2 else phone1
    city = order.get("province_city") or order.get("destination_city") or order.get("city") or "ثبت نشده"
    address = order.get("address") or order.get("customer_address") or "ثبت نشده"
    raw_deposit = str(order.get("deposit_amount", "0") or "0")
    try:
        clean_d = re.findall(r'\d+', raw_deposit.replace(",", "").replace("،", ""))
        d_val = int("".join(clean_d)) if clean_d else 0
        deposit = f"{d_val:,}" if d_val > 0 else raw_deposit
    except Exception:
        deposit = raw_deposit

    raw_total = str(order.get("total_price", "0") or "0")
    total_line = ""
    try:
        clean_tot = re.findall(r'\d+', raw_total.replace(",", "").replace("،", ""))
        tot_val = int("".join(clean_tot)) if clean_tot else 0
        if tot_val > 0:
            total_line = f"💰 <b>قیمت قطعی روز با احتساب هزینه ارسال:</b> <code>{tot_val:,} تومان</code>\n"
    except Exception:
        pass

    created_str = (order.get("created_at") or "")
    created_display = created_str[:16].replace("T", " ")
    status = order.get("status", "Awaiting_Payment")
    admin_note = order.get("admin_note", "").strip()

    shipping_method = order.get("shipping_method", "freight")
    is_post = (shipping_method == "post")

    if is_post:
        method_line = "📮 <b>نحوه ارسال:</b> پست پیشتاز (تسویه کامل - بدون بیعانه)\n"
        payment_line = f"💳 <b>مبلغ تسویه فاکتور:</b> <code>{tot_val:,} تومان</code>\n" if tot_val > 0 else f"💳 <b>مبلغ تسویه فاکتور:</b> <code>{deposit} تومان</code>\n"
    else:
        method_line = "🚚 <b>نحوه ارسال:</b> باربری اختصاصی (بیعانه + تسویه در محل)\n"
        payment_line = f"💳 <b>مبلغ بیعانه پیش‌پرداخت:</b> <code>{deposit} تومان</code>\n"

    header = (
        f"📦 <b>شناسنامه رهگیری سفارش <code>{code}</code></b>\n\n"
        f"<blockquote>▫️ <b>کالای سفارشی:</b> {product_name}\n"
        f"👤 <b>تحویل‌گیرنده:</b> {full_name}\n"
        f"📱 <b>شماره تماس:</b> <code>{phone_display}</code>\n"
        f"📍 <b>مقصد ارسال:</b> {city}\n"
        f"🏠 <b>آدرس پستی:</b> {address}\n"
        f"{method_line}"
        f"{total_line}"
        f"{payment_line}"
        f"📅 <b>زمان صدور پیش‌فاکتور:</b> <code>{created_display}</code></blockquote>\n\n"
    )

    # محاسبه زمان باقی‌مانده از مهلت ۵ ساعته واریز
    deadline_notice = ""
    term_title = "تسویه کامل فاکتور" if is_post else "واریز بیعانه"
    if status == "Awaiting_Payment" and created_str:
        try:
            c_at = datetime.fromisoformat(created_str)
            elapsed_sec = (datetime.now() - c_at).total_seconds()
            remaining_sec = (5.0 * 3600.0) - elapsed_sec
            if remaining_sec > 0:
                rem_h = int(remaining_sec // 3600)
                rem_m = int((remaining_sec % 3600) // 60)
                deadline_notice = (
                    f"\n⏱ <b>مهلت باقی‌مانده جهت {term_title}:</b> <code>{rem_h} ساعت و {rem_m} دقیقه</code>\n"
                    f"⚠️ <i>در صورت عدم پرداخت ظرف ۵ ساعت، سفارش به صورت خودکار لغو خواهد شد.</i>"
                )
            else:
                status = "Cancelled"
        except Exception:
            pass

    # ساخت تایم‌لاین گرافیکی و گام‌به‌گام وضعیت
    if status == "Awaiting_Payment":
        if is_post:
            timeline = (
                f"<blockquote>📍 <b>وضعیت کنونی:</b> ⏳ <b>در انتظار پرداخت و تسویه کامل وجه</b>"
                f"{deadline_notice}</blockquote>\n\n"
                "<b>مراحل گام‌به‌گام پیگیری سفارش:</b>\n"
                "🟢 <b>۱. صدور پیش‌فاکتور دیجیتال:</b> انجام شد\n"
                "🟡 <b>۲. واریز ۱۰۰٪ مبلغ فاکتور و ثبت فیش:</b> منتظر آپلود فیش بانکی خریدار\n"
                "⚪️ <b>۳. تایید حسابداری و صدور بیمه‌نامه مرسوله:</b> پس از ثبت فیش\n"
                "⚪️ <b>۴. بسته‌بندی ایمن و تحویل به اداره پست پیشتاز:</b> در نوبت\n"
                "⚪️ <b>۵. تحویل درب آدرس توسط مامور پست:</b> در نوبت\n\n"
                "👇 <i>جهت نهایی‌سازی سفارش و ارسال، دکمه «📸 ارسال تصویر فیش واریزی» را لمس فرمایید.</i>"
            )
        else:
            timeline = (
                f"<blockquote>📍 <b>وضعیت کنونی:</b> ⏳ <b>در انتظار واریز بیعانه</b>"
                f"{deadline_notice}</blockquote>\n\n"
                "<b>مراحل گام‌به‌گام پیگیری سفارش:</b>\n"
                "🟢 <b>۱. صدور پیش‌فاکتور دیجیتال:</b> انجام شد\n"
                "🟡 <b>۲. واریز بیعانه و ثبت فیش:</b> منتظر آپلود فیش بانکی خریدار\n"
                "⚪️ <b>۳. تایید حسابداری و بیمه‌نامه:</b> پس از ثبت فیش\n"
                "⚪️ <b>۴. تخصیص بار و تحویل به باربر اختصاصی:</b> در نوبت\n"
                "⚪️ <b>۵. تست حضوری و تسویه درب منزل:</b> در نوبت\n\n"
                "👇 <i>جهت رزرو قطعی دستگاه و هماهنگی ارسال، دکمه «📸 ارسال تصویر فیش واریزی» را لمس فرمایید.</i>"
            )
    elif status == "Receipt_Uploaded":
        timeline = (
            "<blockquote>📍 <b>وضعیت کنونی:</b> 🔎 <b>فیش واریزی دریافت شد (در حال بررسی حسابداری)</b>\n"
            "⏳ فرآیند استعلام و تایید فیش توسط حسابداری معمولاً بین ۱۵ تا ۳۰ دقیقه زمان می‌برد.</blockquote>\n\n"
            "<b>مراحل گام‌به‌گام پیگیری سفارش:</b>\n"
            "🟢 <b>۱. صدور پیش‌فاکتور دیجیتال:</b> تایید شد\n"
            f"🟢 <b>۲. پرداخت وجه ({'تسویه کامل' if is_post else 'بیعانه'}) و ثبت فیش:</b> فیش دریافت گردید\n"
            "🟡 <b>۳. تایید حسابداری و صدور بیمه بار:</b> در حال بررسی تراکنش بانکی\n"
            f"⚪️ <b>۴. تحویل به {'اداره پست پیشتاز' if is_post else 'باربر اختصاصی'}:</b> پس از تایید نهایی\n"
            f"⚪️ <b>۵. {'تحویل درب آدرس توسط پست' if is_post else 'تست حضوری و تسویه درب منزل'}:</b> در نوبت"
        )
    elif status == "Approved":
        if is_post:
            timeline = (
                "<blockquote>📍 <b>وضعیت کنونی:</b> 📮 <b>تایید نهایی و آماده‌سازی ارسال با پست پیشتاز</b>\n"
                "🛡 <b>تعهد سلامت کالا:</b> مرسوله دارای بیمه کامل سلامت فیزیکی بوده و تا زمان دریافت صحیح تحت پوشش است.</blockquote>\n\n"
                "<b>مراحل گام‌به‌گام پیگیری سفارش:</b>\n"
                "🟢 <b>۱. صدور پیش‌فاکتور دیجیتال:</b> تایید شد\n"
                "🟢 <b>۲. تسویه کامل وجه و تایید حسابداری:</b> تایید شد (مانده صفر)\n"
                "🟢 <b>۳. بسته‌بندی ضدضربه و صدور بیمه پستی:</b> صادر گردید\n"
                "🟡 <b>۴. تحویل به اداره پست پیشتاز:</b> مرسوله جهت ارسال به باجه پستی ارجاع گردید\n"
                "⚪️ <b>۵. دریافت بسته توسط خریدار:</b> در انتظار توزیع پستی"
            )
        else:
            timeline = (
                "<blockquote>📍 <b>وضعیت کنونی:</b> 🚚 <b>تایید نهایی و در حال ارسال به مقصد</b>\n"
                "🛡 <b>تعهد سلامت کالا:</b> دستگاه تا لحظه تحویل، تست سلامت فیزیکی و اتصال به برق در حضور باربر تحت پوشش بیمه کامل است.</blockquote>\n\n"
                "<b>مراحل گام‌به‌گام پیگیری سفارش:</b>\n"
                "🟢 <b>۱. صدور پیش‌فاکتور دیجیتال:</b> تایید شد\n"
                "🟢 <b>۲. واریز بیعانه و تایید حسابداری:</b> تایید شد\n"
                "🟢 <b>۳. صدور بیمه‌نامه سلامت کالا و بارنامه:</b> صادر گردید\n"
                "🟡 <b>۴. بارگیری و تحویل به باربر اختصاصی:</b> کالا به باربر تحویل داده شد و در مسیر مقصد است\n"
                "⚪️ <b>۵. تست حضوری و تسویه نهایی درب منزل:</b> در انتظار رسیدن به مقصد"
            )
    elif status == "Delivered":
        timeline = (
            "<blockquote>📍 <b>وضعیت کنونی:</b> ✅ <b>تحویل داده شد و سفارش تکمیل گردید</b>\n"
            "🌹 <i>از خرید و اعتماد ارزشمند شما به مجموعه هوشمند کالا صمیمانه سپاسگزاریم.</i></blockquote>"
        )
    elif status == "Cancelled":
        timeline = (
            f"<blockquote>📍 <b>وضعیت کنونی:</b> ❌ <b>سفارش به صورت خودکار لغو شد</b>\n"
            f"⚠️ <b>علت لغو:</b> عدم {term_title} ظرف مهلت قانونی ۵ ساعت پس از ثبت سفارش.</blockquote>\n\n"
            f"💡 <i>کالای رزرو شده به انبار بازگردانده شده است. در صورت تمایل، می‌توانید مجدداً از طریق ربات استعلام قیمت گرفته و سفارش جدید ثبت فرمایید.</i>"
        )
    elif status == "Rejected":
        timeline = (
            f"<blockquote>📍 <b>وضعیت کنونی:</b> ❌ <b>فیش یا سفارش تایید نگردید</b>\n"
            f"⚠️ <b>علت:</b> {admin_note or 'عدم تطابق مبلغ واریزی با فاکتور یا انصراف خریدار'}</blockquote>\n\n"
            f"📞 <i>جهت پیگیری یا رفع مشکل، می‌توانید با کارشناسان پشتیبانی در ارتباط باشید.</i>"
        )
    else:
        timeline = f"<blockquote>وضعیت سفارش: <b>{STATUS_MAP.get(status, status)}</b></blockquote>"

    footer = ""
    if admin_note and status in ["Approved", "Delivered"]:
        footer = f"\n\n<blockquote>📋 <b>اطلاعات واحد ترابری و باربری:</b>\n{admin_note}</blockquote>"

    return header + timeline + footer


def order_detail_keyboard(order: Dict[str, Any]) -> InlineKeyboardMarkup:
    """کیبورد زیر کارت مشخصات و رهگیری سفارش (زیر هم)"""
    buttons = []
    code = order.get("order_code", "")
    status = order.get("status", "Awaiting_Payment")

    # اگر در انتظار پرداخت است دکمه ارسال فیش قرار می‌گیرد
    if status == "Awaiting_Payment":
        buttons.append([
            InlineKeyboardButton("📸 ارسال تصویر فیش واریزی", callback_data=f"uprec|{code}")
        ])

    # دکمه مشاهده فاکتور / پیش‌فاکتور رسمی دیجیتال
    is_pre = (status in ["Awaiting_Payment", "Receipt_Uploaded", "Cancelled"])
    inv_label = "🧾 مشاهده تصویر پیش‌فاکتور رسمی" if is_pre else "🧾 مشاهده فاکتور رسمی و قطعی فروش"
    buttons.append([
        InlineKeyboardButton(inv_label, callback_data=f"view_inv|{code}")
    ])

    buttons.append([
        InlineKeyboardButton("🔄 به‌روزرسانی لحظه‌ای وضعیت", callback_data=f"track_ord|{code}")
    ])
    buttons.append([
        InlineKeyboardButton("📞 پشتیبانی و مشاوره", callback_data="show_support")
    ])
    buttons.append([
        InlineKeyboardButton("🔙 بازگشت به لیست سفارش‌ها", callback_data="track_order_list")
    ])
    buttons.append([
        InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")
    ])

    return InlineKeyboardMarkup(buttons)


async def show_order_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنجره اصلی لیست سفارشات کاربر"""
    user_id = update.effective_user.id
    # هنگام فراخوانی، سفارشات منقضی به صورت خودکار لغو می‌شوند
    orders = await db.get_orders_by_user(user_id)

    text = format_order_list_message(orders)
    kb = order_list_keyboard(orders)

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
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def order_tracking_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت رویدادهای کلیک بخش رهگیری سفارشات"""
    query = update.callback_query
    data = query.data
    try:
        await query.answer()
    except Exception:
        pass

    if data in ["track_order_list", "track_refresh_list"]:
        await show_order_tracking(update, context)

    elif data.startswith("track_ord|"):
        order_code = data.split("|")[1]
        order = await db.get_order_by_code(order_code)
        if not order:
            await query.message.reply_text("❌ اطلاعات این سفارش در سامانه یافت نشد.")
            return

        detail_text = format_order_detail_message(order)
        detail_kb = order_detail_keyboard(order)

        try:
            await query.edit_message_text(detail_text, reply_markup=detail_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(detail_text, reply_markup=detail_kb, parse_mode="HTML")

    elif data.startswith("view_inv|"):
        order_code = data.split("|")[1]
        order = await db.get_order_by_code(order_code)
        if not order:
            await query.message.reply_text("❌ اطلاعات سفارش یافت نشد.")
            return

        import os
        from invoice_service import generate_invoice_png, build_invoice_data_from_order

        is_pre = (order.get("status") in ["Awaiting_Payment", "Receipt_Uploaded", "Cancelled"])
        prefix = "pre_invoice" if is_pre else "final_invoice"
        file_path = f"invoices/{prefix}_{order_code}.png"

        if not os.path.exists(file_path):
            os.makedirs("invoices", exist_ok=True)
            inv_data = build_invoice_data_from_order(order)
            generate_invoice_png(inv_data, output_path=file_path, is_pre_invoice=is_pre)

        caption_title = "پیش‌فاکتور رسمی سفارش (در انتظار بیعانه)" if is_pre else "فاکتور رسمی و قطعی فروش (بیعانه تایید شده)"
        cap = (
            f"🧾 <b>تصویر رسمی {caption_title}</b>\n\n"
            f"<blockquote>🔖 <b>کد سفارش:</b> <code>{order_code}</code>\n"
            f"▫️ <b>وضعیت سند:</b> {STATUS_MAP.get(order.get('status'), order.get('status'))}</blockquote>"
        )
        inv_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 بازگشت به جزئیات سفارش", callback_data=f"track_ord|{order_code}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست سفارشات", callback_data="track_order_list")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]
        ])

        if os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f_img:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=f_img,
                        caption=cap,
                        reply_markup=inv_kb,
                        parse_mode="HTML",
                        read_timeout=60.0,
                        write_timeout=90.0,
                        connect_timeout=30.0
                    )
                return
            except Exception as e:
                logger.warning(f"Error sending invoice photo ({e}), attempting document fallback...")
                try:
                    with open(file_path, "rb") as f_doc:
                        await context.bot.send_document(
                            chat_id=query.message.chat_id,
                            document=f_doc,
                            filename=os.path.basename(file_path),
                            caption=cap,
                            reply_markup=inv_kb,
                            parse_mode="HTML",
                            read_timeout=60.0,
                            write_timeout=90.0,
                            connect_timeout=30.0
                        )
                    return
                except Exception as e_doc:
                    logger.error(f"Error sending invoice document: {e_doc}")

        await query.message.reply_text(cap, reply_markup=inv_kb, parse_mode="HTML")


def register_order_tracking_handlers(app):
    """ثبت تمام هندلرهای مربوط به سامانه پیگیری سفارشات"""
    app.add_handler(CommandHandler("track", show_order_tracking))
    app.add_handler(CallbackQueryHandler(order_tracking_callback_handler, pattern="^(track_order_list|track_refresh_list|track_ord\\||view_inv\\|)"))
