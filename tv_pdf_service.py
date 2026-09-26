"""
TV PDF Price List Generator for AiKala Telegram Bot (@AiKala_bot)
=================================================================
Pure Python ISO 32000-1 / PDF 1.4 tabular price list generator.
- Clean English / Latin text with zero external binary or Node.js dependencies.
- Standard Type 1 Helvetica vector fonts (instantly supported by 100% of viewers/devices).
- Formats all prices with Toman (e.g. 55,000,000 Toman).
- Consecutive tables grouped by brand (SONY, LG, SAMSUNG, etc.) with clean borders.
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
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    return "".join(mapping.get(ch, ch) for ch in str(text))


def normalize_tv_brand(brand_raw: Any, name_raw: str = "") -> str:
    """Normalizes Persian or raw brand names to standard English brand titles."""
    b = str(brand_raw or "").strip()
    n = str(name_raw or "").strip().lower()

    if any(k in b for k in ["سونی", "سونی"]) or "sony" in n or "سونی" in n:
        return "SONY"
    if any(k in b for k in ["ال جی", "ال‌جی", "الجی"]) or "lg" in n or "ال جی" in n or "ال‌جی" in n:
        return "LG"
    if "سامسونگ" in b or "samsung" in n or "سامسونگ" in n:
        return "SAMSUNG"
    if "شیائومی" in b or "xiaomi" in n or "شیائومی" in n:
        return "XIAOMI"
    if "هایسنس" in b or "hisense" in n or "هایسنس" in n:
        return "HISENSE"
    if "توشیبا" in b or "toshiba" in n or "توشیبا" in n:
        return "TOSHIBA"
    if "فیلیپس" in b or "philips" in n or "فیلیپس" in n:
        return "PHILIPS"

    clean_b = b.encode("ascii", "ignore").decode("ascii").strip().upper()
    return clean_b if clean_b and len(clean_b) > 1 else "OTHER"


def clean_tv_model(name_raw: Any, model_raw: Any, brand: str) -> str:
    """Extracts clean English model and size from product name and model_number."""
    m_code = to_eng_digits(str(model_raw or "")).strip()
    n_raw = to_eng_digits(str(name_raw or "")).strip()

    # Search for screen size (e.g. 55, 65, 75, 85)
    size_str = ""
    m_size = re.search(r'(\b[3-9]\d\b)\s*(?:inch|اینچ|")', n_raw, re.I)
    if m_size:
        size_str = f"{m_size.group(1)}\""
    elif re.match(r'^[3-9]\d', m_code):
        size_str = f"{m_code[:2]}\""

    # Clean model code
    clean_code = m_code.encode("ascii", "ignore").decode("ascii").strip()
    if not clean_code or len(clean_code) < 2:
        # Try extracting code from name (e.g. 55X75K or OLED55C3)
        codes = re.findall(r'[A-Za-z0-9]{3,12}', n_raw)
        filtered = [c for c in codes if any(ch.isalpha() for ch in c) and any(ch.isdigit() for ch in c)]
        clean_code = filtered[0].upper() if filtered else ""

    if size_str and clean_code:
        if clean_code.startswith(size_str.replace('"', '')):
            full_model = clean_code
        else:
            full_model = f"{size_str} {clean_code}"
    elif clean_code:
        full_model = clean_code
    elif size_str:
        full_model = f"{brand} {size_str} Smart TV"
    else:
        full_model = f"{brand} Smart TV"

    return full_model.strip()


def normalize_assembly(val: Any) -> str:
    """Converts Persian assembly countries to clean English."""
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
    }
    parts = []
    for k, v in mapping.items():
        if k in s:
            parts.append(v)
    if parts:
        return "/".join(parts[:2])
    clean = s.encode("ascii", "ignore").decode("ascii").strip()
    return clean if clean else "Original"


def normalize_resolution_panel(res: Any, panel: Any) -> str:
    """Creates a compact specs string (e.g. 4K OLED, 4K QLED, 4K IPS)."""
    r_str = str(res or "").strip().upper()
    p_str = str(panel or "").strip().upper()

    r_clean = "4K" if "4K" in r_str else ("FHD" if "FHD" in r_str else ("HD" if "HD" in r_str else ""))
    
    p_clean = ""
    for p_candidate in ["QD-OLED", "WOLED", "OLED", "QLED", "MINI-LED", "ADS", "IPS", "VA"]:
        if p_candidate in p_str:
            p_clean = p_candidate
            break

    if r_clean and p_clean:
        return f"{r_clean} {p_clean}"
    if p_clean:
        return f"4K {p_clean}"
    if r_clean:
        return f"{r_clean} Smart"
    return "4K Smart"


def format_price_toman(price_val: Any) -> str:
    """Formats price in integer with 'Toman' (e.g. 55,000,000 Toman)."""
    if not price_val:
        return "Inquire"
    try:
        clean_str = re.sub(r"[^\d]", "", to_eng_digits(str(price_val)))
        if not clean_str:
            return "Inquire"
        val = int(clean_str)
        # Handle values entered in thousands
        if 1000 <= val <= 900000:
            val = val * 1000
        return f"{val:,} Toman"
    except Exception:
        return "Inquire"


# ─────────────────────────────────────────────────────────────
# Inventory Loader
# ─────────────────────────────────────────────────────────────

def load_all_tv_products() -> List[Dict[str, Any]]:
    """Loads all TV products from search_engine or catalog_products.json."""
    all_prods = []
    try:
        from search_engine import JSON_PRODUCTS, load_json_products
        if not JSON_PRODUCTS:
            load_json_products()
        all_prods = JSON_PRODUCTS
    except Exception as e:
        logger.warning(f"Could not load from search_engine: {e}")

    if not all_prods and os.path.exists("catalog_products.json"):
        try:
            with open("catalog_products.json", "r", encoding="utf-8") as f:
                all_prods = json.load(f)
        except Exception:
            all_prods = []

    tvs = []
    seen_ids = set()

    for p in all_prods:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("product_id") or p.get("id") or "").strip()
        if not pid or pid in seen_ids:
            continue

        cat_key = str(p.get("category_key") or "").strip().lower()
        cat_name = str(p.get("category_name") or p.get("category") or "").strip()
        name = str(p.get("name") or "").strip()

        is_tv = (
            cat_key == "tv"
            or "تلویزیون" in cat_name
            or "تلویزیون" in name
            or "tv" in name.lower()
        )

        if is_tv:
            seen_ids.add(pid)
            tvs.append(p)

    return tvs


# ─────────────────────────────────────────────────────────────
# Pure PDF 1.4 Builder (Byte-accurate, ISO 32000-1)
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


# Table columns specification for TVs: (Header Name, Width pt, Alignment, Max chars)
# Total width: 22 + 155 + 60 + 80 + 75 + 50 + 113 = 555 pt
TABLE_COLS = [
    ("#", 22, "C", 4),
    ("Model & Screen Size", 155, "L", 28),
    ("Brand", 60, "C", 11),
    ("Display & Panel", 80, "L", 16),
    ("Assembly", 75, "L", 15),
    ("PID", 50, "C", 8),
    ("Price (Toman)", 113, "R", 20),
]


def generate_tv_price_list_pdf(output_path: str = "AiKala_TV_PriceList.pdf") -> str:
    """
    Generates a crystal-clear, professional tabular PDF containing 100% of available TVs.
    Uses simple consecutive tables for each brand, clean English text, and prices formatted with 'Toman'.
    """
    tvs = load_all_tv_products()
    total_items = len(tvs)

    table_x = 20
    total_w = sum(w for _, w, _, _ in TABLE_COLS)  # 555 pt
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Group TVs by brand
    brands_map: Dict[str, List[Dict[str, Any]]] = {}
    for item in tvs:
        raw_b = item.get("brand")
        b = normalize_tv_brand(raw_b, item.get("name", ""))
        brands_map.setdefault(b, []).append(item)

    # Sort items inside each brand by price descending
    for b_name in brands_map:
        def get_p(it):
            try:
                return float(it.get("price") or 0)
            except Exception:
                return 0
        brands_map[b_name].sort(key=get_p, reverse=True)

    priority_order = ["SONY", "LG", "SAMSUNG", "XIAOMI", "HISENSE", "TOSHIBA", "PHILIPS", "OTHER"]
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

    if not tvs:
        current_page_ops.append(("empty_notice", 650))
    else:
        for brand_name in sorted_brands:
            brand_items = brands_map[brand_name]

            if cur_y < 120:
                start_new_page()

            # Brand header bar
            b_title = f"{brand_name} TELEVISIONS ({len(brand_items)} Models In Stock)"
            current_page_ops.append(("brand_bar", cur_y, b_title))
            cur_y -= 22

            # Table column header
            current_page_ops.append(("table_header", cur_y))
            cur_y -= 20

            for i, item in enumerate(brand_items):
                overall_item_counter += 1

                if cur_y < 65:
                    start_new_page()
                    current_page_ops.append(("brand_bar", cur_y, f"{brand_name} TELEVISIONS (Continued)"))
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
    # Generate Stream for each Page
    # ─────────────────────────────────────────────────────────────
    pages_streams: List[bytes] = []

    for p_idx, p_ops in enumerate(pages_ops):
        st = io.BytesIO()

        # 1. Top Page Banner (Dark Navy)
        st.write(b"0.06 0.09 0.16 rg 20 808 555 22 re f\n")
        st.write(b"BT /F1 11 Tf 1 1 1 rg 28 815 Td (AiKala - Official TV Price List & Inventory) Tj ET\n")

        # Subtitle Info Bar
        info_line = f"Date: {date_str} | Total Stock: {total_items} Models | Order & Support: 09195859434 | Telegram: @AiKala_bot"
        st.write(f"BT /F2 8 Tf 0.3 0.35 0.45 rg 20 794 Td ({_escape_pdf(info_line)}) Tj ET\n".encode("ascii"))

        # Authenticity Bar
        st.write(b"BT /F1 8 Tf 0.05 0.5 0.25 rg 20 782 Td (Guarantee: 100% Original Direct Import with Full Hardware Warranty) Tj ET\n")
        st.write(b"0.85 0.88 0.92 RG 0.5 w 20 774 m 575 774 l S\n")

        # 2. Render Page Operations
        for op_type, *args in p_ops:
            if op_type == "empty_notice":
                st.write(b"BT /F1 11 Tf 0.3 0.35 0.45 rg 180 650 Td (TV inventory is being updated by administration.) Tj ET\n")
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
                for name, width, align, _ in TABLE_COLS:
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

                model_full = clean_tv_model(item.get("name"), item.get("model_number"), brand_name)
                disp_panel = normalize_resolution_panel(item.get("resolution"), item.get("panel"))
                assembly_str = normalize_assembly(item.get("assembly"))
                pid_str = str(item.get("product_id") or item.get("id") or "")
                price_display = format_price_toman(item.get("price"))

                row_vals = [
                    f"{item_num:02d}",
                    model_full,
                    brand_name,
                    disp_panel,
                    assembly_str,
                    pid_str,
                    price_display,
                ]

                cx = table_x
                for (col_name, col_w, align, max_c), val in zip(TABLE_COLS, row_vals):
                    s_val = _escape_pdf(_fit_text(val, max_c))
                    tx = cx + 3
                    font_code = "/F2"
                    color_rg = "0.1 0.15 0.25 rg"

                    if col_name.startswith("Price"):
                        font_code = "/F1"
                        color_rg = "0.08 0.4 0.2 rg"
                        tx = cx + col_w - (len(s_val) * 4.4) - 4
                    elif col_name in ["#", "Brand", "PID"]:
                        font_code = "/F1" if col_name == "#" else "/F2"
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

    # Standard PDF Type 1 Fonts (Helvetica vector)
    pw.add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    pw.add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf_bytes = pw.write()
    abs_output = os.path.abspath(output_path)
    with open(abs_output, "wb") as f:
        f.write(pdf_bytes)

    logger.info(f"Generated clean tabular TV PDF at {abs_output} ({total_pages} pages, {total_items} items)")
    return abs_output
