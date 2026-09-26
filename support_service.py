"""
AiKala - Dynamic Support & Consulting Service (support_service.py)
==================================================================
ماژول اختصاصی مرکز مشاوره تخصصی و پشتیبانی @AiKala_bot هوشمند کالا
شامل:
- نمایش داینامیک لیست کارشناسان، آیدی دایرکت تلگرام، شماره تماس و ساعات کاری
- اتصال به دیتابیس با امکان فعال/غیرفعال‌سازی، افزودن، ویرایش و حذف توسط ادمین
- ساخت دکمه‌های شیشه‌ای ورود به چت خصوصی تلگرام و تماس سریع
"""

import logging
from typing import List, Dict, Any, Optional
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
from keyboards import is_admin, is_owner
from config import SPONSOR_WEBSITE_URL, SPONSOR_WEBSITE_NAME

logger = logging.getLogger(__name__)
db = Database()

def clean_tg_username(username: str) -> str:
    """پاکسازی و استانداردسازی آیدی کاربری تلگرام"""
    tg = username.strip()
    if tg.startswith("@"):
        tg = tg[1:]
    elif tg.startswith("https://t.me/"):
        tg = tg.replace("https://t.me/", "")
    elif tg.startswith("t.me/"):
        tg = tg.replace("t.me/", "")
    return tg


def format_support_message(agents: List[Dict[str, Any]]) -> str:
    """فرمت‌بندی متن رسمی مرکز مشاوره و پشتیبانی خریداران"""
    header = (
        "📞 <b>مرکز مشاوره تخصصی و پشتیبانی فروشگاه</b>\n\n"
        f"<blockquote>🌐 <b>مالک و حامی رسمی:</b>\n"
        f"💎 وبسایت مرجع: <b>{SPONSOR_WEBSITE_NAME}</b>\n"
        f"🔗 <code>{SPONSOR_WEBSITE_URL}</code></blockquote>\n\n"
        "خریداران گرامی، جهت استعلام قیمت لحظه‌ای، دریافت مشاوره فنی رایگان و هماهنگی ارسال کالا می‌توانید با کارشناسان رسمی مجموعه در ارتباط باشید:\n\n"
    )

    if not agents:
        return (
            "📞 <b>مرکز مشاوره تخصصی و پشتیبانی فروشگاه</b>\n\n"
            f"<blockquote>🌐 <b>مالک و حامی رسمی:</b>\n"
            f"💎 وبسایت مرجع: <b>{SPONSOR_WEBSITE_NAME}</b>\n"
            f"🔗 <code>{SPONSOR_WEBSITE_URL}</code></blockquote>\n\n"
            "▫️ <i>در حال حاضر کارشناسی در سیستم تعریف نشده است.</i>\n\n"
            "📌 لطفاً جهت دریافت راهنمایی و استعلام با مدیریت یا از طریق بخش راهنمای خرید در ارتباط باشید."
        )

    agent_blocks = []
    # تبدیل ارقام به اعداد فارسی برای شماره‌گذاری
    persian_digits = ["۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹", "۱۰"]

    for idx, ag in enumerate(agents):
        num_fa = persian_digits[idx] if idx < len(persian_digits) else str(idx + 1)
        tg_clean = clean_tg_username(ag.get("telegram_username", ""))
        title = ag.get('title', 'کارشناس فروش و مشاوره')
        phone = ag.get('phone', '---')
        hours = ag.get('working_hours', '۹ الی ۲۳')

        block = (
            f"<blockquote>👤 <b>کارشناس {num_fa}: {ag.get('name')}</b>\n"
            f"▫️ <b>سمت:</b> {title}\n"
            f"▫️ <b>آیدی تلگرام:</b> @{tg_clean}\n"
            f"▫️ <b>شماره تماس:</b> <code>{phone}</code>\n"
            f"▫️ <b>ساعت پاسخگویی:</b> <code>{hours}</code></blockquote>"
        )
        agent_blocks.append(block)

    footer = (
        "\n\n👇 <i>جهت ورود به وبسایت، ارتباط سریع در دایرکت تلگرام یا تماس تلفنی، دکمه‌های زیر را لمس فرمایید:</i>"
    )

    return header + "\n\n".join(agent_blocks) + footer


def support_keyboard(agents: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """ساخت دکمه‌های شیشه‌ای تماس و دایرکت تلگرام برای خریدار (زیر هم)"""
    buttons = []

    # دکمه رسمی وبسایت ما (مالک، سرمایه‌گذار و اسپانسر ربات) در بالاترین اولویت
    buttons.append([
        InlineKeyboardButton("🌐 وبسایت رسمی ما (aegkala.com)", url=SPONSOR_WEBSITE_URL)
    ])

    for ag in agents:
        tg_clean = clean_tg_username(ag.get("telegram_username", ""))
        name = ag.get("name", "پشتیبان")
        aid = ag.get("id")

        direct_url = f"https://t.me/{tg_clean}"
        buttons.append([
            InlineKeyboardButton(f"💬 دایرکت تلگرام: {name}", url=direct_url)
        ])
        buttons.append([
            InlineKeyboardButton(f"📞 تماس تلفنی با {name}", callback_data=f"supp_call|{aid}")
        ])

    buttons.append([
        InlineKeyboardButton("ℹ️ راهنمای جامع خرید و ضمانت", callback_data="guide_main")
    ])
    buttons.append([
        InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")
    ])
    return InlineKeyboardMarkup(buttons)


async def show_support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش صفحه پشتیبانی و مشاوره به خریدار به صورت پنجره اختصاصی"""
    # ابتدا اطمینان از وجود داده‌های پیش‌فرض در دیتابیس
    await db.seed_default_support_agents()
    agents = await db.get_support_agents(active_only=True)

    text = format_support_message(agents)
    kb = support_keyboard(agents)

    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            # در صورتی که پیام قبلی عکس‌دار یا غیرقابل ویرایش متنی بود
            await update.callback_query.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
            return
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def support_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت رویدادهای کلیک بخش پشتیبانی خریدار (پنجره تک‌پیامی درجا)"""
    query = update.callback_query
    data = query.data
    try:
        await query.answer()
    except Exception:
        pass

    if data == "close_window":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    elif data == "show_support":
        await show_support_command(update, context)

    elif data.startswith("supp_call|"):
        agent_id = int(data.split("|")[1])
        agent = await db.get_support_agent_by_id(agent_id)
        if not agent:
            await query.message.reply_text("❌ اطلاعات کارشناس یافت نشد.")
            return

        name = agent.get("name")
        phone = agent.get("phone")
        hours = agent.get("working_hours", "۹ الی ۲۳")
        tg_clean = clean_tg_username(agent.get("telegram_username", ""))

        info_text = (
            f"📞 <b>اطلاعات تماس مستقیم با {name}:</b>\n\n"
            f"<blockquote>👤 <b>سمت:</b> {agent.get('title', 'کارشناس فروش')}\n"
            f"📱 <b>شماره موبایل:</b> <code>{phone}</code>\n"
            f"🕒 <b>ساعت پاسخگویی:</b> <code>{hours}</code>\n"
            f"💬 <b>دایرکت تلگرام:</b> @{tg_clean}</blockquote>\n\n"
            f"💡 <i>جهت تماس تلفنی یا کپی شماره، روی عدد شماره موبایل بالا ضربه بزنید.</i>"
        )
        call_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💬 دایرکت تلگرام {name}", url=f"https://t.me/{tg_clean}")],
            [InlineKeyboardButton("🌐 وبسایت رسمی ما (aegkala.com)", url=SPONSOR_WEBSITE_URL)],
            [InlineKeyboardButton("🔙 بازگشت به لیست کارشناسان", callback_data="show_support")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]
        ])
        try:
            await query.edit_message_text(info_text, reply_markup=call_kb, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(info_text, reply_markup=call_kb, parse_mode="HTML")


# =====================================================================
# ⚙️ بخش مدیریت کارشناسان در پنل ادمین (Admin Management)
# =====================================================================

def admin_support_list_keyboard(agents: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """کیبورد لیست کارشناسان در پنل مدیریت"""
    buttons = []
    for ag in agents:
        aid = ag.get("id")
        name = ag.get("name")
        status_icon = "🟢" if ag.get("is_active", 1) == 1 else "🔴"
        buttons.append([
            InlineKeyboardButton(f"{status_icon} {name} ({ag.get('title', '')[:20]})", callback_data=f"admsupp_view|{aid}")
        ])

    buttons.append([InlineKeyboardButton("➕ افزودن کارشناس جدید", callback_data="admsupp_add")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت به پنل اصلی ادمین", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(buttons)


async def admin_support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی مدیریت کارشناسان پشتیبانی (فقط ادمین اصلی)"""
    user = update.effective_user
    if not is_owner(user.id):
        if update.callback_query:
            await update.callback_query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی (مالک) می‌باشد.", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔️ دسترسی غیرمجاز! این بخش تنها در اختیارات ادمین اصلی می‌باشد.")
        return

    await db.seed_default_support_agents()
    agents = await db.get_support_agents(active_only=False)

    if not agents:
        text = (
            "👥 <b>مدیریت کارشناسان پشتیبانی و مشاوره فروش</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 تعداد کل کارشناسان ثبت‌شده: <b>۰ نفر</b>\n\n"
            "⚠️ <i>هنوز کارشناسی در سیستم ثبت نشده است.</i>\n"
            "👇 <i>جهت افزودن کارشناس جدید، دکمه «➕ افزودن کارشناس جدید» را لمس فرمایید:</i>"
        )
    else:
        text = (
            "👥 <b>مدیریت کارشناسان پشتیبانی و مشاوره فروش</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 تعداد کل کارشناسان ثبت‌شده: <b>{len(agents)} نفر</b>\n"
            "▫️ وضعیت 🟢: فعال و قابل مشاهده برای خریداران\n"
            "▫️ وضعیت 🔴: غیرفعال (مرخصی یا عدم پاسخگویی)\n\n"
            "👇 <i>جهت مشاهده جزئیات، ویرایش، حذف یا فعال‌سازی روی کارشناس مربوطه کلیک فرمایید:</i>"
        )
    kb = admin_support_list_keyboard(agents)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def admin_support_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت تعاملات ادمین با بخش کارشناسان (فقط ادمین اصلی)"""
    query = update.callback_query
    user = update.effective_user
    if not is_owner(user.id):
        await query.answer("⛔️ این بخش تنها در اختیارات ادمین اصلی (مالک) می‌باشد.", show_alert=True)
        return

    data = query.data
    await query.answer()

    if data == "adm_manage_support":
        await admin_support_menu(update, context)

    elif data.startswith("admsupp_view|"):
        aid = int(data.split("|")[1])
        agent = await db.get_support_agent_by_id(aid)
        if not agent:
            await query.message.reply_text("❌ کارشناس یافت نشد.")
            return

        status_text = "🟢 فعال (در حال نمایش به کاربران)" if agent.get("is_active") == 1 else "🔴 غیرفعال (مخفی)"
        toggle_btn_text = "🔴 غیرفعال کردن" if agent.get("is_active") == 1 else "🟢 فعال کردن"
        tg_clean = clean_tg_username(agent.get("telegram_username", ""))

        msg = (
            f"👤 <b>اطلاعات کارشناس پشتیبانی:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"▫️ <b>نام و نام خانوادگی:</b> {agent.get('name')}\n"
            f"▫️ <b>سمت / حوزه مشاوره:</b> {agent.get('title')}\n"
            f"▫️ <b>آیدی دایرکت تلگرام:</b> @{tg_clean}\n"
            f"▫️ <b>شماره موبایل:</b> <code>{agent.get('phone')}</code>\n"
            f"▫️ <b>ساعات کاری:</b> {agent.get('working_hours')}\n"
            f"▫️ <b>وضعیت کنونی:</b> {status_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_btn_text, callback_data=f"admsupp_toggle|{aid}")],
            [InlineKeyboardButton("❌ حذف کارشناس", callback_data=f"admsupp_del|{aid}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست کارشناسان", callback_data="adm_manage_support")]
        ])
        await query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")

    elif data.startswith("admsupp_toggle|"):
        aid = int(data.split("|")[1])
        await db.toggle_support_agent_active(aid)
        await query.answer("✅ وضعیت کارشناس با موفقیت تغییر یافت.")
        # بارگذاری مجدد کارت کارشناس
        data = f"admsupp_view|{aid}"
        agent = await db.get_support_agent_by_id(aid)
        if agent:
            status_text = "🟢 فعال (در حال نمایش به کاربران)" if agent.get("is_active") == 1 else "🔴 غیرفعال (مخفی)"
            toggle_btn_text = "🔴 غیرفعال کردن" if agent.get("is_active") == 1 else "🟢 فعال کردن"
            tg_clean = clean_tg_username(agent.get("telegram_username", ""))
            msg = (
                f"👤 <b>اطلاعات کارشناس پشتیبانی:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"▫️ <b>نام و نام خانوادگی:</b> {agent.get('name')}\n"
                f"▫️ <b>سمت / حوزه مشاوره:</b> {agent.get('title')}\n"
                f"▫️ <b>آیدی دایرکت تلگرام:</b> @{tg_clean}\n"
                f"▫️ <b>شماره موبایل:</b> <code>{agent.get('phone')}</code>\n"
                f"▫️ <b>ساعات کاری:</b> {agent.get('working_hours')}\n"
                f"▫️ <b>وضعیت کنونی:</b> {status_text}\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(toggle_btn_text, callback_data=f"admsupp_toggle|{aid}")],
                [InlineKeyboardButton("❌ حذف کارشناس", callback_data=f"admsupp_del|{aid}")],
                [InlineKeyboardButton("🔙 بازگشت به لیست کارشناسان", callback_data="adm_manage_support")]
            ])
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")

    elif data.startswith("admsupp_del|"):
        aid = int(data.split("|")[1])
        await db.delete_support_agent(aid)
        await query.answer("🗑 کارشناس با موفقیت حذف گردید.")
        await admin_support_menu(update, context)

    elif data == "admsupp_add":
        context.user_data["awaiting_support_agent_step"] = "name"
        context.user_data["new_agent_data"] = {}
        prompt = (
            "➕ <b>افزودن کارشناس پشتیبانی جدید (مرحله ۱ از ۵):</b>\n\n"
            "لطفاً <b>نام و نام خانوادگی</b> کارشناس را تایپ و ارسال فرمایید:\n"
            "<i>(مثال: مهندس کاظمی یا آقای حسینی)</i>\n\n"
            "❌ جهت انصراف: /cancel"
        )
        await query.message.reply_text(prompt, parse_mode="HTML")


async def handle_admin_support_agent_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """پردازش ورودی‌های مرحله‌به‌مرحله ادمین برای ثبت کارشناس جدید"""
    step = context.user_data.get("awaiting_support_agent_step")
    if not step:
        return False

    text = update.message.text.strip() if update.message.text else ""
    if text == "/cancel":
        context.user_data.pop("awaiting_support_agent_step", None)
        context.user_data.pop("new_agent_data", None)
        await update.message.reply_text("❌ عملیات افزودن کارشناس لغو گردید.")
        return True

    new_data = context.user_data.get("new_agent_data", {})

    if step == "name":
        new_data["name"] = text
        context.user_data["awaiting_support_agent_step"] = "title"
        await update.message.reply_text(
            f"✅ نام ثبت شد: <b>{text}</b>\n\n"
            f"<b>مرحله ۲ از ۵:</b>\n"
            f"لطفاً <b>سمت یا حوزه مشاوره</b> کارشناس را وارد فرمایید:\n"
            f"<i>(مثال: مشاوره تلویزیون و صوتی تصویری یا مشاوره لوازم خانگی بزرگ)</i>",
            parse_mode="HTML"
        )
        return True

    elif step == "title":
        new_data["title"] = text
        context.user_data["awaiting_support_agent_step"] = "telegram"
        await update.message.reply_text(
            f"✅ سمت ثبت شد: <b>{text}</b>\n\n"
            f"<b>مرحله ۳ از ۵:</b>\n"
            f"لطفاً <b>آیدی دایرکت تلگرام</b> کارشناس را وارد فرمایید:\n"
            f"<i>(مثال: <code>@Kazemi_Aikala</code> یا <code>Kazemi_Aikala</code>)</i>",
            parse_mode="HTML"
        )
        return True

    elif step == "telegram":
        tg_clean = clean_tg_username(text)
        new_data["telegram_username"] = tg_clean
        context.user_data["awaiting_support_agent_step"] = "phone"
        await update.message.reply_text(
            f"✅ آیدی تلگرام ثبت شد: <b>@{tg_clean}</b>\n\n"
            f"<b>مرحله ۴ از ۵:</b>\n"
            f"لطفاً <b>شماره موبایل مستقیم</b> کارشناس را وارد فرمایید:\n"
            f"<i>(مثال: <code>09181234567</code>)</i>",
            parse_mode="HTML"
        )
        return True

    elif step == "phone":
        new_data["phone"] = text
        context.user_data["awaiting_support_agent_step"] = "hours"
        await update.message.reply_text(
            f"✅ شماره تماس ثبت شد: <code>{text}</code>\n\n"
            f"<b>مرحله ۵ از ۵ (پایانی):</b>\n"
            f"لطفاً <b>ساعات پاسخگویی</b> کارشناس را وارد فرمایید:\n"
            f"<i>(مثال: <code>۹ الی ۲۳</code> یا <code>۱۰ الی ۲۲</code>)</i>",
            parse_mode="HTML"
        )
        return True

    elif step == "hours":
        new_data["working_hours"] = text
        # ذخیره نهایی در دیتابیس
        aid = await db.add_support_agent(
            name=new_data.get("name", ""),
            title=new_data.get("title", "کارشناس فروش"),
            telegram_username=new_data.get("telegram_username", ""),
            phone=new_data.get("phone", ""),
            working_hours=new_data.get("working_hours", "۹ الی ۲۳"),
            sort_order=0,
            is_active=1
        )

        context.user_data.pop("awaiting_support_agent_step", None)
        context.user_data.pop("new_agent_data", None)

        tg_clean = new_data.get("telegram_username", "")
        success_msg = (
            f"🎉 <b>کارشناس پشتیبانی جدید با موفقیت ثبت و فعال گردید!</b>\n\n"
            f"👤 <b>نام:</b> {new_data.get('name')}\n"
            f"▫️ <b>سمت:</b> {new_data.get('title')}\n"
            f"▫️ <b>آیدی تلگرام:</b> @{tg_clean}\n"
            f"▫️ <b>شماره موبایل:</b> <code>{new_data.get('phone')}</code>\n"
            f"▫️ <b>ساعت کاری:</b> {new_data.get('working_hours')}\n\n"
            f"✨ <i>این کارشناس هم‌اکنون در بخش پشتیبانی برای تمامی خریداران قابل مشاهده است.</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 مشاهده لیست کارشناسان", callback_data="adm_manage_support")],
            [InlineKeyboardButton("🔙 بازگشت به پنل ادمین", callback_data="adm_back_panel")]
        ])
        await update.message.reply_text(success_msg, reply_markup=kb, parse_mode="HTML")
        return True

    return False


def register_support_handlers(app):
    """ثبت تمام هندلرهای بخش پشتیبانی و مشاوره در برنامه تلگرام"""
    app.add_handler(CommandHandler("support", show_support_command))
    app.add_handler(CallbackQueryHandler(support_callback_handler, pattern="^(show_support|supp_call\\||close_window$)"))
    app.add_handler(CallbackQueryHandler(admin_support_callback_handler, pattern="^(adm_manage_support|admsupp_)"))
