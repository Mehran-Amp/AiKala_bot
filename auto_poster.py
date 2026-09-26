import time
# -*- coding: utf-8 -*-
"""
سیستم ارسال خودکار و زمان‌بندی‌شده محصولات به کانال تلگرام (Auto-Poster)
طراحی شده برای کانال رسمی @AiKala_Khanegi (هوشمند کالا AiKala)
جهت سئو تلگرام، ایندکس گوگل و جذب مخاطب با Deep Linking مستقیم به ربات
"""

import os
import io
import json
import re
import html
import random
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.error import TelegramError, Forbidden, BadRequest

from config import ADMIN_IDS, BOT_LINK
from keyboards import BOT_USERNAME, build_boxed_product_message

logger = logging.getLogger(__name__)

SETTINGS_FILE = "channel_poster_settings.json"
DEFAULT_TARGET_CHANNEL = "@AiKala_Khanegi"

DEFAULT_SETTINGS = {
    "channel_username": DEFAULT_TARGET_CHANNEL,
    "enabled": True,
    "interval_mode": "random",  # "random" (تصادفی متغیر ۱۵ الی ۶۰ دقیقه) یا "fixed" (ثابت)
    "interval_minutes": 30,
    "next_interval_minutes": 25,
    "last_post_time": None,
    "last_product_name": None,
    "last_product_id": None,
    "total_posted": 0,
    "active_hours_start": 8,
    "active_hours_end": 23,
    "posted_product_ids": []
}


def load_poster_settings() -> Dict[str, Any]:
    """بارگذاری تنظیمات ارسال خودکار به کانال"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                res = {**DEFAULT_SETTINGS, **data}
                return res
        except Exception as e:
            logger.error(f"Error loading {SETTINGS_FILE}: {e}")
    return dict(DEFAULT_SETTINGS)


def save_poster_settings(settings: Dict[str, Any]) -> None:
    """ذخیره تنظیمات ارسال خودکار به کانال"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {SETTINGS_FILE}: {e}")


def compute_next_interval(st: Dict[str, Any]) -> int:
    """
    محاسبه هوشمند و متغیر بازه زمانی بعدی جهت شبیه‌سازی رفتار طبیعی انسانی
    و جلوگیری از تشخیص الگو توسط الگوریتم‌های ضد اسپم تلگرام (Anti-Ban/Anti-Flood)
    یکبار ۱۵ دقیقه، یکبار ۳۰ دقیقه، یکبار ۶۰ دقیقه یا مقادیر شناور
    """
    mode = st.get("interval_mode", "random")
    if mode == "fixed":
        return max(5, int(st.get("interval_minutes", 30)))

    # حالت تصادفی: انتخاب متغیر و پویا از بین بازه‌های ۱۵، ۲۰، ۳۰، ۴۵ و ۶۰ دقیقه با نوسان طبیعی (Jitter)
    base_pool = [15, 20, 30, 45, 60]
    base_choice = random.choice(base_pool)
    jitter = random.randint(-3, 4)
    final_val = max(12, base_choice + jitter)
    return final_val


def toggle_poster_enabled() -> bool:
    """روشن یا خاموش کردن ارسال خودکار"""
    st = load_poster_settings()
    st["enabled"] = not st.get("enabled", True)
    save_poster_settings(st)
    return st["enabled"]


def set_poster_interval(val: Any) -> Tuple[str, int]:
    """تنظیم بازه زمانی ارسال؛ پشتیبانی از حالت تصادفی ضد اسپم و حالت زمان ثابت"""
    st = load_poster_settings()
    val_str = str(val).strip().lower()
    if val_str in ["random", "rand", "رندوم", "تصادفی"]:
        st["interval_mode"] = "random"
        st["next_interval_minutes"] = compute_next_interval(st)
        save_poster_settings(st)
        return "random", st["next_interval_minutes"]
    else:
        try:
            m = max(5, int(val))
            st["interval_mode"] = "fixed"
            st["interval_minutes"] = m
            st["next_interval_minutes"] = m
            save_poster_settings(st)
            return "fixed", m
        except Exception:
            return st.get("interval_mode", "random"), st.get("next_interval_minutes", 30)


def set_poster_channel(channel_username: str) -> str:
    """تغییر آیدی کانال مقصد"""
    ch = str(channel_username).strip()
    if not ch.startswith("@") and not ch.startswith("-"):
        ch = f"@{ch}"
    st = load_poster_settings()
    st["channel_username"] = ch
    save_poster_settings(st)
    return ch


def _get_catalog_products() -> List[Dict[str, Any]]:
    """دریافت لیست کالاهای معتبر کاتالوگ با چند لایه پشتیبان و بارگذاری خودکار"""
    try:
        from search_engine import JSON_PRODUCTS, load_json_products
        if not JSON_PRODUCTS:
            load_json_products()
        if JSON_PRODUCTS:
            return JSON_PRODUCTS
    except Exception as e:
        logger.warning(f"Failed to get products from search_engine: {e}")

    # در صورتی که کش حافظه خالی بود، مستقیماً از catalog_products.json بخوان
    for fn in ["catalog_products.json", "momtazkalla_all_products.json"]:
        if os.path.exists(fn):
            try:
                with open(fn, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return list(data.values())
                    elif isinstance(data, list):
                        return data
            except Exception as e:
                logger.warning(f"Failed to read {fn}: {e}")

    return []


def select_next_product_for_channel() -> Optional[Dict[str, Any]]:
    """
    انتخاب فوق‌سریع و هوشمند محصول بعدی برای انتشار در کانال:
    - بدون هیچ‌گونه تاخیر یا لوپ‌های سنگین
    - اولویت با محصولات دارای تصویر
    - چرخش خودکار دوره‌ای کاتالوگ
    """
    prods = _get_catalog_products()
    if not prods:
        return None

    st = load_poster_settings()
    posted_ids = set(str(x) for x in st.get("posted_product_ids", []))

    try:
        from search_engine import is_product_hidden
    except ImportError:
        def is_product_hidden(p): return False

    # کالاهایی که در این دور هنوز ارسال نشده‌اند و فعال (غیرپنهان) هستند
    unposted = [
        p for p in prods 
        if str(p.get("product_id") or p.get("id", "")).strip() not in posted_ids
        and not is_product_hidden(p)
    ]

    # اگر تمام کالاها ارسال شده بودند، چرخه را ریست می‌کنیم
    if not unposted:
        st["posted_product_ids"] = []
        save_poster_settings(st)
        unposted = [p for p in prods if not is_product_hidden(p)]

    # انتخاب آنی و بدون تاخیر از بین کاندیداها
    sample_pool = random.sample(unposted, min(10, len(unposted)))
    chosen = None
    try:
        from photo_service import find_matching_verified_photos
        for cand in sample_pool:
            pid = str(cand.get("product_id") or cand.get("id", "")).strip()
            _, pdata, _ = find_matching_verified_photos(cand or pid)
            if pdata and pdata.get("photo_urls"):
                chosen = cand
                break
    except Exception:
        pass

    if not chosen:
        chosen = sample_pool[0] if sample_pool else random.choice(unposted)

    return chosen


def build_channel_post_content(p: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup, Optional[List[str]]]:
    """
    تولید متن و دکمه‌های شیک و سئو‌شده برای پست کانال
    شامل Deep Link مستقیم به ربات برای استعلام و خرید
    """
    name = p.get("name", "محصول هوشمند کالا")
    raw_brand = p.get("brand", "")
    try:
        from search_engine import detect_product_brand
        brand = detect_product_brand(name, raw_brand)
    except Exception:
        brand = raw_brand if raw_brand else "اورجینال شرکتی"

    category = p.get("category") or p.get("category_name") or "لوازم خانگی"
    subcategory = str(p.get("subcategory") or "").strip()
    clean_pid = str(p.get("product_id") or p.get("id") or "").strip()

    # دیپ لینک به ربات
    deep_link = f"https://t.me/{BOT_USERNAME}?start=prod_{clean_pid}" if clean_pid else f"https://t.me/{BOT_USERNAME}"

    # ایمن‌سازی متون برای حالت HTML تلگرام
    name_esc = html.escape(str(name))
    brand_esc = html.escape(str(brand))
    cat_esc = html.escape(str(category))

    # استخراج مشخصات فنی
    specs = p.get("specs", {})
    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except Exception:
            specs = {}
    if not isinstance(specs, dict):
        specs = {}
    else:
        specs = dict(specs)

    # افزودن مشخصات هوش مصنوعی در صورت وجود
    ai_specs = p.get("ai_specs")
    if isinstance(ai_specs, str):
        try:
            ai_specs = json.loads(ai_specs)
        except Exception:
            ai_specs = {}
    if isinstance(ai_specs, dict):
        specs.update(ai_specs)

    specs_lines = []
    NON_SPEC = {"زیرشاخه", "دسته‌بندی", "دسته", "امتیاز کیفی", "امتیاز", "ضمانت اصالت", "گارانتی", "گارانتی و مهلت تست", "مهلت تست و تعویض"}
    for k, v in specs.items():
        if v and str(v).strip() and k not in NON_SPEC:
            v_str = str(v).strip()
            if v_str not in ["-", "--", "---"]:
                k_esc = html.escape(str(k))
                v_esc = html.escape(v_str)
                specs_lines.append(f"▫️ <b>{k_esc}:</b> {v_esc}")
        if len(specs_lines) >= 5:
            break

    if not specs_lines:
        specs_lines = [
            "▫️ <b>اصالت قطعات:</b> ۱۰۰٪ اورجینال تضمینی",
            "▫️ <b>سلامت فنی:</b> تست کامل قطعات هنگام تحویل"
        ]

    specs_block = "\n".join(specs_lines)

    # نوع محصول (لپ‌تاپ یا لوازم خانگی)
    cat_str = str(category).lower()
    is_laptop = "لپ" in cat_str or "laptop" in cat_str or clean_pid.upper().startswith("LAP")

    if is_laptop:
        warranty_text = "🛡 <b>ضمانت:</b> یک هفته مهلت تست فنی و تعویض بی‌قیدوشرط"
    else:
        warranty_text = (
            "🛡 <b>ضمانت اصالت:</b> ۱۰۰٪ اورجینال با تضمین کتبی\n"
            "🛡 <b>گارانتی شرکتی:</b> ۱۸ ماه گارانتی + ۵ سال خدمات پس از فروش"
        )

    # قیمت روز
    raw_price = p.get("price", 0)
    if isinstance(raw_price, (int, float)) and raw_price > 0:
        price_str = f"{int(raw_price):,} تومان"
    elif p.get("price_formatted"):
        price_str = str(p["price_formatted"])
    else:
        price_str = "استعلام لحظه‌ای در ربات"

    price_esc = html.escape(price_str)

    # برچسب‌های سئو هوشمند تلگرام و گوگل برگرفته از نام کالا، مدل فنی، برند و دسته‌بندی
    def _extract_product_hashtags(prod_name: str, prod_brand: str = "", prod_cat: str = "", laptop: bool = False) -> List[str]:
        res_tags: List[str] = []
        clean_text = re.sub(r'[\(\)\[\]\{\}\/\,\:\;\!\?\"\'\+\*\&\\\|]', ' ', prod_name or "")
        words = clean_text.split()

        stop_words = {'مدل', 'طرح', 'سری', 'اصل', 'اصلی', 'اورجینال', 'شرکتی', 'جدید', 'با', 'و', 'از', 'در', 'برای', 'دارای', 'های', 'ها', 'رنگ'}
        filtered_words = [w for w in words if w not in stop_words]

        # ۱. استخراج کدهای مدل فنی کالا (مثلاً 55X75K, V5, G5, WW90, OLED65C3, ZBOOK)
        model_tags = []
        for w in filtered_words:
            if re.search(r'[A-Za-z]', w) and re.search(r'\d', w):
                clean_m = re.sub(r'[^A-Za-z0-9_]', '', w)
                if clean_m and len(clean_m) >= 2:
                    model_tags.append(f"#{clean_m}")
            elif re.search(r'^[A-Za-z]{3,}$', w):
                model_tags.append(f"#{w}")

        # ۲. تولید هشتگ ترکیبی نام کالا با آندرلاین (مثلاً #تلویزیون_55_اینچ_سونی یا #HP_ZBOOK_17_G5)
        core_words = [re.sub(r'[^A-Za-z0-9_\u0600-\u06FF]', '', w) for w in filtered_words]
        core_words = [w for w in core_words if w and w not in stop_words]
        if core_words:
            comb = '_'.join(core_words[:4])
            if len(comb) <= 35:
                res_tags.append(f"#{comb}")

        # افزودن تگ‌های مدل فنی اختصاصی
        for mt in model_tags[:2]:
            if mt not in res_tags:
                res_tags.append(mt)

        # ۳. ترکیب برند و دسته‌بندی (مثلاً #تلویزیون_سونی، #لپتاپ_HP)
        b_clean = re.sub(r'[^A-Za-z0-9_\u0600-\u06FF]', '', str(prod_brand or '').replace(' ', '_'))
        c_clean = re.sub(r'[^A-Za-z0-9_\u0600-\u06FF]', '', str(prod_cat or '').replace(' ', '_'))
        if c_clean and b_clean and b_clean != "اورجینال_شرکتی":
            cb = f"#{c_clean}_{b_clean}"
            if cb not in res_tags and len(cb) <= 30:
                res_tags.append(cb)

        # ۴. تگ‌های برند و دسته به‌صورت مجزا
        if b_clean and f"#{b_clean}" not in res_tags and b_clean != "اورجینال_شرکتی":
            res_tags.append(f"#{b_clean}")
        if c_clean and f"#{c_clean}" not in res_tags:
            res_tags.append(f"#{c_clean}")

        # ۵. تگ‌های عمومی و برندینگ اختصاصی هوشمند کالا
        res_tags.append("#هوشمند_کالا")
        res_tags.append("#AiKala")
        if laptop:
            if "#لپتاپ" not in res_tags: res_tags.append("#لپتاپ")
        else:
            if "#لوازم_خانگی" not in res_tags: res_tags.append("#لوازم_خانگی")

        return res_tags

    tags_list = _extract_product_hashtags(name, brand, category, is_laptop)
    tags_str = " ".join(tags_list[:6])

    # ساخت پیام شیک با رعایت محدودیت ۱۰۰۰ کاراکتر برای کپشن عکس تلگرام
    caption = (
        f"🌟 <b>{name_esc}</b>\n"
        f"🏷 <b>برند:</b> {brand_esc} | 📂 <b>دسته:</b> {cat_esc}\n\n"
        f"📋 <b>مشخصات کلیدی و فنی:</b>\n"
        f"<blockquote>{specs_block}</blockquote>\n\n"
        f"{warranty_text}\n"
        f"▫️ <b>تست در محل:</b> بررسی فیزیکی و اتصال به برق هنگام تحویل\n\n"
        f"<blockquote>💰 <b>قیمت روز:</b> <code>{price_esc}</code>\n"
        f"⚠️ <i>جهت دریافت قیمت قطعی لحظه‌ای روی دکمه زیر کلیک نمایید.</i></blockquote>\n\n"
        f"👉 <b>ربات رسمی:</b> @{BOT_USERNAME}\n\n"
        f"{tags_str}"
    )

    # دکمه شیشه‌ای متصل به Deep-Link کالا
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛍 استعلام قیمت لحظه‌ای و خرید", url=deep_link)
        ],
        [
            InlineKeyboardButton("🤖 ورود به فروشگاه هوشمند کالا", url=f"https://t.me/{BOT_USERNAME}")
        ]
    ])

    # پیدا کردن عکس‌های کالا
    photo_urls = []
    try:
        from photo_service import find_matching_verified_photos
        _, photo_data, _ = find_matching_verified_photos(p or clean_pid)
        if photo_data:
            urls = photo_data.get("photo_urls") or []
            if urls:
                photo_urls = [u for u in urls if isinstance(u, str) and u.startswith("http")]
    except Exception as e:
        logger.debug(f"Error fetching verified photos for channel post: {e}")

    if not photo_urls:
        web_img = p.get("image_url")
        if web_img and isinstance(web_img, str) and web_img.startswith("http"):
            photo_urls = [web_img]

    return caption, keyboard, photo_urls


async def publish_product_to_channel(bot: Bot, product: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """
    ارسال پست یک کالا به کانال تلگرام به صورت فوق‌سریع و پایدار
    اگر محصول مشخص نشده باشد، محصول بعدی را خودکار انتخاب می‌کند.
    """
    try:
        settings = load_poster_settings()
        raw_channel = settings.get("channel_username") or DEFAULT_TARGET_CHANNEL
        target_channel = str(raw_channel).strip()
        if "t.me/" in target_channel:
            target_channel = "@" + target_channel.split("t.me/")[-1].strip().replace("/", "")
        elif not target_channel.startswith("@") and not target_channel.startswith("-"):
            target_channel = f"@{target_channel}"

        if not product:
            product = select_next_product_for_channel()

        if not product:
            return False, "محصولی در کاتالوگ جهت ارسال به کانال یافت نشد. لطفاً از بارگذاری کاتالوگ اطمینان حاصل فرمایید."

        p_name = product.get("name", "کالا")
        pid = str(product.get("product_id") or product.get("id") or "").strip()

        caption, keyboard, photo_urls = build_channel_post_content(product)

        # تلگرام محدودیت ۱۰۲۴ کاراکتر برای کپشن مدیا دارد
        safe_caption = caption if len(caption) <= 1024 else caption[:1020]

        logger.info(f"📢 [AUTO-POSTER] Attempting to publish '{p_name}' ({pid}) to {target_channel}...")

        sent_success = False
        err_desc = ""

        try:
            # ۱. اگر عکس دارد، عکس همراه با دکمه شیشه‌ای ارسال شود
            if photo_urls:
                first_photo = photo_urls[0]
                try:
                    # حل مشکل لینک‌های تلسکوپ یا CDN با محدودیت زمانی حداکثر ۳ ثانیه
                    from photo_service import resolve_media_for_telegram
                    media_obj, _ = await asyncio.wait_for(resolve_media_for_telegram(first_photo), timeout=3.0)
                    if media_obj:
                        if hasattr(media_obj, "seek"):
                            media_obj.seek(0)
                        await bot.send_photo(
                            chat_id=target_channel,
                            photo=media_obj,
                            caption=safe_caption,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                        sent_success = True
                except (Forbidden, BadRequest) as e_tg:
                    logger.warning(f"Telegram API error when sending media object: {e_tg}")
                    raise e_tg
                except Exception as e_photo:
                    logger.warning(f"Fast media resolve fallback to direct photo URL or text: {e_photo}")
                    try:
                        await bot.send_photo(
                            chat_id=target_channel,
                            photo=first_photo,
                            caption=safe_caption,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                        sent_success = True
                    except (Forbidden, BadRequest) as e_tg2:
                        logger.warning(f"Telegram API error on direct photo URL send: {e_tg2}")
                        raise e_tg2
                    except Exception as e2:
                        logger.warning(f"Direct photo send failed, falling back to text: {e2}")

            # ۲. در صورتی که عکسی نبود یا ارسال عکس ناموفق بود، پیام متنی با دکمه ارسال می‌شود
            if not sent_success:
                await bot.send_message(
                    chat_id=target_channel,
                    text=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                sent_success = True

        except Forbidden as e_forb:
            err_desc = (
                f"ربات هنوز در کانال {target_channel} عضو یا ادمین نیست!\n"
                f"لطفاً ربات @{BOT_USERNAME} را به کانال اضافه کرده و دسترسی ارسال پیام (Post Messages) بدهید."
            )
            logger.error(f"Auto-poster Forbidden error: {e_forb}")
            return False, err_desc
        except BadRequest as e_bad:
            err_msg = str(e_bad)
            err_lower = err_msg.lower()
            if "chat not found" in err_lower:
                err_desc = f"کانال با آیدی {target_channel} یافت نشد. لطفاً مطمئن شوید آیدی کانال صحیح و عمومی است."
            elif "not enough rights" in err_lower or "have no rights" in err_lower:
                err_desc = f"ربات در کانال {target_channel} دسترسی لازم برای ارسال پیام (Post Messages) را ندارد."
            elif "bot was kicked" in err_lower or "bot is not a member" in err_lower:
                err_desc = f"ربات در کانال {target_channel} عضو نیست. لطفاً @{BOT_USERNAME} را به عنوان ادمین اضافه فرمایید."
            else:
                err_desc = f"خطای تلگرام: {err_msg}"
            logger.error(f"Auto-poster BadRequest error: {e_bad}")
            return False, err_desc
        except Exception as ex:
            err_desc = f"خطای غیرمنتظره در ارسال: {str(ex)}"
            logger.error(f"Auto-poster unexpected error: {ex}")
            return False, err_desc

        if sent_success:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            settings["last_post_time"] = now_str
            settings["last_product_name"] = p_name
            settings["last_product_id"] = pid
            settings["total_posted"] = settings.get("total_posted", 0) + 1

            posted_list = settings.get("posted_product_ids", [])
            if pid and pid not in posted_list:
                posted_list.append(pid)
            settings["posted_product_ids"] = posted_list

            next_val = compute_next_interval(settings)
            settings["next_interval_minutes"] = next_val

            save_poster_settings(settings)
            logger.info(f"✅ [AUTO-POSTER] Successfully published '{p_name}' to {target_channel} (Total: {settings['total_posted']}). Next post in ~{next_val} mins.")
            return True, f"پست با موفقیت در کانال {target_channel} منتشر گردید."

        return False, err_desc or "خطای نامشخص در ارسال پست"

    except Exception as master_ex:
        logger.error(f"Fatal error in publish_product_to_channel: {master_ex}", exc_info=True)
        return False, f"خطای داخلی: {master_ex}"


async def channel_auto_poster_background_task(bot: Bot):
    """
    تسک دائمی در پس‌زمینه که طبق بازه زمانی متغیر و ضد اسپم محصولات را به کانال ارسال می‌کند.
    """
    logger.info("🚀 [AUTO-POSTER] Channel auto-poster background task started.")
    # تاخیر اولیه هنگام بالا آمدن ربات جهت اطمینان از استارت کامل سرویس‌ها
    await asyncio.sleep(45)

    while True:
        try:
            settings = load_poster_settings()
            enabled = settings.get("enabled", False)

            if not enabled:
                await asyncio.sleep(60)
                continue

            # بررسی ساعات مجاز ارسال (مثلاً از ۸ صبح تا ۲۳:۳۰ شب به وقت ایران)
            now = datetime.now()
            start_h = settings.get("active_hours_start", 8)
            end_h = settings.get("active_hours_end", 23)

            # در خارج ساعات فعال، ارسال انجام نمی‌شود تا مزاحمتی ایجاد نکند
            if not (start_h <= now.hour <= end_h):
                await asyncio.sleep(120)
                continue

            last_time_str = settings.get("last_post_time")
            # بازه زمانی متغیر تصادفی یا ثابت تعیین‌شده
            interval_min = settings.get("next_interval_minutes") or settings.get("interval_minutes", 30)

            should_post = False
            if not last_time_str:
                should_post = True
            else:
                try:
                    last_dt = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M")
                    elapsed_seconds = (now - last_dt).total_seconds()
                    if elapsed_seconds >= (interval_min * 60):
                        should_post = True
                except Exception:
                    should_post = True

            if should_post:
                logger.info("⏱ [AUTO-POSTER] Interval reached. Selecting next product to post...")
                success, msg = await publish_product_to_channel(bot)
                if not success:
                    logger.warning(f"⚠️ [AUTO-POSTER] Post attempt failed: {msg}")
                # پس از تلاش، حداقل ۳۰ ثانیه مکث
                await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Error in channel_auto_poster_background_task loop: {e}")

        await asyncio.sleep(60)
