"""
ماژول مشاور هوشمند خرید با گوگل جمینای (Gemini Shopping Advisor)
برای فروشگاه هوشمند کالا (@AiKala_bot)

ویژگی‌ها و چارچوب‌ها:
۱. فقط و فقط از Google Gemini API استفاده می‌کند (مدل‌های پرسرعت gemini-flash-lite-latest و نسخه ۳).
۲. تمرکز انحصاری بر محصولات و کاتالوگ فروشگاه هوشمند کالا و رد قاطع سوالات غیرمرتبط جهت جلوگیری از مصرف بیهوده توکن.
۳. اولویت‌بندی ظریف و هوشمندانه برند اصیل و آلمانی آاگ (AEG) بدون اصرار نامتعارف یا ساختگی.
۴. اعتمادسازی قوی با شیوه خرید هوشمند کالا: ضمانت اصالت کتبی ۱۰۰٪، پرداخت درب منزل پس از تست فیزیکی و روشن کردن در حضور باربر، و ۱۸ الی ۲۴ ماه گارانتی کشوری.
۵. پاسخ‌های شفاف، مختصر، کاربردی و اقناع‌کننده همراه با استخراج و ارائه دکمه‌های مستقیم مشاهده و خرید کالاهای مرتبط.
"""

import os
import re
import json
import logging
import asyncio
import urllib.request
import urllib.parse
from typing import Optional, List, Dict, Any, Tuple

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import ContextTypes
except ImportError:
    Update = InlineKeyboardButton = InlineKeyboardMarkup = ReplyKeyboardMarkup = KeyboardButton = object
    class MockObj:
        DEFAULT_TYPE = object
    ContextTypes = MockObj

from gemini_enricher import get_gemini_api_key
from search_engine import JSON_PRODUCTS, search_products, BRAND_SYNONYMS
from keyboards import make_safe_cb, resolve_safe_cb

logger = logging.getLogger(__name__)

# مدل‌های مجاز جمینای به ترتیب اولویت و پایداری سهمیه
ADVISOR_GEMINI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite"
]

ADVISOR_WELCOME_TEXT = (
    "🧠 <b>مشاور هوشمند خرید هوشمند کالا (Google Gemini AI)</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "سلام! من کارشناس و مشاور هوشمند خرید شما در فروشگاه <b>هوشمند کالا</b> هستم.\n\n"
    "<blockquote>📦 <b>موجودی و قیمت لحظه‌ای محصولات:</b>\n"
    "▫️ تمامی قیمت‌ها و وضعیت موجودی کاتالوگ فروشگاه به صورت مستقیم و روزانه بروزرسانی می‌شوند.\n"
    "▫️ بررسی و مقایسه فنی انواع برندها و مدل‌ها متناسب با متراژ، کاربری و بودجه شما\n"
    "▫️ خرید مطمئن با ضمانت اصالت ۱۰۰٪ کتبی، فاکتور معتبر و تسویه پس از تست درب منزل</blockquote>\n\n"
    "<blockquote>💡 <b>نحوه عملکرد پیام‌ها و جستجو:</b>\n"
    "▫️ ارسال مستقیم هرگونه متن در چت ربات، صرفاً به عنوان <b>جستجوی کالا در کاتالوگ</b> پردازش می‌شود.\n"
    "▫️ جهت دریافت <b>مشاوره تخصصی هوش مصنوعی</b>، همواره از دکمه «🧠 مشاور هوشمند خرید» یا گزینه‌های سریع زیر استفاده فرمایید.</blockquote>\n\n"
    "💬 <i>اکنون می‌توانید سوال خود، نام کالا، برند یا بودجه مدنظرتان را تایپ نمایید یا یکی از موضوعات زیر را لمس کنید:</i>"
)


def get_advisor_menu_keyboard() -> InlineKeyboardMarkup:
    """کیبورد راهنما و دسترسی سریع به سوالات پرتکرار مشاوره"""
    buttons = [
        [
            InlineKeyboardButton("🚚 نحوه ارسال، تسویه درب منزل و باربری", callback_data="adv_q|shipping"),
            InlineKeyboardButton("📜 شرایط گارانتی و فاکتور فوری", callback_data="adv_q|warranty")
        ],
        [
            InlineKeyboardButton("🧹 مشاوره خرید جاروبرقی باکیفیت", callback_data="adv_q|vacuum"),
            InlineKeyboardButton("🧺 بهترین ماشین لباسشویی", callback_data="adv_q|wash")
        ],
        [
            InlineKeyboardButton("🍽 تفاوت مدل‌های ظرفشویی", callback_data="adv_q|dish"),
            InlineKeyboardButton("📺 راهنمای سایز و خرید تلویزیون", callback_data="adv_q|tv")
        ],
        [
            InlineKeyboardButton("💎 چرا لوازم خانگی اصیل آاگ (AEG)؟", callback_data="adv_q|aeg_intro")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def build_advisor_system_prompt() -> str:
    """تولید دستورالعمل دقیق هویتی و رفتاری مشاور خرید جمینای"""
    return (
        "تو مشاور ارشد و کارشناس خبره خرید فروشگاه هوشمند کالا (AiKala_bot) هستی.\n"
        "وظیفه اصلی تو: ارائه راهنمایی و مشاوره کاملاً فنی، بی‌طرفانه، کارشناسی و متمرکز بر سوال و نیاز دقیق خریدار بر اساس کالاهای واقعی کاتالوگ فروشگاه است.\n\n"
        "قوانین و چارچوب‌های اکید و تخطی‌ناپذیر:\n"
        "۱. احترام کامل به کاتالوگ و عدم ادعای کذب درباره عدم موجودی برندها:\n"
        "   - فروشگاه هوشمند کالا تنوع بسیار بالایی از برترین برندهای روز جهان را دارد (از جمله ال‌جی/LG، سامسونگ، سونی، بوش، آاگ/AEG، هایسنس، فیلیپس، گری و...).\n"
        "   - هرگز و تحت هیچ شرایطی ادعا نکن که برندی در فروشگاه موجود نیست یا تمرکز فروشگاه فقط روی یک برند خاص است! اگر کاربر درباره برند مشخصی (مثلاً ال‌جی، سامسونگ، سونی یا بوش) پرسید، مدل‌های آن برند در کاتالوگ را بررسی کرده و ویژگی‌های مثبت و منفی فنی آن را تشریح کن.\n\n"
        "۲. تمرکز ۹۰٪ بر پاسخ فنی، کاربردی و حل سوال خریدار (بدون تبلیغات زائد):\n"
        "   - پاسخ تو باید در درجه اول مستقیماً به سوال کاربر بپردازد (مثلاً اگر درباره کیفیت تلویزیون‌های ال‌جی پرسید، پنل‌های OLED و QNED و نانوسل ال‌جی، سیستم‌عامل webOS و امکانات گیمینگ آن را با دقت فنی توضیح بده و مدل‌های موجود آن را معرفی کن).\n"
        "   - از تکرار مکرر تبلیغات طولانی فروشگاه و بندهای اعتمادسازی در هر پیام اکیداً خودداری کن! توضیحات درباره فروشگاه و اعتماد نباید بیش از ۱ الی ۲ خط کوتاه و مختصر در پایان پاسخ باشد.\n"
        "   - اگر کاربر در متنش سوالی درباره چگونگی اعتماد، نحوه ثبت سفارش، بیعانه، نحوه ارسال یا گارانتی پرسید، آنگاه توضیحات کامل اعتمادسازی (سابقه ۲۰ ساله، فاکتور فوری، بیعانه جزئی، تسویه پس از تست درب منزل و گارانتی معتبر) را تشریح کن؛ در غیر این صورت فقط روی مشخصات فنی و مقایسه متمرکز باش.\n\n"
        "۳. جایگاه ویژه و بالاترین ارزش خرید برند اصیل آاگ (AEG):\n"
        "   - قانون اساسی: در تمام سوالات عمومی، مقایسه‌ای و انتخاب کالا در لوازم خانگی و آشپزخانه (به‌ویژه ظرفشویی، لباسشویی و جاروبرقی)، برند اصیل و مهندسی آلمان **آاگ (AEG)** همواره دارای **بالاترین ارزش خرید، برترین کیفیت متریال، مهندسی قطعات و طول عمر** در فروشگاه هوشمند کالا است.\n"
        "   - نحوه پاسخگویی: ابتدا همیشه باافتخار مدل‌های آاگ (AEG) را به عنوان گزینه برتر، پرچمدار و بالاترین ارزش خرید با برتری کیفی نسبت به رقبا معرفی کن. سپس به عنوان گزینه‌های بعدی سایر برندهای معتبر کاتالوگ (بوش، ال‌جی، سامسونگ) را با بیان نقاط قوتشان معرفی نما تا کاربر حق انتخاب کامل داشته باشد.\n"
        "   - در جمع‌بندی نهایی 'بیشترین ارزش خرید'، حتماً آاگ (AEG) را در رتبه اول معرفی کن (مثلاً ظرفشویی سری 8 یا 6 آاگ با فناوری‌های پیشرفته AirDry و SoftGrips و موتور Inverter Silent).\n"
        "   - تنها استثنا: اگر کاربر منحصراً و صریحاً فقط درباره یک برند مشخص (مثلاً فقط درباره تلویزیون سونی یا فقط یخچال سامسونگ) پرسید، روی همان برند پاسخ کامل بده، اما در سوالات مقایسه‌ای یا انتخاب بهترین کالا، آاگ را در صدر قرار بده.\n\n"
        "۴. تطابق صددرصدی موضوع کالا با سوال کاربر:\n"
        "   - اگر کاربر درباره تلویزیون پرسید، منحصراً تلویزیون؛ اگر درباره یخچال پرسید، منحصراً یخچال و فریزر؛ اگر لباسشویی پرسید، لباسشویی معرفی کن.\n\n"
        "۵. اصول اعتمادسازی فروشگاه هوشمند کالا (فقط به صورت بسیار کوتاه ۱-۲ خطی در پایان یا در صورت سوال کاربر):\n"
        "   - اشاره کوتاه به اینکه تمامی کالاها با ضمانت اصالت کتبی ۱۰۰٪، فاکتور رسمی فوری، ۱۸ تا ۲۴ ماه گارانتی کشوری و ارسال با باربری اختصاصی (بیعانه جزئی و تسویه درب منزل پس از تست سلامت کالا) عرضه می‌شوند.\n\n"
        "۶. ثبت مدل‌های پیشنهادی برای ساخت دکمه‌های خرید در ربات:\n"
        "   - حتماً در آخرین خط پاسخ، ۲ الی ۳ مدل دقیق از کاتالوگ که متناسب با موضوع سوال کاربر معرفی کردی را دقیقاً با این فرمت بنویس تا دکمه‌های خرید زیر پیام نمایش داده شوند:\n"
        "   [مدل‌های پیشنهادی: مدل ۱ | مدل ۲]"
    )


# نقشه‌برداری جامع کلمات کلیدی به دسته‌بندی‌های کاتالوگ
QUERY_CATEGORY_MAP: Dict[str, List[str]] = {
    "یخچال فریزر": ["یخچال", "فریزر", "ساید", "دوقلو", "یخچالی", "refrigerator", "side", "fridge"],
    "ماشین لباسشویی": ["لباسشویی", "لباس شویی", "لباسشوئی", "واشینگ", "washing"],
    "ماشین ظرفشویی": ["ظرفشویی", "ظرف شویی", "ظرفشوئی", "دیش واشر", "dishwasher"],
    "تلویزیون": ["تلویزیون", "تی وی", "tv", "اینچ", "inch", "oled", "qled", "qned", "led", "تلویزین"],
    "کولر گازی": ["کولر", "اسپلیت", "اسپیلت", "کولرگازی", "گازی", "btu", "سرمایش"],
    "لوازم ریز برقی": [
        "جارو", "جاروبرقی", "مخلوط کن", "خردکن", "سرخ کن", "هواپز", "غذاساز",
        "قهوه ساز", "اسپرسوساز", "چای ساز", "همزن", "چرخ گوشت", "اتو", "پلوپز",
        "آسیاب", "گوشت کوب", "لوازم ریز", "آشپزخانه", "لوازم پخت", "پخت و پز", "فر", "مایکروویو"
    ],
    "محصولات آاگ/AEG": ["آاگ", "aeg", "ای ای جی"]
}


def detect_query_category(query: str) -> Optional[str]:
    """تشخیص هوشمند دسته‌بندی موضوعی سوال کاربر"""
    q_lower = query.lower()
    for cat_name, kws in QUERY_CATEGORY_MAP.items():
        for kw in kws:
            if kw in q_lower:
                return cat_name
    return None


def detect_query_brand(query: str) -> Optional[str]:
    """تشخیص برند موردنظر کاربر در سوال با بررسی دقیق مرز کلمات و مترادف‌ها"""
    q_clean = query.lower()
    # استخراج توکن‌های مجزا با در نظر گرفتن نیم‌فاصله و علائم نگارشی
    tokens = set(re.findall(r'[\w\u200c]+', q_clean))
    candidates = []
    for brand_key, synonyms in BRAND_SYNONYMS.items():
        for syn in synonyms:
            syn_lower = syn.lower().strip()
            # اگر مترادف چند کلمه‌ای باشد
            if " " in syn_lower or "-" in syn_lower:
                if syn_lower in q_clean:
                    candidates.append((len(syn_lower), brand_key))
            else:
                # کلمه تک واژه‌ای مثل دل (dell) نباید بخشی از 'مدل' یا 'مدل‌های' باشد
                if syn_lower in tokens:
                    candidates.append((len(syn_lower), brand_key))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return None


def get_products_by_brand(brand_key: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """استخراج تمام محصولات متعلق به یک برند خاص با امکان فیلتر دسته‌بندی"""
    synonyms = [s.lower() for s in BRAND_SYNONYMS.get(brand_key, [brand_key])]
    matched = []
    for p in JSON_PRODUCTS:
        p_brand = (p.get("brand") or "").lower()
        p_name = (p.get("name") or "").lower()
        p_cat = (p.get("category_name") or p.get("category_key") or "")
        if category and category not in p_cat:
            continue
        if any(syn in p_brand or syn in p_name for syn in synonyms):
            matched.append(p)
    return matched


def extract_relevant_catalog_snippets(user_query: str, max_items: int = 14) -> Tuple[str, Optional[str], Optional[str]]:
    """استخراج بخش‌های دقیق و مرتبط از کاتالوگ واقعی بر اساس دسته‌بندی، برند و کوئری کاربر"""
    found_products = []
    q_clean = user_query.strip()
    detected_cat = detect_query_category(q_clean)
    detected_brand = detect_query_brand(q_clean)

    # ۱. اولویت اول: اگر کاربر برند خاصی را مدنظر قرار داده (ال‌جی، سامسونگ، بوش، سونی، گری و...)
    if detected_brand:
        brand_items = get_products_by_brand(detected_brand, detected_cat)
        found_products.extend(brand_items[:max_items])

    # ۲. استخراج مدل‌های شاخص آاگ در صورتی که کاربر اسمی از برند خاصی نبرده اما سوال عمومی یا لوازم باکیفیت دارد
    if not detected_brand:
        q_lower = q_clean.lower()
        is_aeg_relevant = any(k in q_lower for k in ["آاگ", "aeg", "آشپزخانه", "برند", "مارک", "کیفیت", "بهترین", "پیشنهاد", "جارو", "لباسشویی", "ظرفشویی", "فر", "مایکروویو", "ارزش", "خرید"])
        if is_aeg_relevant:
            aeg_items = [p for p in JSON_PRODUCTS if "آاگ" in (p.get("brand") or "") or "aeg" in (p.get("name") or "").lower()]
            if detected_cat:
                cat_aeg = []
                for p in aeg_items:
                    p_c = (p.get("category_name") or "") + " " + (p.get("category_key") or "")
                    p_n = p.get("name") or ""
                    # بررسی تطابق با دسته‌بندی موضوعی یا نام کالا (مانند ظرفشویی آاگ)
                    cat_short = detected_cat.replace("ماشین ", "").strip()
                    if detected_cat in p_c or cat_short in p_n:
                        cat_aeg.append(p)
                found_products.extend(cat_aeg[:3])
            else:
                found_products.extend(aeg_items[:3])

    # ۳. جستجوی مستقیم عبارت
    if len(found_products) < max_items:
        direct_hits = search_products(q_clean)
        for h in direct_hits:
            if detected_cat:
                h_cat = (h.get("category_name") or h.get("category_key") or "")
                h_name = h.get("name") or ""
                cat_short = detected_cat.replace("ماشین ", "").strip()
                if detected_cat not in h_cat and cat_short not in h_name:
                    continue
            if h not in found_products:
                found_products.append(h)
                if len(found_products) >= max_items:
                    break

    # ۴. جستجوی متنی بر اساس کلیدواژه‌های اصلی (حذف کلمات توقف عمومی)
    if len(found_products) < max_items:
        stop_words = {"برای", "برا", "چه", "پیشنهاد", "میدی", "میدید", "میخواستم", "میخوام", "بهترین", "خوب", "نفر", "یک", "رو", "در", "با", "از", "کدوم", "کدام", "چرا", "ندارید", "دارید", "هست", "قیمت"}
        meaningful_tokens = [w for w in q_clean.split() if len(w) > 1 and w.lower() not in stop_words]
        for token in meaningful_tokens:
            hits = search_products(token)
            for h in hits:
                if detected_cat:
                    h_cat = (h.get("category_name") or h.get("category_key") or "")
                    h_name = h.get("name") or ""
                    cat_short = detected_cat.replace("ماشین ", "").strip()
                    if detected_cat not in h_cat and cat_short not in h_name:
                        continue
                if h not in found_products:
                    found_products.append(h)
                    if len(found_products) >= max_items:
                        break
            if len(found_products) >= max_items:
                break

    # ۵. اگر دسته‌بندی تشخیص داده شده اما هنوز ظرفیت دارد، کاتالوگ همان دسته‌بندی را پر کنیم
    if detected_cat and len(found_products) < max_items:
        cat_matches = [
            p for p in JSON_PRODUCTS
            if detected_cat in (p.get("category_name") or "") or detected_cat in (p.get("category_key") or "")
        ]
        for p in cat_matches:
            if p not in found_products:
                found_products.append(p)
                if len(found_products) >= max_items:
                    break

    # ۶. در صورت عدم تشخیص دسته‌بندی و خالی بودن، جستجوی عمومی در کاتالوگ
    if not found_products:
        search_hits = search_products(q_clean)
        if search_hits:
            found_products.extend(search_hits[:max_items])

    if not found_products:
        # نمونه عمومی متنوع از دسته‌بندی‌های مختلف
        found_products = JSON_PRODUCTS[:max_items]

    snippets = []
    for p in found_products[:max_items]:
        pid = p.get("product_id", "")
        name = p.get("name", "")
        price = p.get("price", 0)
        brand = p.get("brand", "")
        cat = p.get("category_name", "")
        specs = p.get("specs") or p.get("ai_specs") or {}
        specs_str = "، ".join([f"{k}: {v}" for k, v in list(specs.items())[:3]]) if isinstance(specs, dict) else ""
        price_str = f"{price:,} تومان" if price else "تماس با واحد فروش"
        snippets.append(f"- کد {pid} | {name} (برند: {brand}، دسته: {cat}) | قیمت: {price_str} | مشخصات: {specs_str}")

    return "\n".join(snippets), detected_cat, detected_brand


async def consult_gemini_shopping_advisor(
    user_query: str,
    context_product: Optional[Dict[str, Any]] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    فراخوانی انحصاری Google Gemini جهت ارائه مشاوره هوشمند،
    و استخراج لیست کالاهای متناظر جهت تولید دکمه‌های خرید شیشه‌ای.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return (
            "⚠️ در حال حاضر ارتباط با دستیار هوشمند گوگل به دلیل عدم تنظیم کلید API برقرار نیست.\n"
            "لطفاً جهت مشاوره تخصصی با شماره‌ها یا آی‌دی پشتیبانی فروشگاه تماس حاصل فرمایید.",
            []
        )

    catalog_context, detected_cat, detected_brand = extract_relevant_catalog_snippets(user_query)
    
    specific_product_context = ""
    if context_product:
        p_name = context_product.get("name", "")
        p_price = context_product.get("price", 0)
        p_specs = context_product.get("specs") or context_product.get("ai_specs") or {}
        specific_product_context = (
            f"\n\nکالایی که کاربر در صفحه آن قرار دارد:\n"
            f"نام: {p_name}\n"
            f"قیمت: {p_price:,} تومان\n"
            f"مشخصات: {p_specs}\n"
        )

    system_instruction = build_advisor_system_prompt()
    
    full_prompt = (
        f"{system_instruction}\n\n"
        f"📋 موجودی مرتبط کاتالوگ فروشگاه هوشمند کالا:\n"
        f"{catalog_context}"
        f"{specific_product_context}\n\n"
        f"پرسش کاربر:\n{user_query}\n\n"
        f"پاسخ کارشناسی و فنی مشاور:"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": full_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 800
        }
    }

    response_text = ""
    for model_name in ADVISOR_GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            loop = asyncio.get_running_loop()
            resp_data = await loop.run_in_executor(
                None,
                lambda: _fetch_gemini_url(req)
            )
            if resp_data:
                candidates = resp_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        response_text = parts[0]["text"].strip()
                        break
        except Exception as e:
            logger.warning(f"⚠️ Advisor call failed on model {model_name}: {e}")
            continue

    if not response_text:
        return (
            "⚠️ متأسفانه در حال حاضر به دلیل ترافیک بالای سرورهای هوش مصنوعی، دریافت پاسخ مقدور نشد.\n"
            "لطفاً چند لحظه بعد مجدداً پیام خود را ارسال فرمایید یا با بخش «پشتیبانی و مشاوره» در تماس باشید.",
            []
        )

    # پاکسازی و استخراج کالاهای پیشنهادی برای دکمه‌های مستقیم متناسب با دسته‌بندی
    suggested_products: List[Dict[str, Any]] = []
    clean_response = response_text

    # تابع کمکی برای اعتبارسنجی انطباق دسته‌بندی و برند کالا با نیاز کاربر
    def _is_product_category_matched(prod: Dict[str, Any]) -> bool:
        if detected_brand:
            b_syns = [s.lower() for s in BRAND_SYNONYMS.get(detected_brand, [detected_brand])]
            p_b = (prod.get("brand") or "").lower()
            p_n = (prod.get("name") or "").lower()
            if not any(s in p_b or s in p_n for s in b_syns):
                return False
        if not detected_cat:
            return True
        p_c = (prod.get("category_name") or prod.get("category_key") or "").strip()
        # استثنا: محصولات آاگ ممکن است در دسته محصولات آاگ باشند اما موضوعاً مرتبط باشند
        if "آاگ" in p_c or "aeg" in p_c.lower():
            return True
        return detected_cat in p_c or p_c in detected_cat

    # استخراج خط [مدل‌های پیشنهادی: ...]
    match = re.search(r"\[مدل‌های پیشنهادی:\s*([^\]]+)\]", response_text)
    if match:
        models_line = match.group(1)
        model_names = [m.strip() for m in models_line.split("|") if m.strip()]
        for m_name in model_names:
            hits = search_products(m_name)
            for hit in hits:
                if hit not in suggested_products and _is_product_category_matched(hit):
                    suggested_products.append(hit)
                    break
        # حذف آن خط سیستمی از دید کاربر
        clean_response = response_text[:match.start()].strip()

    # اگر از طریق خط مدل‌های پیشنهادی محصول کافی پیدا نشد، بررسی متن
    if len(suggested_products) < 2:
        for p in JSON_PRODUCTS:
            if not _is_product_category_matched(p):
                continue
            pid = str(p.get("product_id", ""))
            pname = p.get("name", "")
            pmodel = p.get("model_number", "")
            if (pmodel and len(pmodel) >= 3 and pmodel.lower() in clean_response.lower()) or (pname and pname in clean_response):
                if p not in suggested_products:
                    suggested_products.append(p)
                if len(suggested_products) >= 3:
                    break

    # اگر کاربر برند خاصی خواسته بود اما دکمه‌ها خالی ماند، کالاهای همان برند را بیاوریم
    if not suggested_products and detected_brand:
        brand_matches = get_products_by_brand(detected_brand, detected_cat)
        suggested_products.extend(brand_matches[:2])

    # اگر باز هم پیدا نشد ولی دسته‌بندی مشخص بود، ۲ کالای اول متناسب با همان دسته را بیاوریم
    if not suggested_products and detected_cat:
        cat_matches = [
            p for p in JSON_PRODUCTS
            if detected_cat in (p.get("category_name") or "") or detected_cat in (p.get("category_key") or "")
        ]
        suggested_products.extend(cat_matches[:2])

    return clean_response, suggested_products[:3]


def _fetch_gemini_url(req: urllib.request.Request) -> Optional[dict]:
    """اجرای سنکرون درخواست HTTP با تایم‌اوت مشخص"""
    try:
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"Gemini HTTP Advisor Error: {e}")
        return None


def build_advisor_response_keyboard(
    suggested_products: List[Dict[str, Any]],
    context_pid: Optional[str] = None
) -> InlineKeyboardMarkup:
    """ساخت دکمه‌های شیشه‌ای خرید مستقیم و اقدام پس از پاسخ هوش مصنوعی"""
    buttons = []
    
    # دکمه‌های مستقیم مشاهده و خرید کالاهای پیشنهاد شده
    for p in suggested_products:
        pid = str(p.get("product_id", "")).strip()
        pname = p.get("name", "کالا")
        short_name = pname[:28] + "…" if len(pname) > 30 else pname
        buttons.append([
            InlineKeyboardButton(f"🛒 مشاهده و خرید {short_name}", callback_data=make_safe_cb("sel", pid))
        ])

    # اگر کاربر از صفحه یک کالای خاص مشاوره گرفته باشد
    if context_pid:
        buttons.append([
            InlineKeyboardButton("🔙 بازگشت به کالای قبلی", callback_data=make_safe_cb("sel", context_pid))
        ])

    buttons.append([
        InlineKeyboardButton("❓ پرسش سوال دیگر از جمینای", callback_data="adv_ask_more"),
        InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(buttons)
