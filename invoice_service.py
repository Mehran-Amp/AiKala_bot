"""
Option B: Ultra HD (1200px) Modern Executive POS & Invoice Generator
========================================================================
- رزولوشن Full HD (عرض ۱۲۰۰ پیکسل شارپ و خوانا در موبایل و چاپ اداری)
- زبان تماماً فارسی با تاریخ خورشیدی جلالی (jdatetime)
- پشتیبانی هوشمند از لوگوی اختصاصی (logo.png) با فال‌بک مدرن نشان تجاری
- پشتیبانی از مهر رسمی فروشگاه (stamp.png) با فال‌بک مهر برداری شرکتی
- تفکیک کامل پیش‌فاکتور (در انتظار بیعانه) و فاکتور فروش رسمی و قطعی
- درج ۵ بند رسمی شرایط تحویل و ضمانت به همراه تاییدیه کتبی تحویل در فاکتور نهایی
"""
import time


import os
import re
import urllib.request
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# ── پالت رنگی مدرن و صنعتی (Fintech Slate Palette) ───────────────
WHITE = (255, 255, 255)
COLOR_BG_PAGE = (255, 255, 255)
COLOR_DARK = (15, 23, 42)          # سنگ سرمه‌ای تیره #0F172A
COLOR_NAVY = (30, 41, 59)          # سرمه‌ای مایل به خاکستری #1E293B
COLOR_GRAY = (71, 85, 105)         # خاکستری مات #475569
COLOR_MUTED = (148, 163, 184)      # خاکستری روشن #94A3B8
COLOR_BORDER = (226, 232, 240)     # خطوط حاشیه مدرن #E2E8F0
COLOR_BORDER_LIGHT = (241, 245, 249) # #F1F5F9
COLOR_BG_CARD = (248, 250, 252)    # پس‌زمینه کارت‌ها #F8FAFC

# رنگ‌های وضعیت
COLOR_GREEN = (16, 185, 129)       # سبز زمردی مدرن #10B981
COLOR_GREEN_DARK = (5, 150, 105)   # #059669
COLOR_GREEN_BG = (236, 253, 245)   # #ECFDF5
COLOR_GREEN_BORDER = (167, 243, 208) # #A7F3D0

COLOR_ORANGE = (217, 119, 6)       # کهربایی گرم #D97706
COLOR_ORANGE_DARK = (180, 83, 9)   # #B45309
COLOR_ORANGE_BG = (255, 251, 235)  # #FFFBEB
COLOR_ORANGE_BORDER = (253, 230, 138) # #FDE68A

COLOR_RED = (225, 29, 72)          # رز تیره #E11D48
COLOR_RED_BG = (255, 241, 242)     # #FFF1F2
COLOR_RED_BORDER = (254, 205, 211) # #FECDD3

COLOR_BLUE = (2, 132, 199)         # آبی کاربنی شرکتی #0284C7
COLOR_BLUE_BG = (240, 249, 255)    # #F0F9FF
COLOR_BLUE_BORDER = (186, 230, 253) # #BAE6FD

try:
    from PIL import Image, ImageDraw, ImageFont, features
    HAS_PIL = True
    HAS_RAQM = bool(features.check("raqm"))
except Exception:
    HAS_PIL = False
    HAS_RAQM = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_RESHAPER = True
except ImportError:
    HAS_RESHAPER = False

def fa(text: str) -> str:
    """
    مبدل و تطبیق‌دهنده متن فارسی برای چیدمان راست‌به‌چپ (RTL):
    - در صورتی که کتابخانه Pillow دارای موتور Raqm (HarfBuzz + FriBidi) باشد،
      متن فارسی به طور مستقیم، با بالاترین کیفیت، اتصال کامل حروف و اعمال خودکار جهت RTL رندر می‌شود.
      پیش‌پردازش arabic_reshaper + bidi در حضور Raqm سبب معکوس شدن دوباره حروف کلمات و جدا شدن حروف می‌شود.
    - در صورتی که Raqm در محیط فعال نباشد (Fallback)، از ترکیب arabic_reshaper و python-bidi استفاده می‌شود.
    """
    if not text:
        return ""
    s = str(text)
    if HAS_RAQM:
        return s
    if HAS_RESHAPER:
        try:
            return get_display(arabic_reshaper.reshape(s))
        except Exception:
            return s
    return s

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

def to_fa_digits(text: Any) -> str:
    """تبدیل ارقام انگلیسی به فارسی جهت یکدستی اسناد رسمی"""
    if text is None:
        return ""
    mapping = {'0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴', '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'}
    res = []
    for ch in str(text):
        res.append(mapping.get(ch, ch))
    return "".join(res)

try:
    import jdatetime
    def _persian_now_formatted() -> str:
        try:
            now = jdatetime.datetime.now()
            m_name = PERSIAN_MONTHS[now.month - 1]
            # خروجی مانند: ۱۳ شهریور ۱۴۰۵ - ساعت ۰۹:۳۰
            return f"{to_fa_digits(now.day)} {m_name} {to_fa_digits(now.year)} - ساعت {to_fa_digits(now.strftime('%H:%M'))}"
        except Exception:
            return to_fa_digits(datetime.now().strftime("%Y/%m/%d - %H:%M"))
except ImportError:
    def _persian_now_formatted() -> str:
        return to_fa_digits(datetime.now().strftime("%Y/%m/%d - %H:%M"))

try:
    import config
    SHOP_NAME = getattr(config, "SHOP_NAME", "AiKala_bot هوشمند کالا اولین فروشگاه تلگرامی لوازم خانگی و لپتاب در ایران")
    SHOP_PHONE = getattr(config, "SHOP_PHONE", "۰۲۱-۹۱۰۰۰۰۰۰  |  ۰۹۱۲۳۴۵۶۷۸۹")
    SHOP_ADDRESS = getattr(config, "SHOP_ADDRESS", "بازارچه مرزی منطقه آزاد کردستان-بانه، مجتمع تجاری پاسارگاد، فروشگاه AiKala")
    LICENSE_NO = getattr(config, "LICENSE_NO", "125366980")
    CARD_NUMBER = getattr(config, "CARD_NUMBER", "")
    CARD_HOLDER = getattr(config, "CARD_HOLDER", "")
    CARD_SHABA = getattr(config, "CARD_SHABA", "")
except ImportError:
    SHOP_NAME = "AiKala_bot هوشمند کالا اولین فروشگاه تلگرامی لوازم خانگی و لپتاب در ایران"
    SHOP_PHONE = "۰۹۱۹۵۸۵۹۴۳۴"
    SHOP_ADDRESS = "بازارچه مرزی منطقه آزاد کردستان-بانه، مجتمع تجاری پاسارگاد، فروشگاه AiKala"
    LICENSE_NO = "125366980"
    CARD_NUMBER = ""
    CARD_HOLDER = ""
    CARD_SHABA = ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
FONT_REGULAR = os.path.join(FONTS_DIR, "Vazirmatn-Regular.ttf")
FONT_BOLD = os.path.join(FONTS_DIR, "Vazirmatn-Bold.ttf")

def _ensure_fonts():
    os.makedirs(FONTS_DIR, exist_ok=True)
    urls = {
        FONT_REGULAR: "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf",
        FONT_BOLD: "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Bold.ttf",
    }
    for path, url in urls.items():
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            try:
                urllib.request.urlretrieve(url, path, timeout=10)
            except Exception as e:
                logger.debug(f"Font download warning: {e}")

_ensure_fonts()

def find_image_file(filename: str) -> Optional[str]:
    """جستجوی هوشمند فایل تصویری مانند logo.png یا stamp.png در مسیرهای پروژه"""
    search_paths = [
        filename,
        os.path.join(BASE_DIR, filename),
        os.path.join(BASE_DIR, "public", filename),
        os.path.join(os.getcwd(), filename),
        os.path.join(os.getcwd(), "public", filename),
        os.path.join("/public", filename),
    ]
    for p in search_paths:
        if os.path.isfile(p) and os.path.getsize(p) > 50:
            return p
    return None

def _format_price(value) -> str:
    try:
        s = str(value).replace(",", "").replace("،", "").strip()
        if not s or s == "0":
            return "۰"
        n = int(s)
        formatted = f"{n:,}"
        return to_fa_digits(formatted).replace(",", "،")
    except Exception:
        return to_fa_digits(str(value))

def _get_font(size: int, bold: bool = False):
    if not HAS_PIL:
        return None
    path = FONT_BOLD if bold else FONT_REGULAR
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    for sys_font in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "arialbd.ttf" if bold else "arial.ttf"
    ]:
        if os.path.exists(sys_font):
            try:
                return ImageFont.truetype(sys_font, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None

def _text_size(draw, text: str, font) -> tuple:
    if not draw or not font:
        return len(text) * 16, 32
    if hasattr(draw, "textbbox"):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            pass
    return len(text) * 16, 32

def _wrap_text(draw, text: str, font, max_w: int) -> List[str]:
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    current = ""
    for w in words:
        test = current + " " + w if current else w
        tw, _ = _text_size(draw, fa(test), font)
        if tw <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines if lines else [""]


def generate_invoice_png(order_data: dict, output_path: str = "invoice.png", is_pre_invoice: bool = False) -> Optional[str]:
    """
    تولید فاکتور اداری مدرن با رزولوشن Full HD (۱۲۰۰ پیکسل):
    is_pre_invoice=True  -> پیش‌فاکتور رسمی خرید با نشان کهربایی (در انتظار واریز بیعانه)
    is_pre_invoice=False -> فاکتور فروش رسمی و قطعی با مهر رسمی شرکتی و ۵ بند حقوقی تحویل
    """
    if not HAS_PIL:
        logger.warning("Pillow (PIL) is not installed. Skipping PNG generation.")
        return None

    _ensure_fonts()

    W = 1200
    PAD = 48
    CW = W - PAD * 2

    # ایجاد بوم با ارتفاع سخاوتمندانه (پس از پایان رسم دقیقاً برش می‌خورد)
    img = Image.new("RGB", (W, 4600), WHITE)
    draw = ImageDraw.Draw(img)

    # حاشیه قاب کلی صفحه
    draw.rectangle([(0, 0), (W - 1, 4599)], outline=COLOR_BORDER, width=1)

    y = PAD

    # نوار باریک گرادیانی / شاخص در بالاترین نقطه
    accent_bar_color = COLOR_ORANGE if is_pre_invoice else COLOR_GREEN
    draw.rectangle([(0, 0), (W, 10)], fill=accent_bar_color)

    # ─────────────────────────────────────────────────────────────
    # ۱. بخش هدر اصلی (Logo, Header Title, Badges, QR)
    # ─────────────────────────────────────────────────────────────
    header_h = 135
    header_y = y

    # بررسی لوگوی کاربر (logo.png)
    logo_path = find_image_file("logo.png")
    logo_loaded = False
    emblem_w = 210
    emblem_h = 90
    emblem_x = PAD + 10
    emblem_y = header_y + (header_h - emblem_h) // 2

    if logo_path:
        try:
            with Image.open(logo_path) as l_img:
                l_img = l_img.convert("RGBA")
                # تغییر اندازه حفظ تناسب (حداکثر عرض ۲۲۰، حداکثر ارتفاع ۹۵)
                l_img.thumbnail((220, 95), Image.Resampling.LANCZOS)
                lw, lh = l_img.size
                lx = PAD + 10
                ly = header_y + (header_h - lh) // 2
                img.paste(l_img, (lx, ly), mask=l_img)
                logo_loaded = True
                emblem_x = lx
                emblem_w = lw
                emblem_y = ly
                emblem_h = lh
        except Exception as e:
            logger.warning(f"Could not load custom logo.png: {e}")

    if not logo_loaded:
        # نشان تجاری شکیل و هندسی برای AiKala
        draw.rounded_rectangle(
            [emblem_x, emblem_y, emblem_x + emblem_w, emblem_y + emblem_h],
            radius=12,
            fill=COLOR_NAVY
        )
        draw.rounded_rectangle(
            [emblem_x + 4, emblem_y + 4, emblem_x + emblem_w - 4, emblem_y + emblem_h - 4],
            radius=10,
            outline=COLOR_BLUE,
            width=1
        )
        # تایپوگرافی لوگو
        f_logo1 = _get_font(28, bold=True)
        t_logo1 = "AiKala"
        draw.text((emblem_x + 22, emblem_y + 14), t_logo1, font=f_logo1, fill=WHITE)

        f_logo2 = _get_font(18, bold=True)
        t_logo2 = fa("هوشمند کالا")
        draw.text((emblem_x + 22, emblem_y + 48), t_logo2, font=f_logo2, fill=COLOR_MUTED)

        # دات نئونی هوشمند
        draw.ellipse([emblem_x + emblem_w - 28, emblem_y + 24, emblem_x + emblem_w - 16, emblem_y + 36], fill=COLOR_BLUE)

    # عنوان و اطلاعات فروشگاه در سمت راست
    raw_shop_title = order_data.get("shop_name") or SHOP_NAME
    if not raw_shop_title or any(old in raw_shop_title for old in ["بازرگانی هوشمند کالا", "فروشگاه آی‌کالا", "فروشگاه آی کالا", "AiKala_bot"]):
        raw_shop_title = "هوشمند کالا (@AiKala_bot) | اولین فروشگاه تلگرامی لوازم خانگی و لپ‌تاپ در ایران"
    shop_title = fa(raw_shop_title)

    # محاسبه دقیق اندازه فونت عنوان جهت قرارگیری استاندارد و بدون تداخل با نشان تجاری سمت چپ
    max_title_w = W - PAD - (emblem_x + emblem_w + 24) - 10
    title_font_sz = 26
    f_shop = _get_font(title_font_sz, bold=True)
    tw_shop, _ = _text_size(draw, shop_title, f_shop)
    while tw_shop > max_title_w and title_font_sz > 17:
        title_font_sz -= 1
        f_shop = _get_font(title_font_sz, bold=True)
        tw_shop, _ = _text_size(draw, shop_title, f_shop)

    draw.text((W - PAD - tw_shop - 10, header_y + 8), shop_title, font=f_shop, fill=COLOR_DARK)

    f_sub = _get_font(19)
    sub_title = fa("مرکز تخصصی لوازم خانگی، صوتی تصویری و لپ‌تاپ اورجینال با ضمانت کتبی اصالت")
    tw_sub, _ = _text_size(draw, sub_title, f_sub)
    draw.text((W - PAD - tw_sub - 10, header_y + 54), sub_title, font=f_sub, fill=COLOR_GRAY)

    info_line = fa(f"تلفن: {order_data.get('shop_phone', SHOP_PHONE)}   |   شماره ثبت بازرگانی: {to_fa_digits(order_data.get('license_no', LICENSE_NO))}")
    tw_info, _ = _text_size(draw, info_line, f_sub)
    draw.text((W - PAD - tw_info - 10, header_y + 88), info_line, font=f_sub, fill=COLOR_MUTED)

    y += header_h + 20

    # ─────────────────────────────────────────────────────────────
    # ۲. نوار وضعیت فاکتور (کپسول مدرن دوطرفه)
    # ─────────────────────────────────────────────────────────────
    bar_h = 56
    if is_pre_invoice:
        b_bg, b_border, b_text = COLOR_ORANGE_BG, COLOR_ORANGE_BORDER, COLOR_ORANGE_DARK
        badge_text = fa("پیش‌فاکتور رسمی خرید (غیرقطعی — در انتظار بیعانه)")
        right_sub = fa("مهلت اعتبار رزرو انبار: ۵ ساعت کاری")
    else:
        b_bg, b_border, b_text = COLOR_GREEN_BG, COLOR_GREEN_BORDER, COLOR_GREEN_DARK
        badge_text = fa("فاکتور فروش رسمی و قطعی (بیعانه تایید شد)")
        right_sub = fa("وضعیت: قطعی و تخصیص به واحد باربری")

    draw.rounded_rectangle([PAD, y, W - PAD, y + bar_h], radius=10, fill=b_bg, outline=b_border, width=1)

    f_badge = _get_font(22, bold=True)
    draw.text((W - PAD - 24 - _text_size(draw, badge_text, f_badge)[0], y + 15), badge_text, font=f_badge, fill=b_text)

    f_bar_sub = _get_font(19)
    draw.text((PAD + 24, y + 17), right_sub, font=f_bar_sub, fill=b_text)

    y += bar_h + 24

    # ─────────────────────────────────────────────────────────────
    # ۳. مشخصات سند و خریدار (دو باکس متقارن و مینیمال)
    # ─────────────────────────────────────────────────────────────
    col_w = (CW - 24) // 2
    box_h = 190

    # باکس راست: مشخصات خریدار و تحویل
    rx1 = PAD + col_w + 24
    rx2 = W - PAD
    draw.rounded_rectangle([rx1, y, rx2, y + box_h], radius=12, fill=COLOR_BG_CARD, outline=COLOR_BORDER, width=1)

    f_box_header = _get_font(21, bold=True)
    t_bh_r = fa("مشخصات خریدار و تحویل‌گیرنده:")
    draw.text((rx2 - 20 - _text_size(draw, t_bh_r, f_box_header)[0], y + 16), t_bh_r, font=f_box_header, fill=COLOR_NAVY)
    draw.line([(rx1 + 16, y + 50), (rx2 - 16, y + 50)], fill=COLOR_BORDER, width=1)

    f_kv_lbl = _get_font(20)
    f_kv_val = _get_font(20, bold=True)

    def draw_box_row(bx1, bx2, cur_y, label, val, is_val_bold=True, val_color=COLOR_DARK):
        tl = fa(label)
        tv = fa(val)
        twl, _ = _text_size(draw, tl, f_kv_lbl)
        twv, _ = _text_size(draw, tv, f_kv_val)
        draw.text((bx2 - 20 - twl, cur_y), tl, font=f_kv_lbl, fill=COLOR_GRAY)
        draw.text((bx1 + 20, cur_y), tv, font=f_kv_val if is_val_bold else f_kv_lbl, fill=val_color)

    r_cur_y = y + 62
    c_name = order_data.get("customer_name") or "خریدار محترم"
    draw_box_row(rx1, rx2, r_cur_y, "تحویل‌گیرنده:", c_name)
    r_cur_y += 38

    c_phone = to_fa_digits(order_data.get("customer_phone") or "-")
    draw_box_row(rx1, rx2, r_cur_y, "شماره تماس:", c_phone)
    r_cur_y += 38

    c_city = order_data.get("customer_city") or order_data.get("province_city") or "مقصد ثبت‌شده"
    draw_box_row(rx1, rx2, r_cur_y, "استان و شهر مقصد:", c_city)

    # باکس چپ: مشخصات فاکتور و ترابری
    lx1 = PAD
    lx2 = PAD + col_w
    draw.rounded_rectangle([lx1, y, lx2, y + box_h], radius=12, fill=COLOR_BG_CARD, outline=COLOR_BORDER, width=1)

    t_bh_l = fa("اطلاعات رسمی فاکتور:")
    draw.text((lx2 - 20 - _text_size(draw, t_bh_l, f_box_header)[0], y + 16), t_bh_l, font=f_box_header, fill=COLOR_NAVY)
    draw.line([(lx1 + 16, y + 50), (lx2 - 16, y + 50)], fill=COLOR_BORDER, width=1)

    l_cur_y = y + 62
    inv_num_val = to_fa_digits(order_data.get("invoice_number", f"INV-{order_data.get('order_code', '')}"))
    draw_box_row(lx1, lx2, l_cur_y, "شماره فاکتور:", inv_num_val)
    l_cur_y += 38

    ord_code_val = f"#{order_data.get('order_code', '')}"
    draw_box_row(lx1, lx2, l_cur_y, "شناسه رهگیری سفارش:", ord_code_val, val_color=COLOR_BLUE)
    l_cur_y += 38

    date_val = str(order_data.get("date") or _persian_now_formatted())
    draw_box_row(lx1, lx2, l_cur_y, "تاریخ و زمان صدور:", date_val, is_val_bold=False)

    y += box_h + 16

    # آدرس دقیق و کامل تحویل در یک نوار اختصاصی
    c_addr = order_data.get("customer_address") or "-"
    c_postal = order_data.get("customer_postal")
    full_addr_str = f"نشانی دقیق محل تحویل: {c_addr}"
    if c_postal and c_postal != "-":
        full_addr_str += f"   (کد پستی: {to_fa_digits(c_postal)})"

    addr_lines = _wrap_text(draw, full_addr_str, _get_font(20), CW - 50)
    addr_h = len(addr_lines) * 32 + 20
    draw.rounded_rectangle([PAD, y, W - PAD, y + addr_h], radius=10, fill=WHITE, outline=COLOR_BORDER, width=1)
    
    cur_ay = y + 10
    for al in addr_lines:
        tal = fa(al)
        tw, _ = _text_size(draw, tal, _get_font(20))
        draw.text((W - PAD - 20 - tw, cur_ay), tal, font=_get_font(20), fill=COLOR_DARK)
        cur_ay += 32

    y += addr_h + 26

    # ─────────────────────────────────────────────────────────────
    # ۴. جدول اقلام سفارش (Line Items Table با طراحی دقیق)
    # ─────────────────────────────────────────────────────────────
    th_h = 44
    draw.rounded_rectangle([PAD, y, W - PAD, y + th_h], radius=8, fill=COLOR_BORDER_LIGHT)

    f_th = _get_font(21, bold=True)
    # ستون‌ها با فواصل دقیق هندسی جهت جلوگیری از هرگونه همپوشانی:
    # ردیف (مرکز W - PAD - 45) | شرح کالا (تراز راست W - PAD - 120) | ضمانت (مرکز PAD + 460) | تعداد (مرکز PAD + 310) | مبلغ کل (تراز چپ PAD + 24)
    x_row = W - PAD - 45
    x_desc = W - PAD - 120
    x_spec = PAD + 460
    x_qty = PAD + 310
    x_price = PAD + 24

    draw.text((x_row - _text_size(draw, fa("ردیف"), f_th)[0] // 2, y + 10), fa("ردیف"), font=f_th, fill=COLOR_NAVY)
    draw.text((x_desc - _text_size(draw, fa("شرح کالا و مشخصات فنی"), f_th)[0], y + 10), fa("شرح کالا و مشخصات فنی"), font=f_th, fill=COLOR_NAVY)
    draw.text((x_spec - _text_size(draw, fa("ضمانت و اصالت"), f_th)[0] // 2, y + 10), fa("ضمانت و اصالت"), font=f_th, fill=COLOR_NAVY)
    draw.text((x_qty - _text_size(draw, fa("تعداد"), f_th)[0] // 2, y + 10), fa("تعداد"), font=f_th, fill=COLOR_NAVY)
    draw.text((x_price, y + 10), fa("مبلغ کل (تومان)"), font=f_th, fill=COLOR_NAVY)

    y += th_h + 12

    # سطرهای جدول
    items = order_data.get("items") or []
    if not items:
        items = [{
            "name": "کالای انتخابی هوشمند کالا",
            "meta": "اورجینال شرکتی با گارانتی معتبر",
            "qty": 1,
            "total": order_data.get("grand_total", "۰")
        }]

    for idx, itm in enumerate(items, start=1):
        item_name = str(itm.get("name", "کالا"))
        item_meta = str(itm.get("meta", "۲ سال ضمانت طلایی + ۵ سال خدمات"))
        item_qty = to_fa_digits(itm.get("qty", 1))
        item_total = str(itm.get("total", "۰"))

        # محاسبه شکست متن کالا حداکثر در عرض ۵۰۰ پیکسل
        desc_lines = _wrap_text(draw, item_name, _get_font(23, bold=True), 500)
        row_content_h = max(len(desc_lines) * 36 + 28, 70)

        # پس‌زمینه لطیف متناوب
        draw.line([(PAD, y + row_content_h), (W - PAD, y + row_content_h)], fill=COLOR_BORDER_LIGHT, width=1)

        # ردیف
        f_itm = _get_font(22)
        f_itm_b = _get_font(23, bold=True)
        draw.text((x_row - _text_size(draw, to_fa_digits(idx), f_itm)[0] // 2, y + 14), to_fa_digits(idx), font=f_itm, fill=COLOR_GRAY)

        # شرح کالا
        cur_dy = y + 12
        for dl in desc_lines:
            tdl = fa(dl)
            tw, _ = _text_size(draw, tdl, f_itm_b)
            draw.text((x_desc - tw, cur_dy), tdl, font=f_itm_b, fill=COLOR_DARK)
            cur_dy += 34

        # ضمانت و برند (با فونت خوانا و اندازه متناسب)
        f_meta = _get_font(18)
        meta_txt = fa(item_meta[:32] if len(item_meta) > 32 else item_meta)
        draw.text((x_spec - _text_size(draw, meta_txt, f_meta)[0] // 2, y + 16), meta_txt, font=f_meta, fill=COLOR_GRAY)

        # تعداد
        draw.text((x_qty - _text_size(draw, item_qty, f_itm_b)[0] // 2, y + 14), item_qty, font=f_itm_b, fill=COLOR_DARK)

        # مبلغ کل
        price_fa = fa(f"{item_total}")
        draw.text((x_price, y + 14), price_fa, font=f_itm_b, fill=COLOR_DARK)

        y += row_content_h + 12

    y += 10

    # ─────────────────────────────────────────────────────────────
    # ۵. کارت محاسبات مالی و تسویه (کاملاً تفکیک‌شده و بدون همپوشانی)
    # ─────────────────────────────────────────────────────────────
    finance_h = 240
    draw.rounded_rectangle([PAD, y, W - PAD, y + finance_h], radius=12, fill=COLOR_BG_CARD, outline=COLOR_BORDER, width=1)

    # خط جداکننده عمودی بین دو ستون (در مرکز باکس)
    mid_x = PAD + CW // 2
    draw.line([(mid_x, y + 16), (mid_x, y + finance_h - 16)], fill=COLOR_BORDER, width=1)

    # ستون راست: توضیحات مالی و روش تسویه
    # محدوده متنی ستون راست: از mid_x + 20 تا W - PAD - 24 (حداکثر عرض ۴۸۰ پیکسل)
    fin_rx2 = W - PAD - 24
    max_text_w_right = 480

    if is_pre_invoice:
        f_fh_r = _get_font(21, bold=True)
        t_f1 = fa("نحوه نهایی‌سازی سفارش با بیعانه:")
        draw.text((fin_rx2 - _text_size(draw, t_f1, f_fh_r)[0], y + 18), t_f1, font=f_fh_r, fill=COLOR_ORANGE_DARK)

        card_num_raw = str(order_data.get("card_number") or getattr(config, "CARD_NUMBER", "") or "").strip()
        card_holder_raw = str(order_data.get("card_holder") or getattr(config, "CARD_HOLDER", "") or "").strip()
        card_shaba_raw = str(order_data.get("card_shaba") or getattr(config, "CARD_SHABA", "") or "").strip()

        # تولید بندها با خط‌شکنی خودکار برای جلوگیری قطعی از همپوشانی متون
        raw_paragraphs = []
        if card_num_raw:
            raw_paragraphs.append(f"• شماره کارت واریز: {to_fa_digits(card_num_raw)}")
        if card_shaba_raw:
            raw_paragraphs.append(f"• شماره شبا بانکی: {to_fa_digits(card_shaba_raw)}")
        if card_holder_raw:
            raw_paragraphs.append(f"• به نام دارنده حساب: {card_holder_raw}")
        if not raw_paragraphs:
            raw_paragraphs.append("• اطلاعات بانکی واریز بیعانه توسط واحد مالی اعلام می‌گردد.")
        raw_paragraphs.append("• پس از واریز بیعانه، فاکتور رسمی قطعی فروش همراه با مهر شرکت صادر می‌گردد.")

        f_fb_r = _get_font(18)
        cur_fy = y + 54
        for p in raw_paragraphs:
            sub_lines = _wrap_text(draw, p, f_fb_r, max_w=max_text_w_right)
            for sl in sub_lines:
                tsl = fa(sl)
                tw, _ = _text_size(draw, tsl, f_fb_r)
                draw.text((fin_rx2 - tw, cur_fy), tsl, font=f_fb_r, fill=COLOR_GRAY)
                cur_fy += 28
            cur_fy += 4
    else:
        f_fh_r = _get_font(21, bold=True)
        t_f1 = fa("شرایط تسویه مانده‌حساب در مقصد:")
        draw.text((fin_rx2 - _text_size(draw, t_f1, f_fh_r)[0], y + 18), t_f1, font=f_fh_r, fill=COLOR_GREEN_DARK)

        raw_paragraphs = [
            "• بیعانه شما به عنوان پیش‌پرداخت رزرو و بسته‌بندی در سامانه ثبت گردید.",
            "• مانده فاکتور پس از تحویل کالا، تست سلامت کامل فیزیکی و روشن شدن تسویه می‌شود.",
            "• همراه با کالا برگه گارانتی طلایی شرکتی ۲۴ ماهه تقدیم خواهد شد."
        ]

        f_fb_r = _get_font(18)
        cur_fy = y + 54
        for p in raw_paragraphs:
            sub_lines = _wrap_text(draw, p, f_fb_r, max_w=max_text_w_right)
            for sl in sub_lines:
                tsl = fa(sl)
                tw, _ = _text_size(draw, tsl, f_fb_r)
                draw.text((fin_rx2 - tw, cur_fy), tsl, font=f_fb_r, fill=COLOR_GRAY)
                cur_fy += 28
            cur_fy += 4

    # ستون چپ: ارقام مالی با کادر اختصاصی
    fin_lx1 = PAD + 24
    fin_lx2 = mid_x - 20

    f_sum_lbl = _get_font(20)
    f_sum_val = _get_font(21, bold=True)

    def draw_fin_row(cur_y, label, val_str, val_color=COLOR_DARK, bold_val=True):
        tl = fa(label)
        tv = fa(f"{val_str} تومان")
        draw.text((fin_lx2 - _text_size(draw, tl, f_sum_lbl)[0], cur_y), tl, font=f_sum_lbl, fill=COLOR_GRAY)
        draw.text((fin_lx1, cur_y), tv, font=f_sum_val if bold_val else f_sum_lbl, fill=val_color)

    draw_fin_row(y + 18, "مبلغ کل فاکتور:", order_data.get("grand_total", "۰"))

    is_post = order_data.get("shipping_method") == "post" or (
        order_data.get("deposit") == order_data.get("grand_total") and order_data.get("remaining") in ["۰", "0", ""]
    )
    dep_pct = getattr(config, "DEPOSIT_PERCENT", 8)

    if is_pre_invoice:
        if is_post:
            draw_fin_row(y + 68, "مبلغ قابل پرداخت (تسویه کامل):", order_data.get("grand_total", "۰"), val_color=COLOR_ORANGE_DARK)
            # کادر برجسته شیوه ارسال پستی
            draw.rounded_rectangle([fin_lx1, y + 130, fin_lx2, y + 215], radius=8, fill=COLOR_ORANGE_BG, outline=COLOR_ORANGE_BORDER, width=1)
            t_rem_lbl = fa("شیوه ارسال و شرایط تسویه:")
            t_rem_val = fa("پست پیشتاز (تسویه کامل - مانده صفر)")
            draw.text((fin_lx2 - 16 - _text_size(draw, t_rem_lbl, _get_font(17, bold=True))[0], y + 148), t_rem_lbl, font=_get_font(17, bold=True), fill=COLOR_ORANGE_DARK)
            draw.text((fin_lx1 + 16, y + 146), t_rem_val, font=_get_font(19, bold=True), fill=COLOR_ORANGE_DARK)
        else:
            draw_fin_row(y + 68, f"مبلغ بیعانه پیش‌پرداخت ({dep_pct}٪):", order_data.get("deposit", "۰"), val_color=COLOR_ORANGE_DARK)
            # کادر برجسته مانده
            draw.rounded_rectangle([fin_lx1, y + 130, fin_lx2, y + 215], radius=8, fill=COLOR_ORANGE_BG, outline=COLOR_ORANGE_BORDER, width=1)
            t_rem_lbl = fa("مانده قابل پرداخت در محل:")
            t_rem_val = fa(f"{order_data.get('remaining', '۰')} تومان")
            draw.text((fin_lx2 - 16 - _text_size(draw, t_rem_lbl, _get_font(19, bold=True))[0], y + 148), t_rem_lbl, font=_get_font(19, bold=True), fill=COLOR_ORANGE_DARK)
            draw.text((fin_lx1 + 16, y + 146), t_rem_val, font=_get_font(21, bold=True), fill=COLOR_ORANGE_DARK)
    else:
        if is_post:
            draw_fin_row(y + 68, "مبلغ پرداخت‌شده (تسویه ۱۰۰٪ کامل):", f"{order_data.get('grand_total', '۰')}  [ تایید شد ]", val_color=COLOR_GREEN_DARK)
            # کادر برجسته وضعیت تسویه پستی
            draw.rounded_rectangle([fin_lx1, y + 130, fin_lx2, y + 215], radius=8, fill=COLOR_GREEN_BG, outline=COLOR_GREEN_BORDER, width=1)
            t_rem_lbl = fa("وضعیت حساب و شیوه تحویل:")
            t_rem_val = fa("تسویه کامل - تحویل به پست پیشتاز")
            draw.text((fin_lx2 - 16 - _text_size(draw, t_rem_lbl, _get_font(17, bold=True))[0], y + 148), t_rem_lbl, font=_get_font(17, bold=True), fill=COLOR_GREEN_DARK)
            draw.text((fin_lx1 + 16, y + 146), t_rem_val, font=_get_font(19, bold=True), fill=COLOR_GREEN_DARK)
        else:
            draw_fin_row(y + 68, f"بیعانه پرداخت‌شده ({dep_pct}٪):", f"{order_data.get('deposit', '۰')}  [ تایید شد ]", val_color=COLOR_GREEN_DARK)
            # کادر برجسته مانده تسویه در محل
            draw.rounded_rectangle([fin_lx1, y + 130, fin_lx2, y + 215], radius=8, fill=COLOR_RED_BG, outline=COLOR_RED_BORDER, width=1)
            t_rem_lbl = fa("مانده تسویه بعد از تست در محل:")
            t_rem_val = fa(f"{order_data.get('remaining', '۰')} تومان")
            draw.text((fin_lx2 - 16 - _text_size(draw, t_rem_lbl, _get_font(19, bold=True))[0], y + 148), t_rem_lbl, font=_get_font(19, bold=True), fill=COLOR_RED)
            draw.text((fin_lx1 + 16, y + 146), t_rem_val, font=_get_font(21, bold=True), fill=COLOR_RED)

    y += finance_h + 24

    # ─────────────────────────────────────────────────────────────
    # ۶. بخش اختصاصی شرایط و تعهدات (در فاکتور نهایی فقط)
    # ─────────────────────────────────────────────────────────────
    if not is_pre_invoice:
        # فاکتور نهایی و قطعی فروش -> درج دقیق ۵ بند و تاییدیه خریدار
        terms_card_y = y
        f_terms_title = _get_font(22, bold=True)
        t_th = fa("شرایط و ضوابط رسمی تحویل، گارانتی و تسویه فاکتور:")
        draw.text((W - PAD - 10 - _text_size(draw, t_th, f_terms_title)[0], y), t_th, font=f_terms_title, fill=COLOR_NAVY)
        y += 38

        official_terms = [
            "۱. قیمت اجناس به نرخ روز بوده و این مرکز در مورد نوسانات بازار پاسخگو نیست.",
            "۲. خریدار موظف است کالا را از لحاظ سلامت فیزیکی قبل از تسویه با باربر بررسی نماید.",
            "۳. جهت نصب و فعال سازی گارانتی محصولات، هزینه ایاب و ذهاب نصاب به عهده خریدار می باشد.",
            "۴. ارسال محصول بسته به شرایط جوی و مسافت ممکن است ۱ الی ۴ روز کاری زمان ببرد.",
            "۵. هوشمند کالا (@AiKala_bot) تضمین‌کننده اصالت ۱۰۰٪ کالا و گارانتی معتبر خرید شماست."
        ]

        f_term_txt = _get_font(20)
        for term_line in official_terms:
            for wrapped in _wrap_text(draw, term_line, f_term_txt, CW - 20):
                twrapped = fa(wrapped)
                draw.text((W - PAD - 10 - _text_size(draw, twrapped, f_term_txt)[0], y), twrapped, font=f_term_txt, fill=COLOR_DARK)
                y += 31
            y += 4

        y += 24

    else:
        # در پیش‌فاکتور این ۵ بند و اقرارنامه لازم نیست
        # پیام راهنمای واریز بیعانه و رزرو
        draw.rounded_rectangle([PAD, y, W - PAD, y + 86], radius=10, fill=COLOR_ORANGE_BG, outline=COLOR_ORANGE_BORDER, width=1)
        f_notice = _get_font(20)
        t_n1 = fa("نکته مهم: پیش‌فاکتور فوق جهت تخصیص کالا در انبار صادر گردیده و حداکثر ۵ ساعت کاری معتبر است.")
        t_n2 = fa("پس از واریز بیعانه، فاکتور رسمی فروش همراه با مهر شرکتی، کد پیگیری باربری و گارانتی کتبی صادر می‌شود.")
        draw.text(((W - _text_size(draw, t_n1, f_notice)[0]) // 2, y + 14), t_n1, font=f_notice, fill=COLOR_ORANGE_DARK)
        draw.text(((W - _text_size(draw, t_n2, f_notice)[0]) // 2, y + 46), t_n2, font=f_notice, fill=COLOR_GRAY)
        y += 105

    # ─────────────────────────────────────────────────────────────
    # ۷. بخش انتهای فاکتور (QR Code رهگیری، مهر رسمی stamp.png)
    # ─────────────────────────────────────────────────────────────
    footer_block_h = 160
    fb_y = y

    # رسم کیوآرکد اختصاصی رهگیری
    if HAS_QRCODE:
        try:
            qr = qrcode.QRCode(version=1, box_size=5, border=1)
            qr_url = f"https://t.me/AiKala_bot?start=track_{order_data.get('order_code', '')}"
            qr.add_data(qr_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color=COLOR_DARK, back_color=WHITE).convert("RGB")
            img.paste(qr_img, (PAD + 20, fb_y + 10))

            f_qr_lbl = _get_font(17)
            t_qr = fa("اسکن استعلام آنلاین")
            draw.text((PAD + 20 + (qr_img.width - _text_size(draw, t_qr, f_qr_lbl)[0]) // 2, fb_y + qr_img.height + 14), t_qr, font=f_qr_lbl, fill=COLOR_GRAY)
        except Exception as e:
            logger.warning(f"QR code generation failed: {e}")

    # مهر رسمی فروشگاه در سمت چپ / مرکز انتهای فاکتور
    stamp_x = W - PAD - 260
    stamp_y = fb_y + 10

    if not is_pre_invoice:
        # فاکتور نهایی: بررسی وجود فایل stamp.png
        stamp_path = find_image_file("stamp.png")
        stamp_loaded = False
        if stamp_path:
            try:
                with Image.open(stamp_path) as s_img:
                    s_img = s_img.convert("RGBA")
                    s_img.thumbnail((240, 130), Image.Resampling.LANCZOS)
                    sw, sh = s_img.size
                    sx = stamp_x + (240 - sw) // 2
                    sy = stamp_y + (130 - sh) // 2
                    img.paste(s_img, (sx, sy), mask=s_img)
                    stamp_loaded = True
            except Exception as e:
                logger.warning(f"Could not load custom stamp.png: {e}")

        if not stamp_loaded:
            # مهر برداری شرکتی فوق‌العاده شکیل با دو خط بیضی و تایپوگرافی رسمی
            s_color = COLOR_GREEN_DARK
            scx = stamp_x + 120
            scy = stamp_y + 65
            draw.ellipse([scx - 115, scy - 52, scx + 115, scy + 52], outline=s_color, width=3)
            draw.ellipse([scx - 108, scy - 45, scx + 108, scy + 45], outline=s_color, width=1)

            t_st1 = fa("بازرگانی هوشمند کالا • AiKala")
            t_st2 = fa("امور مالی و ترخیص کالا")
            t_st3 = fa("★ تایید و صادر گردید ★")

            f_st1 = _get_font(18, bold=True)
            f_st2 = _get_font(18, bold=True)
            f_st3 = _get_font(16)

            draw.text((scx - _text_size(draw, t_st1, f_st1)[0] // 2, scy - 38), t_st1, font=f_st1, fill=s_color)
            draw.text((scx - _text_size(draw, t_st2, f_st2)[0] // 2, scy - 12), t_st2, font=f_st2, fill=s_color)
            draw.text((scx - _text_size(draw, t_st3, f_st3)[0] // 2, scy + 14), t_st3, font=f_st3, fill=s_color)

    else:
        # در پیش‌فاکتور: نشان تایید کارشناسی و در انتظار واریز بیعانه
        s_color = COLOR_ORANGE_DARK
        scx = stamp_x + 120
        scy = stamp_y + 65
        draw.ellipse([scx - 115, scy - 50, scx + 115, scy + 50], outline=s_color, width=2)

        t_st1 = fa("واحد فروش هوشمند کالا")
        t_st2 = fa("پیش‌فاکتور غیرقطعی")
        t_st3 = fa("در انتظار واریز بیعانه")

        f_st1 = _get_font(17, bold=True)
        f_st2 = _get_font(17)
        f_st3 = _get_font(15)

        draw.text((scx - _text_size(draw, t_st1, f_st1)[0] // 2, scy - 34), t_st1, font=f_st1, fill=s_color)
        draw.text((scx - _text_size(draw, t_st2, f_st2)[0] // 2, scy - 8), t_st2, font=f_st2, fill=s_color)
        draw.text((scx - _text_size(draw, t_st3, f_st3)[0] // 2, scy + 16), t_st3, font=f_st3, fill=s_color)

    y += footer_block_h + 20

    # نوار پایانی پایین صفحه
    draw.rounded_rectangle([PAD, y, W - PAD, y + 46], radius=8, fill=COLOR_NAVY)
    f_footer_bar = _get_font(19)
    t_fbar = fa("سامانه رسمی هوشمند کالا @AiKala_bot • ارسال تضمینی با بیمه بار به سراسر کشور")
    tw_fb, _ = _text_size(draw, t_fbar, f_footer_bar)
    draw.text(((W - tw_fb) // 2, y + 12), t_fbar, font=f_footer_bar, fill=WHITE)

    y += 46 + PAD

    # برش دقیق به ابعاد واقعی محتوا
    img = img.crop((0, 0, W, y))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "PNG", optimize=False)
    logger.info(f"Invoice generated successfully: {output_path} (W={W}, H={y})")
    return output_path


def build_invoice_data_from_order(order: dict, product: dict = None) -> dict:
    """تبدیل دیکشنری سفارش و مشخصات محصول به ساختار استاندارد فاکتور با محاسبه دقیق ۸٪ بیعانه"""
    prod = product or {}

    def _clean_num(val) -> int:
        if not val:
            return 0
        trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        raw = str(val).translate(trans).replace(",", "").replace("،", "").strip()
        digits = re.findall(r'\d+', raw)
        return int("".join(digits)) if digits else 0

    price = _clean_num(order.get('total_price')) or _clean_num(order.get('final_price')) or _clean_num(prod.get('price')) or _clean_num(order.get('price'))
    deposit = _clean_num(order.get('deposit_amount'))
    shipping_method = order.get('shipping_method', 'freight')

    dep_pct = getattr(config, "DEPOSIT_PERCENT", 8)
    if shipping_method == "post":
        deposit = price
        remaining = 0
    else:
        if deposit == 0 and price > 0:
            deposit = int(round((price * (dep_pct / 100.0)) / 10000)) * 10000
            if deposit == 0:
                deposit = int(round((price * (dep_pct / 100.0)) / 1000)) * 1000

        if price == 0 and deposit > 0:
            price = int(round((deposit / (dep_pct / 100.0)) / 10000)) * 10000

        remaining = max(0, price - deposit)

    p_name = prod.get('name') or order.get('product_name') or 'کالای انتخابی هوشمند کالا'
    p_brand = prod.get('brand') or order.get('brand', 'اورجینال شرکتی')
    p_code = str(prod.get('product_id', order.get('product_id', '-')))[:16]

    return {
        "shop_name": SHOP_NAME,
        "shop_phone": SHOP_PHONE,
        "shop_address": SHOP_ADDRESS,
        "license_no": LICENSE_NO,
        "card_number": getattr(config, "CARD_NUMBER", "") or "",
        "card_holder": getattr(config, "CARD_HOLDER", "") or "",
        "card_shaba": getattr(config, "CARD_SHABA", "") or "",
        "invoice_number": f"INV-{order.get('order_code', '')}",
        "date": _persian_now_formatted(),
        "order_code": order.get('order_code', ''),
        "shipping_method": shipping_method,
        "customer_name": order.get('full_name', 'خریدار محترم'),
        "customer_phone": order.get('phone1', '-'),
        "customer_phone2": order.get('phone2', ''),
        "customer_city": order.get('province_city', ''),
        "customer_address": order.get('address', '-'),
        "customer_postal": order.get('postal_code', '-'),
        "items": [
            {
                "name": p_name,
                "meta": f"برند: {p_brand} | ۲ سال ضمانت کتبی شرکتی",
                "code": p_code,
                "qty": 1,
                "unit_price": _format_price(str(price)),
                "total": _format_price(str(price))
            }
        ],
        "subtotal": _format_price(str(price)),
        "grand_total": _format_price(str(price)),
        "deposit": _format_price(str(deposit)),
        "remaining": _format_price(str(remaining))
    }
