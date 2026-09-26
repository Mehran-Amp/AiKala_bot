import React, { useState } from "react";
import { ReceiptData } from "./types";
import { OptionBReceipt } from "./components/OptionBReceipt";
import { ChannelMonitorTab } from "./components/ChannelMonitorTab";
import { AudioCatalogTab } from "./components/AudioCatalogTab";
import {
  FileText,
  AlertCircle,
  Copy,
  Check,
  Settings,
  ShieldCheck,
  Code2,
  RefreshCw,
  Terminal,
  MessageSquare,
  Send,
  Image as ImageIcon,
  XCircle,
  CreditCard,
  Hash,
  Sparkles,
  ExternalLink,
  Radio,
  Volume2
} from "lucide-react";

export default function App() {
  const [activeTab, setActiveTab] = useState<"audio_catalog" | "channels" | "simulator" | "preview" | "python_code" | "troubleshooting">("audio_catalog");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Editable state for invoice
  const [productName, setProductName] = useState("تلویزیون ۵۵ اینچ ال جی مدل OLED C4 (مدل ۲۰۲۴)");
  const [productPrice, setProductPrice] = useState(143000000);
  const [depositPercent, setDepositPercent] = useState(8);
  const [customerName, setCustomerName] = useState("مهرداد امین‌زاده");
  const [customerPhone, setCustomerPhone] = useState("09195859434");
  const [customerAddress, setCustomerAddress] = useState("تهران، پاسداران، خیابان شهید پایدار فرد، کوچه شبنم، پلاک ۱۲، واحد ۴");
  const [orderCode, setOrderCode] = useState("8011");
  const [isPreInvoice, setIsPreInvoice] = useState(true);

  // Simulator state
  const [simStep, setSimStep] = useState<"waiting_payment" | "prompt_photo" | "prompt_text" | "cancelled" | "paid">("waiting_payment");
  const [simTrackingInput, setSimTrackingInput] = useState("");
  const [simUploadedReceipt, setSimUploadedReceipt] = useState<string | null>(null);

  // Calculations
  const deposit = Math.round((productPrice * depositPercent) / 100);
  const remaining = Math.max(0, productPrice - deposit);

  const receiptData: ReceiptData = {
    shopName: "AiKala_bot هوشمند کالا اولین فروشگاه تلگرامی لوازم خانگی و لپتاب در ایران",
    shopPhone: "۰۹۱۹۵۸۵۹۴۳۴",
    shopAddress: "بازارچه مرزی منطقه آزاد کردستان-بانه، مجتمع تجاری پاسارگاد، فروشگاه AiKala",
    licenseNo: "125366980",
    invoiceNumber: `INV-${orderCode}`,
    orderCode: orderCode,
    date: "۱۴۰۵/۰۶/۱۰ - ۱۶:۳۰",
    customerName: customerName,
    customerPhone: customerPhone,
    customerAddress: customerAddress,
    customerPostal: "1958641203",
    items: [
      {
        name: productName,
        meta: "برند: ال جی (LG) | پنل OLED evo | ۲ سال گارانتی تعویض کتبی + ۵ سال خدمات پس از فروش سراسری",
        code: "TV-OLED-55C4",
        qty: 1,
        unitPrice: productPrice,
        total: productPrice
      }
    ],
    subtotal: productPrice,
    grandTotal: productPrice,
    deposit: deposit,
    remaining: remaining,
    isPreInvoice: isPreInvoice
  };

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2500);
  };

  // Full HD 1200px generator Python Code
  const pythonInvoiceGeneratorCode = `\"\"\"
Option B: Ultra HD (1200px) POS Thermal Invoice & Pre-Invoice Generator
========================================================================
- رزولوشن Full HD (عرض ۱۲۰۰ پیکسل فوق‌العاده شارپ و خوانا در موبایل و چاپ)
- طراحی دقیق و ظریف Option B با خطوط داتد، کارت‌های مجزا و مهر شرکتی
- تفکیک پیش‌فاکتور (در انتظار واریز بیعانه) و فاکتور فروش قطعی
- شامل توابع کامل generate_invoice_png و build_invoice_data_from_order
\"\"\"

import os
import urllib.request
import logging
from datetime import datetime
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── پالت رنگی استاندارد و شفاف ──────────────────────────────────
WHITE = (255, 255, 255)
COLOR_DARK = (15, 23, 42)
COLOR_GRAY = (71, 85, 105)
COLOR_MUTED = (148, 163, 184)
COLOR_BORDER = (226, 232, 240)
COLOR_BG_CARD = (248, 250, 252)
COLOR_RED = (225, 29, 72)
COLOR_RED_BG = (255, 241, 242)
COLOR_RED_BORDER = (254, 205, 211)
COLOR_GREEN = (22, 163, 74)
COLOR_GREEN_BG = (240, 253, 244)
COLOR_GREEN_BORDER = (187, 247, 208)
COLOR_ORANGE = (217, 119, 6)
COLOR_ORANGE_BG = (254, 243, 199)
COLOR_ORANGE_BORDER = (253, 230, 138)

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    def fa(text: str) -> str:
        if not text:
            return ""
        try:
            return get_display(arabic_reshaper.reshape(str(text)))
        except:
            return str(text)
except ImportError:
    def fa(text: str) -> str:
        return str(text) if text else ""

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import jdatetime
    def _persian_now() -> str:
        return jdatetime.datetime.now().strftime("%Y/%m/%d - %H:%M")
except ImportError:
    def _persian_now() -> str:
        return datetime.now().strftime("%Y-%m-%d - %H:%M")

from config import SHOP_NAME, SHOP_PHONE, SHOP_ADDRESS, LICENSE_NO

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
                urllib.request.urlretrieve(url, path)
            except Exception as e:
                logger.warning(f"Font download warning: {e}")

_ensure_fonts()

def _format_price(value) -> str:
    try:
        s = str(value).replace(",", "").replace("،", "").strip()
        if not s or s == "0":
            return "۰"
        n = int(s)
        return f"{n:,}".replace(",", "،")
    except:
        return str(value)

def _get_font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT_REGULAR
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except:
            pass
    for sys_font in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf"
    ]:
        if os.path.exists(sys_font):
            try:
                return ImageFont.truetype(sys_font, size)
            except:
                pass
    return ImageFont.load_default()

def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple:
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    return len(text) * 16, 32

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> List[str]:
    words = str(text).split()
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


def generate_invoice_png(order_data: dict, output_path: str = "invoice.png", is_pre_invoice: bool = False) -> str:
    \"\"\"
    تولید فاکتور Full HD (۱۲۰۰ پیکسل) با ظرافت و رزولوشن رتینا
    \"\"\"
    _ensure_fonts()

    W = 1200  # رزولوشن Full HD واقعی جهت شفافیت ۱۰۰٪
    PAD = 55
    CW = W - PAD * 2

    img = Image.new("RGB", (W, 4500), WHITE)
    draw = ImageDraw.Draw(img)

    y = PAD

    def draw_dashed_line(cur_y: int, color=COLOR_BORDER):
        for x_dot in range(PAD, W - PAD, 20):
            draw.line([(x_dot, cur_y), (x_dot + 10, cur_y)], fill=color, width=2)
        return cur_y + 30

    # نوار رنگی بالای فیش
    draw.rectangle([(0, 0), (W, 8)], fill=COLOR_RED)

    # ۱. هدر فروشگاه
    shop_title = fa(order_data.get("shop_name", SHOP_NAME))
    f_shop = _get_font(46, bold=True)
    tw, _ = _text_size(draw, shop_title, f_shop)
    draw.text(((W - tw) // 2, y), shop_title, font=f_shop, fill=COLOR_DARK)
    y += 75

    # نشان رسمی وضعیت سند
    if is_pre_invoice:
        badge_title = fa("پـیـش‌فـاکـتـور رسـمـی خـریـد (غـیـرقـطـعـی)")
        bg_c, brd_c, txt_c = COLOR_ORANGE_BG, COLOR_ORANGE_BORDER, COLOR_ORANGE
    else:
        badge_title = fa("فـاکـتـور فـروش رسـمـی و قـطـعـی")
        bg_c, brd_c, txt_c = COLOR_GREEN_BG, COLOR_GREEN_BORDER, COLOR_GREEN

    f_badge = _get_font(25, bold=True)
    bw, bh = _text_size(draw, badge_title, f_badge)
    bx = (W - bw - 48) // 2
    draw.rounded_rectangle([bx, y, bx + bw + 48, y + bh + 22], radius=12, fill=bg_c, outline=brd_c, width=2)
    draw.text(((W - bw) // 2, y + 11), badge_title, font=f_badge, fill=txt_c)
    y += bh + 48

    # آدرس و تلفن فروشگاه
    f_info = _get_font(23)
    info1 = fa(f"آدرس: {order_data.get('shop_address', SHOP_ADDRESS)}")
    tw, _ = _text_size(draw, info1, f_info)
    draw.text(((W - tw) // 2, y), info1, font=f_info, fill=COLOR_GRAY)
    y += 38

    info2 = fa(f"تلفن تماس: {order_data.get('shop_phone', SHOP_PHONE)}   |   شماره ثبت: {order_data.get('license_no', LICENSE_NO)}")
    tw, _ = _text_size(draw, info2, f_info)
    draw.text(((W - tw) // 2, y), info2, font=f_info, fill=COLOR_GRAY)
    y += 45

    y = draw_dashed_line(y)

    # ۲. مشخصات سفارش و خریدار
    def draw_row(label: str, val: str, bold=False, color=COLOR_DARK, size=26):
        nonlocal y
        tl, tv = fa(label), fa(val)
        fl, fv = _get_font(size, bold=bold), _get_font(size, bold=True)
        twl, _ = _text_size(draw, tl, fl)
        draw.text((W - PAD - twl, y), tl, font=fl, fill=COLOR_GRAY)
        draw.text((PAD, y), tv, font=fv, fill=color)
        y += size + 22

    inv_lbl = "شماره پیش‌فاکتور:" if is_pre_invoice else "شماره فاکتور:"
    draw_row(inv_lbl, str(order_data.get('invoice_number', '')))
    draw_row("کد رهگیری سفارش:", f"#{order_data.get('order_code', '')}", bold=True, color=COLOR_RED, size=28)
    draw_row("تاریخ و ساعت صدور:", str(order_data.get('date', _persian_now())))
    draw_row("نام خریدار:", str(order_data.get('customer_name', 'نامشخص')), bold=True)
    draw_row("شماره همراه خریدار:", str(order_data.get('customer_phone', '-')))

    # کارت نشانی خریدار با پس‌زمینه لطیف
    addr_lines = _wrap_text(draw, f"نشانی تحویل مقصد: {order_data.get('customer_address', '-')}", _get_font(23), CW - 40)
    card_h = len(addr_lines) * 36 + 24
    draw.rounded_rectangle([PAD, y, W - PAD, y + card_h], radius=12, fill=COLOR_BG_CARD, outline=COLOR_BORDER, width=1)
    
    cur_card_y = y + 12
    for al in addr_lines:
        t = fa(al)
        tw, _ = _text_size(draw, t, _get_font(23))
        draw.text((W - PAD - 20 - tw, cur_card_y), t, font=_get_font(23), fill=COLOR_DARK)
        cur_card_y += 36
    y += card_h + 20

    y = draw_dashed_line(y)

    # ۳. اقلام سفارش
    f_tbl_h = _get_font(24, bold=True)
    draw.text((W - PAD - _text_size(draw, fa("شرح کالا و مشخصات فنی"), f_tbl_h)[0], y), fa("شرح کالا و مشخصات فنی"), font=f_tbl_h, fill=COLOR_GRAY)
    draw.text((PAD, y), fa("مبلغ کل (تومان)"), font=f_tbl_h, fill=COLOR_GRAY)
    y += 45
    draw.line([(PAD, y), (W - PAD, y)], fill=COLOR_DARK, width=2)
    y += 24

    for item in order_data.get("items", []):
        name = str(item.get("name", ""))
        meta = str(item.get("meta", ""))
        price_txt = str(item.get("total", "۰"))

        name_lines = _wrap_text(draw, name, _get_font(28, bold=True), CW - 320)
        for idx, nl in enumerate(name_lines):
            t = fa(nl)
            tw, _ = _text_size(draw, t, _get_font(28, bold=True))
            draw.text((W - PAD - tw, y), t, font=_get_font(28, bold=True), fill=COLOR_DARK)
            if idx == 0:
                tp = fa(f"{price_txt}")
                draw.text((PAD, y), tp, font=_get_font(28, bold=True), fill=COLOR_DARK)
            y += 42

        if meta:
            for ml in _wrap_text(draw, f"• {meta}", _get_font(21), CW):
                t = fa(ml)
                tw, _ = _text_size(draw, t, _get_font(21))
                draw.text((W - PAD - tw, y), t, font=_get_font(21), fill=COLOR_GRAY)
                y += 32
        y += 10

    y = draw_dashed_line(y)

    # ۴. محاسبات مالی و کارت وضعیت بیعانه
    draw_row("مبلغ کل کالا:", f"{order_data.get('grand_total', '۰')} تومان", size=27)

    if is_pre_invoice:
        # پیش‌فاکتور با بچ واریز نشده
        draw_row("مبلغ بیعانه پیش‌پرداخت (۸٪):", f"{order_data.get('deposit', '۰')} تومان", bold=True, size=27)

        # کارت بیعانه در انتظار واریز
        draw.rounded_rectangle([PAD, y, W - PAD, y + 80], radius=14, fill=COLOR_ORANGE_BG, outline=COLOR_ORANGE_BORDER, width=2)
        nt = fa("وضعیت بیعانه: ⏳ در انتظار واریز (پرداخت نشده)  |  مهلت اعتبار: ۳ ساعت")
        tw, _ = _text_size(draw, nt, _get_font(22, bold=True))
        draw.text(((W - tw) // 2, y + 26), nt, font=_get_font(22, bold=True), fill=COLOR_ORANGE)
        y += 105

        draw_row("مانده تسویه در محل:", f"{order_data.get('remaining', '۰')} تومان", bold=True, color=COLOR_RED, size=28)
    else:
        # فاکتور فروش قطعی
        draw_row("بیعانه دریافتی (۸٪):", f"{order_data.get('deposit', '۰')} تومان  [ ✅ پرداخت و تایید شد ]", bold=True, color=COLOR_GREEN, size=27)

        # کارت برجسته مانده حساب
        draw.rounded_rectangle([PAD, y, W - PAD, y + 86], radius=14, fill=COLOR_RED_BG, outline=COLOR_RED_BORDER, width=2)
        tl, tv = fa("مانده تسویه پس از تست در محل:"), fa(f"{order_data.get('remaining', '۰')} تومان")
        draw.text((W - PAD - 24 - _text_size(draw, tl, _get_font(25, bold=True))[0], y + 26), tl, font=_get_font(25, bold=True), fill=COLOR_RED)
        draw.text((PAD + 24, y + 24), tv, font=_get_font(28, bold=True), fill=COLOR_RED)
        y += 110

    y = draw_dashed_line(y)

    # ۵. شرایط فروش و گارانتی کتبی
    f_th2 = _get_font(24, bold=True)
    draw.text((W - PAD - _text_size(draw, fa("شرایط فروش، تحویل و گارانتی کالا:"), f_th2)[0], y), fa("شرایط فروش، تحویل و گارانتی کالا:"), font=f_th2, fill=COLOR_DARK)
    y += 42

    terms = [
        "۱. گارانتی کتبی: کلیه اجناس دارای ۲ سال ضمانت تعویض قطعات و ۵ سال خدمات پس از فروش می‌باشند.",
        "۲. مهلت تست: خریدار موظف است کالا را هنگام تحویل از لحاظ اصالت و سلامت و روشن شدن بررسی نماید.",
        "۳. تسویه نهایی: مانده فاکتور پس از تحویل و رضایت کامل در محل تسویه می‌گردد."
    ]
    for term in terms:
        for tl in _wrap_text(draw, term, _get_font(20), CW):
            t = fa(tl)
            tw, _ = _text_size(draw, t, _get_font(20))
            draw.text((W - PAD - tw, y), t, font=_get_font(20), fill=COLOR_GRAY)
            y += 32
        y += 6

    y += 20

    # ۶. QR Code و مهر رسمی
    if HAS_QRCODE:
        try:
            qr = qrcode.QRCode(version=1, box_size=6, border=1)
            qr.add_data(f"https://t.me/AiKala_bot?start=track_{order_data.get('order_code', '')}")
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color=COLOR_DARK, back_color=WHITE).convert('RGB')
            img.paste(qr_img, (PAD + 20, y))
            draw.text((PAD + 28, y + 140), fa("اسکن رهگیری"), font=_get_font(18), fill=COLOR_GRAY)
        except Exception as e:
            logger.warning(f"QR error: {e}")

    # مهر شرکتی بیضی با حاشیه دوتایی
    scx = W - PAD - 170
    scy = y + 70
    s_color = COLOR_ORANGE if is_pre_invoice else COLOR_GREEN
    draw.ellipse([scx - 130, scy - 56, scx + 130, scy + 56], outline=s_color, width=3)
    draw.ellipse([scx - 122, scy - 48, scx + 122, scy + 48], outline=s_color, width=1)
    
    s1 = fa("پیش‌فاکتور خرید" if is_pre_invoice else "فروشگاه آی‌کالا")
    s2 = fa("در انتظار واریز" if is_pre_invoice else "تایید و صادر شد")
    draw.text((scx - _text_size(draw, s1, _get_font(22, bold=True))[0] // 2, scy - 28), s1, font=_get_font(22, bold=True), fill=s_color)
    draw.text((scx - _text_size(draw, s2, _get_font(19))[0] // 2, scy + 6), s2, font=_get_font(19), fill=s_color)

    y += 180

    # نوار پایانی
    draw.rounded_rectangle([PAD, y, W - PAD, y + 54], radius=10, fill=COLOR_DARK)
    bt = fa("فروشگاه آی‌کالا • ارسال تضمینی با باربری اختصاصی به سراسر کشور")
    tw, _ = _text_size(draw, bt, _get_font(20))
    draw.text(((W - tw) // 2, y + 14), bt, font=_get_font(20), fill=WHITE)
    y += 75

    # برش دقیق
    img = img.crop((0, 0, W, y))
    img.save(output_path, "PNG", quality=100, optimize=True)
    return output_path


def build_invoice_data_from_order(order: dict, product: dict) -> dict:
    \"\"\"تبدیل دیکشنری سفارش و محصول به ورودی استاندارد فاکتور\"\"\"
    deposit = 0
    try:
        deposit = int(str(order.get('deposit_amount', '0') or '0').replace(',', '').replace('،', ''))
    except:
        pass

    price = 0
    try:
        price = int(str(product.get('price', '0') or '0').replace(',', '').replace('،', '').strip())
    except:
        pass

    remaining = max(0, price - deposit)

    return {
        "shop_name": SHOP_NAME,
        "shop_phone": SHOP_PHONE,
        "shop_address": SHOP_ADDRESS,
        "license_no": LICENSE_NO,
        "invoice_number": f"INV-{order['order_code']}",
        "date": _persian_now(),
        "order_code": order['order_code'],
        "customer_name": order.get('full_name', 'نامشخص'),
        "customer_phone": order.get('phone1', '-'),
        "customer_phone2": order.get('phone2', ''),
        "customer_address": order.get('address', '-'),
        "customer_postal": order.get('postal_code', '-'),
        "items": [
            {
                "name": product.get('name', 'نامشخص'),
                "meta": f"برند: {product.get('brand', '-')} | ۲ سال ضمانت تعویض کتبی + ۵ سال خدمات پس از فروش",
                "code": str(product.get('product_id', '-'))[:14],
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
`;

  // Complete bot.py order flow snippet
  const pythonBotCompleteFlowCode = `\"\"\"
کدهای تصحیح شده برای bot.py:
۱. اضافه شدن دکمه‌های «ارسال تصویر فیش»، «ثبت شماره پیگیری» و «انصراف از خرید»
۲. رفع ریشه‌ای عدم کارکرد دکمه «لغو سفارش» در طول فرآیند ثبت سفارش
\"\"\"
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from invoice_generator import generate_invoice_png, build_invoice_data_from_order

# تعریف حالات فرآیند سفارش (ConversationHandler States)
(
    ORDER_NAME,
    ORDER_PHONE1,
    ORDER_PHONE2,
    ORDER_ADDRESS,
    ORDER_CONFIRM,
    ORDER_RECEIPT,
) = range(6)

# کلیدواژه‌های معتبر جهت انصراف و لغو سفارش در هر مرحله
CANCEL_KEYWORDS = [
    "❌ لغو سفارش",
    "لغو سفارش",
    "❌ انصراف از خرید",
    "انصراف از خرید",
    "❌ انصراف از سفارش",
    "انصراف از سفارش",
    "انصراف",
    "لغو"
]

def is_cancel_command(text: str) -> bool:
    \"\"\"بررسی اینکه آیا پیام ارسالی کاربر دستور لغو سفارش است یا خیر\"\"\"
    if not text:
        return False
    t = str(text).strip()
    return t in CANCEL_KEYWORDS or any(w in t for w in ["لغو سفارش", "انصراف از خرید", "انصراف از سفارش"])

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    \"\"\"
    لغو فوری سفارش و خروج کامل از ConversationHandler:
    - پاکسازی سشن و دیتای موقت
    - حذف کیبورد پایین صفحه (ReplyKeyboardRemove)
    - ارسال پیام شفاف لغو به کاربر
    \"\"\"
    # پاکسازی تمام متغیرهای موقت سفارش
    keys_to_delete = [k for k in context.user_data.keys() if k.startswith("order_") or k in ["current_order_code", "receipt_mode"]]
    for k in keys_to_delete:
        context.user_data.pop(k, None)

    cancel_msg = (
        "❌ <b>سفارش با موفقیت لغو گردید.</b>\\n\\n"
        "هر زمان مایل بودید می‌توانید از طریق جستجو یا دسته‌بندی محصولات، مجدداً سفارش جدیدی ثبت فرمایید."
    )

    if update.callback_query:
        query = update.callback_query
        try:
            await query.answer("سفارش لغو شد.")
        except Exception:
            pass
        try:
            await query.edit_message_text(cancel_msg, parse_mode="HTML")
        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=cancel_msg,
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )
    elif update.message:
        await update.message.reply_text(
            cancel_msg,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )

    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────
# توابع دریافت مشخصات مشتری با پشتیبانی ۱۰۰٪ از دکمه لغو سفارش
# ─────────────────────────────────────────────────────────────

async def order_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    \"\"\"دریافت نام و نام خانوادگی خریدار\"\"\"
    text = update.message.text.strip() if update.message and update.message.text else ""
    if is_cancel_command(text):
        return await cancel_order(update, context)

    if len(text) < 3:
        await update.message.reply_text(
            "⚠️ لطفاً نام و نام خانوادگی معتبر خود را وارد فرمایید:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ لغو سفارش")]], resize_keyboard=True)
        )
        return ORDER_NAME

    context.user_data["order_name"] = text
    await update.message.reply_text(
        "📱 لطفاً <b>شماره تماس همراه اول</b> (جهت هماهنگی تحویل و تماس راننده) را وارد نمایید:\\nنمونه: <code>09121234567</code>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ لغو سفارش")]], resize_keyboard=True)
    )
    return ORDER_PHONE1


async def order_phone1_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    \"\"\"دریافت شماره تماس اول خریدار\"\"\"
    text = update.message.text.strip() if update.message and update.message.text else ""
    if is_cancel_command(text):
        return await cancel_order(update, context)

    # اعتبارسنجی شماره همراه ایران
    import re
    cleaned = re.sub(r"[^0-9]", "", text)
    if not (len(cleaned) == 11 and cleaned.startswith("09")):
        await update.message.reply_text(
            "⚠️ <b>شماره تماس نامعتبر است!</b>\\nلطفاً شماره همراه ۱۱ رقمی معتبر وارد فرمایید (مثال: 09121234567):",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ لغو سفارش")]], resize_keyboard=True)
        )
        return ORDER_PHONE1

    context.user_data["order_phone1"] = cleaned
    await update.message.reply_text(
        "📍 لطفاً <b>نشانی دقیق پستی</b> (شامل استان، شهر، خیابان، پلاک، واحد و کد پستی در صورت وجود) را بنویسید:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ لغو سفارش")]], resize_keyboard=True)
    )
    return ORDER_ADDRESS


async def order_address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    \"\"\"دریافت آدرس تحویل و نمایش پیش‌نمایش تایید سفارش\"\"\"
    text = update.message.text.strip() if update.message and update.message.text else ""
    if is_cancel_command(text):
        return await cancel_order(update, context)

    if len(text) < 10:
        await update.message.reply_text(
            "⚠️ لطفاً آدرس کامل‌تری همراه با نام شهر یا پلاک وارد نمایید:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ لغو سفارش")]], resize_keyboard=True)
        )
        return ORDER_ADDRESS

    context.user_data["order_address"] = text

    # خلاصه سفارش جهت تایید نهایی
    p_name = context.user_data.get("order_product_name", "کالای انتخابی")
    p_price = int(str(context.user_data.get("order_product_price", 0) or 0).replace(",", ""))
    deposit = int(round((p_price * 0.08) / 10000)) * 10000 if p_price >= 100000 else round(p_price * 0.08)
    context.user_data["order_deposit"] = deposit
    context.user_data["order_remaining"] = max(0, p_price - deposit)

    summary = (
        "📋 <b>خلاصه مشخصات فاکتور قبل از صدور:</b>\\n\\n"
        f"🔹 <b>کالا:</b> {p_name}\\n"
        f"💰 <b>قیمت قطعی روز با احتساب هزینه ارسال درب منزل:</b> {p_price:,} تومان\\n"
        f"💳 <b>مبلغ بیعانه پیش‌پرداخت (۸٪):</b> <b>{deposit:,} تومان</b>\\n"
        f"💵 <b>مانده تسویه در محل:</b> <b>{(p_price - deposit):,} تومان</b>\\n\\n"
        f"👤 <b>تحویل‌گیرنده:</b> {context.user_data.get('order_name')}\\n"
        f"📞 <b>شماره تماس:</b> <code>{context.user_data.get('order_phone1')}</code>\\n"
        f"📍 <b>نشانی مقصد:</b> {context.user_data.get('order_address')}\\n\\n"
        "آیا اطلاعات فوق مورد تایید است؟"
    )

    confirm_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید و صدور پیش‌فاکتور", callback_data="order_confirm|yes"),
            InlineKeyboardButton("❌ لغو سفارش", callback_data="order_confirm|no")
        ]
    ])

    await update.message.reply_text(
        summary,
        parse_mode="HTML",
        reply_markup=confirm_kb
    )
    return ORDER_CONFIRM


# ─────────────────────────────────────────────────────────────
# مرحله تایید و صدور پیش‌فاکتور + پیام شماره کارت با دکمه‌های جدید
# ─────────────────────────────────────────────────────────────

async def order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data in ["order_confirm|no", "order_cancel"]:
        return await cancel_order(update, context)

    chat_id = query.message.chat_id
    order_code = await generate_unique_order_code()
    deposit = context.user_data.get("order_deposit", 0)
    price_val = context.user_data.get("order_product_price", "0")

    # ۱. ذخیره سفارش در دیتابیس
    order_data = {
        "order_code": order_code,
        "user_id": query.from_user.id,
        "username": query.from_user.username or "",
        "product_id": context.user_data.get("order_product_id", ""),
        "product_name": context.user_data.get("order_product_name", "کالای انتخابی"),
        "full_name": context.user_data.get("order_name", "خریدار"),
        "phone1": context.user_data.get("order_phone1", "-"),
        "phone2": context.user_data.get("order_phone2", ""),
        "address": context.user_data.get("order_address", "-"),
        "postal_code": context.user_data.get("order_postal", ""),
        "deposit_amount": str(deposit),
        "status": "Awaiting_Payment"
    }
    await db.create_order(order_data)
    context.user_data["current_order_code"] = order_code

    # ۲. آماده‌سازی اطلاعات محصول
    product = await db.get_product_by_id(order_data['product_id'])
    if not product:
        product = context.user_data.get("last_search_results", {}).get(order_data['product_id'])
    if not product:
        product = {
            "name": order_data['product_name'],
            "price": str(price_val),
            "brand": "اصلی"
        }

    # ۳. تولید پیش‌فاکتور Full HD Option B (is_pre_invoice=True)
    png_path = f"pre_invoice_{order_code}.png"
    try:
        inv_data = build_invoice_data_from_order(order_data, product)
        generate_invoice_png(inv_data, png_path, is_pre_invoice=True)

        with open(png_path, "rb") as photo_file:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo_file,
                caption=(
                    f"🧾 <b>پیش‌فاکتور رسمی خرید سفارش #{order_code} صادر گردید.</b>\\n\\n"
                    f"وضعیت بیعانه: <b>⏳ در انتظار واریز</b>\\n"
                    f"⚠️ <i>این پیش‌فاکتور به مدت ۳ ساعت جهت واریز بیعانه معتبر است.</i>"
                ),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error in pre-invoice generation: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ پیش‌فاکتور سفارش <code>#{order_code}</code> ثبت گردید.\\nعلت خطا در تصویر: <code>{e}</code>",
            parse_mode="HTML"
        )
    finally:
        if os.path.exists(png_path):
            try:
                os.remove(png_path)
            except:
                pass

    # ۴. پیام اطلاعات حساب بانکی همراه با دکمه‌های شیشه‌ای و کیبورد پایین
    card_info = (
        f"💳 <b>اطلاعات پرداخت بیعانه سفارش #{order_code}</b>\\n\\n"
        f"💰 مبلغ بیعانه پیش‌پرداخت (۸٪): <b>{deposit:,} تومان</b>\\n\\n"
        f"💳 شماره کارت: <code>{DEPOSIT_CARD_NUMBER}</code>\\n"
        f"▫️ شماره شبا بانکی: IR <code>620120020000005786685564</code>\\n"
        f"👤 به نام: <b>{DEPOSIT_CARD_NAME}</b>\\n\\n"
        "📎 لطفاً پس از واریز، <b>تصویر فیش واریزی یا شماره پیگیری</b> را همینجا ارسال فرمایید:"
    )

    # دکمه‌های شیشه‌ای (Inline) زیر متن پیام
    inline_actions_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📸 ارسال تصویر فیش", callback_data="btn_send_photo"),
            InlineKeyboardButton("🔢 ارسال کد پیگیری (متن)", callback_data="btn_send_text")
        ],
        [
            InlineKeyboardButton("❌ انصراف از خرید", callback_data="order_cancel")
        ]
    ])

    # دکمه‌های کیبورد پایین صفحه (ReplyKeyboard) جهت راحتی کامل در موبایل
    reply_actions_kb = ReplyKeyboardMarkup([
        [KeyboardButton("📸 ارسال عکس فیش بیعانه"), KeyboardButton("🔢 ثبت شماره پیگیری")],
        [KeyboardButton("❌ انصراف از خرید")]
    ], resize_keyboard=True)

    # ارسال پیام با کیبورد شیشه‌ای
    await context.bot.send_message(
        chat_id=chat_id,
        text=card_info,
        parse_mode="HTML",
        reply_markup=inline_actions_kb
    )

    # ارسال راهنمای کیبورد پایین صفحه
    await context.bot.send_message(
        chat_id=chat_id,
        text="👇 از دکمه‌های زیر نیز می‌توانید جهت ارسال فیش یا انصراف استفاده نمایید:",
        reply_markup=reply_actions_kb
    )

    return ORDER_RECEIPT


# ─────────────────────────────────────────────────────────────
# دریافت فیش بیعانه (عکس یا متن) + پشتیبانی کامل از دکمه‌های انتخابی
# ─────────────────────────────────────────────────────────────

async def order_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    \"\"\"پردازش ارسال تصویر فیش، شماره پیگیری متنی یا انصراف\"\"\"

    # ۱. بررسی کلیک روی دکمه‌های اینلاین
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "order_cancel":
            return await cancel_order(update, context)

        if query.data == "btn_send_photo":
            await query.message.reply_text("📸 لطفاً عکس فیش واریزی یا اسکرین‌شات رسید بانکی خود را ارسال فرمایید:")
            return ORDER_RECEIPT

        if query.data == "btn_send_text":
            await query.message.reply_text("🔢 لطفاً شماره پیگیری یا شناسه ارجاع فیش واریزی خود را تایپ و ارسال فرمایید:")
            return ORDER_RECEIPT

    # ۲. بررسی پیام متنی
    if update.message and update.message.text:
        text = update.message.text.strip()

        # الف) دکمه انصراف
        if is_cancel_command(text):
            return await cancel_order(update, context)

        # ب) درخواست راهنمای ارسال عکس
        if text in ["📸 ارسال عکس فیش بیعانه", "📸 ارسال تصویر فیش"]:
            await update.message.reply_text("📸 لطفاً تصویر فیش واریزی خود را در همین صفحه ارسال فرمایید:")
            return ORDER_RECEIPT

        # ج) درخواست راهنمای ارسال کد پیگیری
        if text in ["🔢 ثبت شماره پیگیری", "🔢 ارسال کد پیگیری (متن)"]:
            await update.message.reply_text("🔢 لطفاً شماره پیگیری، تاریخ یا اطلاعات واریزی را به صورت متن ارسال نمایید:")
            return ORDER_RECEIPT

        # د) کاربر خود شماره پیگیری را تایپ کرده است!
        tracking_code = text
        order_code = context.user_data.get("current_order_code", "نامشخص")

        await db.update_order_receipt(order_code, receipt_type="text", receipt_value=tracking_code)
        
        await update.message.reply_text(
            f"✅ <b>شماره پیگیری فیش با موفقیت ثبت شد.</b>\\n\\n"
            f"کد رهگیری سفارش: <code>#{order_code}</code>\\n"
            f"شناسه پیگیری واریز: <code>{tracking_code}</code>\\n\\n"
            "⏳ پس از تایید توسط واحد مالی، فاکتور قطعی و هماهنگی ارسال با شما انجام خواهد شد.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END

    # ۳. بررسی ارسال عکس فیش
    if update.message and update.message.photo:
        photo = update.message.photo[-1]
        order_code = context.user_data.get("current_order_code", "نامشخص")
        file_id = photo.file_id

        await db.update_order_receipt(order_code, receipt_type="photo", receipt_value=file_id)

        await update.message.reply_text(
            f"✅ <b>تصویر فیش واریزی دریافت شد.</b>\\n\\n"
            f"کد رهگیری سفارش: <code>#{order_code}</code>\\n"
            "⏳ پس از بررسی رسید توسط همکاران حسابداری، وضعیت به «پرداخت شد» تغییر یافته و هماهنگی ارسال انجام خواهد شد.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END

    # در صورت ارسال فایل نامرتبط
    await update.message.reply_text(
        "⚠️ لطفاً تصویر فیش یا شماره پیگیری معتبر ارسال فرمایید (یا روی ❌ انصراف از خرید بزنید):",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("📸 ارسال عکس فیش بیعانه"), KeyboardButton("🔢 ثبت شماره پیگیری")],
            [KeyboardButton("❌ انصراف از خرید")]
        ], resize_keyboard=True)
    )
    return ORDER_RECEIPT


# ─────────────────────────────────────────────────────────────
# تنظیمات ConversationHandler با اضافه شدن کامل Fallbacks
# ─────────────────────────────────────────────────────────────
order_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(order_start_handler, pattern=r"^start_order\|")
    ],
    states={
        ORDER_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, order_name_handler)
        ],
        ORDER_PHONE1: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone1_handler)
        ],
        ORDER_ADDRESS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, order_address_handler)
        ],
        ORDER_CONFIRM: [
            CallbackQueryHandler(order_confirm, pattern=r"^(order_confirm\|yes|order_confirm\|no|order_cancel)$")
        ],
        ORDER_RECEIPT: [
            CallbackQueryHandler(order_receipt_handler, pattern=r"^(btn_send_photo|btn_send_text|order_cancel)$"),
            MessageHandler(filters.PHOTO, order_receipt_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, order_receipt_handler)
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_order),
        MessageHandler(filters.Regex(r"^(❌\\s*)?(لغو سفارش|انصراف از خرید|انصراف از سفارش|انصراف|لغو)$"), cancel_order),
        CallbackQueryHandler(cancel_order, pattern=r"^(order_cancel|cancel_order|order_confirm\\|no)$")
    ],
    allow_reentry=True
)
`;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col antialiased">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-rose-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Volume2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-black text-lg text-white">سامانه فروشگاهی و کاتالوگ هوشمند AiKala</span>
                <span className="text-[10px] bg-indigo-500/20 text-indigo-300 font-bold px-2 py-0.5 rounded-full border border-indigo-500/30">
                  سیستم صوتی + ربات
                </span>
              </div>
              <p className="text-xs text-slate-400">کاتالوگ ۴۲ مدل سیستم صوتی، استخراج لیست قیمت PDF، پایش کانال‌ها و شبیه‌ساز فاکتور</p>
            </div>
          </div>

          {/* Tab Selector */}
          <div className="flex items-center bg-slate-800/90 p-1 rounded-xl border border-slate-700/70 text-xs overflow-x-auto">
            <button
              onClick={() => setActiveTab("audio_catalog")}
              className={`px-3.5 py-1.5 rounded-lg font-bold transition cursor-pointer flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "audio_catalog"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Volume2 className="w-3.5 h-3.5" />
              🔊 کاتالوگ و قیمت‌های سیستم صوتی
            </button>
            <button
              onClick={() => setActiveTab("channels")}
              className={`px-3.5 py-1.5 rounded-lg font-bold transition cursor-pointer flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "channels"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Radio className="w-3.5 h-3.5" />
              📡 پایش کانال‌ها
            </button>
            <button
              onClick={() => setActiveTab("simulator")}
              className={`px-3.5 py-1.5 rounded-lg font-bold transition cursor-pointer flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "simulator"
                  ? "bg-rose-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              شبیه‌ساز تلگرام
            </button>
            <button
              onClick={() => setActiveTab("preview")}
              className={`px-3.5 py-1.5 rounded-lg font-bold transition cursor-pointer flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "preview"
                  ? "bg-rose-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              پیش‌نمایش فیش بیعانه
            </button>
            <button
              onClick={() => setActiveTab("python_code")}
              className={`px-3.5 py-1.5 rounded-lg font-bold transition cursor-pointer flex items-center gap-1.5 whitespace-nowrap ${
                activeTab === "python_code"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              کدهای پایتون
            </button>
            <button
              onClick={() => setActiveTab("troubleshooting")}
              className={`px-3.5 py-1.5 rounded-lg font-bold transition cursor-pointer flex items-center gap-1.5 ${
                activeTab === "troubleshooting"
                  ? "bg-amber-600 text-white shadow-sm"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <AlertCircle className="w-3.5 h-3.5" />
              رفع مشکل لغو سفارش
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8">
        
        {/* ── TAB 0: AUDIO SYSTEMS & STORE CATALOG ── */}
        {activeTab === "audio_catalog" && <AudioCatalogTab />}

        {/* ── TAB 1: TELEGRAM CHAT SIMULATOR ── */}
        {activeTab === "simulator" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left Column: Flow Explanation & Controls */}
            <div className="lg:col-span-5 space-y-6">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
                <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
                  <Sparkles className="w-5 h-5 text-amber-400" />
                  <h3 className="font-bold text-sm text-white">تست تعاملی دکمه‌های پیام واریز بیعانه</h3>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">
                  طبق درخواست شما، دقیقاً زیر پیام حاوی شماره کارت واریز بیعانه:
                </p>

                <div className="space-y-2 text-xs">
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                    <span className="w-2 h-2 rounded-full bg-indigo-400 mt-1.5 shrink-0"></span>
                    <div>
                      <span className="font-bold text-white block">۱. دکمه ارسال فیش بیعانه (عکس یا متن):</span>
                      <span className="text-slate-400 text-[11px]">
                        کاربر می‌تواند با دکمه‌های <b>«📸 ارسال تصویر فیش»</b> یا <b>«🔢 ارسال کد پیگیری»</b> فیش خود را ارسال نماید و هر دو شیوه پشتیبانی می‌شود.
                      </span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-start gap-2.5">
                    <span className="w-2 h-2 rounded-full bg-rose-400 mt-1.5 shrink-0"></span>
                    <div>
                      <span className="font-bold text-white block">۲. دکمه انصراف از خرید (لغو فوری سفارش):</span>
                      <span className="text-slate-400 text-[11px]">
                        در هر مرحله از ثبت سفارش، زدن روی دکمه <b>«❌ انصراف از خرید»</b> یا <b>«❌ لغو سفارش»</b> سشن را بلافاصله می‌بندد و کیبورد را حذف می‌کند.
                      </span>
                    </div>
                  </div>
                </div>

                {/* Reset State Button */}
                <div className="pt-2">
                  <button
                    onClick={() => {
                      setSimStep("waiting_payment");
                      setSimTrackingInput("");
                      setSimUploadedReceipt(null);
                    }}
                    className="w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 cursor-pointer border border-slate-700"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    بازنشانی به حالت اولیه پیش‌فاکتور
                  </button>
                </div>
              </div>

              {/* Summary of Fix for Cancel Button */}
              <div className="bg-rose-950/20 border border-rose-800/40 rounded-2xl p-5 space-y-3">
                <div className="flex items-center gap-2 text-rose-300 font-bold text-xs">
                  <XCircle className="w-4 h-4 text-rose-400" />
                  <span>چرا دکمه لغو سفارش قبلاً عمل نمی‌کرد؟</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  هنگام درخواست آدرس یا تلفن، ربات متن ارسالی کاربر را به جای بررسی لغو، به عنوان شماره تلفن یا نام خریدار ذخیره می‌کرد. با اضافه شدن شرط <code className="text-rose-300 bg-slate-900 px-1 rounded">is_cancel_command</code> در ابتدای تمام مراحل، این باگ ۱۰۰٪ رفع شد.
                </p>
              </div>
            </div>

            {/* Right Column: Telegram Chat Mockup */}
            <div className="lg:col-span-7 flex justify-center">
              <div className="w-full max-w-[420px] bg-slate-900 border-2 border-slate-800 rounded-3xl overflow-hidden shadow-2xl flex flex-col font-sans">
                {/* Telegram Header */}
                <div className="bg-slate-800/90 px-4 py-3 border-b border-slate-700/80 flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-rose-500 to-amber-500 flex items-center justify-center font-bold text-white text-xs shadow-sm">
                      آی
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-xs text-white">فروشگاه آی‌کالا (ربات تلگرام)</div>
                      <div className="text-[10px] text-emerald-400">bot • آنلاین</div>
                    </div>
                  </div>
                  <span className="text-[10px] text-slate-400 bg-slate-950/60 px-2 py-0.5 rounded-full border border-slate-700">
                    #{orderCode}
                  </span>
                </div>

                {/* Telegram Chat Body */}
                <div className="p-4 space-y-3.5 bg-slate-950/90 min-h-[500px] text-right flex flex-col justify-end text-xs">
                  
                  {/* 1. Pre-Invoice Thumbnail message */}
                  <div className="bg-slate-900 p-3 rounded-2xl rounded-tr-none border border-slate-800 shadow-md space-y-2 max-w-[90%] self-start">
                    <div className="relative rounded-xl overflow-hidden border border-slate-700 bg-slate-950">
                      <img
                        src="https://images.unsplash.com/photo-1593784991095-a205069470b6?w=600&auto=format&fit=crop&q=80"
                        alt="Pre-invoice preview"
                        className="w-full h-32 object-cover opacity-80"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent flex items-end p-2">
                        <div className="text-[10px] text-amber-300 font-bold flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                          پیش‌فاکتور رسمی Option B (Full HD 1200px)
                        </div>
                      </div>
                    </div>

                    <div className="text-[11px] text-slate-200 leading-relaxed">
                      🧾 <b>پیش‌فاکتور رسمی خرید سفارش #{orderCode} صادر گردید.</b>
                      <div className="text-amber-400 font-bold mt-1">وضعیت بیعانه: ⏳ در انتظار واریز</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">⚠️ این پیش‌فاکتور به مدت ۳ ساعت جهت واریز بیعانه معتبر است.</div>
                    </div>
                  </div>

                  {/* 2. Payment Card Message with Requested Buttons */}
                  <div className="bg-slate-900 p-3.5 rounded-2xl rounded-tr-none border border-slate-800 shadow-md space-y-3 max-w-[95%] self-start">
                    <div className="flex items-center gap-1.5 text-slate-200 font-bold border-b border-slate-800 pb-2">
                      <CreditCard className="w-4 h-4 text-amber-400" />
                      <span>اطلاعات پرداخت بیعانه سفارش #{orderCode}</span>
                    </div>

                    <div className="space-y-1.5 text-xs text-slate-300 leading-relaxed">
                      <div className="flex justify-between">
                        <span className="text-slate-400">مبلغ بیعانه پیش‌پرداخت (۸٪):</span>
                        <span className="font-bold text-amber-400 font-mono">{deposit.toLocaleString("fa-IR")} تومان</span>
                      </div>
                      <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-center text-sm font-bold text-white tracking-widest select-all">
                        ۶۰۳۷ - ۹۹۷۵ - ۴۳۲۱ - ۸۸۹۰
                      </div>
                      <div className="flex justify-between text-[11px]">
                        <span className="text-slate-400">به نام:</span>
                        <span className="font-bold text-slate-200">AiKala_bot هوشمند کالا</span>
                      </div>
                    </div>

                    <div className="pt-1 text-[11px] text-slate-300 font-medium">
                      📎 لطفاً پس از واریز، <b>تصویر فیش واریزی یا شماره پیگیری</b> را همینجا ارسال فرمایید:
                    </div>

                    {/* Inline Keyboard Buttons Exactly As Requested */}
                    <div className="pt-2 space-y-1.5">
                      <div className="grid grid-cols-2 gap-1.5">
                        <button
                          onClick={() => setSimStep("prompt_photo")}
                          className={`py-2 px-2 rounded-xl text-[11px] font-bold border transition flex items-center justify-center gap-1.5 cursor-pointer ${
                            simStep === "prompt_photo"
                              ? "bg-indigo-600 border-indigo-500 text-white shadow-sm"
                              : "bg-slate-950 hover:bg-slate-800 border-slate-700 text-slate-200"
                          }`}
                        >
                          <ImageIcon className="w-3.5 h-3.5 text-indigo-400" />
                          ارسال تصویر فیش
                        </button>
                        <button
                          onClick={() => setSimStep("prompt_text")}
                          className={`py-2 px-2 rounded-xl text-[11px] font-bold border transition flex items-center justify-center gap-1.5 cursor-pointer ${
                            simStep === "prompt_text"
                              ? "bg-indigo-600 border-indigo-500 text-white shadow-sm"
                              : "bg-slate-950 hover:bg-slate-800 border-slate-700 text-slate-200"
                          }`}
                        >
                          <Hash className="w-3.5 h-3.5 text-emerald-400" />
                          ارسال کد پیگیری (متن)
                        </button>
                      </div>

                      <button
                        onClick={() => setSimStep("cancelled")}
                        className={`w-full py-2 px-2 rounded-xl text-[11px] font-bold border transition flex items-center justify-center gap-1.5 cursor-pointer ${
                          simStep === "cancelled"
                            ? "bg-rose-600 border-rose-500 text-white"
                            : "bg-slate-950 hover:bg-rose-950/40 border-rose-800/60 text-rose-300"
                        }`}
                      >
                        <XCircle className="w-3.5 h-3.5 text-rose-400" />
                        ❌ انصراف از خرید
                      </button>
                    </div>
                  </div>

                  {/* Step Interactive Feedback */}
                  {simStep === "prompt_photo" && (
                    <div className="bg-indigo-950/40 border border-indigo-500/40 p-3 rounded-2xl text-indigo-200 space-y-2 self-start max-w-[90%] animate-in fade-in">
                      <div className="font-bold flex items-center gap-1.5 text-xs">
                        <ImageIcon className="w-3.5 h-3.5 text-indigo-300" />
                        <span>📸 شبیه‌سازی ارسال عکس فیش واریزی:</span>
                      </div>
                      <p className="text-[11px] text-slate-300">
                        در این حالت کاربر می‌تواند تصویر فیش خود را از گالری یا دوربین تلگرام ارسال کند:
                      </p>
                      <button
                        onClick={() => {
                          setSimUploadedReceipt("receipt_uploaded");
                          setSimStep("paid");
                        }}
                        className="py-1.5 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-[11px] font-bold cursor-pointer transition w-full"
                      >
                        ارسال تصویر تستی فیش بانکی 📸
                      </button>
                    </div>
                  )}

                  {simStep === "prompt_text" && (
                    <div className="bg-emerald-950/40 border border-emerald-500/40 p-3 rounded-2xl text-emerald-200 space-y-2 self-start max-w-[90%] animate-in fade-in">
                      <div className="font-bold flex items-center gap-1.5 text-xs">
                        <Hash className="w-3.5 h-3.5 text-emerald-300" />
                        <span>🔢 ارسال شماره پیگیری (متن):</span>
                      </div>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="مثلاً: 492019582"
                          value={simTrackingInput}
                          onChange={(e) => setSimTrackingInput(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-100 text-xs font-mono focus:outline-none"
                        />
                        <button
                          onClick={() => {
                            if (simTrackingInput.trim()) {
                              setSimStep("paid");
                            }
                          }}
                          className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold cursor-pointer shrink-0"
                        >
                          ثبت
                        </button>
                      </div>
                    </div>
                  )}

                  {simStep === "cancelled" && (
                    <div className="bg-rose-950/60 border border-rose-500/60 p-3 rounded-2xl text-rose-200 space-y-1.5 self-start max-w-[90%] animate-in fade-in">
                      <div className="font-bold flex items-center gap-1.5 text-xs text-rose-300">
                        <XCircle className="w-4 h-4 text-rose-400" />
                        <span>❌ سفارش با موفقیت لغو گردید.</span>
                      </div>
                      <p className="text-[11px] text-slate-300 leading-relaxed">
                        سشن کاربر پاکسازی شده و کیبورد منوی اصلی جایگزین گردید.
                      </p>
                    </div>
                  )}

                  {simStep === "paid" && (
                    <div className="bg-emerald-950/60 border border-emerald-500/60 p-3 rounded-2xl text-emerald-200 space-y-1.5 self-start max-w-[90%] animate-in fade-in">
                      <div className="font-bold flex items-center gap-1.5 text-xs text-emerald-300">
                        <Check className="w-4 h-4 text-emerald-400" />
                        <span>✅ فیش بیعانه با موفقیت دریافت شد!</span>
                      </div>
                      <p className="text-[11px] text-slate-300 leading-relaxed">
                        کد رهگیری: <b>#{orderCode}</b>
                        <br />
                        وضعیت در پنل حسابداری ثبت و پس از تایید اپراتور، فاکتور نهایی صادر می‌گردد.
                      </p>
                    </div>
                  )}
                </div>

                {/* Telegram Bottom Reply Keyboard Mockup */}
                <div className="p-2.5 bg-slate-900 border-t border-slate-800 space-y-1.5">
                  <div className="text-[10px] text-slate-400 text-center font-medium">کیبورد دکمه‌ای تلگرام در پایین صفحه:</div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      onClick={() => setSimStep("prompt_photo")}
                      className="py-2 px-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-[11px] font-bold border border-slate-700 transition cursor-pointer"
                    >
                      📸 ارسال عکس فیش بیعانه
                    </button>
                    <button
                      onClick={() => setSimStep("prompt_text")}
                      className="py-2 px-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-[11px] font-bold border border-slate-700 transition cursor-pointer"
                    >
                      🔢 ثبت شماره پیگیری
                    </button>
                  </div>
                  <button
                    onClick={() => setSimStep("cancelled")}
                    className="w-full py-2 px-2 bg-slate-950 hover:bg-rose-950/40 text-rose-400 rounded-xl text-[11px] font-bold border border-rose-900/60 transition cursor-pointer flex items-center justify-center gap-1"
                  >
                    <XCircle className="w-3.5 h-3.5 text-rose-500" />
                    ❌ انصراف از خرید
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 2: OPTION B RECEIPT PREVIEW ── */}
        {activeTab === "preview" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Control & Customization Sidebar */}
            <div className="lg:col-span-6 space-y-6">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Settings className="w-4 h-4 text-rose-400" />
                    <h3 className="font-bold text-sm text-white">تغییر وضعیت فاکتور و مشخصات کالا</h3>
                  </div>
                  <button
                    onClick={() => {
                      setOrderCode(Math.floor(1000 + Math.random() * 9000).toString());
                    }}
                    className="flex items-center gap-1 text-xs text-rose-400 hover:text-rose-300 cursor-pointer font-medium"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    کد سفارش جدید
                  </button>
                </div>

                {/* Status Switcher: Pre-Invoice vs Final */}
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-slate-400">مرحله صدور فاکتور:</label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setIsPreInvoice(true)}
                      className={`p-3 rounded-xl border text-right transition cursor-pointer flex flex-col gap-1 ${
                        isPreInvoice
                          ? "bg-amber-500/15 border-amber-500/50 text-amber-200"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      <span className="font-bold text-xs flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                        ۱. پیش‌فاکتور رسمی خرید
                      </span>
                      <span className="text-[11px] text-slate-400">
                        وضعیت بیعانه: <b className="text-amber-400">در انتظار واریز ⏳</b>
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setIsPreInvoice(false)}
                      className={`p-3 rounded-xl border text-right transition cursor-pointer flex flex-col gap-1 ${
                        !isPreInvoice
                          ? "bg-emerald-500/15 border-emerald-500/50 text-emerald-200"
                          : "bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700"
                      }`}
                    >
                      <span className="font-bold text-xs flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                        ۲. فاکتور فروش قطعی
                      </span>
                      <span className="text-[11px] text-slate-400">
                        وضعیت بیعانه: <b className="text-emerald-400">پرداخت و تایید شد ✅</b>
                      </span>
                    </button>
                  </div>
                </div>

                {/* Form Fields */}
                <div className="space-y-3.5 text-xs">
                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">عنوان کالا:</label>
                    <input
                      type="text"
                      value={productName}
                      onChange={(e) => setProductName(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-rose-500 transition"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">مبلغ کل کالا (تومان):</label>
                      <input
                        type="number"
                        value={productPrice}
                        onChange={(e) => setProductPrice(Number(e.target.value))}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-rose-500 font-mono transition"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">درصد بیعانه:</label>
                      <input
                        type="number"
                        value={depositPercent}
                        onChange={(e) => setDepositPercent(Number(e.target.value))}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-rose-500 font-mono transition"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">نام خریدار:</label>
                      <input
                        type="text"
                        value={customerName}
                        onChange={(e) => setCustomerName(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-rose-500 transition"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">شماره تماس خریدار:</label>
                      <input
                        type="text"
                        value={customerPhone}
                        onChange={(e) => setCustomerPhone(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-rose-500 font-mono transition"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">آدرس تحویل مقصد:</label>
                    <textarea
                      rows={2}
                      value={customerAddress}
                      onChange={(e) => setCustomerAddress(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-rose-500 transition"
                    />
                  </div>
                </div>

                {/* Financial Summary Box */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs">
                  <div className="flex justify-between text-slate-400">
                    <span>مبلغ کل کالا:</span>
                    <span className="font-bold text-slate-200">{productPrice.toLocaleString("fa-IR")} تومان</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>بیعانه پیش‌پرداخت ({depositPercent}٪):</span>
                    <span className="font-bold text-amber-400">{deposit.toLocaleString("fa-IR")} تومان</span>
                  </div>
                  <div className="flex justify-between border-t border-slate-800 pt-2 text-slate-300">
                    <span>مانده تسویه پس از تست در محل:</span>
                    <span className="font-black text-rose-400">{remaining.toLocaleString("fa-IR")} تومان</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Receipt Preview Component */}
            <div className="lg:col-span-6 flex justify-center">
              <OptionBReceipt
                data={receiptData}
                onPrint={() => window.print()}
              />
            </div>
          </div>
        )}

        {/* ── TAB 3: PYTHON CODE READY TO COPY ── */}
        {activeTab === "python_code" && (
          <div className="space-y-6">
            {/* Python bot.py complete flow */}
            <div className="space-y-3">
              <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-900 border border-slate-800">
                <div>
                  <h3 className="font-bold text-sm text-white">۱. کدهای کامل bot.py (رفع مشکل لغو سفارش + دکمه‌های بیعانه)</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    این کد را مستقیماً در <code className="text-rose-400 font-mono">bot.py</code> قرار دهید. تمام مراحل دارای لغو فوری هستند.
                  </p>
                </div>
                <button
                  onClick={() => handleCopy(pythonBotCompleteFlowCode, "bot_code")}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer shrink-0"
                >
                  {copiedKey === "bot_code" ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-300" />
                      کپی شد!
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      کپی کدهای bot.py
                    </>
                  )}
                </button>
              </div>

              <div className="relative rounded-2xl overflow-hidden border border-slate-800 bg-slate-950">
                <pre className="p-5 font-mono text-xs text-slate-300 overflow-x-auto max-h-[480px] leading-relaxed">
                  {pythonBotCompleteFlowCode}
                </pre>
              </div>
            </div>

            {/* Python Generator File */}
            <div className="space-y-3">
              <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-900 border border-slate-800">
                <div>
                  <h3 className="font-bold text-sm text-white">۲. فایل کامل invoice_generator.py (طراحی Option B Full HD)</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    شامل تولید تصویر با عرض ۱۲۰۰ پیکسل و تابع <code className="text-indigo-400 font-mono">build_invoice_data_from_order</code>
                  </p>
                </div>
                <button
                  onClick={() => handleCopy(pythonInvoiceGeneratorCode, "gen_code")}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer shrink-0"
                >
                  {copiedKey === "gen_code" ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-300" />
                      کپی شد!
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      کپی کد invoice_generator.py
                    </>
                  )}
                </button>
              </div>

              <div className="relative rounded-2xl overflow-hidden border border-slate-800 bg-slate-950">
                <pre className="p-5 font-mono text-xs text-slate-300 overflow-x-auto max-h-[480px] leading-relaxed">
                  {pythonInvoiceGeneratorCode}
                </pre>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 4: TROUBLESHOOTING GUIDE ── */}
        {activeTab === "troubleshooting" && (
          <div className="space-y-6">
            <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-200">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center shrink-0 text-rose-400">
                  <AlertCircle className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-rose-100 mb-1">
                    علت دقیق عدم کارکرد دکمه «لغو سفارش» حین ثبت مشخصات چیست؟
                  </h2>
                  <p className="text-sm text-rose-200/80 leading-relaxed">
                    در فریم‌ورک پایتون تلگرام بوت (ConversationHandler)، زمانی که کاربر در مرحله نام، تلفن یا آدرس است، هندلر مربوطه هر متنی را به عنوان مقدار فیلد می‌خواند. اگر کاربر دکمه «❌ لغو سفارش» را می‌زد، ربات عبارت «❌ لغو سفارش» را به عنوان نام یا آدرس ذخیره می‌کرد و به مرحله بعد می‌رفت یا در اعتبارسنجی تلفن ارور می‌داد!
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-2.5">
                <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                  <ShieldCheck className="w-4 h-4" />
                  <span>۱. شرط is_cancel_command</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  در ابتدای توابع <code className="text-slate-200">order_name</code>، <code className="text-slate-200">order_phone</code>، <code className="text-slate-200">order_address</code> و <code className="text-slate-200">order_receipt</code> بررسی می‌شود؛ در صورت کلیک بر لغو، فوراً خروج ثبت می‌گردد.
                </p>
              </div>

              <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-2.5">
                <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm">
                  <Terminal className="w-4 h-4" />
                  <span>۲. تکمیل بخش Fallbacks</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  الگوی Regex عبارت‌های <code className="text-slate-200">❌ انصراف از خرید</code> و <code className="text-slate-200">❌ لغو سفارش</code> به لیست Fallbacks در ConversationHandler متصل گردید.
                </p>
              </div>

              <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-2.5">
                <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
                  <Check className="w-4 h-4" />
                  <span>۳. پاکسازی دیتای موقت و کیبورد</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  با متد <code className="text-slate-200">ReplyKeyboardRemove()</code> و پاکسازی کلیدهای <code className="text-slate-200">context.user_data</code>، کاربر مجدداً به منوی پاک و اصلی برمی‌گردد.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 5: CHANNEL MONITOR & MULTI-SOURCE CATCHUP ── */}
        {activeTab === "channels" && <ChannelMonitorTab />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 px-6 text-center text-xs text-slate-400">
        فروشگاه لوازم خانگی آی‌کالا • پیاده‌سازی استاندارد Option B، فیش حرارتی ۸۰mm و ربات تلگرام
      </footer>
    </div>
  );
}
