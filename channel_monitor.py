"""
AiKala - Autonomous Channel Monitor & Smart Reposter (channel_monitor.py)
========================================================================
سیستم پیشرفته و هوشمند پایش کانال‌های مبدا و ریپوست به کانال @AiKala_Image:
۱. استخراج پست‌های ۴ ماه گذشته تمامی کانال‌های متصل با تمرکز بر پست‌های حاوی عکس (تک‌عکس و آلبوم)
۲. حفظ ۱۰۰٪ ساختار، کپشن و چیدمان آلبوم بدون حذف هیچ محتوایی
۳. ریپوست با مالکیت کامل کانال @AiKala_Image توسط ربات ادمین (بدن هدر فوروارد و با قابلیت ویرایش بعدی)
۴. ممانعت قطعی از ثبت پست‌های تکراری با ثبت شناسه در دیتابیس و فایل وضعیت
۵. زمان‌بندی خودکار هر ۱۲ ساعت یک‌بار جهت بررسی و انتشار پست‌های جدید
"""

import os
import re
import sys
import json
import time
import asyncio
import logging
import urllib.request
import urllib.parse
import html as html_lib
import io
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple, Set

try:
    import config
except ImportError:
    config = None

# ردیاب پایدار و استاندارد دیتابیس با sqlite3 توکار بدون نیاز به پکیج‌های خارجی
class ChannelRepostTracker:
    def __init__(self, db_path="bot_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS channel_reposts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_channel TEXT NOT NULL,
                        source_msg_id INTEGER NOT NULL,
                        target_channel TEXT NOT NULL,
                        target_msg_id INTEGER,
                        has_photo INTEGER DEFAULT 1,
                        reposted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(source_channel, source_msg_id)
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_channel_reposts_src ON channel_reposts(source_channel, source_msg_id);")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS monitored_channels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel_id TEXT UNIQUE NOT NULL,
                        channel_name TEXT,
                        keywords TEXT DEFAULT '',
                        active INTEGER DEFAULT 1,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
        except Exception as e:
            logger.warning(f"Tracker DB init note: {e}")

    def is_reposted(self, source_channel: str, source_msg_id: int) -> bool:
        src = source_channel.strip().lower()
        if not src.startswith("@"):
            src = f"@{src}"
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM channel_reposts WHERE LOWER(source_channel) = ? AND source_msg_id = ?", (src, source_msg_id))
                return cur.fetchone() is not None
        except Exception:
            return False

    def record_repost(self, source_channel: str, source_msg_id: int, target_channel: str, target_msg_id: Optional[int] = None, has_photo: bool = True):
        src = source_channel.strip().lower()
        if not src.startswith("@"):
            src = f"@{src}"
        tgt = target_channel.strip().lower()
        if not tgt.startswith("@"):
            tgt = f"@{tgt}"
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute("""
                    INSERT INTO channel_reposts (source_channel, source_msg_id, target_channel, target_msg_id, has_photo, reposted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_channel, source_msg_id) DO UPDATE SET
                        target_channel = excluded.target_channel,
                        target_msg_id = excluded.target_msg_id
                """, (src, source_msg_id, tgt, target_msg_id, 1 if has_photo else 0, datetime.now().isoformat()))
                conn.commit()
        except Exception as e:
            logger.error(f"Error recording repost in tracker: {e}")

    def get_reposted_ids(self, source_channel: str) -> set:
        src = source_channel.strip().lower()
        if not src.startswith("@"):
            src = f"@{src}"
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("SELECT source_msg_id FROM channel_reposts WHERE LOWER(source_channel) = ?", (src,))
                return set(r[0] for r in cur.fetchall())
        except Exception:
            return set()

    def get_total_count(self) -> int:
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM channel_reposts")
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def get_stats(self) -> Dict[str, int]:
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("SELECT source_channel, COUNT(*) FROM channel_reposts GROUP BY source_channel")
                return {r[0]: r[1] for r in cur.fetchall()}
        except Exception:
            return {}

    def get_monitored_channels(self) -> List[str]:
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                cur = conn.cursor()
                cur.execute("SELECT channel_id FROM monitored_channels WHERE active = 1")
                return [r[0] for r in cur.fetchall()]
        except Exception:
            return []

    def add_channel(self, channel_id: str):
        cid = channel_id.strip()
        if not cid.startswith("@") and not cid.startswith("-100"):
            cid = f"@{cid}"
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute("""
                    INSERT INTO monitored_channels (channel_id, channel_name, active, added_at)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(channel_id) DO UPDATE SET active = 1
                """, (cid, cid, datetime.now().isoformat()))
                conn.commit()
        except Exception as e:
            logger.error(f"Error adding channel to tracker: {e}")

    def delete_channel(self, channel_id: str):
        cid = channel_id.strip().lower()
        try:
            with sqlite3.connect(self.db_path, timeout=5) as conn:
                conn.execute("DELETE FROM monitored_channels WHERE LOWER(channel_id) = ?", (cid,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error deleting channel from tracker: {e}")

tracker = ChannelRepostTracker()

try:
    from database import Database
    db = Database()
except Exception:
    db = None

# کانال مقصد و تنظیمات تلگرام
TARGET_IMAGE_CHANNEL = getattr(
    config, "TARGET_IMAGE_CHANNEL",
    getattr(config, "PHOTOS_CHANNEL", os.getenv("TARGET_IMAGE_CHANNEL", "@img_ai_amp"))
)
if not TARGET_IMAGE_CHANNEL.startswith("@") and not str(TARGET_IMAGE_CHANNEL).startswith("-100"):
    TARGET_IMAGE_CHANNEL = f"@{TARGET_IMAGE_CHANNEL}"

BOT_TOKEN = getattr(config, "TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))

STATE_FILE = "monitor_state.json"
DEFAULT_HISTORY_DAYS = 120          # ۴ ماه گذشته (۱۲۰ روز)

# ─── زمان‌بندی شبانه (یک‌بار در ۲۴ ساعت بین ساعات ۰۲:۰۰ الی ۰۵:۰۰ بامداد به وقت تهران) ───
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))
NIGHT_WINDOW_START_HOUR = 2   # آغاز بازه شبانه: ۰۲:۰۰ بامداد
NIGHT_WINDOW_END_HOUR = 5     # پایان بازه شبانه: ۰۵:۰۰ بامداد
TARGET_NIGHT_HOUR = 2         # ساعت اجرای روزانه: ۰۲:۳۰ بامداد
TARGET_NIGHT_MINUTE = 30

def get_tehran_now() -> datetime:
    """دریافت زمان کنونی دقیق به وقت ایران (تهران UTC+3:30)"""
    return datetime.now(TEHRAN_TZ)

def get_next_night_run_datetime(from_dt: Optional[datetime] = None) -> datetime:
    """محاسبه دقیق زمان اجرای شبانه بعدی (ساعت 02:30 بامداد به وقت تهران)"""
    now = from_dt or get_tehran_now()
    target_today = now.replace(hour=TARGET_NIGHT_HOUR, minute=TARGET_NIGHT_MINUTE, second=0, microsecond=0)
    if now < target_today:
        return target_today
    return target_today + timedelta(days=1)

def seconds_until_next_night_run() -> float:
    """محاسبه ثانیه‌های باقیمانده تا اجرای شبانه بعدی"""
    now = get_tehran_now()
    next_run = get_next_night_run_datetime(now)
    diff = (next_run - now).total_seconds()
    return max(0.0, diff)

def is_within_night_window(dt: Optional[datetime] = None) -> bool:
    """بررسی اینکه آیا زمان کنونی در بازه شبانه مجاز (۲ الی ۵ بامداد تهران) قرار دارد یا خیر"""
    now = dt or get_tehran_now()
    return NIGHT_WINDOW_START_HOUR <= now.hour < NIGHT_WINDOW_END_HOUR

logger = logging.getLogger("ChannelMonitor")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | [CHANNEL-MONITOR] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# وضعیت مانیتورینگ جهت گزارش به پنل ادمین
MONITOR_STATUS = {
    "is_running": False,
    "last_run": None,
    "next_run": get_next_night_run_datetime().strftime("%Y-%m-%d %H:%M:%S (تهران)"),
    "total_reposted": 0,
    "current_channel": None,
    "errors_count": 0,
}


def load_monitor_state() -> Dict[str, int]:
    """بارگذاری آخرین وضعیت شناسه‌های بررسی شده برای هر کانال"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading {STATE_FILE}: {e}")
    return {}


def save_monitor_state(state: Dict[str, int]):
    """ذخیره امن وضعیت شناسه‌های پردازش شده"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {STATE_FILE}: {e}")


def normalize_channel_username(ch: str) -> str:
    """استانداردسازی نام کانال به فرمت @username"""
    c = ch.strip()
    if c.startswith("https://t.me/"):
        c = c.replace("https://t.me/", "")
    elif c.startswith("t.me/"):
        c = c.replace("t.me/", "")
    if "/" in c:
        c = c.split("/")[0]
    if not c.startswith("@") and not c.startswith("-100"):
        c = f"@{c}"
    return c


async def get_target_channels_list() -> List[str]:
    """دریافت لیست جامع کانال‌های تحت پایش از دیتابیس و کانفیگ"""
    channels_set: Set[str] = set()

    # ۱. کانال‌های فعال ثبت شده در دیتابیس
    for ch in tracker.get_monitored_channels():
        channels_set.add(normalize_channel_username(ch))

    if db:
        try:
            db_channels = await db.get_monitored_channels()
            for ch in db_channels:
                if ch.get("active", True):
                    channels_set.add(normalize_channel_username(ch["channel_id"]))
        except Exception as e:
            logger.warning(f"Failed to read channels from DB: {e}")

    # ۲. کانال‌های پیش‌فرض موجود در config.TARGET_CHANNEL_ID
    default_channels_raw = getattr(config, "TARGET_CHANNEL_ID", "") or ""
    if default_channels_raw:
        for ch in default_channels_raw.split(","):
            if ch.strip():
                channels_set.add(normalize_channel_username(ch))

    # ۳. کانال‌های موجود در monitor_state.json
    state = load_monitor_state()
    for ch in state.keys():
        if ch.strip():
            channels_set.add(normalize_channel_username(ch))

    # حذف کانال مقصد از لیست مبدا در صورت وجود
    target_clean = normalize_channel_username(TARGET_IMAGE_CHANNEL).lower()
    final_list = [c for c in sorted(list(channels_set)) if c.lower() != target_clean]
    return final_list


# ─── موتور دانلود تصاویر با بافر رم ───

def download_image_bytes(url: str, timeout: int = 12) -> Optional[bytes]:
    """دانلود باینری عکس در رم با هدر معتبر برای عبور بدون خطای cURL"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        logger.debug(f"Failed to download image {url[:70]}: {e}")
        return None


# ─── موتور ارسال پیام به تلگرام بات بدون وابستگی به لایبرری خاص ───

async def telegram_api_call(method: str, params: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """ارسال درخواست مستقیم و ایمن به Telegram Bot API با پشتیبانی از چندبخشی (Multipart)"""
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured!")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    
    def _do_request():
        if files:
            import mimetypes
            boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
            body = io.BytesIO()
            
            # فیلدهای معمولی
            if params:
                for k, v in params.items():
                    val = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
                    body.write(f"--{boundary}\r\n".encode("utf-8"))
                    body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
                    body.write(f"{val}\r\n".encode("utf-8"))
                    
            # فیلدهای فایل
            for field_name, (filename, file_data) in files.items():
                mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                body.write(f"--{boundary}\r\n".encode("utf-8"))
                body.write(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
                body.write(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
                body.write(file_data)
                body.write(b"\r\n")
                
            body.write(f"--{boundary}--\r\n".encode("utf-8"))
            body_bytes = body.getvalue()
            
            req = urllib.request.Request(
                url,
                data=body_bytes,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "User-Agent": "AiKala-ChannelMonitor/2.0"
                }
            )
        else:
            json_data = json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=json_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "AiKala-ChannelMonitor/2.0"
                }
            )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(err_body)
            except Exception:
                return {"ok": False, "error_code": he.code, "description": err_body}
        except Exception as exc:
            return {"ok": False, "description": str(exc)}

    res = await asyncio.to_thread(_do_request)
    return res


# ─── تبدیل ساختار HTML تلگرام وب به متن سالم با حفظ ساختار ───

def html_to_telegram_caption(html_text: str) -> str:
    """تبدیل دقیق متن HTML ویجت به متن با حفظ فرمت و ساختار کامل بدون حذف کلمات"""
    if not html_text:
        return ""
    # تبدیل تگ‌های شکست خط به newline
    t = re.sub(r'<br\s*/?>', '\n', html_text)
    t = re.sub(r'</?(?:p|div)[^>]*>', '\n', t)
    # حفظ لینک‌های تلگرام
    t = re.sub(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', r'<a href="\1">\2</a>', t)
    # حذف سایر تگ‌های غیرمجاز و حفظ متن درون آن‌ها
    t = re.sub(r'<(?!\/?(?:b|strong|i|em|u|ins|s|strike|del|a|code|pre)\b)[^>]+>', '', t)
    t = html_lib.unescape(t)
    return t.strip()


def strip_html_tags(text: str) -> str:
    """استخراج متن خام بدون هیچ تگی جهت فال‌بک در صورت خطای ساختار HTML"""
    t = re.sub(r'<[^>]+>', '', text or '')
    return html_lib.unescape(t).strip()


# ─── اسکرپر پیشرفته پست‌ها و آلبوم‌های وب کانال ───

def parse_channel_web_page(html: str) -> List[Dict[str, Any]]:
    """تجزیه HTML صفحه کانال تلگرام به ساختارهای پست کامل شامل تاریخ، آلبوم و متن"""
    posts = []
    if not html:
        return posts

    # بخش‌های مربوط به هر پیام
    message_blocks = html.split('class="tgme_widget_message_wrap')
    for block in message_blocks[1:]:
        # شناسه پست
        m_id = re.search(r'data-post="[^/]+/(\d+)"', block)
        if not m_id:
            continue
        msg_id = int(m_id.group(1))

        # تاریخ و ساعت پیام
        m_time = re.search(r'<time\s+datetime="([^"]+)"', block)
        post_datetime: Optional[datetime] = None
        if m_time:
            try:
                # 2026-08-16T08:12:54+00:00
                dt_str = m_time.group(1)
                if "+" in dt_str or dt_str.endswith("Z"):
                    post_datetime = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                else:
                    post_datetime = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
            except Exception:
                pass

        # استخراج عکس‌ها
        raw_photos = re.findall(r"background-image:url\(\x27([^\x27]+)\x27\)", block)
        clean_photos = []
        for p in raw_photos:
            if "emoji" not in p and ("telesco.pe" in p or "cdn" in p or "telegram" in p):
                if p not in clean_photos:
                    clean_photos.append(p)

        # استخراج متن کپشن
        m_text = re.search(r'class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
        caption_html = m_text.group(1) if m_text else ""
        caption = html_to_telegram_caption(caption_html)

        # آیا پیام حاوی عکس است؟ (تک‌عکس یا آلبوم)
        if clean_photos:
            posts.append({
                "msg_id": msg_id,
                "datetime": post_datetime,
                "photos": clean_photos,
                "caption": caption,
                "caption_raw": caption_html
            })

    return posts


async def fetch_channel_posts_from_web(channel_clean: str, before_id: Optional[int] = None) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """واکشی یک صفحه از پست‌های کانال تلگرام از طریق ویو عمومی با هدرهای مرورگر"""
    url = f"https://t.me/s/{channel_clean}"
    if before_id:
        url += f"?before={before_id}"

    def _fetch():
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "fa,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"Fetch web failed for {url}: {e}")
            return ""

    html = await asyncio.to_thread(_fetch)
    if not html:
        return [], None

    posts = parse_channel_web_page(html)
    min_id = None
    all_mids = [p["msg_id"] for p in posts]
    if all_mids:
        min_id = min(all_mids)

    return posts, min_id


# ─── ارسال پست به @AiKala_Image به صورت مستقل (با مالکیت @AiKala_Image) ───

async def repost_photo_post_to_target(post: Dict[str, Any], source_channel: str) -> Optional[int]:
    """
    ریپوست عکس یا آلبوم بدون هیچ‌گونه حذف، با مالکیت کامل کانال @AiKala_Image.
    - اگر ۱ عکس باشد: sendPhoto
    - اگر چند عکس باشد: sendMediaGroup (InputMediaPhoto)
    - اگر کپشن طولانی‌تر از ۱۰۲۴ کاراکتر باشد، بخش اولیه با عکس و مابقی بلافاصله به عنوان ریپلای متصل ارسال می‌گردد.
    """
    photos = post.get("photos", [])
    if not photos:
        return None

    caption = post.get("caption", "").strip()
    msg_id = post.get("msg_id")

    # دانلود عکس‌ها در رم
    download_tasks = [asyncio.to_thread(download_image_bytes, p) for p in photos]
    downloaded = await asyncio.gather(*download_tasks)
    valid_photos = [b for b in downloaded if b is not None and len(b) > 1000]

    if not valid_photos:
        logger.warning(f"⚠️ [REPOST] Could not download any photos for {source_channel}/{msg_id}")
        return None

    # تقسیم کپشن در صورت بیشتر بودن از ۱۰۲۴ کاراکتر (محدودیت مدیا تلگرام)
    media_caption = caption
    followup_text = ""
    if len(caption) > 1024:
        # برش هوشمند روی آخرین خط یا فاصله قبل از ۱۰۰۰ کاراکتر
        split_idx = caption.rfind("\n", 0, 1000)
        if split_idx <= 200:
            split_idx = caption.rfind(" ", 0, 1000)
        if split_idx <= 200:
            split_idx = 1000
        media_caption = caption[:split_idx] + "..."
        followup_text = caption[split_idx:].strip()

    target_msg_id: Optional[int] = None

    # الف) پست تک‌عکس
    if len(valid_photos) == 1:
        photo_bytes = valid_photos[0]
        params = {
            "chat_id": TARGET_IMAGE_CHANNEL,
            "caption": media_caption,
            "parse_mode": "HTML"
        }
        files = {
            "photo": ("image.jpg", photo_bytes)
        }
        res = await telegram_api_call("sendPhoto", params=params, files=files)

        # در صورت خطای پارس HTML، تلاش مجدد با متن خام
        if not res.get("ok"):
            err_desc = res.get("description", "")
            if "can't parse" in err_desc.lower() or "entity" in err_desc.lower():
                logger.debug(f"HTML parse failed ({err_desc}), retrying plain text...")
                params["caption"] = strip_html_tags(media_caption)
                params.pop("parse_mode", None)
                res = await telegram_api_call("sendPhoto", params=params, files=files)
            elif "flood" in err_desc.lower() or res.get("error_code") == 429:
                wait_sec = res.get("parameters", {}).get("retry_after", 10)
                logger.warning(f"⏳ Rate limit hit. Sleeping {wait_sec + 2}s...")
                await asyncio.sleep(wait_sec + 2)
                res = await telegram_api_call("sendPhoto", params=params, files=files)

        if res.get("ok"):
            target_msg_id = res.get("result", {}).get("message_id")
        else:
            logger.error(f"❌ Failed to sendPhoto for {source_channel}/{msg_id}: {res.get('description')}")
            return None

    # ب) پست چند عکسه (آلبوم / MediaGroup)
    else:
        # ساخت InputMediaPhoto تا حداکثر ۱۰ عکس (سقف تلگرام برای هر آلبوم)
        chunk = valid_photos[:10]
        media_array = []
        files = {}
        for idx, p_bytes in enumerate(chunk):
            attach_name = f"photo_{idx}.jpg"
            files[attach_name] = (attach_name, p_bytes)
            item = {
                "type": "photo",
                "media": f"attach://{attach_name}"
            }
            if idx == 0 and media_caption:
                item["caption"] = media_caption
                item["parse_mode"] = "HTML"
            media_array.append(item)

        params = {
            "chat_id": TARGET_IMAGE_CHANNEL,
            "media": media_array
        }
        res = await telegram_api_call("sendMediaGroup", params=params, files=files)

        # فال‌بک در صورت خطای پارس HTML
        if not res.get("ok"):
            err_desc = res.get("description", "")
            if "can't parse" in err_desc.lower() or "entity" in err_desc.lower():
                logger.debug(f"MediaGroup HTML parse failed, retrying plain text...")
                media_array[0]["caption"] = strip_html_tags(media_caption)
                media_array[0].pop("parse_mode", None)
                params["media"] = media_array
                res = await telegram_api_call("sendMediaGroup", params=params, files=files)
            elif "flood" in err_desc.lower() or res.get("error_code") == 429:
                wait_sec = res.get("parameters", {}).get("retry_after", 10)
                logger.warning(f"⏳ Rate limit hit. Sleeping {wait_sec + 2}s...")
                await asyncio.sleep(wait_sec + 2)
                res = await telegram_api_call("sendMediaGroup", params=params, files=files)

        if res.get("ok"):
            # تلگرام لیستی از پیام‌های ارسال شده را بازمی‌گرداند
            results_list = res.get("result", [])
            if results_list and isinstance(results_list, list):
                target_msg_id = results_list[0].get("message_id")
        else:
            logger.error(f"❌ Failed to sendMediaGroup for {source_channel}/{msg_id}: {res.get('description')}")
            return None

    # ارسال متن تکمیلی بلند به صورت ریپلای در صورت نیاز
    if target_msg_id and followup_text:
        try:
            await asyncio.sleep(0.8)
            f_res = await telegram_api_call("sendMessage", params={
                "chat_id": TARGET_IMAGE_CHANNEL,
                "text": strip_html_tags(followup_text),
                "reply_to_message_id": target_msg_id
            })
            if not f_res.get("ok"):
                await telegram_api_call("sendMessage", params={
                    "chat_id": TARGET_IMAGE_CHANNEL,
                    "text": strip_html_tags(followup_text)
                })
        except Exception as e:
            logger.debug(f"Followup text send note: {e}")

    # ثبت در نقشه عکس‌های کاتالوگ فروشگاه ربات جهت دسترسی سریع خریداران
    try:
        from photo_service import register_photo_message
        if target_msg_id and photos:
            register_photo_message(
                text=caption,
                photo_file_id=photos[0],
                msg_id=target_msg_id
            )
    except Exception:
        pass

    return target_msg_id


# ─── اسکن و ریپوست یک کانال خاص (۴ ماه گذشته یا تا آخرین پست دیده شده) ───

async def sync_single_channel(channel: str, days: int = DEFAULT_HISTORY_DAYS, max_pages: int = 40) -> Dict[str, Any]:
    """
    پویش کانال مبدا، استخراج پست‌های عکس‌دار ۴ ماه گذشته و ریپوست ایمن به @AiKala_Image
    """
    ch_norm = normalize_channel_username(channel)
    ch_clean = ch_norm.replace("@", "")
    logger.info(f"📡 [CHANNEL SYNC] Starting sync for {ch_norm} (past {days} days)...")

    MONITOR_STATUS["current_channel"] = ch_norm

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    state = load_monitor_state()
    reposted_count = 0
    scanned_posts_count = 0

    # خواندن پست‌های قبلاً ریپوست شده از دیتابیس برای جلوگیری قطعی از تکرار
    already_reposted_ids = tracker.get_reposted_ids(ch_norm)
    if db:
        try:
            db_ids = await db.get_reposted_ids(ch_norm)
            already_reposted_ids.update(db_ids)
        except Exception as e:
            logger.debug(f"DB read reposted ids note: {e}")

    current_before_id: Optional[int] = None
    stop_scanning = False

    for page_idx in range(max_pages):
        if stop_scanning:
            break

        posts, min_id = await fetch_channel_posts_from_web(ch_clean, before_id=current_before_id)
        if not posts or not min_id:
            logger.info(f"   ℹ️ Reached end of available posts for {ch_norm} at page {page_idx + 1}.")
            break

        # مرتب‌سازی پست‌ها بر اساس شناسه (از قدیمی به جدید)
        posts.sort(key=lambda p: p["msg_id"])

        for post in posts:
            scanned_posts_count += 1
            p_mid = post["msg_id"]
            p_dt = post.get("datetime")

            # ۱. بررسی محدوده زمانی ۴ ماه گذشته
            if p_dt and p_dt < cutoff_date:
                logger.info(f"   🛑 Reached 4-month cutoff ({p_dt.strftime('%Y-%m-%d')}) for {ch_norm}.")
                stop_scanning = True
                break

            # ۲. بررسی آیا قبلاً ریپوست شده است؟
            if p_mid in already_reposted_ids or tracker.is_reposted(ch_norm, p_mid):
                continue

            if db:
                is_done = await db.is_post_reposted(ch_norm, p_mid)
                if is_done:
                    already_reposted_ids.add(p_mid)
                    continue

            # ۳. ریپوست به کانال مقصد @AiKala_Image
            try:
                target_mid = await repost_photo_post_to_target(post, ch_norm)
                if target_mid:
                    reposted_count += 1
                    MONITOR_STATUS["total_reposted"] += 1
                    already_reposted_ids.add(p_mid)

                    tracker.record_repost(
                        source_channel=ch_norm,
                        source_msg_id=p_mid,
                        target_channel=TARGET_IMAGE_CHANNEL,
                        target_msg_id=target_mid,
                        has_photo=True
                    )

                    if db:
                        try:
                            await db.record_repost(
                                source_channel=ch_norm,
                                source_msg_id=p_mid,
                                target_channel=TARGET_IMAGE_CHANNEL,
                                target_msg_id=target_mid,
                                has_photo=True
                            )
                        except Exception:
                            pass

                    logger.info(
                        f"   ✅ Reposted {ch_norm}/{p_mid} -> {TARGET_IMAGE_CHANNEL}/{target_mid} "
                        f"({len(post['photos'])} photo(s))"
                    )

                    # تاخیر مناسب بین ارسال‌ها جهت ممانعت از محدودیت نرخ تلگرام (Flood Rate Limits)
                    await asyncio.sleep(2.5)

            except Exception as e:
                MONITOR_STATUS["errors_count"] += 1
                logger.error(f"Error reposting post {ch_norm}/{p_mid}: {e}")
                await asyncio.sleep(3)

        # به روزرسانی نشانگر وضعیت
        if min_id and (current_before_id is None or min_id < current_before_id):
            current_before_id = min_id
        else:
            break

        # تاخیر ملایم بین صفحات وب
        await asyncio.sleep(1.2)

    # به روزرسانی آخرین شناسه پردازش شده در فایل وضعیت
    if already_reposted_ids:
        state[ch_norm] = max(already_reposted_ids)
        save_monitor_state(state)

    logger.info(f"🏁 [CHANNEL SYNC COMPLETE] {ch_norm}: Scanned {scanned_posts_count} posts, Reposted {reposted_count} new posts.")
    return {
        "channel": ch_norm,
        "scanned": scanned_posts_count,
        "reposted": reposted_count
    }


# ─── پایش جامع تمامی کانال‌ها ───

async def sync_all_monitored_channels(days: int = DEFAULT_HISTORY_DAYS) -> Dict[str, Any]:
    """اجرای همگام‌سازی و ریپوست برای تمامی کانال‌های متصل به سیستم"""
    channels = await get_target_channels_list()
    logger.info(f"🚀 [MONITOR ALL] Starting full 12-hour sync cycle for {len(channels)} channel(s)...")

    results = {}
    total_reposted_cycle = 0

    for ch in channels:
        try:
            res = await sync_single_channel(ch, days=days)
            results[ch] = res
            total_reposted_cycle += res.get("reposted", 0)
        except Exception as e:
            logger.error(f"Failed to sync channel {ch}: {e}")
            results[ch] = {"channel": ch, "error": str(e), "reposted": 0}

        # فاصله کوتاه بین کانال‌ها
        await asyncio.sleep(3.0)

    now_t = get_tehran_now()
    next_t = get_next_night_run_datetime(now_t)
    MONITOR_STATUS["last_run"] = now_t.strftime("%Y-%m-%d %H:%M:%S (تهران)")
    MONITOR_STATUS["next_run"] = next_t.strftime("%Y-%m-%d %H:%M:%S (تهران)")
    MONITOR_STATUS["current_channel"] = None

    logger.info(f"✨ [MONITOR CYCLE COMPLETED] Reposted {total_reposted_cycle} new photo posts to {TARGET_IMAGE_CHANNEL}.")
    return {
        "channels_count": len(channels),
        "total_reposted": total_reposted_cycle,
        "details": results
    }


# ─── افزودن کانال جدید و آغاز فوری پویش ۴ ماهه ───

async def add_and_sync_channel(channel_username: str) -> Dict[str, Any]:
    """افزودن کانال جدید به لیست پایش و آغاز فوری بررسی و ریپوست پست‌های ۴ ماه گذشته آن"""
    c_norm = normalize_channel_username(channel_username)
    if db:
        await db.add_monitored_channel(c_norm, channel_name=c_norm)

    # اجرای همگام‌سازی ۴ ماهه برای کانال تازه افزوده شده
    res = await sync_single_channel(c_norm, days=DEFAULT_HISTORY_DAYS)
    return res


# ─── حلقه دائمی زمان‌بندی شبانه (Daemon Worker) ───

async def sleep_gracefully(total_seconds: float, slice_seconds: float = 60.0):
    """خواب در فواصل زمانی کوتاه تا امکان هندل کردن سیگنال‌ها و خروج ایمن همیشه میسر باشد"""
    remaining = total_seconds
    while remaining > 0:
        step = min(remaining, slice_seconds)
        await asyncio.sleep(step)
        remaining -= step


async def run_channel_monitor_loop():
    """حلقه زمان‌بندی خودکار شبانه پایش کانال‌ها (یک‌بار در ۲۴ ساعت در دل شب):
    - اجرای خودکار منحصراً بین ساعات ۰۲:۰۰ الی ۰۵:۰۰ بامداد به وقت تهران (هدف: ساعت ۰۲:۳۰ بامداد)
    - در تمام ساعات روز در حالت استندبای و خواب کامل قرار دارد تا هیچ بار پردازشی یا افت سرعتی برای ربات ایجاد نشود.
    """
    MONITOR_STATUS["is_running"] = True
    next_night = get_next_night_run_datetime()
    MONITOR_STATUS["next_run"] = next_night.strftime("%Y-%m-%d %H:%M:%S (تهران)")
    logger.info(
        f"🌙 [NIGHTLY MONITOR STARTED] Scheduled ONCE per 24 hours between 02:00 and 05:00 AM (Tehran). "
        f"Next execution target: {MONITOR_STATUS['next_run']}. Standby mode active during daytime."
    )

    last_executed_night_date: Optional[str] = None

    while True:
        now_tehran = get_tehran_now()
        today_date_str = now_tehran.strftime("%Y-%m-%d")

        # آیا هم‌اکنون در بازه نیمه‌شب (۲ تا ۵ بامداد) هستیم و امشب هنوز اجرا نشده است؟
        if is_within_night_window(now_tehran) and last_executed_night_date != today_date_str:
            logger.info(
                f"🌕 [MIDNIGHT SYNC TRIGGERED] Current Tehran time: {now_tehran.strftime('%H:%M:%S')}. "
                f"Starting once-daily night sync cycle for all monitored channels..."
            )
            try:
                await sync_all_monitored_channels(days=DEFAULT_HISTORY_DAYS)
                last_executed_night_date = today_date_str
            except Exception as e:
                logger.error(f"❌ Error in nightly channel sync cycle: {e}")

            # پس از پایان اجرای شبانه، محاسبه زمان انتظار تا فردا شب ساعت ۰۲:۳۰
            next_night = get_next_night_run_datetime()
            MONITOR_STATUS["next_run"] = next_night.strftime("%Y-%m-%d %H:%M:%S (تهران)")
            wait_seconds = seconds_until_next_night_run()
            hours_wait = wait_seconds / 3600.0
            logger.info(
                f"😴 [NIGHT SYNC FINISHED] Sleeping for ~{hours_wait:.1f} hours until tomorrow night's run at {MONITOR_STATUS['next_run']}..."
            )
            await sleep_gracefully(wait_seconds)
        else:
            # خارج از بازه شبانه، یا امشب اجرا شده است: استندبای و خواب سبک تا فرارسیدن ساعت ۰۲:۳۰ بامداد
            wait_seconds = seconds_until_next_night_run()
            next_night = get_next_night_run_datetime()
            MONITOR_STATUS["next_run"] = next_night.strftime("%Y-%m-%d %H:%M:%S (تهران)")
            hours_wait = wait_seconds / 3600.0
            logger.info(
                f"☀️ [DAYTIME STANDBY] Outside night window (Tehran time: {now_tehran.strftime('%H:%M:%S')}). "
                f"Standing by for ~{hours_wait:.1f} hours until midnight run at {MONITOR_STATUS['next_run']}. (Zero bot latency)"
            )
            await sleep_gracefully(wait_seconds)


def main():
    """نقطه ورود اجرای مستقیم خط فرمان (CLI)"""
    import argparse
    parser = argparse.ArgumentParser(description="AiKala Autonomous Channel Monitor & Reposter")
    parser.add_argument("--sync-now", action="store_true", help="Run one full sync cycle immediately and exit")
    parser.add_argument("--channel", type=str, help="Sync specific channel only (e.g. @BanehErsal)")
    parser.add_argument("--days", type=int, default=DEFAULT_HISTORY_DAYS, help="Number of days to look back (default: 120)")
    args = parser.parse_args()

    if args.channel:
        asyncio.run(sync_single_channel(args.channel, days=args.days))
    elif args.sync_now:
        asyncio.run(sync_all_monitored_channels(days=args.days))
    else:
        try:
            asyncio.run(run_channel_monitor_loop())
        except KeyboardInterrupt:
            logger.info("Channel monitor stopped by user.")


if __name__ == "__main__":
    main()
