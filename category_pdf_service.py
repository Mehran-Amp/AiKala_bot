"""
Universal Category PDF Price List Generator for AiKala Shop (@AiKala_bot)
==========================================================================
Generates high-precision, ISO 32000-1 / PDF 1.4 tabular price lists for:
- tv (Televisions)
- conditioner (Air Conditioners / کولر گازی)
- refrigerator (Refrigerators / یخچال فریزر)
- washing_machine (Washing Machines / ماشین لباسشویی)
- dishwasher (Dishwashers / ماشین ظرفشویی)
- small_appliances (Small Electric Appliances / لوازم ریز برقی)
- aeg (AEG & Miele Products / محصولات آاگ و میله)
- laptop (Laptops / لپ‌تاپ)
- audio (Audio Systems & PartyBoxes / سیستم صوتی و اسپیکر)

Features:
- Pure Python byte-accurate PDF generator with 0 external dependencies.
- Standard vector Helvetica / Helvetica-Bold Type 1 fonts.
- Grouped by brand and sorted by price descending.
- All prices strictly formatted with 'Toman' (e.g. 55,000,000 Toman).
- Deeply resilient against missing fields.
"""
import time


import os
import io
import re
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────
# Text & Digit Helpers
# ─────────────────────────────────────────────────────────────

def to_eng_digits(text: Any) -> str:
    """Converts Persian and Arabic digits to standard English digits."""
    if text is None:
        return ""
    mapping = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    return "".join(mapping.get(ch, ch) for ch in str(text))


BRAND_EN_MAP = {
    # TVs & Home Appliances
    "ال جی": "LG",
    "ال‌جی": "LG",
    "الجی": "LG",
    "سامسونگ": "SAMSUNG",
    "سونی": "SONY",
    "بوش": "BOSCH",
    "هایسنس": "HISENSE",
    "گری": "GREE",
    "کریر": "CARRIER",
    "جنرال شکار": "GENERAL SHEKAR",
    "جنرال گلد": "GENERAL GOLD",
    "جنرال برلین": "GENERAL BERLIN",
    "اجنرال": "OGENERAL",
    "ایوولی": "EVVOLI",
    "یونیوا": "UNEVA",
    "گیبسون": "GIBSON",
    "توشیبا": "TOSHIBA",
    "شیائومی": "XIAOMI",
    "فیلیپس": "PHILIPS",
    "هیتاچی": "HITACHI",
    "گرینه": "GORENJE",
    "دوو": "DAEWOO",
    "آاگ": "AEG",
    "میله": "MIELE",
    "پاناسونیک": "PANASONIC",
    "کنوود": "KENWOOD",
    "براون": "BRAUN",
    "تفال": "TEFAL",
    "دلونگی": "DELONGHI",
    "نینجا": "NINJA",
    "کوکماز": "KORKMAZ",
    "سنکور": "SENCOR",
    "کارچر": "KARCHER",
    "کرشر": "KARCHER",
    "بلک اند دکر": "BLACK&DECKER",
    # Laptops
    "اچ پی": "HP",
    "لنوو": "LENOVO",
    "دل": "DELL",
    "ایسوس": "ASUS",
    "اپل": "APPLE",
    "ایسر": "ACER",
    "مایکروسافت": "MICROSOFT",
    "ام اس ای": "MSI",
    "ام‌اس‌ای": "MSI",
}


def normalize_brand(raw_brand: Any, raw_name: str = "") -> str:
    """Returns normalized English brand name."""
    b_str = str(raw_brand or "").strip()
    n_str = str(raw_name or "").strip().lower()

    for fa_k, en_v in BRAND_EN_MAP.items():
        if fa_k in b_str or fa_k.lower() in n_str:
            return en_v

    clean = b_str.encode("ascii", "ignore").decode("ascii").strip().upper()
    return clean if clean and len(clean) > 1 else "OTHER"


def format_price_toman(price_val: Any) -> str:
    """Formats price with comma separators and 'Toman' suffix."""
    if not price_val:
        return "Inquire"
    try:
        clean_str = re.sub(r"[^\d]", "", to_eng_digits(str(price_val)))
        if not clean_str:
            return "Inquire"
        val = int(clean_str)
        if 1000 <= val <= 900000:
            val = val * 1000
        return f"{val:,} Toman"
    except Exception:
        return "Inquire"


def normalize_country(val: Any) -> str:
    """Translates assembly/origin country to English."""
    s = str(val or "").strip()
    if not s or s == "-":
        return "Original"
    mapping = {
        "ویتنام": "Vietnam",
        "اندونزی": "Indonesia",
        "مالزی": "Malaysia",
        "مصر": "Egypt",
        "اسلواکی": "Slovakia",
        "مجارستان": "Hungary",
        "لهستان": "Poland",
        "مکزیک": "Mexico",
        "چین": "China",
        "کره": "Korea",
        "تایلند": "Thailand",
        "ترکیه": "Turkey",
        "آلمان": "Germany",
        "ایتالیا": "Italy",
    }
    parts = []
    for k, v in mapping.items():
        if k in s:
            parts.append(v)
    if parts:
        return "/".join(parts[:2])
    clean = s.encode("ascii", "ignore").decode("ascii").strip()
    return clean if clean else "Original"


def clean_spec_text(txt: Any, default: str = "-") -> str:
    """Ascii sanitizes and strips Persian from specification strings."""
    if not txt:
        return default
    s = to_eng_digits(str(txt)).strip()
    # Remove common Persian noise
    s = re.sub(r'(?:مدل|اینچ|کیلو|فوت|هزار|لیتر|وات|بار|سبد|نفره|درب)', '', s)
    s = s.encode("ascii", "ignore").decode("ascii").strip()
    s = re.sub(r'\s+', ' ', s)
    return s if s else default


# ─────────────────────────────────────────────────────────────
# Pure PDF 1.4 Engine (ISO 32000-1 Compliant)
# ─────────────────────────────────────────────────────────────

class _PdfBuilder:
    """Byte-accurate PDF 1.4 document builder with zero external dependencies."""
    def __init__(self):
        self.objects: List[bytes] = []

    def add_object(self, content_bytes: bytes) -> int:
        self.objects.append(content_bytes)
        return len(self.objects)

    def write(self) -> bytes:
        buf = io.BytesIO()
        buf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        offsets = [0]
        for i, obj in enumerate(self.objects):
            obj_num = i + 1
            offsets.append(buf.tell())
            buf.write(f"{obj_num} 0 obj\n".encode("ascii"))
            buf.write(obj)
            buf.write(b"\nendobj\n")

        xref_offset = buf.tell()
        total_objs = len(self.objects) + 1
        buf.write(f"xref\n0 {total_objs}\n".encode("ascii"))
        buf.write(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            buf.write(f"{off:010d} 00000 n \n".encode("ascii"))

        buf.write(f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\n".encode("ascii"))
        buf.write(f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
        return buf.getvalue()


def _escape_pdf(s: Any) -> str:
    """Sanitizes text for PDF literal strings (...)."""
    if not s:
        return ""
    st = str(s).strip()
    st = st.replace("\\", "/").replace("(", "[").replace(")", "]")
    return st.encode("ascii", "ignore").decode("ascii")


def _fit_text(text: str, max_chars: int) -> str:
    """Trims and appends dots if text exceeds max characters."""
    s = str(text).strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars - 2] + ".."


# ─────────────────────────────────────────────────────────────
# Category Schema & Extraction Configurations
# ─────────────────────────────────────────────────────────────

CATEGORY_CONFIGS: Dict[str, Dict[str, Any]] = {
    "tv": {
        "title": "TELEVISIONS (TV)",
        "persian_title": "تلویزیون‌های اصلی",
        "guarantee": "Guarantee: 100% Original Direct Import with Full Hardware Warranty",
        "cols": [
            ("#", 22, "C", 4),
            ("Model & Screen Size", 155, "L", 28),
            ("Brand", 60, "C", 11),
            ("Display & Panel", 80, "L", 16),
            ("Assembly", 75, "L", 15),
            ("PID", 50, "C", 8),
            ("Price (Toman)", 113, "R", 20),
        ],
        "extract": lambda p, b: [
            _extract_tv_model(p, b),
            b,
            _extract_tv_panel(p),
            normalize_country(p.get("assembly")),
            str(p.get("product_id") or p.get("id") or ""),
            format_price_toman(p.get("price")),
        ]
    },
    "conditioner": {
        "title": "AIR CONDITIONERS (SPLIT)",
        "persian_title": "کولرهای گازی اصلی و اسپلیت",
        "guarantee": "Guarantee: 100% Original Heavy Duty Inverter with Installation Guarantee",
        "cols": [
            ("#", 22, "C", 4),
            ("Model & Series", 160, "L", 28),
            ("Brand", 70, "C", 12),
            ("Capacity BTU", 75, "C", 14),
            ("Motor & Type", 65, "C", 12),
            ("PID", 50, "C", 8),
            ("Price (Toman)", 113, "R", 20),
        ],
        "extract": lambda p, b: [
            _extract_ac_model(p, b),
            b,
            _extract_ac_capacity(p),
            _extract_ac_type(p),
            str(p.get("product_id") or p.get("id") or ""),
            format_price_toman(p.get("price")),
        ]
    },
    "refrigerator": {
        "title": "REFRIGERATORS & FREEZERS",
        "persian_title": "یخچال و فریزرهای ساید و دوقلو",
        "guarantee": "Guarantee: 100% Original Direct Import with 5-Year Compressor Warranty",
        "cols": [
            ("#", 22, "C", 4),
            ("Model & Series", 155, "L", 28),
            ("Brand", 65, "C", 12),
            ("Design / Plan", 75, "L", 15),
            ("Capacity", 75, "L", 15),
            ("PID", 50, "C", 8),
            ("Price (Toman)", 113, "R", 20),
        ],
        "extract": lambda p, b: [
            _extract_fridge_model(p, b),
            b,
            _extract_fridge_plan(p),
            _extract_fridge_capacity(p),
            str(p.get("product_id") or p.get("id") or ""),
            format_price_toman(p.get("price")),
        ]
    },
    "washing_machine": {
        "title": "WASHING MACHINES",
        "persian_title": "ماشین‌های لباسشویی اصلی",
        "guarantee": "Guarantee: 100% Original Direct Drive Motor with 10-Year Motor Warranty",
        "cols": [
            ("#", 22, "C", 4),
            ("Model & Series", 160, "L", 28),
            ("Brand", 65, "C", 12),
            ("Capacity (Kg)", 70, "C", 13),
            ("Assembly", 75, "L", 15),
            ("PID", 50, "C", 8),
            ("Price (Toman)", 113, "R", 20),
        ],
        "extract": lambda p, b: [
            _extract_washer_model(p, b),
            b,
            _extract_washer_capacity(p),
            normalize_country(p.get("assembly")),
            str(p.get("product_id") or p.get("id") or ""),
            format_price_toman(p.get("price")),
        ]
    },
    "dishwasher": {
        "title": "DISHWASHERS",
        "persian_title": "ماشین‌های ظرفشویی اورجینال",
        "guarantee": "Guarantee: 100% Original Low Consumption with 18-Month Official Warranty",
        "cols": [
            ("#", 22, "C", 4),
            ("Model & Series", 165, "L", 29),
            ("Brand", 65, "C", 12),
            ("Baskets / Racks", 70, "C", 13),
            ("Assembly", 70, "L", 14),
            ("PID", 50, "C", 8),
            ("Price (Toman)", 113, "R", 20),
        ],
        "extract": lambda p, b: [
            _extract_dishwasher_model(p, b),
            b,
            _extract_dishwasher_baskets(p),
            normalize_country(p.get("assembly")),
            str(p.get("product_id") or p.get("id") or ""),
            format_price_toman(p.get("price")),
        ]
    },
    "small_appliances": {
        "title": "SMALL HOME APPLIANCES",
        "persian_title": "لوازم ریز برقی و آشپزخانه",
        "guarantee": "Guarantee: 100% Authentic European & Japanese Import with Replacement Guarantee",
        "cols": [
            ("#", 22, "C", 4),
            ("Product Name & Model", 185, "L", 34),
            ("Brand", 70, "C", 13),
            ("Subcategory", 115, "L", 20),
            ("PID", 50, "C", 8),
            ("Price (Toman)", 113, "R", 20),
        ],
        "extract": lambda p, b: [
            _extract_small_appliance_model(p, b),
            b,
            _extract_subcategory_en(p.get("subcategory") or p.get("category_name")),
            str(p.get("product_id") or p.get("id") or ""),
            format_price_toman(p.get("price")),
        ]
    },
    "aeg": {
        "title": "AEG & MIELE PREMIUM PRODUCTS",
        "persian_title": "محصولات پریمیوم آاگ و میله",
        "guarantee": "Guarantee: 100% Original German & European Luxury Appliances",
        "cols": [
            ("#", 22, "C", 4),
            ("Product Title & Model", 185, "L", 34),
            ("Brand", 70, "C", 13),
            ("Category", 115, "L", 20),
            ("PID", 50, "C", 8),
            ("Price (Toman)", 113, "R", 20),
        ],
        "extract": lambda p, b: [
            _extract_small_appliance_model(p, b),
            b,
            _extract_subcategory_en(p.get("subcategory") or p.get("category_name")),
            str(p.get("product_id") or p.get("id") or ""),
            format_price_toman(p.get("price")),
        ]
    },
    "audio": {
        "title": "PREMIUM AUDIO SYSTEMS & SPEAKERS",
        "persian_title": "سیستم‌های صوتی، اسپیکر و ساندبار اورجینال",
        "guarantee": "Guarantee: 100% Original High-Fidelity Audio with Official Sound Test Guarantee",
        "cols": [
            ("#", 22, "C", 4),
            ("Model & Description", 185, "L", 34),
            ("Brand", 70, "C", 13),
            ("Type / Specifications", 115, "L", 20),
            ("Code", 50, "C", 8),
            ("Price (Toman)", 113, "R", 20),
        ],
        "extract": lambda p, b: [
            _extract_audio_model(p, b),
            b,
            _extract_audio_type(p),
            str(p.get("code") or p.get("product_id") or ""),
            format_price_toman(p.get("price")),
        ]
    },
    "laptop": {
        "title": "OFFICIAL LAPTOPS & ULTRABOOKS",
        "persian_title": "لپ‌تاپ‌های استوک و اپن‌باکس",
        "guarantee": "Guarantee: 7-Day Full Hardware Test & Replacement Guarantee on all models",
        "cols": [
            ("#", 22, "C", 4),
            ("Model & Code", 135, "L", 28),
            ("CPU", 75, "L", 16),
            ("RAM", 45, "L", 11),
            ("Storage", 60, "L", 13),
            ("GPU", 75, "L", 16),
            ("Display", 50, "L", 11),
            ("Grade", 30, "C", 7),
            ("Price (Toman)", 63, "R", 14),
        ],
        "extract": None  # Handled via custom laptop extractor
    }
}


# ─────────────────────────────────────────────────────────────
# Category-Specific Model Cleaners
# ─────────────────────────────────────────────────────────────

def _extract_tv_model(p: Dict[str, Any], brand: str) -> str:
    m_code = to_eng_digits(str(p.get("model_number") or "")).strip()
    n_raw = to_eng_digits(str(p.get("name") or "")).strip()
    size_str = ""
    m_size = re.search(r'(\b[3-9]\d\b)\s*(?:inch|اینچ|")', n_raw, re.I)
    if m_size:
        size_str = f"{m_size.group(1)}\""
    elif re.match(r'^[3-9]\d', m_code):
        size_str = f"{m_code[:2]}\""

    clean_code = m_code.encode("ascii", "ignore").decode("ascii").strip()
    if not clean_code or len(clean_code) < 2:
        codes = re.findall(r'[A-Za-z0-9]{3,12}', n_raw)
        filtered = [c for c in codes if any(ch.isalpha() for ch in c) and any(ch.isdigit() for ch in c)]
        clean_code = filtered[0].upper() if filtered else ""

    if size_str and clean_code:
        return clean_code if clean_code.startswith(size_str.replace('"', '')) else f"{size_str} {clean_code}"
    return clean_code or size_str or f"{brand} Smart TV"


def _extract_tv_panel(p: Dict[str, Any]) -> str:
    r_str = str(p.get("resolution") or "").strip().upper()
    p_str = str(p.get("panel") or "").strip().upper()
    r_clean = "4K" if "4K" in r_str else ("FHD" if "FHD" in r_str else ("HD" if "HD" in r_str else ""))
    for p_c in ["QD-OLED", "WOLED", "OLED", "QLED", "MINI-LED", "ADS", "IPS", "VA"]:
        if p_c in p_str:
            return f"{r_clean} {p_c}".strip()
    return f"{r_clean} Smart".strip() if r_clean else "4K Smart"


def _extract_ac_model(p: Dict[str, Any], brand: str) -> str:
    n_raw = to_eng_digits(str(p.get("name") or p.get("model_number") or "")).strip()
    codes = re.findall(r'[A-Za-z0-9\-]{4,14}', n_raw)
    valid_codes = [c for c in codes if any(ch.isdigit() for ch in c) and c.upper() != "12000" and c.upper() != "18000" and c.upper() != "24000" and c.upper() != "30000"]
    code_str = valid_codes[0].upper() if valid_codes else ""

    inv = "Inverter" if any(k in n_raw for k in ["اینورتر", "inverter", "پلار"]) else ""
    cap = p.get("capacity_btu") or ""
    cap_str = f"{cap} BTU" if cap else ""

    parts = [p for p in [code_str, inv, cap_str] if p]
    if parts:
        return " - ".join(parts)
    clean = n_raw.encode("ascii", "ignore").decode("ascii").strip()
    return clean if clean else f"{brand} Split AC"


def _extract_ac_capacity(p: Dict[str, Any]) -> str:
    c = str(p.get("capacity_btu") or "").strip()
    if c:
        return f"{c} BTU"
    n = to_eng_digits(str(p.get("name") or ""))
    m = re.search(r'\b(9000|12000|18000|24000|30000|36000)\b', n)
    if m:
        return f"{m.group(1)} BTU"
    return "12K-30K"


def _extract_ac_type(p: Dict[str, Any]) -> str:
    t = str(p.get("ac_type") or p.get("specs", {}).get("نوع موتور") or "").strip()
    n = str(p.get("name") or "").lower()
    if "اینورتر" in t or "اینورتر" in n or "inverter" in n:
        return "T3 Inverter"
    if "t3" in n or "پیستونی" in t:
        return "T3 Rotary"
    return "Rotary Inverter"


def _extract_fridge_model(p: Dict[str, Any], brand: str) -> str:
    m = to_eng_digits(str(p.get("model_number") or "")).strip()
    n = to_eng_digits(str(p.get("name") or "")).strip()
    clean_m = m.encode("ascii", "ignore").decode("ascii").strip()
    if clean_m and len(clean_m) > 1:
        return clean_m
    codes = re.findall(r'[A-Za-z0-9\-]{3,12}', n)
    filtered = [c for c in codes if any(ch.isalpha() for ch in c) and any(ch.isdigit() for ch in c)]
    if filtered:
        return filtered[0].upper()
    return f"{brand} Refrigerator"


def _extract_fridge_plan(p: Dict[str, Any]) -> str:
    plan = str(p.get("plan") or "").strip()
    mapping = {
        "ساید": "Side by Side",
        "دوقلو": "Twin / Two-Door",
        "بالا": "Top Freezer",
        "پایین": "Bottom Freezer",
        "فرانسوی": "French Door",
        "هتلی": "Compact Hotel",
        "تک درب": "Single Door",
    }
    for k, v in mapping.items():
        if k in plan:
            return v
    doors = p.get("num_doors")
    if doors:
        return f"{doors}-Door"
    return "Side by Side"


def _extract_fridge_capacity(p: Dict[str, Any]) -> str:
    c = str(p.get("capacity_foot") or "").strip()
    if c:
        return f"{c} Foot"
    return "Standard"


def _extract_washer_model(p: Dict[str, Any], brand: str) -> str:
    m = to_eng_digits(str(p.get("model_number") or "")).strip()
    n = to_eng_digits(str(p.get("name") or "")).strip()
    clean_m = m.encode("ascii", "ignore").decode("ascii").strip()
    if clean_m and len(clean_m) > 1:
        return clean_m
    codes = re.findall(r'[A-Za-z0-9\-]{3,12}', n)
    filtered = [c for c in codes if any(ch.isalpha() for ch in c)]
    if filtered:
        return filtered[0].upper()
    return f"{brand} Front Load"


def _extract_washer_capacity(p: Dict[str, Any]) -> str:
    c = str(p.get("capacity_kg") or "").strip()
    if c:
        return f"{c} Kg"
    n = to_eng_digits(str(p.get("name") or ""))
    m = re.search(r'(\b[6-9]\b|\b1[0-5]\b)\s*(?:کیلو|kg)', n, re.I)
    if m:
        return f"{m.group(1)} Kg"
    return "8-9 Kg"


def _extract_dishwasher_model(p: Dict[str, Any], brand: str) -> str:
    m = to_eng_digits(str(p.get("model_number") or "")).strip()
    n = to_eng_digits(str(p.get("name") or "")).strip()
    clean_m = m.encode("ascii", "ignore").decode("ascii").strip()
    if clean_m and len(clean_m) > 1:
        return clean_m
    codes = re.findall(r'[A-Za-z0-9\-]{3,12}', n)
    filtered = [c for c in codes if any(ch.isdigit() for ch in c)]
    if filtered:
        return filtered[0].upper()
    return f"{brand} Dishwasher"


def _extract_dishwasher_baskets(p: Dict[str, Any]) -> str:
    b = str(p.get("baskets") or "").strip()
    if "3" in b or "سه" in b:
        return "3 Baskets"
    if "2" in b or "دو" in b:
        return "2 Baskets"
    return "3 Baskets (Full)"


def _extract_small_appliance_model(p: Dict[str, Any], brand: str) -> str:
    m = to_eng_digits(str(p.get("model_number") or "")).strip()
    n = to_eng_digits(str(p.get("name") or "")).strip()
    clean_m = m.encode("ascii", "ignore").decode("ascii").strip()
    if clean_m and len(clean_m) > 3 and not any(k in clean_m.lower() for k in ["جارو", "سرخ", "قهوه", "اتو"]):
        return clean_m
    codes = re.findall(r'[A-Za-z0-9\-]{3,15}', n)
    filtered = [c for c in codes if any(ch.isalpha() for ch in c) and any(ch.isdigit() for ch in c)]
    if filtered:
        return f"{filtered[0].upper()}"
    clean_n = n.encode("ascii", "ignore").decode("ascii").strip()
    return clean_n if clean_n else f"{brand} Appliance"


def _extract_subcategory_en(subcat_raw: Any) -> str:
    s = str(subcat_raw or "").strip()
    mapping = {
        "جاروبرقی": "Vacuum Cleaner",
        "سرخ کن": "Air Fryer",
        "قهوه": "Coffee Maker",
        "اسپرسو": "Espresso Machine",
        "آسیاب": "Grinder",
        "مخلوط کن": "Blender",
        "غذاساز": "Food Processor",
        "اتو": "Steam Iron",
        "ساندویچ": "Sandwich Maker",
        "مایکروویو": "Microwave Oven",
        "سولاردام": "SolarDOM",
        "خردکن": "Chopper",
        "آبمیوه": "Juicer",
        "گوشت": "Meat Grinder",
        "کتری": "Kettle",
        "چای": "Tea Maker",
        "توستر": "Toaster",
        "پلوپز": "Rice Cooker",
    }
    for k, v in mapping.items():
        if k in s:
            return v
    clean = s.encode("ascii", "ignore").decode("ascii").strip()
    return clean if clean else "Home Appliance"


def _extract_audio_model(p: Dict[str, Any], brand: str) -> str:
    m = str(p.get("model") or "").strip()
    if m:
        return m
    raw = str(p.get("name") or "").strip()
    raw = re.sub(r'\[.*?\]', '', raw).strip()
    raw = re.sub(r'^(سیستم صوتی|اسپیکر|ساندبار)\s+(جی بی ال|هارمن کاردن|سونی)?\s*(مدل)?\s*', '', raw, flags=re.I).strip()
    return raw or f"{brand} Audio System"


def _extract_audio_type(p: Dict[str, Any]) -> str:
    specs = p.get("specs") or {}
    power = str(specs.get("توان خروجی (Output Power)") or "").strip()
    sub = str(p.get("subcategory") or "").strip()
    if "پارتی" in sub or "PartyBox" in sub:
        t = "PartyBox"
    elif "ساندبار" in sub or "Soundbar" in sub:
        t = "Soundbar"
    elif "پرتابل" in sub or "Portable" in sub:
        t = "Portable"
    elif "خانگی" in sub or "Home" in sub:
        t = "Home Audio"
    else:
        t = "Audio System"
    if power:
        p_short = power.replace(" RMS", "").replace("~", "").strip()
        return f"{t} ({p_short})"
    return t


# ─────────────────────────────────────────────────────────────
# Inventory Loader by Category Key
# ─────────────────────────────────────────────────────────────

def load_category_products(category_key: str) -> List[Dict[str, Any]]:
    """Loads all products belonging to a given category_key."""
    all_prods = []
    try:
        from search_engine import JSON_PRODUCTS, load_json_products
        if not JSON_PRODUCTS:
            load_json_products()
        all_prods = JSON_PRODUCTS
    except Exception as e:
        logger.warning(f"Could not load search_engine products: {e}")

    if not all_prods and os.path.exists("catalog_products.json"):
        try:
            with open("catalog_products.json", "r", encoding="utf-8") as f:
                all_prods = json.load(f)
        except Exception:
            all_prods = []

    matched = []
    seen_ids = set()

    for p in all_prods:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("product_id") or p.get("id") or "").strip()
        if not pid or pid in seen_ids:
            continue

        cat_k = str(p.get("category_key") or "").strip().lower()
        cat_name = str(p.get("category_name") or p.get("category") or "").strip()
        name = str(p.get("name") or "").strip()

        is_match = False
        if category_key == "tv":
            is_match = cat_k == "tv" or "تلویزیون" in cat_name or "تلویزیون" in name or "tv" in name.lower()
        elif category_key == "conditioner":
            is_match = cat_k == "conditioner" or "کولر" in cat_name or "اسپلیت" in cat_name or "کولر" in name
        elif category_key == "refrigerator":
            is_match = cat_k == "refrigerator" or "یخچال" in cat_name or "فریزر" in cat_name or "یخچال" in name
        elif category_key == "washing_machine":
            is_match = cat_k == "washing_machine" or "لباسشویی" in cat_name or "لباسشویی" in name
        elif category_key == "dishwasher":
            is_match = cat_k == "dishwasher" or "ظرفشویی" in cat_name or "ظرفشویی" in name
        elif category_key == "small_appliances":
            is_match = cat_k == "small_appliances" or "لوازم ریز" in cat_name or "ریز برقی" in cat_name
        elif category_key == "aeg":
            is_match = cat_k == "aeg" or "آاگ" in cat_name or "آاگ" in name or "aeg" in name.lower()
        elif category_key == "laptop":
            is_match = cat_k == "laptop" or "لپ‌تاپ" in cat_name or "لپتاپ" in cat_name or "laptop" in cat_name.lower()
        elif category_key == "audio":
            is_match = cat_k == "audio" or "صوتی" in cat_name or "اسپیکر" in cat_name or "ساندبار" in cat_name or "پارتی" in cat_name or "audio" in name.lower() or "speaker" in name.lower()
        else:
            is_match = cat_k == category_key

        if is_match:
            seen_ids.add(pid)
            matched.append(p)

    return matched


# ─────────────────────────────────────────────────────────────
# Universal Tabular PDF Generator
# ─────────────────────────────────────────────────────────────

def generate_category_pdf(category_key: str, output_path: Optional[str] = None) -> str:
    """
    Generates a crystal-clear, professional tabular PDF for ANY category.
    - Uses pure Python PDF 1.4 ISO 32000-1 engine.
    - Zero external dependencies or binary calls.
    - Formats all prices with Toman.
    - Returns absolute file path.
    """
    if category_key == "laptop":
        try:
            from laptop_pdf_service import generate_laptops_price_list_pdf
            default_out = "AiKala_Laptops_PriceList.pdf" if not output_path else output_path
            return generate_laptops_price_list_pdf(default_out)
        except Exception as e:
            logger.warning(f"Fallback laptop generator called: {e}")

    cfg = CATEGORY_CONFIGS.get(category_key, CATEGORY_CONFIGS["tv"])
    items = load_category_products(category_key)
    total_items = len(items)

    if not output_path:
        output_path = f"AiKala_{category_key.capitalize()}_PriceList.pdf"

    table_x = 20
    cols = cfg["cols"]
    total_w = sum(w for _, w, _, _ in cols)  # 555 pt
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Group items by brand
    brands_map: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        raw_b = item.get("brand")
        b = normalize_brand(raw_b, item.get("name", ""))
        brands_map.setdefault(b, []).append(item)

    # Sort inside each brand by price descending
    for b_name in brands_map:
        def get_p(it):
            try:
                return float(it.get("price") or 0)
            except Exception:
                return 0
        brands_map[b_name].sort(key=get_p, reverse=True)

    # Priority sorting of brands
    priority_order = [
        "SONY", "LG", "SAMSUNG", "BOSCH", "GREE", "CARRIER",
        "GENERAL SHEKAR", "GENERAL GOLD", "OGENERAL", "HISENSE",
        "HITACHI", "TOSHIBA", "PHILIPS", "AEG", "MIELE", "DAEWOO", "OTHER"
    ]
    sorted_brands = sorted(
        brands_map.keys(),
        key=lambda x: (priority_order.index(x) if x in priority_order else 99, x)
    )

    # ─────────────────────────────────────────────────────────────
    # Multi-page Layout Planner
    # ─────────────────────────────────────────────────────────────
    pages_ops: List[List[Any]] = []
    current_page_ops: List[Any] = []
    cur_y = 745

    def start_new_page():
        nonlocal cur_y, current_page_ops
        if current_page_ops:
            pages_ops.append(current_page_ops)
        current_page_ops = []
        cur_y = 745

    start_new_page()
    overall_item_counter = 0

    if not items:
        current_page_ops.append(("empty_notice", 650))
    else:
        for brand_name in sorted_brands:
            brand_items = brands_map[brand_name]

            if cur_y < 120:
                start_new_page()

            b_title = f"{brand_name} {cfg['title']} ({len(brand_items)} Models In Stock)"
            current_page_ops.append(("brand_bar", cur_y, b_title))
            cur_y -= 22

            current_page_ops.append(("table_header", cur_y))
            cur_y -= 20

            for i, item in enumerate(brand_items):
                overall_item_counter += 1

                if cur_y < 65:
                    start_new_page()
                    current_page_ops.append(("brand_bar", cur_y, f"{brand_name} {cfg['title']} (Continued)"))
                    cur_y -= 22
                    current_page_ops.append(("table_header", cur_y))
                    cur_y -= 20

                current_page_ops.append(("row", cur_y, overall_item_counter, item, i % 2 == 0, brand_name))
                cur_y -= 22

            cur_y -= 12

    if current_page_ops:
        pages_ops.append(current_page_ops)

    total_pages = len(pages_ops)

    # ─────────────────────────────────────────────────────────────
    # Generate Page Streams
    # ─────────────────────────────────────────────────────────────
    pages_streams: List[bytes] = []

    for p_idx, p_ops in enumerate(pages_ops):
        st = io.BytesIO()

        # Top Page Banner
        st.write(b"0.06 0.09 0.16 rg 20 808 555 22 re f\n")
        banner_title = f"AiKala - Official {cfg['title']} Price List & Inventory"
        st.write(f"BT /F1 10.5 Tf 1 1 1 rg 28 815 Td ({_escape_pdf(banner_title)}) Tj ET\n".encode("ascii"))

        # Subtitle Info Bar
        info_line = f"Date: {date_str} | Total Stock: {total_items} Models | Order & Support: 09195859434 | Telegram: @AiKala_bot"
        st.write(f"BT /F2 8 Tf 0.3 0.35 0.45 rg 20 794 Td ({_escape_pdf(info_line)}) Tj ET\n".encode("ascii"))

        # Guarantee Bar
        st.write(f"BT /F1 8 Tf 0.05 0.5 0.25 rg 20 782 Td ({_escape_pdf(cfg['guarantee'])}) Tj ET\n".encode("ascii"))
        st.write(b"0.85 0.88 0.92 RG 0.5 w 20 774 m 575 774 l S\n")

        for op_type, *args in p_ops:
            if op_type == "empty_notice":
                st.write(b"BT /F1 11 Tf 0.3 0.35 0.45 rg 180 650 Td (Product inventory is currently being updated.) Tj ET\n")
                st.write(b"BT /F2 9 Tf 0.1 0.2 0.35 rg 195 630 Td (For live pricing and orders, contact: 09195859434) Tj ET\n")

            elif op_type == "brand_bar":
                y_pos, b_title = args
                st.write(f"0.12 0.23 0.54 rg {table_x} {y_pos} {total_w} 20 re f\n".encode("ascii"))
                st.write(f"0.12 0.23 0.54 RG 0.5 w {table_x} {y_pos} {total_w} 20 re S\n".encode("ascii"))
                st.write(f"BT /F1 8.5 Tf 1 1 1 rg {table_x + 8:.1f} {y_pos + 6:.1f} Td ({_escape_pdf(b_title)}) Tj ET\n".encode("ascii"))

            elif op_type == "table_header":
                y_pos = args[0]
                st.write(f"0.09 0.15 0.24 rg {table_x} {y_pos} {total_w} 18 re f\n".encode("ascii"))
                st.write(f"0.09 0.15 0.24 RG 0.5 w {table_x} {y_pos} {total_w} 18 re S\n".encode("ascii"))
                cx = table_x
                for name, width, align, _ in cols:
                    tx = cx + 3
                    if align == "C":
                        tx = cx + (width / 2) - (len(name) * 2.2)
                    elif align == "R":
                        tx = cx + width - (len(name) * 4.5) - 4
                    st.write(f"BT /F1 7.5 Tf 1 1 1 rg {tx:.1f} {y_pos + 5:.1f} Td ({name}) Tj ET\n".encode("ascii"))
                    cx += width

            elif op_type == "row":
                y_pos, item_num, item, is_even, brand_name = args
                row_h = 22
                bg_rg = "1 1 1 rg" if is_even else "0.97 0.98 0.99 rg"
                st.write(f"{bg_rg} {table_x} {y_pos} {total_w} {row_h} re f\n".encode("ascii"))
                st.write(f"0.88 0.90 0.93 RG 0.5 w {table_x} {y_pos} {total_w} {row_h} re S\n".encode("ascii"))

                extracted_vals = cfg["extract"](item, brand_name)
                row_vals = [f"{item_num:02d}"] + extracted_vals

                cx = table_x
                for (col_name, col_w, align, max_c), val in zip(cols, row_vals):
                    s_val = _escape_pdf(_fit_text(val, max_c))
                    tx = cx + 3
                    font_code = "/F2"
                    color_rg = "0.1 0.15 0.25 rg"

                    if col_name.startswith("Price"):
                        font_code = "/F1"
                        color_rg = "0.08 0.4 0.2 rg"
                        tx = cx + col_w - (len(s_val) * 4.4) - 4
                    elif align == "C":
                        font_code = "/F1" if col_name == "#" else "/F2"
                        color_rg = "0.3 0.35 0.45 rg"
                        tx = cx + (col_w / 2) - (len(s_val) * 2.2)
                    elif col_name.startswith("Model") or col_name.startswith("Product"):
                        font_code = "/F1"
                        color_rg = "0.06 0.09 0.16 rg"

                    st.write(f"BT {font_code} 7.5 Tf {color_rg} {tx:.1f} {y_pos + 7:.1f} Td ({s_val}) Tj ET\n".encode("ascii"))
                    st.write(f"0.88 0.90 0.93 RG 0.5 w {cx} {y_pos} m {cx} {y_pos + row_h} l S\n".encode("ascii"))
                    cx += col_w

        # Page Footer Bar
        st.write(b"0.85 0.88 0.92 RG 0.5 w 20 45 m 575 45 l S\n")
        page_info = f"Page {p_idx + 1} of {total_pages}"
        st.write(f"BT /F2 8 Tf 0.4 0.45 0.55 rg 285 32 Td ({page_info}) Tj ET\n".encode("ascii"))
        st.write(b"BT /F2 8 Tf 0.2 0.25 0.35 rg 20 32 Td (AiKala Official Telegram Bot: @AiKala_bot) Tj ET\n")
        st.write(b"BT /F2 8 Tf 0.2 0.25 0.35 rg 470 32 Td (Direct Contact: 09195859434) Tj ET\n")

        pages_streams.append(st.getvalue())

    # Assemble Document
    pw = _PdfBuilder()
    pw.add_object(b"<< /Type /Catalog /Pages 2 0 R >>")

    kid_refs = " ".join(f"{3 + i * 2} 0 R" for i in range(total_pages))
    pw.add_object(f"<< /Type /Pages /Kids [{kid_refs}] /Count {total_pages} >>".encode("ascii"))

    font_bold_id = 3 + total_pages * 2
    font_reg_id = font_bold_id + 1

    for i, p_bytes in enumerate(pages_streams):
        content_id = 4 + i * 2
        res = f"<< /Font << /F1 {font_bold_id} 0 R /F2 {font_reg_id} 0 R >> >>"
        pw.add_object(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_id} 0 R /Resources {res} >>".encode("ascii"))
        pw.add_object(b"<< /Length " + str(len(p_bytes)).encode("ascii") + b" >>\nstream\n" + p_bytes + b"\nendstream")

    pw.add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    pw.add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf_bytes = pw.write()
    abs_output = os.path.abspath(output_path)
    with open(abs_output, "wb") as f:
        f.write(pdf_bytes)

    logger.info(f"Generated clean tabular PDF for {category_key} at {abs_output} ({total_pages} pages, {total_items} items)")
    return abs_output
