"""
AiKala - Freeze & Maintenance Controller (freeze_service.py)
===========================================================
مدیریت توقف موقت (Pause / Freeze) فعالیت‌های ربات توسط ادمین اصلی:
- تعلیق کامل پاسخگویی ربات به کاربران عادی در زمان بروزرسانی یا تغییرات سرور
- تنظیم پیام اختصاصی و سفارشی جهت نمایش به کاربران
- ذخیره‌سازی وضعیت در bot_freeze_state.json با قابلیت پشتیبان‌گیری و بازیابی
- بازگشت فوری به حالت عادی (Resume / Unfreeze)
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

FREEZE_STATE_FILE = "bot_freeze_state.json"

DEFAULT_FREEZE_MESSAGE = (
    "⏸ فعالیت‌های ربات به دلیل بروزرسانی و ارتقای سرور موقتاً متوقف شده است.\n"
    "از شکیبایی شما سپاسگزاریم؛ به زودی در دسترس خواهیم بود."
)

DEFAULT_FREEZE_STATE: Dict[str, Any] = {
    "is_frozen": False,
    "freeze_message": DEFAULT_FREEZE_MESSAGE,
    "updated_at": "",
    "updated_by": None
}

def load_freeze_state() -> Dict[str, Any]:
    """بارگذاری ایمن وضعیت فریز از فایل پیکربندی"""
    state = dict(DEFAULT_FREEZE_STATE)
    if os.path.exists(FREEZE_STATE_FILE):
        try:
            with open(FREEZE_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    state.update(data)
        except Exception as e:
            logger.warning(f"Error loading {FREEZE_STATE_FILE}: {e}")
    return state

def save_freeze_state(state: Dict[str, Any]) -> bool:
    """ذخیره اتمیک وضعیت فریز در دیسک"""
    try:
        temp_file = f"{FREEZE_STATE_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, FREEZE_STATE_FILE)
        return True
    except Exception as e:
        logger.error(f"Error saving {FREEZE_STATE_FILE}: {e}")
        return False

def is_bot_frozen() -> bool:
    """بررسی اینکه آیا ربات در حالت فریز / تعلیق قرار دارد یا خیر"""
    state = load_freeze_state()
    return bool(state.get("is_frozen", False))

def get_freeze_message() -> str:
    """دریافت پیام تنظیم‌شده ادمین برای زمان فریز"""
    state = load_freeze_state()
    msg = state.get("freeze_message", "")
    if not msg or not str(msg).strip():
        return DEFAULT_FREEZE_MESSAGE
    return str(msg).strip()

def freeze_bot(admin_id: int, custom_message: Optional[str] = None) -> Tuple[bool, str]:
    """
    فعال‌سازی حالت فریز ربات توسط ادمین اصلی
    """
    state = load_freeze_state()
    state["is_frozen"] = True
    if custom_message and str(custom_message).strip():
        state["freeze_message"] = str(custom_message).strip()
    
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    state["updated_at"] = now_str
    state["updated_by"] = int(admin_id) if admin_id else None

    ok = save_freeze_state(state)
    if ok:
        logger.info(f"Bot frozen by admin {admin_id} at {now_str}")
        return True, "ربات با موفقیت فریز گردید."
    return False, "خطا در ذخیره وضعیت فریز ربات."

def unfreeze_bot(admin_id: int) -> Tuple[bool, str]:
    """
    خروج ربات از حالت فریز و بازگشت به روال عادی و اجرایی
    """
    state = load_freeze_state()
    state["is_frozen"] = False
    
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    state["updated_at"] = now_str
    state["updated_by"] = int(admin_id) if admin_id else None

    ok = save_freeze_state(state)
    if ok:
        logger.info(f"Bot unfrozen (resumed) by admin {admin_id} at {now_str}")
        return True, "ربات با موفقیت فعال شد و به روال عادی بازگشت."
    return False, "خطا در فعال‌سازی مجدد ربات."

def set_freeze_message(admin_id: int, new_message: str) -> Tuple[bool, str]:
    """
    ویرایش متن پیام فریز بدون تغییر در وضعیت جاری ربات
    """
    if not new_message or not str(new_message).strip():
        return False, "پیام نمی‌تواند خالی باشد."
    
    state = load_freeze_state()
    state["freeze_message"] = str(new_message).strip()
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    state["updated_at"] = now_str
    state["updated_by"] = int(admin_id) if admin_id else None

    ok = save_freeze_state(state)
    if ok:
        logger.info(f"Freeze message updated by admin {admin_id}")
        return True, "پیام فریز با موفقیت بروزرسانی شد."
    return False, "خطا در بروزرسانی پیام فریز."

def get_freeze_status_summary() -> Dict[str, Any]:
    """دریافت خلاصه وضعیت برای نمایش در پنل مدیریت"""
    state = load_freeze_state()
    return {
        "is_frozen": state.get("is_frozen", False),
        "message": state.get("freeze_message", DEFAULT_FREEZE_MESSAGE),
        "updated_at": state.get("updated_at", "نامشخص"),
        "updated_by": state.get("updated_by", "نامشخص")
    }
