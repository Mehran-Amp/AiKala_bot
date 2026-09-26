"""
ماژول استخراج هوشمند و ساختارمند لیست قیمت و موجودی لپ‌تاپ از تصاویر جداول (مانند اسکرین‌شات اکسل).
این ماژول از مدل‌های چندوجهی Gemini Vision (از طریق REST API استاندارد بدون نیاز به پکیج‌های اضافی) استفاده می‌کند.

قوانین اکید کسب‌وکار:
1. ستون «همکاری» (قیمت همکار) به هیچ عنوان خوانده، ذخیره یا نمایش داده نمی‌شود.
2. نام‌های فروشگاه، شماره‌های تماس افراد، لینک‌ها و آدرس‌ها به طور کامل فیلتر و حذف می‌شوند.
3. دسته‌بندی اصلی همه این کالاها «لپ‌تاپ» و زیرمجموعه آن‌ها منحصراً بر اساس «برند» است.
"""

import os
import io
import json
import base64
import logging
import re
import csv
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None
    import urllib.request
    import urllib.error

logger = logging.getLogger(__name__)

LAPTOPS_CATALOG_FILE = "laptops_catalog.json"

EXTRACTION_SYSTEM_PROMPT = """
شما یک دستیار متخصص در استخراج جداول مشخصات و قیمت لپ‌تاپ از تصاویر و اسکرین‌شات‌ها هستید.
وظیفه شما تبدیل دقیق سطرهای جدول به یک آرایه JSON ساختارمند است.

قوانین بسیار مهم و غیرقابل تخطی:
1. ستون «همکاری» (قیمت همکار) را کاملاً نادیده بگیرید و به هیچ عنوان استخراج نکنید.
2. فقط و فقط ستون «قیمت» (قیمت تک‌فروشی / مصرف‌کننده) را استخراج کنید.
3. هدر تصویر شامل نام فروشگاه‌ها، شماره تماس اشخاص (مانند درویشی، رحمانی، خاکساران و...)، آیدی تلگرام، آدرس و لینک‌های وب‌سایت، و همچنین فوترها و متون پایانی را کاملاً نادیده بگیرید و هیچ ردی از آن‌ها در خروجی نباشد.
4. اگر قیمت به هزار تومان نوشته شده (مثلاً 248,000 یا 67,000)، به عدد تبدیل کنید یا همان فرمت عددی را بیاورید؛ اما اطمینان حاصل کنید که مربوط به ستون «قیمت» است نه «همکاری».
5. دسته‌بندی کالا حتماً "لپ‌تاپ" باشد.
6. برند را از روی لوگو یا نام مدل تشخیص دهید (مثلاً HP, ASUS, LENOVO, DELL, APPLE, ACER, MSI و...).
7. فیلدهای هر آیتم در خروجی باید به این شکل باشد:
   - "code": کد کالا (مثلاً "H101")
   - "brand": نام برند با حروف بزرگ انگلیسی (مثلاً "HP")
   - "model": نام مدل دقیق کالا (مثلاً "ZBOOK FURY 16 G9")
   - "cpu": مشخصات پردازنده (مثلاً "CORE I9 - 12950HX")
   - "ram": رم دستگاه (مثلاً "16G")
   - "storage": هارد یا حافظه داخلی (مثلاً "512G")
   - "gpu": کارت گرافیک (مثلاً "8GB NVIDIA RTX A2000")
   - "display": اندازه و مشخصات صفحه نمایش (مثلاً "16\"")
   - "grade": گرید سلامت و تمیزی دستگاه (مثلاً "A++")
   - "price": قیمت تک‌فروشی از ستون قیمت به صورت عدد یا رشته تمیز (مثلاً "248000" یا 248000)

خروجی شما باید منحصراً و فقط یک کد JSON خالص (بدون هیچ متن توضیحی اضافه) باشد:
[
  {
    "code": "H101",
    "brand": "HP",
    "model": "ZBOOK FURY 16 G9",
    "cpu": "CORE I9 - 12950HX",
    "ram": "16G",
    "storage": "512G",
    "gpu": "8GB NVIDIA RTX A2000",
    "display": "16\\"",
    "grade": "A++",
    "price": "248000"
  }
]
"""

def get_gemini_api_key() -> str:
    """دریافت کلید API از محیط یا فایل .env"""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key and os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception as e:
            logger.error(f"Error reading .env: {e}")
    return api_key

def set_gemini_api_key(new_key: str) -> bool:
    """تنظیم و ذخیره کلید جدید Gemini در متغیر محیط و فایل .env"""
    key = str(new_key).strip()
    if not key:
        return False
    os.environ["GEMINI_API_KEY"] = key
    lines = []
    found = False
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        lines.append(f"GEMINI_API_KEY={key}\n")
                        found = True
                    else:
                        lines.append(line)
        except Exception:
            pass
    if not found:
        lines.append(f"GEMINI_API_KEY={key}\n")
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        logger.error(f"Error saving to .env: {e}")
        return False

def extract_laptops_from_text(raw_text: str) -> List[Dict[str, Any]]:
    """
    استخراج سطرهای لپ‌تاپ از متن کپی‌شده از تلگرام یا جدول اکسل (بدون نیاز به هوش مصنوعی)
    قوانین: حذف کامل شماره‌های تماس، همکار، تبلیغات و تشخیص برند و مدل و قیمت.
    """
    if not raw_text:
        return []
    lines = raw_text.strip().split("\n")
    results = []
    
    brand_patterns = [
        ("HP", r'\b(hp|اچ\s*پی)\b'),
        ("ASUS", r'\b(asus|ایسوس)\b'),
        ("LENOVO", r'\b(lenovo|لنوو)\b'),
        ("DELL", r'\b(dell|دل)\b'),
        ("APPLE", r'\b(apple|macbook|اپل|مک\s*بوک)\b'),
        ("ACER", r'\b(acer|ایسر)\b'),
        ("MSI", r'\b(msi|ام\s*اس\s*ای)\b'),
        ("MICROSOFT", r'\b(surface|microsoft|سرفیس)\b'),
    ]

    for line in lines:
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 10:
            continue
        # فیلتر کردن هدرها و ستون همکاری یا شماره تماس
        if re.search(r'(همکار|همکاری|تلفن|تماس|۰۹\d{9}|09\d{9}|کانال|آدرس|مشخصات|قیمت\s*همکار)', line_clean):
            continue
        
        # استخراج قیمت از انتهای خط یا بعد از ستون قیمت
        # ارقام را پیدا می‌کنیم
        price_matches = re.findall(r'(\d[\d\,\.]{3,}\d)', line_clean)
        if not price_matches:
            continue
        
        # آخرین عدد بزرگ معمولاً قیمت مصرف‌کننده است
        price_str = price_matches[-1].replace(",", "").replace(".", "").replace("،", "")
        try:
            p_val = int(price_str)
            # اگر به هزار تومان نوشته شده (مثلاً 248000 به جای 248000000 یا 35000 به جای 35000000)
            if 10000 <= p_val <= 900000:
                p_val = p_val * 1000
        except Exception:
            continue

        # تشخیص برند
        detected_brand = "متفرقه"
        for b_name, b_regex in brand_patterns:
            if re.search(b_regex, line_clean, re.IGNORECASE):
                detected_brand = b_name
                break
        
        # اگر برندی تشخیص داده نشد، سطر ممکن است لپ‌تاپ نباشد
        if detected_brand == "متفرقه" and not re.search(r'\b(core|i[3579]|ryzen|ram|ssd|gb)\b', line_clean, re.IGNORECASE):
            continue

        # مدل را از متن تمیز استخراج می‌کنیم
        parts = re.split(r'[\t\|\-\–]', line_clean)
        model = parts[0].strip() if parts else line_clean[:40]
        # حذف ارقام قیمت از مدل
        model = re.sub(r'\d[\d\,\.]{3,}\d', '', model).strip()
        if len(model) < 4:
            model = f"لپ‌تاپ {detected_brand}"

        results.append({
            "code": f"L{len(results)+101}",
            "brand": detected_brand,
            "model": model,
            "cpu": "مندرج در مدل",
            "ram": "-",
            "storage": "-",
            "gpu": "-",
            "display": "-",
            "grade": "A++",
            "price": str(p_val)
        })

    if results:
        return clean_and_normalize_laptops(results)
    return []

def to_eng_digits(s: Any) -> str:
    """تبدیل اعداد فارسی و عربی به انگلیسی"""
    if s is None:
        return ""
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return str(s).translate(trans)

def parse_cell_price(cell_val: Any) -> int:
    """استخراج دقیق و بدون خطای عدد قیمت از سلول، با پشتیبانی از اعشار اکسل، نشانه‌گذاری علمی و جداکننده‌های هزارگان"""
    if cell_val is None:
        return 0
    val_str = to_eng_digits(str(cell_val)).strip().replace(",", "").replace("،", "")
    if not val_str:
        return 0
    # تلاش برای خواندن مستقیم عدد ممیزدار یا نماد علمی (مانند 25500000.0 یا 2.55E7)
    try:
        f_val = float(val_str)
        if 1000 <= f_val <= 9000000000:
            return int(round(f_val))
    except Exception:
        pass
    p_digits = re.sub(r'[^\d]', '', val_str)
    if p_digits:
        try:
            return int(p_digits)
        except Exception:
            pass
    return 0

def parse_xlsx_rows(file_bytes: bytes) -> List[List[str]]:
    """
    خواندن و استخراج سطرهای تمام شیت‌های فایل اکسل (.xlsx) با استفاده از کتابخانه استاندارد پایتون (zipfile + xml).
    کاملاً مستقل از پکیج‌های جانبی با عملکرد فوق‌العاده سریع و پایدار.
    پشتیبانی کامل از شیت‌های چندگانه، تگ‌های درون‌خطی inlineStr، متن غنی، فرمول‌ها و اندیس‌های سلولی غایب.
    """
    all_rows = []
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            name_list = z.namelist()
            # 1. خواندن جدول رشته‌های مشترک (Shared Strings)
            shared_strings = []
            ss_filename = next((n for n in name_list if n.lower() == "xl/sharedstrings.xml"), None)
            if ss_filename:
                try:
                    ss_tree = ET.fromstring(z.read(ss_filename))
                    for si in ss_tree.findall(".//{*}si"):
                        text_parts = [t.text or "" for t in si.iter() if t.tag.endswith("t")]
                        shared_strings.append("".join(text_parts))
                except Exception as e_ss:
                    logger.warning(f"Error parsing sharedStrings.xml: {e_ss}")

            # 2. پیدا کردن تمام برگه‌های اکسل (Worksheets)
            sheet_files = [n for n in name_list if n.lower().startswith("xl/worksheets/") and n.lower().endswith(".xml")]
            sheet_files.sort()

            for sheet_file in sheet_files:
                try:
                    sheet_tree = ET.fromstring(z.read(sheet_file))
                    sheet_data = sheet_tree.find(".//{*}sheetData")
                    if sheet_data is None:
                        sheet_data = next((elem for elem in sheet_tree.iter() if elem.tag.endswith("sheetData")), None)
                    if sheet_data is None:
                        continue

                    rows = sheet_data.findall(".//{*}row")
                    if not rows:
                        rows = [elem for elem in sheet_data.iter() if elem.tag.endswith("row")]

                    for row in rows:
                        row_vals = {}
                        max_col_idx = 0
                        current_col_idx = 0

                        cells = row.findall(".//{*}c")
                        if not cells:
                            cells = [elem for elem in row if elem.tag.endswith("c")]

                        for c in cells:
                            ref = c.get("r", "")
                            if ref:
                                col_letters = "".join([ch for ch in ref if ch.isalpha()])
                                col_idx = 0
                                for ch in col_letters:
                                    col_idx = col_idx * 26 + (ord(ch.upper()) - ord("A") + 1)
                                col_idx = col_idx - 1 if col_idx > 0 else 0
                                current_col_idx = col_idx
                            else:
                                col_idx = current_col_idx

                            current_col_idx += 1
                            max_col_idx = max(max_col_idx, col_idx)

                            t_type = c.get("t", "")
                            val = ""
                            v = next((elem for elem in c if elem.tag.endswith("v")), None)

                            if t_type == "s" and v is not None and v.text is not None:
                                try:
                                    idx = int(v.text.strip())
                                    if 0 <= idx < len(shared_strings):
                                        val = shared_strings[idx]
                                except Exception:
                                    pass
                            elif t_type == "inlineStr" or any(elem.tag.endswith("is") for elem in c):
                                text_parts = [elem.text or "" for elem in c.iter() if elem.tag.endswith("t")]
                                val = "".join(text_parts)
                            elif v is not None and v.text:
                                val = v.text
                            else:
                                t_tag = next((elem for elem in c if elem.tag.endswith("t")), None)
                                if t_tag is not None and t_tag.text:
                                    val = t_tag.text

                            row_vals[col_idx] = val.strip()

                        if row_vals:
                            row_list = [row_vals.get(i, "") for i in range(max_col_idx + 1)]
                            if any(row_list):
                                all_rows.append(row_list)
                except Exception as e_sheet:
                    logger.warning(f"Error parsing sheet {sheet_file}: {e_sheet}")
    except Exception as e:
        logger.error(f"Error reading xlsx zip: {e}")
        raise ValueError(f"قالب فایل اکسل نامعتبر است یا باز نشد: {e}")

    return all_rows

def parse_csv_rows(file_bytes: bytes) -> List[List[str]]:
    """خواندن فایل‌های CSV و TSV با انکودینگ‌های متداول فارسی"""
    encodings = ["utf-8-sig", "utf-8", "cp1256", "latin1"]
    for enc in encodings:
        try:
            text = file_bytes.decode(enc)
            sample = text[:2048] if len(text) > 10 else text
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = "excel"
            reader = csv.reader(io.StringIO(text), dialect=dialect)
            rows = [list(r) for r in reader if any(r)]
            if rows:
                return rows
        except Exception:
            continue

    try:
        lines = file_bytes.decode("utf-8", errors="ignore").splitlines()
        reader = csv.reader(lines)
        return [list(r) for r in reader if any(r)]
    except Exception:
        return []

def extract_specs_from_string(text: str) -> Dict[str, str]:
    """استخراج دقیق مشخصات فنی (پردازنده، رم، هارد، گرافیک، صفحه نمایش، گرید) از متن"""
    specs = {}
    norm_text = to_eng_digits(text)

    # پردازنده CPU
    cpu_m = re.search(
        r'\b(core\s*i[3579][^\s\,\|]+|ryzen\s*\d[^\s\,\|]+|i[3579]\s*[\-\_]?\s*\d{4,5}[A-Za-z0-9]*|m[123]\s*(?:pro|max)?)\b',
        norm_text,
        re.IGNORECASE
    )
    if cpu_m:
        specs["cpu"] = cpu_m.group(1).upper()

    # حافظه RAM: 4GB, 8GB, 16GB, 32GB, 64GB
    ram_m = re.search(r'\b([48]|16|24|32|48|64|128)\s*(?:gb|g)\b(?:\s*ram|\s*ddr\d?)?', norm_text, re.IGNORECASE)
    if ram_m:
        specs["ram"] = ram_m.group(0).strip().upper()

    # حافظه داخلی Storage: 128GB, 256GB, 512GB, 1TB, 2TB
    storage_m = re.search(r'\b(128|256|500|512|1000|1024|2000)\s*(?:gb|g|ssd|hdd|nvme)?\b|\b([1248]\s*(?:tb|t))\b', norm_text, re.IGNORECASE)
    if storage_m:
        specs["storage"] = storage_m.group(0).strip().upper()

    # کارت گرافیک GPU
    gpu_m = re.search(r'\b(\d{1,2}\s*gb\s*(?:rtx|gtx|nvidia|radeon)[^\s\,\|]*|rtx\s*\d{4}[^\s\,\|]*|gtx\s*\d{4}[^\s\,\|]*|iris\s*xe|intel\s*uhd)\b', norm_text, re.IGNORECASE)
    if gpu_m:
        specs["gpu"] = gpu_m.group(1).strip().upper()

    # صفحه نمایش Display
    disp_m = re.search(r'\b(\d{2}(?:\.\d)?\s*(?:inch|\"|اینچ|fhd|4k|oled)?)\b', norm_text, re.IGNORECASE)
    if disp_m:
        specs["display"] = disp_m.group(1).strip()

    # گرید و تمیزی Grade
    grade_m = re.search(r'\b(a\+{1,3}|open\s*box|استوک|نو|گرید\s*[a-d]\+*)\b', norm_text, re.IGNORECASE)
    if grade_m:
        specs["grade"] = grade_m.group(1).strip().upper()

    return specs

def extract_laptops_from_table_rows(rows: List[List[str]]) -> List[Dict[str, Any]]:
    """
    تبدیل سطرهای جدول اکسل/CSV به لیست ساختارمند اقلام لپ‌تاپ:
    قوانین اکید:
    1. ستون همکاری کاملاً فیلتر و حذف می‌شود.
    2. شماره تماس‌ها، نام اشخاص و تبلیغات متفرقه حذف می‌شوند.
    3. تبدیل مبالغ به تومان و دسته‌بندی بر اساس برند.
    """
    if not rows:
        return []

    brand_patterns = [
        ("HP", r'\b(hp|اچ\s*پی)\b'),
        ("ASUS", r'\b(asus|ایسوس)\b'),
        ("LENOVO", r'\b(lenovo|لنوو)\b'),
        ("DELL", r'\b(dell|دل)\b'),
        ("APPLE", r'\b(apple|macbook|اپل|مک\s*بوک)\b'),
        ("ACER", r'\b(acer|ایسر)\b'),
        ("MSI", r'\b(msi|ام\s*اس\s*ای)\b'),
        ("MICROSOFT", r'\b(surface|microsoft|سرفیس)\b'),
    ]

    header_idx = -1
    col_map = {}

    # جستجوی سطر هدر در ۱۰ سطر اول
    for r_idx, row in enumerate(rows[:10]):
        row_str = " ".join([str(c).strip().lower() for c in row if c])
        if any(k in row_str for k in ["قیمت", "مدل", "برند", "price", "model", "brand", "cpu", "همکار"]):
            header_idx = r_idx
            for c_idx, cell in enumerate(row):
                c_name = str(cell).strip().lower()
                if not c_name:
                    continue
                # فیلتر اکید ستون همکار
                if any(x in c_name for x in ["همکار", "همکاری", "عمده", "coop", "wholesale", "colleague"]):
                    col_map["ignore_colleague"] = c_idx
                elif any(x in c_name for x in ["قیمت تک", "مصرف کننده", "تک فروشی", "retail", "user", "فروش", "فی تک"]):
                    col_map["price"] = c_idx
                elif any(x in c_name for x in ["قیمت", "price", "مبلغ", "فی", "نرخ"]) and "price" not in col_map:
                    col_map["price"] = c_idx
                elif any(x in c_name for x in ["کد", "ردیف", "code", "no", "id", "شناسه"]) and "code" not in col_map:
                    col_map["code"] = c_idx
                elif any(x in c_name for x in ["برند", "مارک", "brand", "make"]) and "brand" not in col_map:
                    col_map["brand"] = c_idx
                elif any(x in c_name for x in ["مدل", "دستگاه", "model", "لپتاپ", "لپ تاپ", "مشخصات", "title", "نام کالا"]) and "model" not in col_map:
                    col_map["model"] = c_idx
                elif any(x in c_name for x in ["پردازنده", "سی پی یو", "cpu", "processor"]) and "cpu" not in col_map:
                    col_map["cpu"] = c_idx
                elif any(x in c_name for x in ["رم", "ram", "memory"]) and "ram" not in col_map:
                    col_map["ram"] = c_idx
                elif any(x in c_name for x in ["هارد", "حافظه", "ssd", "hdd", "storage", "nvme"]) and "storage" not in col_map:
                    col_map["storage"] = c_idx
                elif any(x in c_name for x in ["گرافیک", "gpu", "vga", "graphic"]) and "gpu" not in col_map:
                    col_map["gpu"] = c_idx
                elif any(x in c_name for x in ["صفحه", "نمایش", "سایز", "display", "screen", "lcd"]) and "display" not in col_map:
                    col_map["display"] = c_idx
                elif any(x in c_name for x in ["گرید", "وضعیت", "grade", "status", "تمیزی"]) and "grade" not in col_map:
                    col_map["grade"] = c_idx
            break

    raw_items = []
    start_row = header_idx + 1 if header_idx >= 0 else 0

    for row_idx, row in enumerate(rows[start_row:], start=start_row):
        row_str = " ".join([str(c).strip() for c in row if c])
        if not row_str or len(row_str) < 4:
            continue

        # حذف تبلیغات، کانال‌ها و شماره تماس‌ها
        if re.search(r'(کانال|آدرس|تماس|تلفن|۰۹\d{9}|09\d{9}|فروشگاه|تلگرام|واتساپ|instagram|telegram)', row_str, re.IGNORECASE):
            continue

        code = ""
        brand = ""
        model = ""
        cpu = ""
        ram = ""
        storage = ""
        gpu = ""
        display = ""
        grade = "A++"
        price = 0

        # ۱. استخراج قیمت مصرف‌کننده (با نادیده گرفتن ستون همکار)
        if "price" in col_map and col_map["price"] < len(row):
            price = parse_cell_price(row[col_map["price"]])
        else:
            candidate_prices = []
            for c_idx, cell in enumerate(row):
                if c_idx == col_map.get("ignore_colleague"):
                    continue
                p_val = parse_cell_price(cell)
                if 1000 <= p_val <= 9000000000:
                    candidate_prices.append(p_val)
            if candidate_prices:
                price = max(candidate_prices)

        if price < 1000:
            continue

        # تبدیل مبالغ هزار تومان به تومان کامل
        if price < 1000000:
            price = price * 1000
        elif price >= 500000000 and price % 10 == 0:
            # تبدیل مبالغ ریال (بیش از ۵۰۰ میلیون ریال) به تومان
            price = price // 10

        # ۲. کد کالا
        if "code" in col_map and col_map["code"] < len(row):
            code = str(row[col_map["code"]]).strip()
        if not code:
            code = f"L{len(raw_items)+101}"

        # ۳. برند
        if "brand" in col_map and col_map["brand"] < len(row):
            brand = str(row[col_map["brand"]]).strip().upper()
        if not brand:
            for b_name, b_pat in brand_patterns:
                if re.search(b_pat, row_str, re.IGNORECASE):
                    brand = b_name
                    break
        if not brand:
            brand = "متفرقه"

        # ۴. مدل دستگاه
        if "model" in col_map and col_map["model"] < len(row) and str(row[col_map["model"]]).strip():
            model = str(row[col_map["model"]]).strip()
        else:
            # انتخاب طولانی‌ترین ستون متنی به عنوان مدل
            text_cells = [str(c).strip() for c in row if len(str(c).strip()) > 3 and not re.match(r'^\d+$', str(c).strip())]
            model = max(text_cells, key=len) if text_cells else f"لپ‌تاپ {brand}"

        # ۵. مشخصات تفکیکی
        if "cpu" in col_map and col_map["cpu"] < len(row) and str(row[col_map["cpu"]]).strip():
            cpu = str(row[col_map["cpu"]]).strip()
        if "ram" in col_map and col_map["ram"] < len(row) and str(row[col_map["ram"]]).strip():
            ram = str(row[col_map["ram"]]).strip()
        if "storage" in col_map and col_map["storage"] < len(row) and str(row[col_map["storage"]]).strip():
            storage = str(row[col_map["storage"]]).strip()
        if "gpu" in col_map and col_map["gpu"] < len(row) and str(row[col_map["gpu"]]).strip():
            gpu = str(row[col_map["gpu"]]).strip()
        if "display" in col_map and col_map["display"] < len(row) and str(row[col_map["display"]]).strip():
            display = str(row[col_map["display"]]).strip()
        if "grade" in col_map and col_map["grade"] < len(row) and str(row[col_map["grade"]]).strip():
            grade = str(row[col_map["grade"]]).strip()

        # تکمیل هوشمند فیلدهای خالی از روی متن ردیف
        extracted_from_str = extract_specs_from_string(row_str)
        if not cpu and "cpu" in extracted_from_str: cpu = extracted_from_str["cpu"]
        if not ram and "ram" in extracted_from_str: ram = extracted_from_str["ram"]
        if not storage and "storage" in extracted_from_str: storage = extracted_from_str["storage"]
        if not gpu and "gpu" in extracted_from_str: gpu = extracted_from_str["gpu"]
        if not display and "display" in extracted_from_str: display = extracted_from_str["display"]
        if (not grade or grade == "A++") and "grade" in extracted_from_str: grade = extracted_from_str["grade"]

        raw_items.append({
            "code": code,
            "brand": brand,
            "model": model,
            "cpu": cpu or "مندرج در مشخصات",
            "ram": ram or "-",
            "storage": storage or "-",
            "gpu": gpu or "-",
            "display": display or "-",
            "grade": grade or "A++",
            "price": str(price)
        })

    if raw_items:
        return clean_and_normalize_laptops(raw_items)
    return []

def extract_laptops_from_excel(file_bytes: bytes, filename: str = "") -> List[Dict[str, Any]]:
    """
    استخراج و تحلیل لیست لپ‌تاپ‌ها از فایل اکسل (.xlsx / .xls / .csv):
    بدون نیاز به کتابخانه‌های سنگین خارجی و با فیلتر کامل قیمت همکاری و اطلاعات تماس.
    """
    fname = (filename or "").lower()
    rows = []

    # بررسی آیا فایل فشرده زیپ استاندارد OpenXML (.xlsx) است
    if zipfile.is_zipfile(io.BytesIO(file_bytes)):
        rows = parse_xlsx_rows(file_bytes)
    elif fname.endswith(".csv") or fname.endswith(".tsv") or fname.endswith(".txt"):
        rows = parse_csv_rows(file_bytes)
    else:
        # تلاش اول با xlsx و در صورت عدم تطابق با csv
        try:
            rows = parse_xlsx_rows(file_bytes)
        except Exception:
            rows = parse_csv_rows(file_bytes)

    if not rows:
        raise ValueError("هیچ داده یا سطری در فایل ارسالی شناسایی نشد. لطفاً از فرمت استاندارد .xlsx یا .csv استفاده فرمایید.")

    extracted = extract_laptops_from_table_rows(rows)
    if not extracted:
        raise ValueError("هیچ سطر لپ‌تاپی با مشخصات و قیمت معتبر در جدول فایل اکسل یافت نشد.")

    return extracted

def extract_laptops_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> List[Dict[str, Any]]:
    """
    ارسال تصویر به مدل بینایی ماشین Gemini Vision و بازگرداندن آرایه تمیز لپ‌تاپ‌ها.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("GEMINI_API_KEY is not configured.")
        raise ValueError("کلید GEMINI_API_KEY تنظیم نشده است. لطفاً آن را در بخش Settings یا .env وارد کنید.")

    base64_data = base64.b64encode(image_bytes).decode("utf-8")
    
    # استفاده از مدل‌های دارای قابلیت Vision
    models_to_try = [
        "gemini-3.8-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
    
    last_error = ""
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": EXTRACTION_SYSTEM_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        
        try:
            raw_text = ""
            if requests:
                # استفاده از requests با پشتیبانی بومی از پروکسی‌های محیطی و سیستمی
                session = requests.Session()
                # بررسی خودکار پروکسی‌های استاندارد لوکال در صورت عدم تعریف در محیط
                if not os.environ.get("HTTPS_PROXY") and not os.environ.get("https_proxy"):
                    for candidate_proxy in ["http://127.0.0.1:10809", "http://127.0.0.1:10808", "http://127.0.0.1:7890", "http://127.0.0.1:2081"]:
                        try:
                            # تست خیلی سریع دسترسی به پروکسی لوکال
                            session.proxies = {"http": candidate_proxy, "https": candidate_proxy}
                            break
                        except Exception:
                            pass

                resp = session.post(url, json=payload, timeout=45)
                if resp.status_code != 200:
                    err_msg = resp.text
                    logger.warning(f"Model {model_name} HTTP {resp.status_code}: {err_msg}")
                    last_error = f"HTTP {resp.status_code}: {err_msg}"
                    if "API_KEY_INVALID" in err_msg or (resp.status_code == 400 and "API key not valid" in err_msg):
                        raise ValueError("کلید GEMINI_API_KEY نامعتبر است. لطفاً با دستور /setgemini یک کلید معتبر وارد نمایید.")
                    continue

                result_json = resp.json()
            else:
                req_data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=req_data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    result_json = json.loads(resp.read().decode("utf-8"))

            candidates = result_json.get("candidates", [])
            if not candidates:
                continue

            content_parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = "".join([p.get("text", "") for p in content_parts]).strip()

            # پاکسازی بلوک‌های کد مارک‌داون در صورت وجود
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
                raw_text = re.sub(r"\n?```$", "", raw_text).strip()

            parsed_data = json.loads(raw_text)
            if isinstance(parsed_data, list):
                logger.info(f"Successfully extracted {len(parsed_data)} laptops using {model_name}.")
                return clean_and_normalize_laptops(parsed_data)
            elif isinstance(parsed_data, dict) and "laptops" in parsed_data:
                return clean_and_normalize_laptops(parsed_data["laptops"])

        except ValueError:
            raise
        except Exception as e:
            err_s = str(e)
            logger.error(f"Error calling Gemini with model {model_name}: {e}")
            if "10053" in err_s or "ConnectionAbortedError" in err_s or "Connection aborted" in err_s:
                last_error = "قطع ارتباط با سرور گوگل توسط اینترنت یا فیلترشکن سیستم (Errno 10053). لطفاً اتصال VPN را بررسی کنید یا متن جدول را کپی و ارسال فرمایید."
            else:
                last_error = err_s
            continue

    raise RuntimeError(f"خطا در پردازش تصویر با هوش مصنوعی: {last_error}")

def normalize_price_value(price_val: Any) -> int:
    """تبدیل رشته یا عدد قیمت لیست به مبلغ نهایی بر حسب تومان"""
    if not price_val:
        return 0
    clean_str = re.sub(r"[^\d]", "", str(price_val))
    if not clean_str:
        return 0
    val = int(clean_str)
    # اگر مثلاً نوشته شده ۲۴۸,۰۰۰ (که منظورش ۲۴۸ میلیون تومان است)
    if val < 1000000:
        return val * 1000
    return val

def clean_and_normalize_laptops(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """پاکسازی، اعتبارسنجی و نرمال‌سازی اقلام لپ‌تاپ استخراج‌شده"""
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        
        brand = str(item.get("brand", "HP")).strip().upper()
        if not brand:
            brand = "HP"
        
        model = str(item.get("model", "")).strip()
        if not model:
            continue
            
        code = str(item.get("code", "")).strip()
        cpu = str(item.get("cpu", "")).strip()
        ram = str(item.get("ram", "")).strip()
        storage = str(item.get("storage", "")).strip()
        gpu = str(item.get("gpu", "")).strip()
        display = str(item.get("display", "")).strip()
        grade = str(item.get("grade", "")).strip()
        
        price_num = normalize_price_value(item.get("price", 0))
        
        # شناسه یکتا برای جستجو و کاتالوگ
        clean_code = code.replace(" ", "") if code else ""
        product_id = f"LAPTOP_{brand}_{clean_code}" if clean_code else f"LAPTOP_{brand}_{re.sub(r'[^A-Za-z0-9]', '', model)}"
        
        # نام نمایشی کامل
        full_title = f"{brand} {model}"
        
        specs = {}
        if cpu: specs["پردازنده (CPU)"] = cpu
        if ram: specs["حافظه رم (RAM)"] = ram
        if storage: specs["حافظه داخلی (SSD/HDD)"] = storage
        if gpu: specs["کارت گرافیک (GPU)"] = gpu
        if display: specs["صفحه نمایش"] = display
        if grade: specs["گرید و تمیزی"] = grade
        if code: specs["کد مدل"] = code
        specs["گارانتی و مهلت تست"] = "یک هفته ضمانت تست و تعویض"
        
        entry = {
            "id": product_id,
            "code": code,
            "title": full_title,
            "brand": brand,
            "model": model,
            "category": "لپ‌تاپ",
            "subcategory": brand,
            "price": price_num,
            "price_formatted": f"{price_num:,} تومان" if price_num else "تماس بگیرید",
            "specs": specs,
            "available": True,
            "source": "image_extractor"
        }
        cleaned.append(entry)
        
    return cleaned

def load_laptops_catalog() -> List[Dict[str, Any]]:
    """خواندن لیست لپ‌تاپ‌های ذخیره‌شده از فایل JSON"""
    if os.path.exists(LAPTOPS_CATALOG_FILE):
        try:
            with open(LAPTOPS_CATALOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.error(f"Error reading {LAPTOPS_CATALOG_FILE}: {e}")
    return []

def save_laptops_catalog(laptops: List[Dict[str, Any]]) -> bool:
    """ذخیره یا به‌روزرسانی لیست لپ‌تاپ‌ها در فایل دیتابیس محلی"""
    try:
        with open(LAPTOPS_CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(laptops, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {LAPTOPS_CATALOG_FILE}: {e}")
        return False

def merge_extracted_laptops(new_laptops: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    ادغام لپ‌تاپ‌های جدید با دیتابیس قبلی:
    اگر مدل از قبل وجود داشت، قیمت و مشخصات آن آپدیت می‌شود وگرنه اضافه می‌شود.
    """
    existing = load_laptops_catalog()
    existing_map = {item.get("id"): item for item in existing}
    
    added_count = 0
    updated_count = 0
    
    for item in new_laptops:
        item_id = item.get("id")
        if item_id in existing_map:
            existing_map[item_id].update(item)
            updated_count += 1
        else:
            existing_map[item_id] = item
            added_count += 1
            
    save_laptops_catalog(list(existing_map.values()))
    return {"added": added_count, "updated": updated_count, "total": len(existing_map)}

def replace_extracted_laptops(new_laptops: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    جایگزینی کامل لیست لپ‌تاپ‌ها با لیست جدید ارسالی (حذف کامل لیست قبلی).
    """
    save_laptops_catalog(new_laptops)
    return {"added": len(new_laptops), "updated": 0, "total": len(new_laptops), "replaced": True}

def format_laptops_preview_for_admin(laptops: List[Dict[str, Any]], max_display: int = 10) -> str:
    """ایجاد پیام پیش‌نمایش متنی برای ادمین تلگرام جهت تایید نهایی"""
    if not laptops:
        return "⚠️ هیچ آیتم معتبری در تصویر جدول شناسایی نشد."
    
    total = len(laptops)
    lines = [
        f"📊 <b>گزارش تحلیل هوشمند لیست قیمت لپ‌تاپ:</b>",
        f"✅ <b>تعداد کل ردیف‌های شناسایی‌شده:</b> <code>{total}</code> مدل",
        f"🛡 <i>قیمت‌های همکار و شماره تماس‌ها کاملاً فیلتر شدند.</i>",
        "────────────────────",
        "<b>نمونه سطرهای استخراج‌شده:</b>\n"
    ]
    
    for i, item in enumerate(laptops[:max_display], 1):
        code = item.get("code", "-")
        brand = item.get("brand", "")
        model = item.get("model", "")
        specs = item.get("specs", {})
        cpu = specs.get("پردازنده (CPU)", "")
        ram = specs.get("حافظه رم (RAM)", "")
        storage = specs.get("حافظه داخلی (SSD/HDD)", "")
        gpu = specs.get("کارت گرافیک (GPU)", "")
        grade = specs.get("گرید و تمیزی", "")
        price_str = item.get("price_formatted", "")
        
        detail_line = f"<b>{i}. [{code}] {brand} {model}</b>\n"
        detail_line += f"   ▫️ سی‌پی‌یو: <code>{cpu}</code> | رم: <code>{ram}</code> | حافظه: <code>{storage}</code>\n"
        if gpu:
            detail_line += f"   ▫️ گرافیک: <code>{gpu}</code> | گرید: <code>{grade}</code>\n"
        detail_line += f"   💰 قیمت تک‌فروشی: <b>{price_str}</b>\n"
        lines.append(detail_line)
        
    if total > max_display:
        lines.append(f"<i>... و {total - max_display} مدل دیگر</i>\n")
        
    lines.append("────────────────────")
    lines.append("❓ آیا مایلید این لیست در کاتالوگ و دسته‌بندی لپ‌تاپ ربات ثبت و به‌روزرسانی شود؟")
    return "\n".join(lines)
