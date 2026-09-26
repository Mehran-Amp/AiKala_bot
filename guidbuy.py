"""
ماژول اختصاصی راهنمای جامع خرید و ضمانت برای ربات @AiKala_bot هوشمند کالا
شامل متن‌ها، کیبوردها و هندلرهای تعاملی بخش راهنما
"""

import logging
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
except ImportError:
    Update = InlineKeyboardButton = InlineKeyboardMarkup = object
    class MockObj:
        DEFAULT_TYPE = object
    ContextTypes = MockObj
    CallbackQueryHandler = CommandHandler = object
from config import SUPPORT_USERNAME

logger = logging.getLogger(__name__)

# ─── متن‌های راهنمای جامع خرید و ضمانت ───

GUIDE_MAIN_TEXT = (
    "💎 <b>راهنمای جامع خرید، ضمانت و تحویل کالا</b>\n\n"
    "<blockquote>🛡 <b>تضمین ۱۰۰٪ امنیت سرمایه و خرید بدون واسطه:</b>\n"
    "کلیه سفارشات دارای ضمانت اصالت کتبی و حق بررسی کامل سلامت فیزیکی و تست کارکرد دستگاه در حضور باربر قبل از تسویه نهایی می‌باشند.</blockquote>\n\n"
    "👇 <i>جهت مطالعه قوانین ارسال، شرایط گارانتی و پاسخ به سوالات متداول، یکی از بخش‌های زیر را لمس فرمایید:</i>"
)

GUIDE_STEPS_TEXT = (
    "🛒 <b>راهنمای گام‌به‌گام ثبت سفارش تا تحویل کالا:</b>\n\n"
    "<b>۱️⃣ استعلام و انتخاب مدل:</b>\n"
    "پس از جستجو یا انتخاب کالا در ربات، با اعلام شهر مقصد، قیمت قطعی روز و شرایط دقیق ارسال را از کارشناسان دریافت می‌فرمایید.\n\n"
    "<b>۲️⃣ ثبت مشخصات و صدور پیش‌فاکتور دیجیتال:</b>\n"
    "با ثبت آدرس و شماره تماس، پیش‌فاکتور رسمی شامل مشخصات کامل دستگاه (مدل دقیق، رنگ، شماره سریال و شیوه ارسال) صادر می‌گردد.\n\n"
    "<b>۳️⃣ پرداخت وجه بر اساس شیوه ارسال:</b>\n"
    "<blockquote>🚚 <b>لوازم خانگی بزرگ و سنگین (باربری اختصاصی):</b>\n"
    "تنها ۸٪ به عنوان بیعانه بارگیری و بیمه بار پرداخت شده و مابقی وجه پس از تحویل، تست سلامت فیزیکی و روشن شدن دستگاه در محل تسویه خواهد شد.</blockquote>\n"
    "<blockquote>📮 <b>محصولات و لوازم ریز (پست پیشتاز):</b>\n"
    "اقلام سبک آشپزخانه با پست پیشتاز ارسال می‌گردند. طبق قوانین اداره پست، <b>کل مبلغ فاکتور پیش از ارسال تسویه می‌گردد</b> و بلافاصله کد رهگیری رسمی پستی برای خریدار صادر می‌شود.</blockquote>\n\n"
    "<b>۴️⃣ ارسال سریع و ایمن:</b>\n"
    "سفارشات باربری با خودرو و بارچین اختصاصی درب منزل (۲۴ تا ۴۸ ساعت کاری) و سفارشات پستی در بسته‌بندی ضدضربه ارسال می‌شوند.\n\n"
    "<b>۵️⃣ تست سلامت فیزیکی و تحویل:</b>\n"
    "در روش باربری دستگاه در حضور راننده بازگشایی و تست می‌شود؛ در روش پستی کلیه مرسولات دارای بیمه کامل سلامت هستند.\n\n"
    "<b>۶️⃣ تسویه نهایی:</b>\n"
    "در سفارش‌های باربری، مانده‌حساب پس از تایید سلامت ظاهری و روشن شدن دستگاه با راننده تسویه می‌گردد."
)

GUIDE_GUARANTEE_TEXT = (
    "🛡 <b>ضمانت اصالت، بررسی و تست کالا هنگام تحویل و خرید حضوری:</b>\n\n"
    "<blockquote>✨ <b>تضمین ۱۰۰٪ اصالت کالا (اورجینال کتبی):</b>\n"
    "تمامی کالاهای فروشگاه کاملاً اورجینال، دست‌نخورده و همراه با کارتن و لوازم جانبی فابریک کمپانی سازنده هستند. اصالت دستگاه به صورت کتبی در فاکتور قید شده و در صورت هرگونه مغایرت، دستگاه بدون قید و شرط مرجوع می‌شود.</blockquote>\n\n"
    "<blockquote>🔍 <b>بررسی کامل فیزیکی و تست سلامت فنی هنگام تحویل:</b>\n"
    "هنگام تحویل سفارش، شما مجاز به بررسی دقیق و همه‌جانبه دستگاه از لحاظ سلامت فیزیکی و تست سلامت فنی هستید؛ حتی می‌توانید کالا را در حضور باربر به برق متصل نموده و پس از اطمینان کامل از اصالت، صحت کارکرد و سلامت دستگاه، با باربر تسویه فرمایید.</blockquote>\n\n"
    "<blockquote>🏢 <b>امکان خرید و تحویل حضوری در انبار/فروشگاه:</b>\n"
    "خریداران گرامی که تمایل دارند کالا را پیش از خرید از نزدیک بررسی فرمایند، می‌توانند با هماهنگی قبلی با واحد پشتیبانی مراجعه نموده و پس از بازبینی کالا و بررسی شماره سریال و اصالت قطعات، تحویل و تسویه نمایند.</blockquote>"
)

GUIDE_SHIPPING_TEXT = (
    "🚚 <b>شیوه‌های ارسال، بیمه سلامت کالا و تحویل سفارشات:</b>\n\n"
    "<blockquote>🚚 <b>۱️⃣ لوازم خانگی بزرگ و سنگین (باربری اختصاصی):</b>\n"
    "▫️ <b>اقلام مشمول:</b> یخچال، ساید، لباسشویی، ظرفشویی، تلویزیون و کولر گازی\n"
    "▫️ <b>شرایط پرداخت:</b> ۸٪ بیعانه جهت بارگیری + <b>تسویه مانده وجه درب منزل</b> پس از تست فیزیکی و اتصال به برق\n"
    "▫️ <b>ناوگان:</b> حمل با خودرو و بارچین اختصاصی درب منزل (۲۴ الی ۴۸ ساعت)</blockquote>\n\n"
    "<blockquote>📮 <b>۲️⃣ محصولات و لوازم ریز (پست پیشتاز):</b>\n"
    "▫️ <b>اقلام مشمول:</b> سرخ‌کن، قهوه‌ساز، خردکن، ساندبار، جاروبرقی، مایکروفر و لوازم برقی کوچک\n"
    "▫️ <b>شرایط پرداخت:</b> طبق ضوابط شرکت ملی پست مبنی بر عدم امکان دریافت وجه در مقصد، <b>تسویه به صورت کامل پیش از ارسال انجام می‌شود</b>\n"
    "▫️ <b>پیگیری:</b> صدور فوری کد رهگیری ۲۴ رقمی پستی در سامانه</blockquote>\n\n"
    "<blockquote>📦 <b>پوشش کامل بیمه سلامت فیزیکی:</b>\n"
    "تمامی مرسولات از مبدا تا زمان تحویل تحت پوشش کامل بیمه هستند و در صورت هرگونه آسیب، دستگاه بلافاصله و بدون ریالی هزینه برای مشتری تعویض می‌گردد.</blockquote>\n\n"
    "<blockquote>🔄 <b>قوانین انصراف و لغو سفارش:</b>\n"
    "▫️ انصراف قبل از بارگیری یا ارسال پستی: کل مبلغ واریزی بدون کسر هزینه و به صورت آنی مسترد می‌گردد.\n"
    "▫️ انصراف پس از ارسال بدون نقص فنی: صرفاً هزینه کرایه رفت‌وبرگشت طبق بارنامه کسر و مابقی عودت داده می‌شود.</blockquote>"
)

GUIDE_WARRANTY_TEXT = (
    "📜 <b>شرایط گارانتی شرکتی و خدمات پس از فروش:</b>\n\n"
    "<blockquote>🛡 <b>گارانتی معتبر ۱۸ الی ۲۴ ماهه کشوری:</b>\n"
    "کلیه لوازم خانگی ارائه شده قابلیت پوشش توسط شرکت‌های معتبر گارانتی سراسری (شامل ۱۸ تا ۲۴ ماه ضمانت طلایی قطعات و ۵ سال خدمات پس از فروش) را دارا می‌باشند.</blockquote>\n\n"
    "<blockquote>👨‍🔧 <b>نحوه نصب و فعال‌سازی گارانتی:</b>\n"
    "جهت حفظ اعتبار گارانتی، پس از تحویل کالا و تسویه حساب، شماره تماس سامانه مرکزی شرکت گارانتی در اختیارتان قرار می‌گیرد تا تکنسین مجاز در محل حضور یافته، دستگاه را راه‌اندازی و برگه ضمانت‌نامه را مهر نماید.</blockquote>\n\n"
    "<blockquote>⚙️ <b>تضمین تامین قطعات اصلی:</b>\n"
    "تمامی مدل‌های ارائه‌شده از برندهای معتبر بین‌المللی بوده و قطعات اصلی فابریک آن‌ها در بازار کشور به شکل تضمین‌شده تامین است.</blockquote>"
)

GUIDE_FAQ_TEXT = (
    "❓ <b>پرسش‌های متداول خریداران (FAQ):</b>\n\n"
    "<b>۱️⃣ چگونه از اصالت کالا و مدل نامبر مطمئن شوم؟</b>\n"
    "<blockquote>مدل نامبر و شماره سریال حک‌شده روی برچسب بدنه کالا با کاتالوگ سایت جهانی سازنده تطبیق داده شده و اصالت آن به صورت کتبی در فاکتور تضمین می‌شود.</blockquote>\n\n"
    "<b>۲️⃣ نحوه ارسال برای محصولات ریز و درشت چه تفاوتی دارد؟</b>\n"
    "<blockquote>لوازم خانگی درشت با باربری اختصاصی و پرداخت ۸٪ بیعانه ارسال شده و تسویه درب منزل انجام می‌گیرد؛ اما محصولات ریز با پست پیشتاز ارسال شده و طبق مقررات پستی، تسویه کامل پیش از ارسال صورت می‌گیرد.</blockquote>\n\n"
    "<b>۳️⃣ اگر دستگاه در مسیر باربری یا پست آسیب ببیند چه می‌شود؟</b>\n"
    "<blockquote>تمامی مرسولات دارای بیمه اختصاصی هستند؛ در صورت هرگونه آسیب دیدگی، کالا بدون دریافت هزینه‌ای از خریدار با دستگاه کاملاً سالم و نو تعویض می‌گردد.</blockquote>\n\n"
    "<b>۴️⃣ آیا باز کردن کارتن کالا در حضور راننده مجاز است؟</b>\n"
    "<blockquote>بله؛ باز کردن جعبه در حضور راننده باربری جهت بررسی سلامت ظاهری و روشن شدن دستگاه مجاز است و مانعی برای گارانتی شرکتی ایجاد نمی‌کند.</blockquote>"
)

# ─── کیبوردهای ماژول راهنما ───

def help_menu_keyboard() -> InlineKeyboardMarkup:
    """کیبورد سرفصل‌های راهنمای جامع خرید و ضمانت"""
    buttons = [
        [InlineKeyboardButton("🛒 مراحل قدم‌به‌قدم خرید و تسویه", callback_data="guide_steps")],
        [InlineKeyboardButton("🛡️ ضمانت اصالت، تست تحویل و خرید حضوری", callback_data="guide_guarantee")],
        [InlineKeyboardButton("🚚 ارسال، بیمه بار و تست در حضور راننده", callback_data="guide_shipping")],
        [InlineKeyboardButton("📜 گارانتی شرکتی و خدمات پس از فروش", callback_data="guide_warranty")],
        [InlineKeyboardButton("❓ پرسش‌های متداول خریداران (FAQ)", callback_data="guide_faq")],
        [InlineKeyboardButton("📞 پشتیبانی و مشاوره", callback_data="show_support")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(buttons)

def guide_section_keyboard() -> InlineKeyboardMarkup:
    """کیبورد ناوبری زیرصفحات راهنما"""
    buttons = [
        [InlineKeyboardButton("🔙 بازگشت به فهرست راهنما", callback_data="guide_main")],
        [InlineKeyboardButton("📞 پشتیبانی و مشاوره", callback_data="show_support")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(buttons)

# ─── هندلرها ───

async def show_guide_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش صفحه اصلی راهنمای خرید و ضمانت"""
    if update.message:
        await update.message.reply_text(GUIDE_MAIN_TEXT, reply_markup=help_menu_keyboard(), parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(GUIDE_MAIN_TEXT, reply_markup=help_menu_keyboard(), parse_mode="HTML")

async def guide_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه‌های مختلف بخش راهنما"""
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "guide_main":
        await query.edit_message_text(GUIDE_MAIN_TEXT, reply_markup=help_menu_keyboard(), parse_mode="HTML")
    elif data == "guide_steps":
        await query.edit_message_text(GUIDE_STEPS_TEXT, reply_markup=guide_section_keyboard(), parse_mode="HTML")
    elif data == "guide_guarantee":
        await query.edit_message_text(GUIDE_GUARANTEE_TEXT, reply_markup=guide_section_keyboard(), parse_mode="HTML")
    elif data == "guide_shipping":
        await query.edit_message_text(GUIDE_SHIPPING_TEXT, reply_markup=guide_section_keyboard(), parse_mode="HTML")
    elif data == "guide_warranty":
        await query.edit_message_text(GUIDE_WARRANTY_TEXT, reply_markup=guide_section_keyboard(), parse_mode="HTML")
    elif data == "guide_faq":
        await query.edit_message_text(GUIDE_FAQ_TEXT, reply_markup=guide_section_keyboard(), parse_mode="HTML")

def register_guide_handlers(app):
    """ثبت تمام هندلرهای مربوط به راهنمای خرید در برنامه تلگرام"""
    app.add_handler(CommandHandler("help", show_guide_command))
    app.add_handler(CommandHandler("guide", show_guide_command))
    app.add_handler(CallbackQueryHandler(guide_callback_handler, pattern="^guide_"))
