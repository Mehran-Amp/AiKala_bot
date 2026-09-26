"""
ماژول اختصاصی کاتالوگ و مدیریت سیستم صوتی (اسپیکر، پارتی‌باکس، ساندبار، هدفون).
مشابه ماژول لپ‌تاپ (laptop_extractor.py):
- بارگذاری داده‌ها از فایل‌های audio_catalog.csv و audio_catalog.json
- پشتیبانی از استخراج هوشمند فایل اکسل / CSV جدید توسط ادمین
- نرمال‌سازی مشخصات برای جستجو و نمایش کارت محصول در تلگرام
- بدون وابستگی خارجی اضافه
"""

import os
import io
import re
import csv
import json
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

AUDIO_CATALOG_FILE = "audio_catalog.json"
AUDIO_CSV_FILE = "audio_catalog.csv"

def normalize_price_value(price_val: Any) -> int:
    """تبدیل رشته یا عدد قیمت به عدد صحیح به تومان"""
    if not price_val:
        return 0
    clean_str = re.sub(r"[^\d]", "", str(price_val))
    if not clean_str:
        return 0
    val = int(clean_str)
    # اگر مثلاً 159500 (هزار تومان) ثبت شده باشد و کمتر از ۱ میلیون باشد
    if val < 1000000:
        return val * 1000
    return val

def parse_audio_csv(file_content: str) -> List[Dict[str, Any]]:
    """خواندن و پارس کردن محتوای CSV سیستم صوتی"""
    items = []
    reader = csv.reader(io.StringIO(file_content))
    header = None
    col_map = {}
    
    for row in reader:
        if not row or not any(str(c).strip() for c in row):
            continue
        if header is None:
            # تشخیص هدر
            header = [c.strip().lower() for c in row]
            for idx, col in enumerate(header):
                if "code" in col: col_map["code"] = idx
                elif "brand" in col: col_map["brand"] = idx
                elif "category" in col or "sub" in col or "type" in col: col_map["subcat"] = idx
                elif "model" in col: col_map["model"] = idx
                elif "power" in col: col_map["power"] = idx
                elif "spec" in col or "key" in col or "desc" in col: col_map["specs"] = idx
                elif "price" in col or "قیمت" in col: col_map["price"] = idx
            continue
        
        # استخراج فیلدها با توجه به col_map یا موقعیت‌های پیش‌فرض
        code = row[col_map.get("code", 0)].strip() if col_map.get("code", 0) < len(row) else ""
        brand = row[col_map.get("brand", 1)].strip() if col_map.get("brand", 1) < len(row) else "JBL"
        subcat = row[col_map.get("subcat", 2)].strip() if col_map.get("subcat", 2) < len(row) else "Party Speaker"
        model = row[col_map.get("model", 3)].strip() if col_map.get("model", 3) < len(row) else ""
        power = row[col_map.get("power", 4)].strip() if col_map.get("power", 4) < len(row) else "-"
        specs = row[col_map.get("specs", 5)].strip() if col_map.get("specs", 5) < len(row) else ""
        price_raw = row[col_map.get("price", 6)].strip() if col_map.get("price", 6) < len(row) else "0"
        
        if not model and len(row) > 3:
            model = row[3].strip()
            
        if not model:
            continue
            
        items.append({
            "code": code,
            "brand": brand,
            "subcat": subcat,
            "model": model,
            "power": power,
            "specs": specs,
            "price": price_raw
        })
        
    return clean_and_normalize_audio(items)

def clean_and_normalize_audio(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """پاکسازی، ساخت شناسه‌های یکتا و تبدیل به ساختار محصول استاندارد AiKala"""
    cleaned = []
    
    # ترجمه و دسته‌بندی فارسی برای زیرمجموعه‌ها
    subcat_fa_map = {
        "party speaker": "اسپیکر پارتی‌باکس (PartyBox)",
        "portable speaker": "اسپیکر پرتابل و قابل حمل",
        "soundbar": "ساندبار و سینمای خانگی",
        "home speaker": "اسپیکر خانگی و رومیزی",
        "headphones": "هدفون و هندزفری",
        "accessory": "لوازم جانبی و کاور"
    }
    
    brand_fa_map = {
        "JBL": "جی بی ال",
        "HARMAN KARDON": "هارمن کاردن",
        "SONY": "سونی",
        "HOPESTAR": "هوپستار"
    }

    for item in items:
        brand = str(item.get("brand", "JBL")).strip().upper()
        if not brand:
            brand = "JBL"
        model = str(item.get("model", "")).strip()
        if not model:
            continue
            
        code = str(item.get("code", "")).strip()
        subcat_raw = str(item.get("subcat", "Party Speaker")).strip()
        power = str(item.get("power", "-")).strip()
        raw_specs = str(item.get("specs", "")).strip()
        price_num = normalize_price_value(item.get("price", 0))
        
        subcat_fa = subcat_fa_map.get(subcat_raw.lower(), subcat_raw)
        brand_fa = brand_fa_map.get(brand, brand)
        
        # شناسه یکتا
        clean_code = code.replace(" ", "") if code else ""
        product_id = f"AUDIO_{brand}_{clean_code}" if clean_code else f"AUDIO_{brand}_{re.sub(r'[^A-Za-z0-9]', '', model)}"
        
        # عنوان کامل فارسی و انگلیسی
        full_title = f"سیستم صوتی {brand_fa} مدل {model}"
        if code:
            full_title += f" [کد {code}]"
            
        specs_dict = {}
        if code:
            specs_dict["کد انبار"] = code
        specs_dict["برند"] = brand
        specs_dict["نوع محصول"] = subcat_fa
        specs_dict["مدل دستگاه"] = model
        if power and power != "-":
            specs_dict["توان خروجی (Output Power)"] = power
        if raw_specs and raw_specs != "-":
            specs_dict["مشخصات و قابلیت‌های کلیدی"] = raw_specs
            
        specs_dict["ضمانت اصالت"] = "۱۰۰٪ اورجینال شرکتی با تضمین اصالت فیزیکی"
        specs_dict["گارانتی و مهلت تست"] = "یک هفته مهلت تست و تعویض + ۱۸ ماه گارانتی شرکتی"
        
        entry = {
            "id": product_id,
            "product_id": product_id,
            "code": code,
            "name": full_title,
            "title": full_title,
            "brand": brand,
            "model": model,
            "category_key": "audio",
            "category": "سیستم صوتی",
            "category_name": "سیستم صوتی",
            "subcategory": subcat_fa,
            "price": price_num,
            "price_formatted": f"{price_num:,} تومان" if price_num else "تماس بگیرید",
            "specs": specs_dict,
            "available": True,
            "source": "audio_csv"
        }
        cleaned.append(entry)
        
    return cleaned

def load_audio_catalog(force_reload: bool = False) -> List[Dict[str, Any]]:
    """
    خواندن کاتالوگ سیستم‌های صوتی:
    در صورت force_reload=True ابتدا مجدداً از فایل CSV خوانده و ذخیره می‌شود.
    در غیر این صورت، ابتدا از فایل JSON خوانده می‌شود؛ اگر نبود یا خالی بود از audio_catalog.csv خوانده و کش می‌شود.
    """
    if force_reload and os.path.exists(AUDIO_CSV_FILE):
        try:
            with open(AUDIO_CSV_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            items = parse_audio_csv(content)
            if items:
                save_audio_catalog(items)
                return items
        except Exception as e:
            logger.error(f"Error force reloading {AUDIO_CSV_FILE}: {e}")

    if os.path.exists(AUDIO_CATALOG_FILE):
        try:
            with open(AUDIO_CATALOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except Exception as e:
            logger.error(f"Error reading {AUDIO_CATALOG_FILE}: {e}")
            
    # تلاش برای خواندن از CSV
    if os.path.exists(AUDIO_CSV_FILE):
        try:
            with open(AUDIO_CSV_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            items = parse_audio_csv(content)
            if items:
                save_audio_catalog(items)
                return items
        except Exception as e:
            logger.error(f"Error reading {AUDIO_CSV_FILE}: {e}")
            
    return []

def save_audio_catalog(items: List[Dict[str, Any]]) -> bool:
    """ذخیره لیست سیستم صوتی در فایل JSON"""
    try:
        with open(AUDIO_CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {AUDIO_CATALOG_FILE}: {e}")
        return False

def generate_audio_csv_file(target_path: Optional[str] = None) -> str:
    """تولید فایل استاندارد CSV از کاتالوگ فعلی سیستم‌های صوتی برای دانلود توسط ادمین"""
    items = load_audio_catalog()
    out_path = target_path or "AiKala_Audio_Catalog.csv"
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Code", "Brand", "Category", "Model", "Output Power", "Key Specs", "Price (Toman)"])
        for it in items:
            code = it.get("code", "")
            brand = it.get("brand", "")
            subcat = it.get("subcategory", "")
            model = it.get("model", "")
            specs_d = it.get("specs") or {}
            power = specs_d.get("توان خروجی (Output Power)", "-")
            key_specs = specs_d.get("مشخصات و قابلیت‌های کلیدی", "")
            price = it.get("price", 0)
            price_str = f"{price:,} تومان" if price else "0"
            writer.writerow([code, brand, subcat, model, power, key_specs, price_str])
    return out_path

def parse_audio_table_rows(rows: List[List[str]]) -> List[Dict[str, Any]]:
    """
    تبدیل سطرهای جدول اکسل/CSV به لیست ساختارمند اقلام سیستم صوتی:
    - فیلتر هوشمند قیمت همکار
    - تشخیص خودکار ستون‌ها و برندها (JBL, Harman Kardon, Sony, Hopestar و...)
    - پاکسازی شماره تماس و تبلیغات
    """
    if not rows:
        return []

    header_idx = -1
    col_map = {}

    for r_idx, row in enumerate(rows[:10]):
        row_str = " ".join([str(c).strip().lower() for c in row if c])
        if any(k in row_str for k in ["قیمت", "مدل", "برند", "price", "model", "brand", "power", "توان", "همکار"]):
            header_idx = r_idx
            for c_idx, cell in enumerate(row):
                cell_s = str(cell).strip().lower()
                if "همکار" in cell_s or "cooperation" in cell_s or "عمده" in cell_s:
                    col_map["ignore_colleague"] = c_idx
                elif "کد" in cell_s or "code" in cell_s:
                    col_map["code"] = c_idx
                elif "برند" in cell_s or "brand" in cell_s:
                    col_map["brand"] = c_idx
                elif "مدل" in cell_s or "model" in cell_s or "نام" in cell_s:
                    col_map["model"] = c_idx
                elif "دسته" in cell_s or "نوع" in cell_s or "category" in cell_s or "sub" in cell_s or "type" in cell_s:
                    col_map["subcat"] = c_idx
                elif "توان" in cell_s or "power" in cell_s or "وات" in cell_s or "rms" in cell_s:
                    col_map["power"] = c_idx
                elif "مشخص" in cell_s or "ویژگی" in cell_s or "spec" in cell_s or "desc" in cell_s:
                    col_map["specs"] = c_idx
                elif "قیمت" in cell_s or "price" in cell_s:
                    col_map["price"] = c_idx
            break

    raw_items = []
    start_row = header_idx + 1 if header_idx >= 0 else 0

    known_brands = [
        ("JBL", r'\b(jbl|جی\s*بی\s*ال)\b'),
        ("HARMAN KARDON", r'\b(harman\s*kardon|هارمن\s*کاردن|هارمن)\b'),
        ("SONY", r'\b(sony|سونی)\b'),
        ("HOPESTAR", r'\b(hopestar|هوپستار)\b'),
        ("MARSHALL", r'\b(marshall|مارشال)\b'),
        ("BOSE", r'\b(bose|بوز)\b'),
        ("ANKER", r'\b(anker|soundcore|انکر)\b'),
    ]

    for row_idx, row in enumerate(rows[start_row:], start=start_row):
        row_str = " ".join([str(c).strip() for c in row if c])
        if not row_str or len(row_str) < 3:
            continue

        if re.search(r'(کانال|آدرس|تماس|تلفن|۰۹\d{9}|09\d{9}|فروشگاه|تلگرام|واتساپ|instagram|telegram)', row_str, re.IGNORECASE):
            continue

        code = ""
        brand = ""
        model = ""
        subcat = "Party Speaker"
        power = "-"
        specs = ""
        price = 0

        # ۱. استخراج قیمت مصرف‌کننده
        if "price" in col_map and col_map["price"] < len(row):
            price = normalize_price_value(row[col_map["price"]])
        else:
            candidate_prices = []
            for c_idx, cell in enumerate(row):
                if c_idx == col_map.get("ignore_colleague"):
                    continue
                p_val = normalize_price_value(cell)
                if 1000 <= p_val <= 9000000000:
                    candidate_prices.append(p_val)
            if candidate_prices:
                price = max(candidate_prices)

        if price < 1000:
            continue

        if price < 1000000:
            price = price * 1000
        elif price >= 500000000 and price % 10 == 0:
            price = price // 10

        # ۲. کد کالا
        if "code" in col_map and col_map["code"] < len(row):
            code = str(row[col_map["code"]]).strip()

        # ۳. برند
        if "brand" in col_map and col_map["brand"] < len(row) and str(row[col_map["brand"]]).strip():
            brand = str(row[col_map["brand"]]).strip().upper()
        else:
            for b_name, b_rgx in known_brands:
                if re.search(b_rgx, row_str, re.IGNORECASE):
                    brand = b_name
                    break
        if not brand:
            brand = "JBL"

        # ۴. مدل
        if "model" in col_map and col_map["model"] < len(row) and str(row[col_map["model"]]).strip():
            model = str(row[col_map["model"]]).strip()
        else:
            text_cells = [str(c).strip() for c in row if len(str(c).strip()) > 3 and not re.match(r'^\d+$', str(c).strip())]
            model = max(text_cells, key=len) if text_cells else f"اسپیکر {brand}"

        # ۵. نوع و زیردسته
        if "subcat" in col_map and col_map["subcat"] < len(row) and str(row[col_map["subcat"]]).strip():
            subcat = str(row[col_map["subcat"]]).strip()
        else:
            lower_m = (model + " " + row_str).lower()
            if "party" in lower_m or "partybox" in lower_m:
                subcat = "Party Speaker"
            elif "bar" in lower_m or "soundbar" in lower_m:
                subcat = "Soundbar"
            elif "tune" in lower_m or "headphone" in lower_m or "هدفون" in lower_m:
                subcat = "Headphones"
            elif "boombox" in lower_m or "xtreme" in lower_m or "charge" in lower_m or "flip" in lower_m or "clip" in lower_m or "go " in lower_m:
                subcat = "Portable Speaker"
            elif "aura" in lower_m or "onyx" in lower_m or "soundsticks" in lower_m:
                subcat = "Home Speaker"

        # ۶. توان خروجی و مشخصات
        if "power" in col_map and col_map["power"] < len(row) and str(row[col_map["power"]]).strip():
            power = str(row[col_map["power"]]).strip()
        else:
            p_match = re.search(r'\b(\d{1,4}\s*(?:w|watt|وات)(?:\s*rms)?)\b', row_str, re.IGNORECASE)
            if p_match:
                power = p_match.group(1).upper()

        if "specs" in col_map and col_map["specs"] < len(row) and str(row[col_map["specs"]]).strip():
            specs = str(row[col_map["specs"]]).strip()

        raw_items.append({
            "code": code,
            "brand": brand,
            "subcat": subcat,
            "model": model,
            "power": power,
            "specs": specs,
            "price": str(price)
        })

    if raw_items:
        return clean_and_normalize_audio(raw_items)
    return []

def extract_audio_from_excel(file_bytes: bytes, filename: str = "") -> List[Dict[str, Any]]:
    """
    استخراج و تحلیل لیست سیستم صوتی از فایل اکسل (.xlsx / .csv):
    همانند ماژول لپ‌تاپ کاملاً بدون وابستگی خارجی اضافه.
    """
    fname = (filename or "").lower()
    rows = []

    from laptop_extractor import parse_xlsx_rows, parse_csv_rows

    if zipfile.is_zipfile(io.BytesIO(file_bytes)):
        rows = parse_xlsx_rows(file_bytes)
    elif fname.endswith(".csv") or fname.endswith(".tsv") or fname.endswith(".txt"):
        rows = parse_csv_rows(file_bytes)
    else:
        try:
            rows = parse_xlsx_rows(file_bytes)
        except Exception:
            rows = parse_csv_rows(file_bytes)

    if not rows:
        raise ValueError("هیچ داده یا سطری در فایل ارسالی شناسایی نشد. لطفاً از فرمت استاندارد .xlsx یا .csv استفاده فرمایید.")

    extracted = parse_audio_table_rows(rows)
    if not extracted:
        raise ValueError("هیچ سطر سیستم صوتی با مشخصات و قیمت معتبر در جدول فایل یافت نشد.")

    return extracted

def format_audio_preview_for_admin(audio_items: List[Dict[str, Any]], max_display: int = 10) -> str:
    """ایجاد پیام پیش‌نمایش متنی برای ادمین تلگرام جهت تایید نهایی"""
    if not audio_items:
        return "⚠️ هیچ محصولی یافت نشد."

    lines = []
    lines.append(f"📋 <b>تعداد اقلام شناسایی شده: {len(audio_items)} دستگاه</b>")
    lines.append("────────────────────")

    for i, it in enumerate(audio_items[:max_display], 1):
        brand = it.get("brand", "—")
        model = it.get("model", "—")
        subcat = it.get("subcategory", "—")
        price = it.get("price_formatted", "—")
        specs_d = it.get("specs") or {}
        power = specs_d.get("توان خروجی (Output Power)", "")
        p_str = f" | توان: {power}" if power and power != "-" else ""
        lines.append(f"<b>{i}. {brand} - {model}</b>")
        lines.append(f"   ▫️ دسته: {subcat}{p_str} | قیمت: <b>{price}</b>")

    if len(audio_items) > max_display:
        lines.append(f"<i>... و {len(audio_items) - max_display} مدل دیگر</i>")

    return "\n".join(lines)

def merge_audio_products(new_items: List[Dict[str, Any]]) -> Dict[str, int]:
    """ادغام یا به‌روزرسانی سیستم‌های صوتی"""
    existing = load_audio_catalog()
    existing_map = {item.get("id"): item for item in existing}
    
    added_count = 0
    updated_count = 0
    
    for item in new_items:
        item_id = item.get("id")
        if item_id in existing_map:
            existing_map[item_id].update(item)
            updated_count += 1
        else:
            existing_map[item_id] = item
            added_count += 1
            
    save_audio_catalog(list(existing_map.values()))
    return {"added": added_count, "updated": updated_count, "total": len(existing_map)}

def replace_audio_products(new_items: List[Dict[str, Any]]) -> Dict[str, int]:
    """جایگزینی کامل لیست سیستم‌های صوتی"""
    save_audio_catalog(new_items)
    return {"added": len(new_items), "updated": 0, "total": len(new_items), "replaced": True}
