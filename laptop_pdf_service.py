"""
Laptop PDF Price List Generator for AiKala Telegram Bot (@AiKala_bot)
=====================================================================
Generates clean, professional, high-clarity tabular PDF price lists
for ALL available laptops with complete technical specifications,
grade, and current price (formatted with 'T').

Guaranteed features:
1. Zero external binary dependencies (no PIL, no ReportLab required).
2. Uses standard Type 1 Helvetica vector fonts natively supported by 100% of PDF viewers.
3. Clean English / Latin tables with zero unreadable font encoding issues.
4. Simple consecutive tables grouped by brand with crisp borders and headers.
5. Formats all prices cleanly with 'T' (e.g. 18,500,000 T).
6. ISO 32000-1 / PDF 1.4 compliant with byte-accurate xref and stream lengths.
"""
import time


import os
import io
import re
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────
# Text Normalization & Spec Helpers
# ─────────────────────────────────────────────────────────────

def to_eng_digits(text: Any) -> str:
    """Converts Persian and Arabic digits to standard English digits."""
    if text is None:
        return ""
    mapping = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '7': '7', '۸': '8', '۹': '9',
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    return "".join(mapping.get(ch, ch) for ch in str(text))


def clean_spec_text(val: Any, default: str = "-") -> str:
    """
    Cleans and normalizes Persian or English technical spec strings into clean English.
    Strips noise, standardizes units (GB, TB, SSD, FHD, etc.).
    """
    if val is None:
        return default
    s = to_eng_digits(str(val)).strip()
    if not s:
        return default

    # Remove common Persian prefixes
    s = re.sub(r'^(?:پردازنده|سی\s*پی\s*یو|cpu)[:\s\-]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:رم|حافظه\s*رم|ram)[:\s\-]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:هارد|حافظه\s*داخلی|حافظه|ssd|hdd|storage)[:\s\-]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:گرافیک|کارت\s*گرافیک|gpu|vga)[:\s\-]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:صفحه\s*نمایش|نمایشگر|سایز|display|screen)[:\s\-]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:گرید|تمیزی|کیفیت|grade)[:\s\-]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(?:گارانتی|ضمانت|مهلت\s*تست|warranty)[:\s\-]+', '', s, flags=re.IGNORECASE)

    # Unit translations
    s = s.replace('گیگابایت', 'GB').replace('گیگ', 'GB')
    s = s.replace('ترابایت', 'TB').replace('ترا', 'TB')
    s = s.replace('اینچ', ' inch')
    s = s.replace('فول اچ دی', 'FHD').replace('فورکی', '4K')
    s = s.replace('استاندارد', 'Standard')
    s = s.replace('تومان', 'T')

    # Convert non-ascii characters to ascii safe
    s = s.encode('ascii', 'ignore').decode('ascii').strip()
    s = re.sub(r'\s+', ' ', s)
    return s if s else default


def normalize_brand_name(brand_raw: Any) -> str:
    """Normalizes Persian or raw brand names to standard English brand titles."""
    if not brand_raw:
        return "OTHER"
    b = str(brand_raw).strip()
    b_upper = b.upper()

    persian_brands = {
        "اچ پی": "HP",
        "اچ‌پی": "HP",
        "ایسوس": "ASUS",
        "لنوو": "LENOVO",
        "دل": "DELL",
        "اپل": "APPLE",
        "مک بوک": "APPLE",
        "مک‌بوک": "APPLE",
        "سرفیس": "MICROSOFT",
        "مایکروسافت": "MICROSOFT",
        "ایسر": "ACER",
        "ام اس ای": "MSI",
        "ام‌اس‌ای": "MSI",
    }
    for fa_k, en_v in persian_brands.items():
        if fa_k in b:
            return en_v

    for known in ["HP", "LENOVO", "DELL", "ASUS", "APPLE", "ACER", "MICROSOFT", "MSI"]:
        if known in b_upper:
            return known

    clean_b = b_upper.encode("ascii", "ignore").decode("ascii").strip()
    return clean_b if clean_b and len(clean_b) > 1 else "OTHER"


def clean_model_name(model_raw: Any, brand: str) -> str:
    """Cleans up model name, removes repetitive 'لپ‌تاپ' or brand prefixes."""
    if not model_raw:
        return f"{brand} Laptop"
    m = to_eng_digits(str(model_raw)).strip()
    m = re.sub(r'(?:لپ\s*تاپ|لپ‌تاپ|لپتاپ|laptop|استوک|کارکرده)', '', m, flags=re.IGNORECASE).strip()
    # Remove leading brand if already present in model string
    if m.upper().startswith(brand + " "):
        m = m[len(brand) + 1:].strip()
    m = m.encode("ascii", "ignore").decode("ascii").strip()
    m = re.sub(r'\s+', ' ', m)
    return m if m else f"{brand} Standard"


def format_price_toman(price_val: Any) -> str:
    """Formats price in integer with 'T' (e.g. 18,500,000 T)."""
    if not price_val:
        return "Inquire"
    try:
        clean_str = re.sub(r"[^\d]", "", to_eng_digits(str(price_val)))
        if not clean_str:
            return "Inquire"
        val = int(clean_str)
        # If entered in thousands (e.g. 248000 instead of 248000000 or 18500 instead of 18500000)
        if 1000 <= val <= 900000:
            val = val * 1000
        return f"{val:,} T"
    except Exception:
        return "Inquire"


def extract_laptop_specs(lp: Dict[str, Any]) -> Dict[str, str]:
    """
    Extracts complete, normalized technical specifications from any laptop dictionary format.
    Guarantees clean English strings.
    """
    specs = lp.get("specs", {}) if isinstance(lp.get("specs"), dict) else {}

    raw_cpu = (
        specs.get("پردازنده (CPU)") or specs.get("cpu") or specs.get("CPU")
        or lp.get("cpu") or lp.get("CPU") or ""
    )
    raw_ram = (
        specs.get("حافظه رم (RAM)") or specs.get("رم") or specs.get("ram") or specs.get("RAM")
        or lp.get("ram") or lp.get("RAM") or ""
    )
    raw_storage = (
        specs.get("حافظه داخلی (SSD/HDD)") or specs.get("هارد") or specs.get("حافظه")
        or specs.get("storage") or specs.get("ssd") or specs.get("SSD")
        or lp.get("storage") or lp.get("ssd") or ""
    )
    raw_gpu = (
        specs.get("کارت گرافیک (GPU)") or specs.get("گرافیک") or specs.get("gpu") or specs.get("GPU")
        or lp.get("gpu") or lp.get("GPU") or ""
    )
    raw_display = (
        specs.get("صفحه نمایش") or specs.get("نمایشگر") or specs.get("display") or specs.get("screen")
        or lp.get("display") or lp.get("screen") or ""
    )
    raw_grade = (
        specs.get("گرید و تمیزی") or specs.get("گرید") or specs.get("grade") or specs.get("Grade")
        or lp.get("grade") or "A++"
    )
    raw_code = (
        lp.get("code") or specs.get("کد مدل") or specs.get("کد کالا") or specs.get("code") or ""
    )

    # Fallback search from description/title if any critical spec is empty
    desc = str(lp.get("description", "") or lp.get("caption", "") or lp.get("title", ""))
    if not raw_cpu and any(w in desc.lower() for w in ["cpu", "core", "ryzen", "celeron"]):
        m = re.search(r'(?:cpu|پردازنده)[:\s\-]+([^\n\r,\|;]+)', desc, re.I)
        if m:
            raw_cpu = m.group(1).strip()
    if not raw_ram and "ram" in desc.lower():
        m = re.search(r'(?:ram|رم)[:\s\-]+([^\n\r,\|;]+)', desc, re.I)
        if m:
            raw_ram = m.group(1).strip()
    if not raw_storage and any(w in desc.lower() for w in ["ssd", "hdd", "هارد", "حافظه"]):
        m = re.search(r'(?:ssd|hdd|storage|هارد|حافظه)[:\s\-]+([^\n\r,\|;]+)', desc, re.I)
        if m:
            raw_storage = m.group(1).strip()
    if not raw_gpu and any(w in desc.lower() for w in ["gpu", "vga", "گرافیک"]):
        m = re.search(r'(?:gpu|vga|graphic|گرافیک)[:\s\-]+([^\n\r,\|;]+)', desc, re.I)
        if m:
            raw_gpu = m.group(1).strip()
    if not raw_display and any(w in desc.lower() for w in ["display", "screen", "نمایشگر", "صفحه نمایش"]):
        m = re.search(r'(?:display|screen|نمایشگر|صفحه نمایش)[:\s\-]+([^\n\r,\|;]+)', desc, re.I)
        if m:
            raw_display = m.group(1).strip()

    cpu = clean_spec_text(raw_cpu, "Core i5 / i7")
    ram = clean_spec_text(raw_ram, "8GB / 16GB")
    storage = clean_spec_text(raw_storage, "256GB / 512GB")
    gpu = clean_spec_text(raw_gpu, "Intel HD / UHD")
    display = clean_spec_text(raw_display, "14.0 FHD")
    grade = clean_spec_text(raw_grade, "A++")
    code = to_eng_digits(str(raw_code)).strip().encode("ascii", "ignore").decode("ascii")

    return {
        "cpu": cpu,
        "ram": ram,
        "storage": storage,
        "gpu": gpu,
        "display": display,
        "grade": grade,
        "code": code,
        "warranty": "7-Day Test Guarantee"
    }


# Backward compatibility stubs
def fa(text: Any) -> str:
    return str(text) if text is not None else ""

def to_fa_digits(text: Any) -> str:
    return to_eng_digits(text)

def get_shamsi_date_str() -> str:
    try:
        import jdatetime
        now = jdatetime.datetime.now()
        return now.strftime("%Y/%m/%d")
    except ImportError:
        return datetime.now().strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────────
# Inventory Loader
# ─────────────────────────────────────────────────────────────

def load_all_laptops() -> List[Dict[str, Any]]:
    """Loads ALL available laptops from all storage files and caches without loss."""
    laptops = []
    seen_ids = set()

    search_files = [
        "laptops_catalog.json",
        os.path.join(BASE_DIR, "laptops_catalog.json"),
        os.path.join(os.getcwd(), "laptops_catalog.json"),
        os.path.join(os.path.expanduser("~"), "AiKala", "laptops_catalog.json"),
        "/data/data/com.termux/files/home/AiKala/laptops_catalog.json",
    ]

    for lf in search_files:
        if os.path.isfile(lf):
            try:
                with open(lf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for lp in data:
                            lid = lp.get("id") or lp.get("product_id") or f"{lp.get('brand')}_{lp.get('model')}_{lp.get('code')}"
                            if lid not in seen_ids:
                                seen_ids.add(lid)
                                laptops.append(lp)
            except Exception as e:
                logger.warning(f"Error loading {lf}: {e}")

    # Also try laptop_extractor catalog function
    try:
        from laptop_extractor import load_laptops_catalog
        extracted = load_laptops_catalog()
        for lp in extracted:
            lid = lp.get("id") or lp.get("product_id") or f"{lp.get('brand')}_{lp.get('model')}_{lp.get('code')}"
            if lid not in seen_ids:
                seen_ids.add(lid)
                laptops.append(lp)
    except Exception:
        pass

    # Also from search_engine / JSON_PRODUCTS if any
    try:
        from search_engine import JSON_PRODUCTS
        for p in JSON_PRODUCTS:
            cat_key = p.get("category_key")
            cat_name = p.get("category") or p.get("category_name")
            pid = p.get("product_id") or p.get("id")
            if (cat_key == "laptop" or cat_name in ["لپ‌تاپ", "لپ تاپ", "laptop"] or str(pid).upper().startswith("LAP")):
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    laptops.append(p)
    except Exception:
        pass

    logger.info(f"Loaded total of {len(laptops)} laptops for price list PDF")
    return laptops


# ─────────────────────────────────────────────────────────────
# High-Precision Pure PDF 1.4 Generator (ISO 32000-1 Compliant)
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


# Table columns specification: (Header Name, Width pt, Alignment, Max chars)
TABLE_COLS = [
    ("#", 22, "C", 4),
    ("Model & Code", 135, "L", 28),
    ("CPU", 75, "L", 16),
    ("RAM", 45, "L", 11),
    ("Storage", 60, "L", 13),
    ("GPU", 75, "L", 16),
    ("Display", 50, "L", 11),
    ("Grade", 30, "C", 7),
    ("Price", 63, "R", 14),
]


def generate_laptops_price_list_pdf(output_path: str = "AiKala_Laptops_PriceList.pdf") -> str:
    """
    Generates a crystal-clear, professional tabular PDF containing 100% of available laptops.
    Uses simple consecutive tables for each brand, clean English text, and prices formatted with 'T'.
    """
    laptops = load_all_laptops()
    total_items = len(laptops)

    table_x = 20
    total_w = sum(w for _, w, _, _ in TABLE_COLS)  # 555 pt
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Group laptops by brand
    brands_map: Dict[str, List[Dict[str, Any]]] = {}
    for lp in laptops:
        raw_b = lp.get("brand") or (lp.get("specs", {}) if isinstance(lp.get("specs"), dict) else {}).get("brand")
        b = normalize_brand_name(raw_b)
        brands_map.setdefault(b, []).append(lp)

    # Priority sorting for prominent brands
    priority_order = ["HP", "LENOVO", "DELL", "ASUS", "APPLE", "ACER", "MICROSOFT", "MSI"]
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

    if not laptops:
        # Empty inventory placeholder
        current_page_ops.append(("empty_notice", 650))
    else:
        for brand_name in sorted_brands:
            brand_items = brands_map[brand_name]

            # Require space for brand header (22pt) + table column header (20pt) + at least 1 row (22pt) = 64pt
            if cur_y < 120:
                start_new_page()

            # Brand header bar
            b_title = f"{brand_name} LAPTOPS ({len(brand_items)} Models Available)"
            current_page_ops.append(("brand_bar", cur_y, b_title))
            cur_y -= 22

            # Table column header
            current_page_ops.append(("table_header", cur_y))
            cur_y -= 20

            for i, lp in enumerate(brand_items):
                overall_item_counter += 1

                # If approaching bottom footer (45pt), break to next page
                if cur_y < 65:
                    start_new_page()
                    # Repeat continued brand header and table header on new page
                    current_page_ops.append(("brand_bar", cur_y, f"{brand_name} LAPTOPS (Continued)"))
                    cur_y -= 22
                    current_page_ops.append(("table_header", cur_y))
                    cur_y -= 20

                current_page_ops.append(("row", cur_y, overall_item_counter, lp, i % 2 == 0, brand_name))
                cur_y -= 22

            # Clean spacing between consecutive brand tables
            cur_y -= 12

    if current_page_ops:
        pages_ops.append(current_page_ops)

    total_pages = len(pages_ops)

    # ─────────────────────────────────────────────────────────────
    # Generate Stream for each Page
    # ─────────────────────────────────────────────────────────────
    pages_streams: List[bytes] = []

    for p_idx, p_ops in enumerate(pages_ops):
        st = io.BytesIO()

        # 1. Top Page Banner
        # Dark Navy Brand Banner
        st.write(b"0.06 0.09 0.16 rg 20 808 555 22 re f\n")
        st.write(b"BT /F1 11 Tf 1 1 1 rg 28 815 Td (AiKala - Official Laptops Price List & Inventory) Tj ET\n")

        # Subtitle Info Bar
        info_line = f"Date: {date_str} | Total Inventory: {total_items} Models | Order & Support: 09195859434 | Telegram: @AiKala_bot"
        st.write(f"BT /F2 8 Tf 0.3 0.35 0.45 rg 20 794 Td ({_escape_pdf(info_line)}) Tj ET\n".encode("ascii"))

        # Guarantee Bar
        st.write(b"BT /F1 8 Tf 0.05 0.5 0.25 rg 20 782 Td (Guarantee: 7-Day Full Hardware Test & Replacement Guarantee on all models) Tj ET\n")
        st.write(b"0.85 0.88 0.92 RG 0.5 w 20 774 m 575 774 l S\n")

        # 2. Render Page Operations
        for op_type, *args in p_ops:
            if op_type == "empty_notice":
                y_pos = args[0]
                st.write(b"BT /F1 11 Tf 0.3 0.35 0.45 rg 180 650 Td (Laptop catalog is being updated by administration.) Tj ET\n")
                st.write(b"BT /F2 9 Tf 0.1 0.2 0.35 rg 195 630 Td (For live pricing and orders, contact: 09195859434) Tj ET\n")

            elif op_type == "brand_bar":
                y_pos, b_title = args
                # Slate blue filled brand header
                st.write(f"0.12 0.23 0.54 rg {table_x} {y_pos} {total_w} 20 re f\n".encode("ascii"))
                st.write(f"0.12 0.23 0.54 RG 0.5 w {table_x} {y_pos} {total_w} 20 re S\n".encode("ascii"))
                st.write(f"BT /F1 8.5 Tf 1 1 1 rg {table_x + 8:.1f} {y_pos + 6:.1f} Td ({_escape_pdf(b_title)}) Tj ET\n".encode("ascii"))

            elif op_type == "table_header":
                y_pos = args[0]
                # Dark table column header
                st.write(f"0.09 0.15 0.24 rg {table_x} {y_pos} {total_w} 18 re f\n".encode("ascii"))
                st.write(f"0.09 0.15 0.24 RG 0.5 w {table_x} {y_pos} {total_w} 18 re S\n".encode("ascii"))
                cx = table_x
                for name, width, align, _ in TABLE_COLS:
                    tx = cx + 3
                    if align == "C":
                        tx = cx + (width / 2) - (len(name) * 2.2)
                    elif align == "R":
                        tx = cx + width - (len(name) * 4.5) - 4
                    st.write(f"BT /F1 7.5 Tf 1 1 1 rg {tx:.1f} {y_pos + 5:.1f} Td ({name}) Tj ET\n".encode("ascii"))
                    cx += width

            elif op_type == "row":
                y_pos, item_num, lp, is_even, brand_name = args
                row_h = 22
                bg_rg = "1 1 1 rg" if is_even else "0.97 0.98 0.99 rg"
                st.write(f"{bg_rg} {table_x} {y_pos} {total_w} {row_h} re f\n".encode("ascii"))
                st.write(f"0.88 0.90 0.93 RG 0.5 w {table_x} {y_pos} {total_w} {row_h} re S\n".encode("ascii"))

                spec_data = extract_laptop_specs(lp)
                clean_model = clean_model_name(lp.get("model") or lp.get("title") or lp.get("name"), brand_name)
                code_str = spec_data.get("code") or lp.get("code", "")
                model_full = f"{clean_model} [{code_str}]" if code_str else clean_model

                price_display = format_price_toman(lp.get("price"))

                row_vals = [
                    f"{item_num:02d}",
                    model_full,
                    spec_data.get("cpu", "-"),
                    spec_data.get("ram", "-"),
                    spec_data.get("storage", "-"),
                    spec_data.get("gpu", "-"),
                    spec_data.get("display", "-"),
                    spec_data.get("grade", "A++"),
                    price_display,
                ]

                cx = table_x
                for (col_name, col_w, align, max_c), val in zip(TABLE_COLS, row_vals):
                    s_val = _escape_pdf(_fit_text(val, max_c))
                    tx = cx + 3
                    font_code = "/F2"
                    color_rg = "0.1 0.15 0.25 rg"

                    if col_name == "Price":
                        font_code = "/F1"
                        color_rg = "0.08 0.4 0.2 rg"
                        # Right alignment
                        tx = cx + col_w - (len(s_val) * 4.4) - 3
                    elif col_name == "Grade":
                        font_code = "/F1"
                        color_rg = "0.05 0.5 0.25 rg"
                        tx = cx + (col_w / 2) - (len(s_val) * 2.2)
                    elif col_name == "#":
                        font_code = "/F1"
                        color_rg = "0.3 0.35 0.45 rg"
                        tx = cx + (col_w / 2) - (len(s_val) * 2.2)
                    elif col_name.startswith("Model"):
                        font_code = "/F1"
                        color_rg = "0.06 0.09 0.16 rg"

                    st.write(f"BT {font_code} 7.5 Tf {color_rg} {tx:.1f} {y_pos + 7:.1f} Td ({s_val}) Tj ET\n".encode("ascii"))
                    st.write(f"0.88 0.90 0.93 RG 0.5 w {cx} {y_pos} m {cx} {y_pos + row_h} l S\n".encode("ascii"))
                    cx += col_w

        # 3. Page Footer Bar
        st.write(b"0.85 0.88 0.92 RG 0.5 w 20 45 m 575 45 l S\n")
        page_info = f"Page {p_idx + 1} of {total_pages}"
        st.write(f"BT /F2 8 Tf 0.4 0.45 0.55 rg 285 32 Td ({page_info}) Tj ET\n".encode("ascii"))
        st.write(b"BT /F2 8 Tf 0.2 0.25 0.35 rg 20 32 Td (AiKala Official Telegram Bot: @AiKala_bot) Tj ET\n")
        st.write(b"BT /F2 8 Tf 0.2 0.25 0.35 rg 470 32 Td (Direct Contact: 09195859434) Tj ET\n")

        pages_streams.append(st.getvalue())

    # ─────────────────────────────────────────────────────────────
    # Assemble PDF Document
    # ─────────────────────────────────────────────────────────────
    pw = _PdfBuilder()
    # Object 1: Catalog
    pw.add_object(b"<< /Type /Catalog /Pages 2 0 R >>")

    # Object 2: Pages Collection
    kid_refs = " ".join(f"{3 + i * 2} 0 R" for i in range(total_pages))
    pw.add_object(f"<< /Type /Pages /Kids [{kid_refs}] /Count {total_pages} >>".encode("ascii"))

    font_bold_id = 3 + total_pages * 2
    font_reg_id = font_bold_id + 1

    for i, p_bytes in enumerate(pages_streams):
        page_id = 3 + i * 2
        content_id = 4 + i * 2
        res = f"<< /Font << /F1 {font_bold_id} 0 R /F2 {font_reg_id} 0 R >> >>"
        pw.add_object(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_id} 0 R /Resources {res} >>".encode("ascii"))
        pw.add_object(b"<< /Length " + str(len(p_bytes)).encode("ascii") + b" >>\nstream\n" + p_bytes + b"\nendstream")

    # Standard PDF Type 1 Fonts
    pw.add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    pw.add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf_bytes = pw.write()
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)

    logger.info(f"Generated clean tabular PDF at {output_path} ({total_pages} pages, {total_items} items)")
    return output_path


def _generate_fallback_pdf(laptops: List[Dict[str, Any]], output_path: str) -> str:
    """Redirects to the unified, error-free tabular PDF generator."""
    return generate_laptops_price_list_pdf(output_path)
