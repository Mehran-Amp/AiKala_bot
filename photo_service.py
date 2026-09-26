"""
AiKala - Photo Service & Multi-Photo Album Dispatcher (photo_service.py)
========================================================================
مدیریت پیشرفته آلبوم‌های تصویری تلگرام:
- استخراج قطعی و بدون خطای ۴۰۰ از طریق Web Embed تلگرام
- دانلود باینری در قالب رم (io.BytesIO) جهت رفع دائمی خطای webpage_curl_failed
- ارتقای خودکار لینک‌های CDN به file_id دائمی تلگرام
- سیستم تطبیق هوشمند تنوع رنگ و مدل با متادیتا
"""
import time


import os
import re
import json
import logging
import asyncio
import io
import urllib.request
import html as html_lib
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

try:
    from telegram import InputMediaPhoto
    from telegram.ext import ContextTypes
except ImportError:
    InputMediaPhoto = object
    class ContextTypes:
        DEFAULT_TYPE = Any

try:
    import config
except ImportError:
    config = None

ADMIN_IDS = getattr(config, "ADMIN_IDS", [])
PHOTOS_CHANNEL = getattr(config, "PHOTOS_CHANNEL", getattr(config, "PHOTO_CHANNEL", getattr(config, "IMAGE_CHANNEL", getattr(config, "IMAGES_CHANNEL", os.getenv("PHOTOS_CHANNEL", "@img_ai_amp")))))

from search_engine import (
    clean_key,
    _normalize_digits,
    tokenize_model_codes,
    extract_model_market_cores,
    extract_color_from_text,
    extract_capacity_from_text,
    extract_variant_features,
    normalize_brand,
    normalize_category,
    extract_brand_from_text,
    extract_category_from_text,
    parse_post_metadata,
    STOP_WORDS_NOT_MODELS,
    is_model_code,
    detect_product_brand,
    atomic_save_json
)
from keyboards import build_boxed_product_message, product_inline_keyboard

logger = logging.getLogger(__name__)

# ─── تعاریف فایل‌ها و متغیرهای داده‌ای ───

CHANNEL_PHOTOS_MAP_FILE = "channel_photos_map.json"
CHANNEL_POSTS_METADATA: List[Dict[str, Any]] = []
CHANNEL_PHOTOS_MAP: Dict[str, List[str]] = {}
CHANNEL_MEDIA_GROUPS: Dict[str, Dict[str, Any]] = {}

VERIFIED_PHOTOS_FILE = "verified_photos.json"
VERIFIED_PRODUCT_PHOTOS: Dict[str, Dict[str, Any]] = {}
PENDING_IMAGE_REQUESTS: Dict[str, List[int]] = {}

# ─── ذخیره و بازیابی تصاویر تایید شده ───

def load_verified_photos():
    global VERIFIED_PRODUCT_PHOTOS
    if os.path.exists(VERIFIED_PHOTOS_FILE):
        try:
            with open(VERIFIED_PHOTOS_FILE, "r", encoding="utf-8") as f:
                VERIFIED_PRODUCT_PHOTOS = json.load(f)
            logger.info(f"✅ [PHOTOS CACHE] Loaded {len(VERIFIED_PRODUCT_PHOTOS)} verified product photo mappings.")
        except Exception as e:
            logger.warning(f"Error loading verified photos: {e}")
            VERIFIED_PRODUCT_PHOTOS = {}

def save_verified_photos():
    atomic_save_json(VERIFIED_PHOTOS_FILE, VERIFIED_PRODUCT_PHOTOS, indent=2)

def clear_verified_photos() -> int:
    """پاکسازی کامل تمامی تصاویر تایید شده دستی برای محصولات"""
    global VERIFIED_PRODUCT_PHOTOS
    count = len(VERIFIED_PRODUCT_PHOTOS)
    VERIFIED_PRODUCT_PHOTOS.clear()
    save_verified_photos()
    logger.info(f"🗑 [PHOTOS] Cleared {count} verified product photos.")
    return count

def remove_verified_product_photo(pid: str) -> bool:
    """حذف پیوند تصویر و آلبوم تایید شده برای یک محصول خاص"""
    global VERIFIED_PRODUCT_PHOTOS
    clean_pid = str(pid).strip()
    removed = False
    if clean_pid in VERIFIED_PRODUCT_PHOTOS:
        del VERIFIED_PRODUCT_PHOTOS[clean_pid]
        removed = True
    for k in list(VERIFIED_PRODUCT_PHOTOS.keys()):
        if str(k).strip() == clean_pid or str(k).strip().lower() == clean_pid.lower():
            del VERIFIED_PRODUCT_PHOTOS[k]
            removed = True
    if removed:
        save_verified_photos()
        logger.info(f"🗑 [PHOTOS] Removed verified photo mapping for product PID: {clean_pid}")
        try:
            from search_engine import JSON_PRODUCTS
            for p in JSON_PRODUCTS:
                if str(p.get("product_id", "")).strip().lower() == clean_pid.lower():
                    p["extra_description"] = ""
        except Exception:
            pass
    return removed

# ─── سیستم هوشمند شناسایی و ارجاع تصاویر مدل‌های مشابه ───

KNOWN_DISPLAY_SIZES = {'32', '40', '42', '43', '48', '49', '50', '55', '65', '70', '75', '77', '83', '85', '86', '98'}
KNOWN_CAPACITY_NUMS = {'7', '8', '9', '10', '10.5', '12', '14', '28', '30'}

def clean_model_str(s: str) -> str:
    """حذف سایز تلویزیون از ابتدای کد مدل و پاکسازی کاراکترهای اضافه جهت مقایسه تمیز مدل‌ها"""
    if not s:
        return ""
    s_norm = _normalize_digits(str(s)).lower()
    s_norm = re.sub(r'^(?:32|40|42|43|48|49|50|55|65|70|75|77|83|85|86|98)', '', s_norm)
    s_norm = re.sub(r'(مشکی|سفید|نقره\s*ای|سیلور|استیل|دودی|طلایی|black|white|silver|inox)', '', s_norm)
    return re.sub(r'[^a-z0-9]', '', s_norm)

def filter_model_tokens(tokens: set) -> set:
    """فیلتر کردن اعدادی که صرفاً سایز تلویزیون یا ظرفیت ساده هستند"""
    return {
        t for t in tokens
        if t not in KNOWN_DISPLAY_SIZES and t not in KNOWN_CAPACITY_NUMS and len(t) >= 2
    }

def clean_channel_caption(text: str) -> str:
    """
    پالایش هوشمند متن کپشن پست کانال تلگرام برای استفاده به عنوان توضیحات تکمیلی کالا:
    - حذف هشتگ‌ها (#سامسونگ #تلویزیون و ...)
    - حذف آیدی‌ها و لینک‌های تلگرام و وب (@channel, t.me/..., http://...)
    - حذف شماره تلفن‌ها و عبارات تبلیغاتی مثل 'جهت ثبت سفارش تماس بگیرید'
    - حفظ کامل ویژگی‌ها، مشخصات و توضیحات فنی محصول
    """
    if not text:
        return ""
    lines = text.strip().split("\n")
    cleaned_lines = []
    for line in lines:
        l = line.strip()
        if not l:
            continue
        # حذف خطوطی که صرفاً هشتگ هستند
        if re.match(r'^(?:#[\w_]+\s*)+$', l):
            continue
        # حذف خطوطی که حاوی آیدی یا لینک تلگرام یا وب هستند
        if "@" in l or "t.me/" in l or "telegram.me/" in l or "http://" in l or "https://" in l or "www." in l:
            continue
        # حذف عبارات رایج تبلیغاتی یا دعوت به تماس در انتهای پست
        if any(term in l for term in [
            "جهت ثبت سفارش", "جهت خرید", "جهت سفارش", "ثبت سفارش",
            "ارتباط با ما", "تماس با ما", "شماره تماس", "مشاوره و خرید",
            "کانال ما", "کانال تلگرام", "لینک کانال", "آیدی سفارش", "پیوی",
            "ادمین کانال", "واحد فروش", "پاسخگویی"
        ]):
            continue
        # حذف خطوط شماره موبایل
        if re.match(r'^(?:تلفن|موبایل|تماس)?\s*[:\-\s]*09\d{9}\b', l) or re.match(r'^\+?98\d{10}$', l):
            continue
        cleaned_lines.append(l)

    res = "\n".join(cleaned_lines).strip()
    return res

def save_verified_product_entry(
    pid: str,
    product_name: str,
    channel: str,
    message_ids: List[int],
    file_ids: List[str],
    link: Optional[str] = None,
    model_number: str = "",
    brand: str = "",
    category: str = "",
    caption: str = "",
    extra_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """ذخیره دائمی و همیشگی تصاویر تایید شده محصول به همراه شناسه‌های دقیق مدل و توضیحات استخراج‌شده از پست"""
    global VERIFIED_PRODUCT_PHOTOS
    clean_pid = str(pid).strip()

    scope_text = f"{product_name} {model_number}"
    raw_tokens = tokenize_model_codes(scope_text)
    filtered_tokens = list(filter_model_tokens(raw_tokens))
    cores = list(extract_model_market_cores(scope_text))
    det_brand = normalize_brand(brand or detect_product_brand(product_name))
    det_cat = normalize_category(category or extract_category_from_text(product_name))
    color = extract_color_from_text(product_name)
    capacity = extract_capacity_from_text(product_name)
    variant_features = list(extract_variant_features(product_name))

    existing_entry = VERIFIED_PRODUCT_PHOTOS.get(clean_pid, {})
    clean_cap = clean_channel_caption(caption) if caption else existing_entry.get("caption", "")

    entry = {
        "product_id": clean_pid,
        "product_name": product_name,
        "channel": channel,
        "message_ids": sorted(list(set(message_ids))),
        "file_ids": file_ids,
        "link": link or "",
        "model_number": model_number,
        "brand": det_brand,
        "category": det_cat,
        "caption": clean_cap,
        "model_codes": filtered_tokens,
        "cores": cores,
        "color": color,
        "capacity": capacity,
        "features": variant_features,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    if extra_data:
        entry.update(extra_data)

    VERIFIED_PRODUCT_PHOTOS[clean_pid] = entry
    save_verified_photos()
    logger.info(f"💾 [VERIFIED_PHOTOS] Saved persistent entry for pid={clean_pid} ({product_name}). Features: {variant_features}, Color: {color}.")
    return entry

def get_verified_product_caption(target_prod_or_pid: Any) -> str:
    """دریافت توضیحات تکمیلی تایید شده محصول"""
    pid, pdata, _ = find_matching_verified_photos(target_prod_or_pid)
    if pdata and pdata.get("caption"):
        return pdata.get("caption", "").strip()
    return ""

def find_matching_verified_photos(target_prod_or_pid: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    جستجوی دقیق تصاویر تایید شده برای محصول:
    ۱. تطابق مستقیم شناسه کالا (Exact Product ID)
    ۲. در صورت عدم تطابق شناسه، فقط تطابق همتای ۱۰۰٪ یکسان (همان برند، همان دسته، همان کد مدل، همان رنگ و همان ویژگی‌های اختصاصی)
       جلوگیری قطعی از تداخل عکس یخچال‌های هم‌مدل با رنگ‌های متفاوت (سفید، سیلور، دودی) یا ویژگی‌های متفاوت (اینستاویو، دور این دور، ۴ درب و ...)
    """
    if not VERIFIED_PRODUCT_PHOTOS:
        return None, None, None

    target_prod = None
    target_pid = ""

    if isinstance(target_prod_or_pid, dict):
        target_prod = target_prod_or_pid
        target_pid = str(target_prod.get("product_id", "")).strip()
    else:
        target_pid = str(target_prod_or_pid).strip()
        try:
            from search_engine import JSON_PRODUCTS
            clean_seek_pid = target_pid.lower()
            target_prod = next((p for p in JSON_PRODUCTS if str(p.get("product_id", "")).strip().lower() == clean_seek_pid), None)
        except Exception:
            pass

    # ۱. بررسی تطابق مستقیم یا تطابق Case-Insensitive کد کالا
    clean_target_pid = target_pid.lower()
    if clean_target_pid:
        for v_pid, v_data in VERIFIED_PRODUCT_PHOTOS.items():
            if str(v_pid).strip().lower() == clean_target_pid:
                return v_pid, v_data, "exact"

    # ۲. اگر اطلاعات نام کالا موجود نیست، تطابق ناممکن است
    if not target_prod:
        return None, None, None

    pname = target_prod.get("name", "")
    pmodel = str(target_prod.get("model_number", "")).strip()
    scope_text = f"{pname} {pmodel}"

    target_brand = normalize_brand(target_prod.get("brand") or detect_product_brand(pname))
    target_cat = normalize_category(target_prod.get("category_name") or target_prod.get("category_key") or extract_category_from_text(pname))
    target_cores = extract_model_market_cores(scope_text)
    target_clean_model = clean_model_str(pmodel)
    target_color = extract_color_from_text(pname)
    target_cap = extract_capacity_from_text(pname)
    target_feats = extract_variant_features(pname)

    # ۳. بررسی کاتالوگ برای همتای ۱۰۰٪ یکسان (همان واریانت در فایلی دیگر با همان رنگ، آپشن و مدل)
    for v_pid, v_data in VERIFIED_PRODUCT_PHOTOS.items():
        v_name = v_data.get("product_name", "")
        v_model = str(v_data.get("model_number", "")).strip()
        v_scope = f"{v_name} {v_model}"

        # الف) تطابق قطعی برند
        v_brand = v_data.get("brand") or normalize_brand(detect_product_brand(v_name))
        if not target_brand or not v_brand or target_brand != v_brand:
            continue

        # ب) تطابق قطعی دسته‌بندی
        v_cat = v_data.get("category") or normalize_category(extract_category_from_text(v_name))
        if not target_cat or not v_cat or target_cat != v_cat:
            continue

        # ج) تطابق هسته مدل یا کد تمیزشده مدل
        v_cores = set(v_data.get("cores") or extract_model_market_cores(v_scope))
        v_clean_model = clean_model_str(v_model)
        core_matched = bool(target_cores and v_cores and (target_cores & v_cores))
        clean_model_matched = bool(target_clean_model and v_clean_model and target_clean_model == v_clean_model and len(target_clean_model) >= 2)
        if not core_matched and not clean_model_matched:
            continue

        # د) تطابق قطعی رنگ:
        # اگر یکی از دو کالا رنگ مشخصی دارد (سفید، سیلور، دودی، مشکی و...)، هر دو باید دقیقاً همان رنگ باشند
        v_color = v_data.get("color") or extract_color_from_text(v_name)
        if target_color or v_color:
            if target_color != v_color:
                continue

        # ه) تطابق قطعی ویژگی‌های ظاهری و ساختاری (مانند اینستاویو، دور این دور، ۴ درب و ...)
        v_feats = set(v_data.get("features") or extract_variant_features(v_name))
        if target_feats != v_feats:
            continue

        # و) تطابق ظرفیت یا سایز نمایشگر
        v_cap = v_data.get("capacity") or extract_capacity_from_text(v_name)
        if target_cap or v_cap:
            if target_cap != v_cap:
                continue

        # در صورت تطابق ۱۰۰٪ تمام خصوصیات ظاهری و فنی
        logger.info(f"🎯 [EXACT VARIANT PHOTO MATCH] Product '{pname}' (ID: {target_pid}) matched identical variant '{v_name}' (ID: {v_pid})")
        return v_pid, v_data, "exact"

    return None, None, None

load_verified_photos()

# ─── ذخیره و بازیابی نقشه تصاویر کانال ───

def load_channel_photos_map():
    global CHANNEL_PHOTOS_MAP, CHANNEL_POSTS_METADATA, CHANNEL_MEDIA_GROUPS
    if os.path.exists(CHANNEL_PHOTOS_MAP_FILE):
        try:
            with open(CHANNEL_PHOTOS_MAP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    CHANNEL_PHOTOS_MAP = data.get("legacy_map", data)
                    CHANNEL_POSTS_METADATA = data.get("posts_metadata", [])
                    CHANNEL_MEDIA_GROUPS = data.get("media_groups", {})
                elif isinstance(data, list):
                    CHANNEL_POSTS_METADATA = data

            for post in CHANNEL_POSTS_METADATA:
                cap = post.get("caption", "")
                if not post.get("brand"):
                    post["brand"] = extract_brand_from_text(cap)
                if not post.get("category"):
                    post["category"] = extract_category_from_text(cap)
                if not post.get("cores"):
                    post["cores"] = list(extract_model_market_cores(cap))
                if not post.get("models"):
                    post["models"] = list(tokenize_model_codes(cap))

            logger.info(f"[PHOTOS] Loaded {len(CHANNEL_POSTS_METADATA)} structured posts, {len(CHANNEL_MEDIA_GROUPS)} media groups & {len(CHANNEL_PHOTOS_MAP)} model keys.")
        except Exception as e:
            logger.warning(f"Error loading photos map: {e}")
            CHANNEL_PHOTOS_MAP = {}
            CHANNEL_POSTS_METADATA = []
            CHANNEL_MEDIA_GROUPS = {}

def save_channel_photos_map():
    atomic_save_json(CHANNEL_PHOTOS_MAP_FILE, {
        "legacy_map": CHANNEL_PHOTOS_MAP,
        "posts_metadata": CHANNEL_POSTS_METADATA,
        "media_groups": CHANNEL_MEDIA_GROUPS
    }, indent=2)

def clear_channel_photos_cache() -> Tuple[int, int]:
    """پاکسازی کامل کش عکس‌های کانال و متادیتاهای تست"""
    global CHANNEL_PHOTOS_MAP, CHANNEL_POSTS_METADATA, CHANNEL_MEDIA_GROUPS
    posts_count = len(CHANNEL_POSTS_METADATA)
    keys_count = len(CHANNEL_PHOTOS_MAP)
    CHANNEL_PHOTOS_MAP.clear()
    CHANNEL_POSTS_METADATA.clear()
    CHANNEL_MEDIA_GROUPS.clear()
    save_channel_photos_map()
    logger.info(f"🗑 [PHOTOS] Cleared {posts_count} posts and {keys_count} model keys from channel photos cache.")
    return posts_count, keys_count

def clear_all_product_photos() -> Dict[str, int]:
    """پاکسازی کامل هم تصاویر تایید شده و هم کش عکس‌های کانال"""
    v_count = clear_verified_photos()
    p_count, k_count = clear_channel_photos_cache()
    return {
        "verified_count": v_count,
        "posts_count": p_count,
        "keys_count": k_count
    }

load_channel_photos_map()

def register_photo_message(text: str, photo_file_id: str, msg_id: Optional[int] = None, media_group_id: Optional[str] = None):
    """ثبت تصویر در سیستم متادیتا و نقشه کلیدها با پشتیبانی کامل از آلبوم‌ها (Media Groups)"""
    if not photo_file_id:
        return
    caption = text or ""

    matched_existing_post = False
    for post in CHANNEL_POSTS_METADATA:
        mg_match = media_group_id and post.get("media_group_id") == media_group_id
        cap_match = caption and post.get("caption") == caption

        if mg_match or cap_match:
            if "photos" not in post:
                post["photos"] = []
            if photo_file_id not in post["photos"]:
                post["photos"].append(photo_file_id)
            if "msg_ids" not in post:
                post["msg_ids"] = []
            if msg_id and msg_id not in post["msg_ids"]:
                post["msg_ids"].append(msg_id)
            if media_group_id and not post.get("media_group_id"):
                post["media_group_id"] = media_group_id
            if caption and not post.get("caption"):
                post["caption"] = caption
            matched_existing_post = True
            break

    if not matched_existing_post and caption:
        new_meta = parse_post_metadata(caption, [photo_file_id])
        if msg_id:
            new_meta["msg_ids"] = [msg_id]
        if media_group_id:
            new_meta["media_group_id"] = media_group_id
        CHANNEL_POSTS_METADATA.append(new_meta)

    tokens = tokenize_model_codes(caption)
    for tok in tokens:
        k_c = clean_key(tok)
        if len(k_c) >= 2 and is_model_code(k_c):
            if k_c not in CHANNEL_PHOTOS_MAP:
                CHANNEL_PHOTOS_MAP[k_c] = []
            if photo_file_id not in CHANNEL_PHOTOS_MAP[k_c]:
                CHANNEL_PHOTOS_MAP[k_c].append(photo_file_id)

    save_channel_photos_map()

# ─── پارسر لینک‌های کانال تلگرام ───

def parse_telegram_post_link(text: str) -> Optional[Tuple[str, List[int]]]:
    """
    استخراج نام کانال و شماره پیام‌ها از لینک، متن یا آیدی پست تلگرام
    پشتیبانی از:
    - https://t.me/img_ai_amp/452
    - https://t.me/img_ai_amp/452-455 یا 452/455
    - لینک کانال‌های خصوصی: https://t.me/c/2471649987/452
    - رنج عددی: 452-455 یا 452 تا 455
    - شماره تک: 452 یا چند شماره با کاما یا فاصله
    """
    if not text:
        return None
    t = text.strip()

    # ۱. لینک کانال خصوصی تلگرام با پیشوند c/
    c_match = re.search(r't(?:elegram)?\.me/c/(\d+)/(\d+)(?:\s*(?:-|–|_|to|تا|/)\s*(\d+))?', t)
    if c_match:
        c_id = c_match.group(1)
        channel = f"-100{c_id}" if not c_id.startswith("-100") else c_id
        start_id = int(c_match.group(2))
        if c_match.group(3):
            end_id = int(c_match.group(3))
            if 0 < end_id - start_id <= 20:
                return channel, list(range(start_id, end_id + 1))
        return channel, [start_id]

    # ۲. لینک عمومی تلگرام با یا بدون رنج
    link_match = re.search(r't(?:elegram)?\.me/(?!c/)([a-zA-Z0-9_]+)/(\d+)(?:\s*(?:-|–|_|to|تا|/)\s*(\d+))?', t)
    if link_match:
        ch = link_match.group(1)
        channel = f"@{ch}" if not ch.startswith("@") else ch
        start_id = int(link_match.group(2))
        if link_match.group(3):
            end_id = int(link_match.group(3))
            if 0 < end_id - start_id <= 20:
                return channel, list(range(start_id, end_id + 1))
        return channel, [start_id]

    # ۳. رنج عددی مثل 452-455 یا 452 تا 455 یا 452 to 455
    range_match = re.search(r'(\d+)\s*(?:-|–|_|to|تا|/)\s*(\d+)', t, re.IGNORECASE)
    if range_match:
        start_id = int(range_match.group(1))
        end_id = int(range_match.group(2))
        if 0 < end_id - start_id <= 20:
            return PHOTOS_CHANNEL, list(range(start_id, end_id + 1))

    # ۴. اگر فقط اعداد پیام‌ها وارد شده بود (مثلاً 452 یا 452, 453)
    nums = [int(x) for x in re.findall(r'\b\d+\b', t) if 1 <= len(x) <= 8]
    if nums and len(nums) <= 15:
        return PHOTOS_CHANNEL, nums

    return None

# ─── اسکرپر وب‌ویجت امبد تلگرام ───

def extract_text_from_telegram_embed_html(html: str) -> str:
    """استخراج متن و کپشن پست از کدهای HTML ویجت تلگرام"""
    if not html:
        return ""
    match = re.search(r'<div class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not match:
        return ""
    raw_text = match.group(1)
    raw_text = re.sub(r'<br\s*/?>', '\n', raw_text)
    raw_text = re.sub(r'</?(?:p|div)[^>]*>', '\n', raw_text)
    raw_text = re.sub(r'<[^>]+>', '', raw_text)
    return html_lib.unescape(raw_text).strip()

async def scrape_telegram_embed_photos_and_caption(channel_name: str, msg_id: int) -> Tuple[List[str], str]:
    """
    استخراج آنی و قطعی تصاویر آلبوم و کپشن متن از ویجت عمومی تلگرام (Telegram Embed)
    """
    ch = str(channel_name).replace("@", "").strip()
    url = f"https://t.me/{ch}/{msg_id}?embed=1"
    
    def _fetch():
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            logger.debug(f"Fetch embed failed for {url}: {e}")
            return ""
            
    html = await asyncio.to_thread(_fetch)
    if not html or "tgme_widget_message_error" in html or "Post not found" in html:
        return [], ""

    caption = extract_text_from_telegram_embed_html(html)

    # استخراج لینک‌های مستقیم تصاویر در ابعاد بزرگ از cdn تلگرام
    raw_urls = re.findall(r"background-image:url\(\x27(https://[^\x27]+)\x27\)", html)
    clean_urls = []
    for u in raw_urls:
        if "emoji" not in u and ("telesco.pe" in u or "cdn" in u or "telegram" in u):
            if u not in clean_urls:
                clean_urls.append(u)
    return clean_urls, caption

async def scrape_telegram_embed_photos(channel_name: str, msg_id: int) -> List[str]:
    """استخراج تصاویر آلبوم از وب‌ویجت تلگرام (حفظ سازگاری قبلی)"""
    photos, _ = await scrape_telegram_embed_photos_and_caption(channel_name, msg_id)
    return photos

async def probe_telegram_channel_album_and_caption(channel_name: str, base_mid: int) -> Tuple[List[str], List[int], str]:
    """
    پویش جامع استخراج آلبوم کامل و متن کپشن از کانال عمومی تلگرام:
    ۱. استخراج تصاویر گروپ‌شده (MediaGroup) و کپشن از پیام اصلی
    ۲. در صورت تک‌تصویر بودن، پویش پیام‌های متوالی مجاور (عقب و جلو)
    """
    logger.info(f"🔍 [PROBE] Scraping channel {channel_name} around message {base_mid} via Telegram Public Embed...")
    discovered_photos: List[str] = []
    discovered_mids: List[int] = [base_mid]
    main_caption: str = ""
    
    # ۱. استخراج عکس‌ها و کپشن موجود در خود پست
    main_photos, main_caption = await scrape_telegram_embed_photos_and_caption(channel_name, base_mid)
    for p in main_photos:
        if p not in discovered_photos:
            discovered_photos.append(p)
            
    logger.info(f"🔍 [PROBE] Main post {base_mid} returned {len(main_photos)} direct photos and caption len={len(main_caption)}")
    
    # ۲. اگر در پیام مبنا فقط ۱ عکس یا کمتر یافت شد، پیام‌های قبل و بعد را پویش می‌کنیم
    if len(discovered_photos) <= 1:
        # الف) پویش عقب‌گرد (base_mid - 1 تا base_mid - 10)
        for prev_id in range(base_mid - 1, max(1, base_mid - 10), -1):
            p_photos, p_cap = await scrape_telegram_embed_photos_and_caption(channel_name, prev_id)
            if p_photos:
                logger.info(f"   ➕ [PROBE] Discovered {len(p_photos)} photo(s) at previous msg {prev_id}")
                for p in p_photos:
                    if p not in discovered_photos:
                        discovered_photos.insert(0, p)
                if prev_id not in discovered_mids:
                    discovered_mids.insert(0, prev_id)
                if not main_caption and p_cap:
                    main_caption = p_cap
            else:
                break
                
        # ب) پویش پیش‌رو (base_mid + 1 تا base_mid + 10)
        for next_id in range(base_mid + 1, base_mid + 10):
            n_photos, n_cap = await scrape_telegram_embed_photos_and_caption(channel_name, next_id)
            if n_photos:
                logger.info(f"   ➕ [PROBE] Discovered {len(n_photos)} photo(s) at next msg {next_id}")
                for p in n_photos:
                    if p not in discovered_photos:
                        discovered_photos.append(p)
                if next_id not in discovered_mids:
                    discovered_mids.append(next_id)
                if not main_caption and n_cap:
                    main_caption = n_cap
            else:
                break

    logger.info(f"🔍 [PROBE RESULT] Found total {len(discovered_photos)} photos and {len(discovered_mids)} msg IDs for {channel_name}/{base_mid}")
    return discovered_photos, discovered_mids, main_caption

async def probe_telegram_channel_album(channel_name: str, base_mid: int) -> Tuple[List[str], List[int]]:
    """سازگاری با کدهای قبلی"""
    photos, mids, _ = await probe_telegram_channel_album_and_caption(channel_name, base_mid)
    return photos, mids

# ─── حل‌کننده باینری عکس‌ها جهت رفع webpage_curl_failed ───

async def resolve_media_for_telegram(item: Any, timeout: int = 10) -> Tuple[Optional[Any], Optional[str]]:
    """
    بررسی و آماده‌سازی آیتم تصویر برای ارسال امن و تضمینی به تلگرام:
    اگر آدرس اینترنتی (HTTP/HTTPS مانند لینک‌های CDN تلگرام telesco.pe) باشد، محتوای باینری آن توسط بات
    به صورت مستقیم دانلود شده و در قالب شیء io.BytesIO تحویل داده می‌شود تا تلگرام با خطای
    webpage_curl_failed یا Failed to get http url content مواجه نشود.
    در صورت file_id بودن، مستقیم و بدون تغییر بازگردانده می‌شود.
    خروجی: (media_object, original_url_if_downloaded)
    """
    if isinstance(item, str) and (item.startswith("http://") or item.startswith("https://")):
        def _download():
            clean_item = item.strip()
            try:
                parts = urllib.parse.urlsplit(clean_item)
                encoded_path = urllib.parse.quote(urllib.parse.unquote(parts.path))
                encoded_query = urllib.parse.quote(urllib.parse.unquote(parts.query), safe="=&?/")
                fetch_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, encoded_path, encoded_query, parts.fragment))
            except Exception:
                fetch_url = clean_item

            req = urllib.request.Request(
                fetch_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except Exception as e:
                logger.warning(f"⚠️ [DOWNLOAD MEDIA] Failed to download {clean_item[:65]}: {e}")
                return None

        raw_bytes = await asyncio.to_thread(_download)
        if raw_bytes:
            bio = io.BytesIO(raw_bytes)
            bio.name = "photo.jpg"
            return bio, item
        else:
            return None, item
    return item, None

async def prepare_media_items(items: List[Any], timeout: int = 10) -> List[Tuple[Any, Optional[str]]]:
    """دانلود موازی تمامی تصاویر وب به منظور جلوگیری از تاخیر و حذف خطاهای وب پیج تلگرام"""
    tasks = [resolve_media_for_telegram(it, timeout=timeout) for it in items]
    results = await asyncio.gather(*tasks)
    valid_results = []
    for m_obj, orig_url in results:
        if m_obj is not None:
            valid_results.append((m_obj, orig_url))
        elif orig_url:
            logger.warning(f"⚠️ Skipped un-downloadable media URL: {orig_url[:60]}")
    return valid_results

# ─── تحویل تصاویر به کاربر ───

async def send_verified_photos_to_user(
    bot,
    chat_id: int,
    pid: str,
    product_name: str,
    photo_data: Optional[Dict[str, Any]] = None,
    matched_note: Optional[str] = None
) -> bool:
    """ارسال تصاویر تایید شده محصول به صورت آلبوم و همراه با کپشن دقیق بدون ذکر نام کانال یا دکمه لینک"""
    if photo_data is None:
        matched_pid, found_data, match_type = find_matching_verified_photos(pid)
        if found_data:
            photo_data = found_data
        else:
            photo_data = VERIFIED_PRODUCT_PHOTOS.get(pid)

    if not photo_data:
        logger.warning(f"⚠️ [DELIVERY DEBUG] No photo_data in VERIFIED_PRODUCT_PHOTOS for pid={pid}")
        return False

    channel = photo_data.get("channel", PHOTOS_CHANNEL)
    msg_ids = sorted(list(set(photo_data.get("message_ids", []))))
    file_ids = photo_data.get("file_ids", [])

    # غنی‌سازی هوشمند در صورت تک‌عکس بودن با استخراج وب اگر کانال معتبر موجود است
    if len(file_ids) <= 1 and channel and msg_ids:
        ch_clean = str(channel).replace("@", "").strip()
        if not ch_clean.startswith("-"):
            logger.info(f"🔍 [DELIVERY DEBUG] Attempting to enrich single photo from public embed for {channel}/{msg_ids[0]}...")
            scraped, _ = await probe_telegram_channel_album(ch_clean, msg_ids[0])
            if scraped and len(scraped) > len(file_ids):
                logger.info(f"🎉 [DELIVERY DEBUG] Enriched from {len(file_ids)} to {len(scraped)} photos!")
                file_ids = scraped
                photo_data["file_ids"] = scraped
                save_verified_photos()

    logger.info(f"📤 [DELIVERY DEBUG] Initiating photo delivery for {pid} to chat {chat_id}: "
                f"file_ids={len(file_ids)}, msg_ids={len(msg_ids)}, channel={channel}")

    header_msg = (
        f"📸 <b>تصاویر اختصاصی کالا:</b>\n"
        f"🌟 <b>{product_name}</b>"
    )
    if matched_note:
        header_msg += f"\n\nℹ️ <i>{matched_note}</i>"

    sent_any = False

    # ۱. اگر چندین عکس در file_ids داریم (آلبوم تصاویر تلگرام یا لینک‌های CDN)
    if len(file_ids) > 1:
        try:
            logger.info(f"📤 [DELIVERY DEBUG] Preparing {len(file_ids[:10])} media items for {pid}...")
            resolved_items = await prepare_media_items(file_ids[:10])
            if len(resolved_items) > 1:
                media = []
                for i, (m_obj, _) in enumerate(resolved_items):
                    if hasattr(m_obj, "seek"):
                        m_obj.seek(0)
                    media.append(InputMediaPhoto(media=m_obj, filename=f"photo_{i}.jpg", caption=header_msg if i == 0 else "", parse_mode="HTML"))
                logger.info(f"📤 [DELIVERY DEBUG] Sending media group with {len(media)} photos for {pid}...")
                sent_msgs = await bot.send_media_group(chat_id=chat_id, media=media)
                sent_any = True
                logger.info(f"✅ [DELIVERY DEBUG] Successfully sent media group ({len(media)} photos) for {pid}!")

                # ارتقای خودکار لینک‌های CDN موقت به شناسه فایل دائمی تلگرام
                updated_fids = list(file_ids)
                changed = False
                for idx, msg in enumerate(sent_msgs):
                    if msg.photo:
                        new_fid = msg.photo[-1].file_id
                        if idx < len(resolved_items) and resolved_items[idx][1] is not None:
                            updated_fids[idx] = new_fid
                            changed = True
                if changed:
                    photo_data["file_ids"] = updated_fids
                    save_verified_photos()
                    logger.info(f"✨ [DELIVERY DEBUG] Upgraded CDN URLs to permanent Telegram file_ids for {pid}!")
            elif len(resolved_items) == 1:
                m_obj, orig_url = resolved_items[0]
                if hasattr(m_obj, "seek"):
                    m_obj.seek(0)
                msg_sent = await bot.send_photo(chat_id=chat_id, photo=m_obj, caption=header_msg, parse_mode="HTML")
                sent_any = True
                if msg_sent.photo and orig_url is not None:
                    file_ids[0] = msg_sent.photo[-1].file_id
                    photo_data["file_ids"] = file_ids
                    save_verified_photos()
        except Exception as e:
            logger.warning(f"⚠️ [DELIVERY DEBUG] send_media_group failed ({e}). Fallback to sequential send_photo...")
            # Fallback: ارسال تک‌تک تصاویر تا هیچ تصویری جا نماند
            updated_fids = list(file_ids)
            changed = False
            for idx, fid in enumerate(file_ids[:10]):
                try:
                    m_obj, orig_url = await resolve_media_for_telegram(fid)
                    if not m_obj:
                        continue
                    if hasattr(m_obj, "seek"):
                        m_obj.seek(0)
                    cap = header_msg if idx == 0 else ""
                    msg_sent = await bot.send_photo(chat_id=chat_id, photo=m_obj, caption=cap, parse_mode="HTML")
                    sent_any = True
                    logger.info(f"   [DELIVERY DEBUG] Sent photo {idx+1}/{len(file_ids[:10])} sequentially")
                    if msg_sent.photo and orig_url is not None:
                        updated_fids[idx] = msg_sent.photo[-1].file_id
                        changed = True
                except Exception as ex2:
                    logger.warning(f"❌ [DELIVERY DEBUG] Failed send_photo for item {idx}: {ex2}")
            if changed:
                photo_data["file_ids"] = updated_fids
                save_verified_photos()

    # ۲. اگر file_ids یک دانه است یا خالی بود ولی چندین msg_ids داریم
    if not sent_any and len(msg_ids) > 1:
        logger.info(f"📤 [DELIVERY DEBUG] Attempting copy_messages for {len(msg_ids[:10])} messages from {channel}...")
        if hasattr(bot, "copy_messages"):
            try:
                await bot.copy_messages(
                    chat_id=chat_id,
                    from_chat_id=channel,
                    message_ids=msg_ids[:10]
                )
                sent_any = True
                logger.info(f"✅ [DELIVERY DEBUG] copy_messages successfully sent {len(msg_ids[:10])} messages!")
            except Exception as e:
                logger.warning(f"⚠️ [DELIVERY DEBUG] copy_messages failed ({e})")

        # ارسال متوالی پیام‌های آلبوم
        if not sent_any:
            logger.info(f"🔄 [DELIVERY DEBUG] Fallback: Trying sequential copy_message for {len(msg_ids[:10])} messages...")
            for idx, m_id in enumerate(msg_ids[:10]):
                try:
                    cap = header_msg if idx == 0 else ""
                    await bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=channel,
                        message_id=m_id,
                        caption=cap,
                        parse_mode="HTML"
                    )
                    sent_any = True
                    logger.info(f"   [DELIVERY DEBUG] Copied message {m_id} sequentially")
                except Exception as e:
                    logger.warning(f"❌ [DELIVERY DEBUG] Failed copy_message for {m_id}: {e}")

    # ۳. اگر کانال خارجی بود و هیچ پیامی با copy ارسال نشد اما msg_ids داریم -> استخراج آنی از وب
    if not sent_any and msg_ids and channel:
        ch_clean = str(channel).replace("@", "").strip()
        if not ch_clean.startswith("-"):
            logger.info(f"🌐 [DELIVERY DEBUG] Attempting on-the-fly embed scraping for {channel}/{msg_ids[0]}...")
            scraped, _ = await probe_telegram_channel_album(ch_clean, msg_ids[0])
            if scraped:
                try:
                    resolved_scraped = await prepare_media_items(scraped[:10])
                    if len(resolved_scraped) > 1:
                        media = []
                        for i, (m_obj, _) in enumerate(resolved_scraped):
                            if hasattr(m_obj, "seek"):
                                m_obj.seek(0)
                            media.append(InputMediaPhoto(media=m_obj, filename=f"photo_{i}.jpg", caption=header_msg if i == 0 else "", parse_mode="HTML"))
                        sent_msgs = await bot.send_media_group(chat_id=chat_id, media=media)
                        saved_fids = [msg.photo[-1].file_id for msg in sent_msgs if msg.photo]
                        photo_data["file_ids"] = saved_fids if saved_fids else scraped
                    elif len(resolved_scraped) == 1:
                        m_obj, _ = resolved_scraped[0]
                        if hasattr(m_obj, "seek"):
                            m_obj.seek(0)
                        msg_sent = await bot.send_photo(chat_id=chat_id, photo=m_obj, caption=header_msg, parse_mode="HTML")
                        photo_data["file_ids"] = [msg_sent.photo[-1].file_id] if msg_sent.photo else scraped
                    sent_any = True
                    save_verified_photos()
                    logger.info(f"✅ [DELIVERY DEBUG] On-the-fly scraped & sent {len(resolved_scraped)} photos for {pid}!")
                except Exception as e:
                    logger.warning(f"❌ [DELIVERY DEBUG] Failed sending on-the-fly scraped photos: {e}")

    # ۴. ارسال تک‌عکس در صورتی که فقط یک عکس وجود داشت
    if not sent_any:
        if file_ids:
            try:
                logger.info(f"📤 [DELIVERY DEBUG] Sending single photo for {pid}...")
                m_obj, orig_url = await resolve_media_for_telegram(file_ids[0])
                if m_obj:
                    if hasattr(m_obj, "seek"):
                        m_obj.seek(0)
                    msg_sent = await bot.send_photo(chat_id=chat_id, photo=m_obj, caption=header_msg, parse_mode="HTML")
                    sent_any = True
                    if msg_sent.photo and orig_url is not None:
                        file_ids[0] = msg_sent.photo[-1].file_id
                        photo_data["file_ids"] = file_ids
                        save_verified_photos()
            except Exception as e:
                logger.warning(f"❌ [DELIVERY DEBUG] Failed send_photo for {pid}: {e}")
        elif msg_ids:
            try:
                await bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=channel,
                    message_id=msg_ids[0],
                    caption=header_msg,
                    parse_mode="HTML"
                )
                sent_any = True
            except Exception as e:
                logger.warning(f"❌ [DELIVERY DEBUG] Failed copy_message for {pid}: {e}")

    return sent_any

# ─── سیستم تطبیق خودکار گالری محصول ───

def get_product_photos(product: dict, query_context: str = "") -> Tuple[List[str], Optional[str]]:
    p_name = product.get("name", "")
    p_id = str(product.get("product_id", "")).strip().lower()

    search_scope = f"{p_name} {p_id} {query_context}"
    target_models = tokenize_model_codes(search_scope)
    target_cores = extract_model_market_cores(search_scope)
    target_color = extract_color_from_text(search_scope)
    target_capacity = extract_capacity_from_text(search_scope)

    target_brand = normalize_brand(product.get("brand", "")) or extract_brand_from_text(f"{p_name} {query_context}")
    target_category = normalize_category(product.get("category", "")) or extract_category_from_text(f"{p_name} {query_context}")

    logger.info(f"🔎 [PHOTO DEBUG] Product: '{p_name}' | Brand: '{target_brand}' | Cat: '{target_category}'")
    logger.info(f"   ↳ Extracted Tokens: {target_models} | Cores: {target_cores} | Color: {target_color}")

    best_photos: List[str] = []
    best_score = 0
    matched_post_color = ""
    matched_post_title = ""

    for post in CHANNEL_POSTS_METADATA:
        post_models = set(post.get("models", []))
        post_cores = set(post.get("cores", []))
        post_color = post.get("color", "")
        post_capacity = post.get("capacity", "")
        post_caption = post.get("caption", "")
        post_brand = normalize_brand(post.get("brand", "")) or extract_brand_from_text(post_caption)
        post_category = normalize_category(post.get("category", "")) or extract_category_from_text(post_caption)
        post_photos = post.get("photos", []) or [str(m) for m in post.get("msg_ids", [])]

        if not post_photos:
            continue

        if target_brand and post_brand and target_brand != post_brand:
            continue

        if target_category and post_category and target_category != post_category:
            continue

        score = 0

        common_models = (target_models & post_models) - STOP_WORDS_NOT_MODELS
        if common_models:
            score += 120

        common_cores = (target_cores & post_cores) or (target_cores & post_models) or (target_models & post_cores)
        if common_cores and not common_models:
            score += 100

        if score == 0:
            for tm in target_models:
                for pm in post_models:
                    if tm == pm:
                        score += 120
                        break
                    tm_nosize = re.sub(r'^\d{2}', '', tm)
                    pm_nosize = re.sub(r'^\d{2}', '', pm)
                    if tm_nosize and pm_nosize and (tm_nosize == pm or pm_nosize == tm or tm_nosize == pm_nosize):
                        score += 110
                        break
                    if (tm.startswith("ww") and pm.startswith("w") and tm[2:] == pm[1:]) or \
                       (pm.startswith("ww") and tm.startswith("w") and pm[2:] == tm[1:]):
                        score += 100
                        break
                if score > 0:
                    break

        if score == 0:
            continue

        if target_color and post_color:
            if target_color == post_color:
                score += 40
            else:
                score -= 15

        if target_capacity and post_capacity:
            if target_capacity == post_capacity:
                score += 20

        if score > best_score:
            best_score = score
            best_photos = post_photos
            matched_post_color = post_color
            matched_post_title = post_caption[:40]

    if best_photos and best_score >= 70:
        logger.info(f"   ✅ [MATCH FOUND IN POSTS] Score: {best_score} | Matched Post: '{matched_post_title}...' | Photos: {len(best_photos)} | IDs: {best_photos[:4]}")
        note = None
        if target_color and matched_post_color and target_color != matched_post_color:
            note = f"💡 <i>توجه: تصویر بالا مربوط به طراحی ظاهری و پنل این مدل (رنگ <b>{matched_post_color}</b>) می‌باشد و کالای ارسالی طبق سفارش شما به رنگ <b>{target_color}</b> خواهد بود.</i>"
        return best_photos, note

    candidate_keys = (target_models | target_cores) - STOP_WORDS_NOT_MODELS
    for m in candidate_keys:
        k_c = clean_key(m)
        if len(k_c) >= 3 and k_c in CHANNEL_PHOTOS_MAP and CHANNEL_PHOTOS_MAP[k_c]:
            cand_photos = CHANNEL_PHOTOS_MAP[k_c]
            is_valid = True
            for post in CHANNEL_POSTS_METADATA:
                p_photos = post.get("photos", []) or [str(x) for x in post.get("msg_ids", [])]
                if any(cp in p_photos for cp in cand_photos):
                    p_brand = normalize_brand(post.get("brand", "")) or extract_brand_from_text(post.get("caption", ""))
                    p_cat = normalize_category(post.get("category", "")) or extract_category_from_text(post.get("caption", ""))
                    if target_brand and p_brand and target_brand != p_brand:
                        is_valid = False
                        break
                    if target_category and p_cat and target_category != p_cat:
                        is_valid = False
                        break
            if is_valid:
                logger.info(f"   ✅ [MATCH FOUND IN DIRECT MAP] Key: '{k_c}' | Photos: {cand_photos[:4]}")
                return cand_photos, None

    img_url = product.get("image_url", "")
    if img_url and img_url.startswith("http"):
        logger.info(f"   🌐 [USING WEBSITE IMAGE] {img_url}")
        return [img_url], None

    logger.warning(f"   ❌ [NO PHOTO MATCHED] No gallery photos matched for {p_name}")
    return [], None

# ─── ارسال کارت کالا و عکس ───

async def send_product_card_and_photos(chat_id: int, product: dict, context: ContextTypes.DEFAULT_TYPE, user_query: str = ""):
    # تکمیل در لحظه مشخصات با هوش مصنوعی (جمینای / دیپ‌سیک / خاموش طبق تنظیمات پنل ادمین)
    try:
        from gemini_enricher import async_enrich_product_with_gemini_on_demand
        await async_enrich_product_with_gemini_on_demand(product)
    except Exception as e:
        logger.debug(f"On-demand AI specs note: {e}")

    pid = str(product.get("product_id", "")).strip()
    p_name = product.get("name", "")

    # ۱. بررسی وجود تصاویر تایید شده برای این کالا
    matched_pid, photo_data, match_type = find_matching_verified_photos(product or pid)
    photos_sent = False

    if photo_data:
        logger.info(f"📸 [DISPATCH] Verified photos found for '{p_name}'. Sending album first...")
        photos_sent = await send_verified_photos_to_user(
            bot=context.bot,
            chat_id=chat_id,
            pid=pid,
            product_name=p_name,
            photo_data=photo_data,
            matched_note=None
        )

    # بررسی آیا محصول از دسته لپ‌تاپ است (چون عکس ندارند نباید دکمه تصاویر نمایش داده شود)
    is_laptop = (
        product.get("category_key") == "laptop"
        or product.get("category") in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"]
        or product.get("category_name") in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"]
        or str(pid).upper().startswith("LAP")
        or any(w in str(p_name).lower() for w in ["لپ‌تاپ", "لپ تاپ", "لپتاپ", "laptop"])
    )

    # اگر عکس ارسال شده باشد یا کالا لپ‌تاپ باشد، دکمه «تصاویر محصول» نمایش داده نمی‌شود
    show_photo_btn = (not photos_sent) and (not is_laptop)
    is_admin = (chat_id in ADMIN_IDS) if ADMIN_IDS else False

    msg = build_boxed_product_message(product)
    kb = product_inline_keyboard(pid, context, show_photo_button=show_photo_btn, is_admin=is_admin)

    logger.info(f"📤 [DISPATCH] Sending product info box for '{p_name}' (ID: {pid}) to Chat: {chat_id} (is_admin={is_admin}, show_photo_btn={show_photo_btn})")

    # اگر تصاویر آلبوم تایید شده ارسال نشد، آیا عکس وب‌سایتی تکی موجود است؟
    if not photos_sent:
        img_url = product.get("image_url", "")
        if img_url and img_url.startswith("http"):
            try:
                m_obj, _ = await resolve_media_for_telegram(img_url)
                if m_obj:
                    if hasattr(m_obj, "seek"):
                        m_obj.seek(0)
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=m_obj,
                        caption=msg,
                        reply_markup=product_inline_keyboard(pid, context, show_photo_button=False, is_admin=is_admin),
                        parse_mode="HTML"
                    )
                    return
            except Exception as e:
                logger.warning(f"Failed to send web image for {p_name}: {e}")

    # ارسال پنجره مشخصات و قیمت همراه با کیبورد بهینه‌شده و غیرفعال‌سازی پیش‌نمایش لینک (disable link preview)
    try:
        from telegram import LinkPreviewOptions
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            reply_markup=kb,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
