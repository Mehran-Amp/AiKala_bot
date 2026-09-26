"""
Async SQLite Database Manager (database.py)
===========================================
Handles all local caching, user requests, orders, channel posts, price history,
and multi-channel monitoring.
Optimized for high concurrency with WAL mode and busy timeout.
"""
import time


import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import aiosqlite

try:
    import config
    DB_PATH = getattr(config, "DB_PATH", "bot_data.db")
    PRICE_HISTORY_DAYS = getattr(config, "PRICE_HISTORY_DAYS", 10)
except ImportError:
    DB_PATH = "bot_data.db"
    PRICE_HISTORY_DAYS = 10

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database manager with robust concurrency support."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init(self):
        """Initialize database tables and indexes with WAL mode."""
        async with aiosqlite.connect(self.db_path) as db:
            # فعالسازی حالت WAL برای عملکرد موازی و عدم قفل شدن دیتابیس
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA busy_timeout = 5000;")
            await db.execute("PRAGMA synchronous = NORMAL;")

            await db.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT UNIQUE,
                    data_id TEXT,
                    category_key TEXT,
                    category_name TEXT,
                    subcategory TEXT,
                    name TEXT,
                    model_number TEXT,
                    brand TEXT,
                    size TEXT,
                    price INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'b',
                    assembly TEXT,
                    score TEXT,
                    year TEXT,
                    resolution TEXT,
                    panel TEXT,
                    refresh_rate TEXT,
                    backlight TEXT,
                    os TEXT,
                    capacity_btu TEXT,
                    ac_type TEXT,
                    temp_range TEXT,
                    room_size TEXT,
                    energy_consumption TEXT,
                    performance TEXT,
                    key_features TEXT,
                    plan TEXT,
                    capacity_foot TEXT,
                    num_doors TEXT,
                    capacity_kg TEXT,
                    baskets TEXT,
                    more_details TEXT,
                    ai_generated_description TEXT DEFAULT '',
                    category TEXT DEFAULT 'default',
                    colors_json TEXT DEFAULT '{}',
                    specs_json TEXT DEFAULT '{}',
                    url TEXT,
                    image_url TEXT,
                    source TEXT DEFAULT 'MomtazKalla',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE NOT NULL,
                    channel_name TEXT,
                    keywords TEXT DEFAULT '',
                    active INTEGER DEFAULT 1,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS channel_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL,
                    channel_name TEXT,
                    message_id INTEGER,
                    text TEXT,
                    cleaned_text TEXT,
                    date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    product_id TEXT,
                    product_name TEXT NOT NULL,
                    city TEXT,
                    color TEXT,
                    status TEXT DEFAULT 'Pending',
                    admin_response TEXT,
                    final_price TEXT,
                    shipping_method TEXT DEFAULT 'freight',
                    invoice_link TEXT,
                    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_code TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    product_id TEXT,
                    product_name TEXT,
                    full_name TEXT,
                    phone1 TEXT,
                    phone2 TEXT,
                    province_city TEXT,
                    address TEXT,
                    postal_code TEXT,
                    total_price TEXT DEFAULT '0',
                    deposit_amount TEXT,
                    shipping_method TEXT DEFAULT 'freight',
                    receipt_file_id TEXT,
                    receipt_text TEXT,
                    status TEXT DEFAULT 'Awaiting_Payment',
                    admin_note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    price TEXT,
                    color TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_last_view (
                    user_id INTEGER PRIMARY KEY,
                    last_view_date TIMESTAMP DEFAULT '1970-01-01'
                );

                -- جدول کانال‌های تحت پایش
                CREATE TABLE IF NOT EXISTS monitored_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE NOT NULL,
                    channel_name TEXT,
                    keywords TEXT DEFAULT '',
                    active INTEGER DEFAULT 1,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- جدول کارشناسان پشتیبانی و مشاوره فروش
                CREATE TABLE IF NOT EXISTS support_agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    title TEXT,
                    telegram_username TEXT,
                    phone TEXT,
                    working_hours TEXT DEFAULT '۹ الی ۲۳',
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- جدول ثبت پست‌های ریپوست‌شده از کانال‌های مبدا به کانال مقصد
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

                -- جدول آمار استفاده کاربران از دانلودر مدیا
                CREATE TABLE IF NOT EXISTS downloader_users (
                    user_id INTEGER PRIMARY KEY,
                    download_count INTEGER DEFAULT 0,
                    unlocked INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_download_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- جدول رفرال‌های اختصاصی جهت آنلاک دانلود نامحدود
                CREATE TABLE IF NOT EXISTS downloader_referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inviter_id INTEGER NOT NULL,
                    invited_id INTEGER UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.commit()

            # ۱. بررسی و مهاجرت خودکار جدول محصولات (products)
            try:
                p_cursor = await db.execute("PRAGMA table_info(products);")
                p_cols = {row[1] for row in await p_cursor.fetchall()}
                if p_cols:
                    extra_cols = [
                        ("category", "TEXT DEFAULT 'default'"),
                        ("category_key", "TEXT DEFAULT ''"),
                        ("category_name", "TEXT DEFAULT ''"),
                        ("subcategory", "TEXT DEFAULT ''"),
                        ("data_id", "TEXT DEFAULT ''"),
                        ("model_number", "TEXT DEFAULT ''"),
                        ("size", "TEXT DEFAULT ''"),
                        ("price", "INTEGER DEFAULT 0"),
                        ("status", "TEXT DEFAULT 'b'"),
                        ("assembly", "TEXT DEFAULT ''"),
                        ("score", "TEXT DEFAULT ''"),
                        ("year", "TEXT DEFAULT ''"),
                        ("resolution", "TEXT DEFAULT ''"),
                        ("panel", "TEXT DEFAULT ''"),
                        ("refresh_rate", "TEXT DEFAULT ''"),
                        ("backlight", "TEXT DEFAULT ''"),
                        ("os", "TEXT DEFAULT ''"),
                        ("capacity_btu", "TEXT DEFAULT ''"),
                        ("ac_type", "TEXT DEFAULT ''"),
                        ("temp_range", "TEXT DEFAULT ''"),
                        ("room_size", "TEXT DEFAULT ''"),
                        ("energy_consumption", "TEXT DEFAULT ''"),
                        ("performance", "TEXT DEFAULT ''"),
                        ("key_features", "TEXT DEFAULT ''"),
                        ("plan", "TEXT DEFAULT ''"),
                        ("capacity_foot", "TEXT DEFAULT ''"),
                        ("num_doors", "TEXT DEFAULT ''"),
                        ("capacity_kg", "TEXT DEFAULT ''"),
                        ("baskets", "TEXT DEFAULT ''"),
                        ("more_details", "TEXT DEFAULT ''"),
                        ("ai_generated_description", "TEXT DEFAULT ''"),
                        ("colors_json", "TEXT DEFAULT '{}'"),
                        ("specs_json", "TEXT DEFAULT '{}'"),
                        ("url", "TEXT DEFAULT ''"),
                        ("image_url", "TEXT DEFAULT ''"),
                        ("source", "TEXT DEFAULT 'MomtazKalla'"),
                        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                    ]
                    for col_name, col_def in extra_cols:
                        if col_name not in p_cols:
                            await db.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def};")

                    if "category" in p_cols or "category" not in p_cols:
                        if "category_name" in p_cols:
                            await db.execute("UPDATE products SET category = category_name WHERE (category IS NULL OR category = 'default') AND category_name IS NOT NULL;")
                        elif "category_key" in p_cols:
                            await db.execute("UPDATE products SET category = category_key WHERE (category IS NULL OR category = 'default') AND category_key IS NOT NULL;")
            except Exception as e:
                logger.warning(f"Products auto-migration note: {e}")

            # ۲. بررسی و مهاجرت خودکار جدول‌های سفارشات و درخواست‌ها
            try:
                cursor = await db.execute("PRAGMA table_info(user_requests);")
                columns = [row[1] for row in await cursor.fetchall()]
                if "product_id" not in columns:
                    await db.execute("ALTER TABLE user_requests ADD COLUMN product_id TEXT DEFAULT '';")
                if "city" not in columns:
                    await db.execute("ALTER TABLE user_requests ADD COLUMN city TEXT DEFAULT '';")
                if "shipping_method" not in columns:
                    await db.execute("ALTER TABLE user_requests ADD COLUMN shipping_method TEXT DEFAULT 'freight';")

                ord_cursor = await db.execute("PRAGMA table_info(orders);")
                ord_columns = [row[1] for row in await ord_cursor.fetchall()]
                if "total_price" not in ord_columns:
                    await db.execute("ALTER TABLE orders ADD COLUMN total_price TEXT DEFAULT '0';")
                if "shipping_method" not in ord_columns:
                    await db.execute("ALTER TABLE orders ADD COLUMN shipping_method TEXT DEFAULT 'freight';")
            except Exception as e:
                logger.warning(f"Orders/Requests auto-migration note: {e}")

            await db.commit()

            # ۳. ساخت امن ایندکس‌ها با محافظت کامل در برابر خطا
            safe_indexes = [
                ("idx_orders_user", "orders(user_id)"),
                ("idx_orders_status", "orders(status)"),
                ("idx_orders_code", "orders(order_code)"),
                ("idx_products_name", "products(name)"),
                ("idx_products_category", "products(category)"),
                ("idx_channel_posts_date", "channel_posts(date)"),
                ("idx_price_history_product", "price_history(product_id)"),
                ("idx_user_requests_status", "user_requests(status)"),
                ("idx_channel_reposts_source", "channel_reposts(source_channel, source_msg_id)"),
            ]
            for idx_name, target in safe_indexes:
                try:
                    await db.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {target};")
                except Exception as idx_err:
                    logger.debug(f"Index creation note ({idx_name}): {idx_err}")

            await db.commit()

        logger.info("Database initialized successfully.")

    # ------------------- Products -------------------

    async def save_product(self, product: Dict[str, Any]) -> bool:
        """Save or update product in local cache."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                colors_data = product.get("colors", {})
                specs_data = product.get("specs", {})

                colors_json = json.dumps(colors_data, ensure_ascii=False) if isinstance(colors_data, dict) else str(colors_data)
                specs_json = json.dumps(specs_data, ensure_ascii=False) if isinstance(specs_data, dict) else str(specs_data)

                await db.execute("""
                    INSERT INTO products
                    (product_id, name, brand, category, price, colors_json, specs_json, url, image_url, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(product_id) DO UPDATE SET
                        name=excluded.name,
                        brand=excluded.brand,
                        category=excluded.category,
                        price=excluded.price,
                        colors_json=excluded.colors_json,
                        specs_json=excluded.specs_json,
                        url=excluded.url,
                        image_url=excluded.image_url,
                        source=excluded.source,
                        updated_at=excluded.updated_at
                """, (
                    product.get("product_id", ""),
                    product.get("name", ""),
                    product.get("brand", ""),
                    product.get("category", "default"),
                    str(product.get("price", "")),
                    colors_json,
                    specs_json,
                    product.get("url", ""),
                    product.get("image_url", ""),
                    product.get("source", "MomtazKalla"),
                    datetime.now().isoformat()
                ))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error saving product {product.get('product_id')}: {e}")
                return False

    async def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def search_products(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM products WHERE name LIKE ? OR brand LIKE ? ORDER BY updated_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_products_by_category(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM products WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                (category, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_categories(self) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT DISTINCT category FROM products WHERE category != 'default' ORDER BY category")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    # ------------------- Orders -------------------

    async def create_order(self, order: Dict[str, Any]) -> str:
        async with aiosqlite.connect(self.db_path) as db:
            shipping_method = order.get("shipping_method", "freight")
            try:
                await db.execute("""
                    INSERT INTO orders (
                        order_code, user_id, username, product_id, product_name,
                        full_name, phone1, phone2, province_city, address, postal_code,
                        total_price, deposit_amount, shipping_method, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.get("order_code"),
                    order.get("user_id"),
                    order.get("username", ""),
                    order.get("product_id", ""),
                    order.get("product_name", ""),
                    order.get("full_name", ""),
                    order.get("phone1", ""),
                    order.get("phone2", ""),
                    order.get("province_city", ""),
                    order.get("address", ""),
                    order.get("postal_code", ""),
                    str(order.get("total_price", "0")),
                    str(order.get("deposit_amount", "0")),
                    shipping_method,
                    order.get("status", "Awaiting_Payment"),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                await db.commit()
            except aiosqlite.OperationalError as oe:
                if "no column named shipping_method" in str(oe).lower():
                    try:
                        await db.execute("ALTER TABLE orders ADD COLUMN shipping_method TEXT DEFAULT 'freight';")
                        await db.commit()
                    except Exception:
                        pass
                    await db.execute("""
                        INSERT INTO orders (
                            order_code, user_id, username, product_id, product_name,
                            full_name, phone1, phone2, province_city, address, postal_code,
                            total_price, deposit_amount, shipping_method, status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        order.get("order_code"),
                        order.get("user_id"),
                        order.get("username", ""),
                        order.get("product_id", ""),
                        order.get("product_name", ""),
                        order.get("full_name", ""),
                        order.get("phone1", ""),
                        order.get("phone2", ""),
                        order.get("province_city", ""),
                        order.get("address", ""),
                        order.get("postal_code", ""),
                        str(order.get("total_price", "0")),
                        str(order.get("deposit_amount", "0")),
                        shipping_method,
                        order.get("status", "Awaiting_Payment"),
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))
                    await db.commit()
                else:
                    raise oe
            return order.get("order_code", "")

    async def check_and_expire_orders(self, hours: float = 5.0) -> List[str]:
        """بررسی و لغو خودکار سفارشاتی که پس از گذشت ۵ ساعت بیعانه آن‌ها واریز نشده است"""
        expired_codes = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT order_code, created_at FROM orders WHERE status = 'Awaiting_Payment'")
                rows = await cursor.fetchall()
                now = datetime.now()
                for r in rows:
                    c_at_str = r["created_at"]
                    if not c_at_str:
                        continue
                    try:
                        c_at = datetime.fromisoformat(c_at_str)
                        diff_hours = (now - c_at).total_seconds() / 3600.0
                        if diff_hours >= hours:
                            expired_codes.append(r["order_code"])
                    except Exception as ex:
                        logger.warning(f"Error parsing created_at for order {r['order_code']}: {ex}")

                if expired_codes:
                    placeholders = ",".join(["?"] * len(expired_codes))
                    await db.execute(f"""
                        UPDATE orders 
                        SET status = 'Cancelled',
                            admin_note = 'لغو خودکار به دلیل عدم واریز بیعانه ظرف ۵ ساعت',
                            updated_at = ?
                        WHERE order_code IN ({placeholders})
                    """, [datetime.now().isoformat()] + expired_codes)
                    await db.commit()
                    logger.info(f"⏰ Auto-cancelled {len(expired_codes)} expired orders: {expired_codes}")
        except Exception as e:
            logger.error(f"Error in check_and_expire_orders: {e}")
        return expired_codes

    async def get_order_by_code(self, order_code: str) -> Optional[Dict[str, Any]]:
        await self.check_and_expire_orders()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM orders WHERE order_code = ?", (order_code.strip(),))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_orders_by_user(self, user_id: int, limit: int = 15) -> List[Dict[str, Any]]:
        await self.check_and_expire_orders()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_orders_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        await self.check_and_expire_orders()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status == "Rejected":
                cursor = await db.execute(
                    "SELECT * FROM orders WHERE status IN ('Rejected', 'Cancelled') ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def search_orders(self, query_str: str, limit: int = 20) -> List[Dict[str, Any]]:
        """جستجوی هوشمند سفارشات با شماره سفارش، نام خریدار، شماره تماس یا نام کالا"""
        await self.check_and_expire_orders()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            q = f"%{query_str.strip()}%"
            cursor = await db.execute("""
                SELECT * FROM orders 
                WHERE order_code LIKE ? OR phone1 LIKE ? OR full_name LIKE ? OR product_name LIKE ?
                ORDER BY created_at DESC LIMIT ?
            """, (q, q, q, q, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_all_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        await self.check_and_expire_orders()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def update_order_status(self, order_code: str, status: str,
                                  admin_note: str = "", receipt_file_id: str = "", receipt_text: str = "") -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    UPDATE orders SET 
                        status = ?,
                        admin_note = CASE WHEN ? != '' THEN ? ELSE admin_note END,
                        receipt_file_id = CASE WHEN ? != '' THEN ? ELSE receipt_file_id END,
                        receipt_text = CASE WHEN ? != '' THEN ? ELSE receipt_text END,
                        updated_at = ?
                    WHERE order_code = ?
                """, (
                    status,
                    admin_note, admin_note,
                    receipt_file_id, receipt_file_id,
                    receipt_text, receipt_text,
                    datetime.now().isoformat(),
                    order_code.strip()
                ))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error updating order {order_code}: {e}")
                return False

    # ------------------- Monitored Channels -------------------

    async def get_monitored_channels(self) -> List[Dict[str, Any]]:
        """دریافت تمام کانال‌های فعال و غیرفعال تحت پایش"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT channel_id, channel_name, keywords, active FROM monitored_channels")
            rows = await cursor.fetchall()
            return [
                {
                    "channel_id": r["channel_id"],
                    "channel_name": r["channel_name"] or r["channel_id"],
                    "keywords": (r["keywords"] or "").split(",") if r["keywords"] else [],
                    "active": bool(r["active"])
                }
                for r in rows
            ]

    async def add_monitored_channel(self, channel_id: str, channel_name: str = "") -> str:
        """افزودن کانال جدید برای پایش خودکار"""
        cid = channel_id.strip()
        if not cid.startswith("@") and not cid.startswith("-100"):
            cid = f"@{cid}"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO monitored_channels (channel_id, channel_name, active, added_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    channel_name=excluded.channel_name,
                    active=1
            """, (cid, channel_name or cid, datetime.now().isoformat()))
            await db.commit()
            return cid

    async def delete_monitored_channel(self, channel_id: str):
        """حذف کامل یک کانال از پایش"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM monitored_channels WHERE LOWER(channel_id) = LOWER(?)", (channel_id.strip(),))
            await db.commit()

    async def toggle_monitored_channel(self, channel_id: str) -> bool:
        """تغییر وضعیت فعال/غیرفعال کانال"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT active FROM monitored_channels WHERE LOWER(channel_id) = LOWER(?)", (channel_id.strip(),))
            row = await cursor.fetchone()
            if row:
                new_status = 0 if row["active"] == 1 else 1
                await db.execute(
                    "UPDATE monitored_channels SET active = ? WHERE LOWER(channel_id) = LOWER(?)",
                    (new_status, channel_id.strip())
                )
                await db.commit()
                return bool(new_status)
            return False

    async def is_post_reposted(self, source_channel: str, source_msg_id: int) -> bool:
        """بررسی آیا پستی از کانال مبدا قبلاً ریپوست شده است یا خیر"""
        src = source_channel.strip().lower()
        if not src.startswith("@"):
            src = f"@{src}"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM channel_reposts WHERE LOWER(source_channel) = ? AND source_msg_id = ?",
                (src, source_msg_id)
            )
            row = await cursor.fetchone()
            return bool(row)

    async def record_repost(self, source_channel: str, source_msg_id: int, target_channel: str, target_msg_id: Optional[int] = None, has_photo: bool = True) -> bool:
        """ثبت رکورد ریپوست موفق در دیتابیس جهت ممانعت قطعی از ارسال مجدد"""
        src = source_channel.strip().lower()
        if not src.startswith("@"):
            src = f"@{src}"
        tgt = target_channel.strip().lower()
        if not tgt.startswith("@"):
            tgt = f"@{tgt}"
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO channel_reposts (source_channel, source_msg_id, target_channel, target_msg_id, has_photo, reposted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_channel, source_msg_id) DO UPDATE SET
                        target_channel = excluded.target_channel,
                        target_msg_id = excluded.target_msg_id
                """, (src, source_msg_id, tgt, target_msg_id, 1 if has_photo else 0, datetime.now().isoformat()))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error recording repost {src}/{source_msg_id}: {e}")
                return False

    async def get_reposted_ids(self, source_channel: str) -> set:
        """دریافت مجموعه شناسه‌های پیام‌های قبلاً ریپوست‌شده از یک کانال مبدا"""
        src = source_channel.strip().lower()
        if not src.startswith("@"):
            src = f"@{src}"
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT source_msg_id FROM channel_reposts WHERE LOWER(source_channel) = ?",
                (src,)
            )
            rows = await cursor.fetchall()
            return set(r[0] for r in rows)

    async def get_channel_reposts_count(self, source_channel: Optional[str] = None) -> int:
        """تعداد کل پست‌های ریپوست‌شده (از یک کانال یا تمام کانال‌ها)"""
        async with aiosqlite.connect(self.db_path) as db:
            if source_channel:
                src = source_channel.strip().lower()
                if not src.startswith("@"):
                    src = f"@{src}"
                cursor = await db.execute("SELECT COUNT(*) FROM channel_reposts WHERE LOWER(source_channel) = ?", (src,))
            else:
                cursor = await db.execute("SELECT COUNT(*) FROM channel_reposts")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_all_repost_stats(self) -> Dict[str, int]:
        """گزارش تفکیکی تعداد ریپوست‌های موفق به ازای هر کانال"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT source_channel, COUNT(*) FROM channel_reposts GROUP BY source_channel")
            rows = await cursor.fetchall()
            return {r[0]: r[1] for r in rows}

    # ------------------- Channels & Posts -------------------

    async def get_channels(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM channels ORDER BY channel_name")
            return [dict(row) for row in await cursor.fetchall()]

    async def save_channel(self, channel: Dict[str, Any]) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                keywords = channel.get("keywords", [])
                kw_str = ",".join(keywords) if isinstance(keywords, list) else str(keywords)

                await db.execute("""
                    INSERT INTO channels (channel_id, channel_name, keywords, active)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(channel_id) DO UPDATE SET
                        channel_name=excluded.channel_name,
                        keywords=excluded.keywords,
                        active=excluded.active
                """, (
                    channel.get("channel_id", ""),
                    channel.get("channel_name", ""),
                    kw_str,
                    1 if channel.get("active", True) else 0
                ))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error saving channel: {e}")
                return False

    async def save_channel_post(self, post: Dict[str, Any]) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO channel_posts (channel_id, channel_name, message_id, text, cleaned_text, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    post.get("channel_id", ""),
                    post.get("channel_name", ""),
                    post.get("message_id", 0),
                    post.get("text", ""),
                    post.get("cleaned_text", ""),
                    post.get("date", datetime.now().isoformat())
                ))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error saving post: {e}")
                return False

    async def get_unseen_posts(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT last_view_date FROM user_last_view WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            last_view = row[0] if row else '1970-01-01'

            cursor = await db.execute(
                "SELECT * FROM channel_posts WHERE date > ? ORDER BY date DESC LIMIT ?",
                (last_view, limit)
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def update_last_view(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO user_last_view (user_id, last_view_date)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET last_view_date = excluded.last_view_date
            """, (user_id, datetime.now().isoformat()))
            await db.commit()

    # ------------------- Requests & Price Inquiries -------------------

    async def save_user_request(self, request: Dict[str, Any]) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO user_requests (user_id, username, product_name, color, status, request_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                request.get("user_id", 0),
                request.get("username", ""),
                request.get("product_name", ""),
                request.get("color", ""),
                "Pending",
                datetime.now().isoformat()
            ))
            await db.commit()
            return cursor.lastrowid

    async def get_request_by_id(self, request_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM user_requests WHERE id = ?", (request_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_pending_requests(self, limit: int = 30) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM user_requests WHERE status = 'Pending' ORDER BY request_date DESC LIMIT ?",
                (limit,)
            )
            return [dict(r) for r in await cursor.fetchall()]

    async def update_request_status(self, request_id: int, status: str, admin_response: str = "") -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "UPDATE user_requests SET status = ?, admin_response = ? WHERE id = ?",
                    (status, admin_response, request_id)
                )
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error updating request: {e}")
                return False

    async def create_price_inquiry(self, user_id: int, username: str, product_id: str,
                                   product_name: str, city: str, color: str = "") -> int:
        """ثبت استعلام قیمت با شهر مقصد توسط خریدار"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute("""
                    INSERT INTO user_requests (
                        user_id, username, product_id, product_name, city, color, status, request_date
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
                """, (
                    user_id, username or "", product_id, product_name, city, color, datetime.now().isoformat()
                ))
                await db.commit()
                return cursor.lastrowid
            except aiosqlite.OperationalError as e:
                if "no column named" in str(e).lower():
                    try:
                        await db.execute("ALTER TABLE user_requests ADD COLUMN product_id TEXT DEFAULT '';")
                    except Exception:
                        pass
                    try:
                        await db.execute("ALTER TABLE user_requests ADD COLUMN city TEXT DEFAULT '';")
                    except Exception:
                        pass
                    await db.commit()
                    cursor = await db.execute("""
                        INSERT INTO user_requests (
                            user_id, username, product_id, product_name, city, color, status, request_date
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
                    """, (
                        user_id, username or "", product_id, product_name, city, color, datetime.now().isoformat()
                    ))
                    await db.commit()
                    return cursor.lastrowid
                raise e

    async def get_price_inquiry(self, inquiry_id: int) -> Optional[Dict[str, Any]]:
        """دریافت مشخصات کامل استعلام قیمت جهت پاسخگویی ادمین"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM user_requests WHERE id = ?", (inquiry_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def answer_price_inquiry(self, inquiry_id: int, admin_response: str, final_price: str = "", shipping_method: str = "freight") -> bool:
        """ثبت پاسخ ادمین به استعلام قیمت همراه با شیوه ارسال"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    UPDATE user_requests SET 
                        status = 'Answered',
                        admin_response = ?,
                        final_price = ?,
                        shipping_method = ?
                    WHERE id = ?
                """, (admin_response, final_price, shipping_method, inquiry_id))
                await db.commit()
                return True
            except aiosqlite.OperationalError as oe:
                if "no column named shipping_method" in str(oe).lower():
                    try:
                        await db.execute("ALTER TABLE user_requests ADD COLUMN shipping_method TEXT DEFAULT 'freight';")
                        await db.commit()
                        await db.execute("""
                            UPDATE user_requests SET 
                                status = 'Answered',
                                admin_response = ?,
                                final_price = ?,
                                shipping_method = ?
                            WHERE id = ?
                        """, (admin_response, final_price, shipping_method, inquiry_id))
                        await db.commit()
                        return True
                    except Exception as e2:
                        logger.error(f"Failed fallback update inquiry: {e2}")
                logger.error(f"Error answering price inquiry #{inquiry_id}: {oe}")
                return False
            except Exception as e:
                logger.error(f"Error answering price inquiry #{inquiry_id}: {e}")
                return False

    async def get_latest_user_inquiry(self, user_id: int, product_id: str = "") -> Optional[Dict[str, Any]]:
        """یافتن آخرین استعلام قیمت پاسخ داده شده به کاربر برای تعیین قیمت تمام‌شده و بیعانه ۸٪"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if product_id:
                cursor = await db.execute("""
                    SELECT * FROM user_requests 
                    WHERE user_id = ? AND product_id = ? AND status = 'Answered'
                    ORDER BY id DESC LIMIT 1
                """, (user_id, str(product_id)))
            else:
                cursor = await db.execute("""
                    SELECT * FROM user_requests 
                    WHERE user_id = ? AND status = 'Answered'
                    ORDER BY id DESC LIMIT 1
                """, (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    # ------------------- Price History & Logs -------------------

    async def save_price_history(self, product_id: str, price: str, color: str = "") -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO price_history (product_id, price, color, date) VALUES (?, ?, ?, ?)",
                    (product_id, price, color, datetime.now().isoformat())
                )
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error saving price history: {e}")
                return False

    async def cleanup_price_history(self, days: int = PRICE_HISTORY_DAYS):
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM price_history WHERE date < ?", (cutoff,))
            await db.commit()
            return cursor.rowcount

    async def log_sync(self, action: str, status: str, message: str = "") -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO sync_log (action, status, message) VALUES (?, ?, ?)",
                    (action, status, message)
                )
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error logging sync: {e}")
                return False

    async def get_stats(self) -> Dict[str, int]:
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            cursor = await db.execute("SELECT COUNT(*) FROM products")
            stats["total_products"] = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM orders")
            stats["total_orders"] = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Receipt_Uploaded'")
            stats["pending_receipts"] = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Approved'")
            stats["approved_orders"] = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status IN ('Rejected', 'Cancelled')")
            stats["rejected_orders"] = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Delivered'")
            stats["delivered_orders"] = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Awaiting_Payment'")
            stats["awaiting_payment"] = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM user_requests WHERE status = 'Pending'")
            stats["pending_requests"] = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM channel_posts")
            stats["total_posts"] = (await cursor.fetchone())[0]

            today = datetime.now().strftime("%Y-%m-%d")
            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) = ?", (today,))
            stats["today_orders"] = (await cursor.fetchone())[0]

            try:
                cursor = await db.execute("SELECT COUNT(*) FROM support_agents WHERE is_active = 1")
                stats["active_support_agents"] = (await cursor.fetchone())[0]
            except Exception:
                stats["active_support_agents"] = 0

            try:
                cursor = await db.execute("SELECT COUNT(*) FROM monitored_channels WHERE is_active = 1")
                stats["active_channels"] = (await cursor.fetchone())[0]
            except Exception:
                stats["active_channels"] = 0

            return stats

    async def get_all_active_user_ids(self) -> List[int]:
        """دریافت شناسه عددی تمامی کاربرانی که تا کنون با ربات تعامل داشته‌اند"""
        async with aiosqlite.connect(self.db_path) as db:
            query = """
                SELECT DISTINCT user_id FROM (
                    SELECT user_id FROM user_last_view
                    UNION
                    SELECT user_id FROM orders
                    UNION
                    SELECT user_id FROM user_requests
                ) WHERE user_id IS NOT NULL AND user_id > 0
            """
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            return [int(r[0]) for r in rows if r[0]]

    # ─── متدهای مدیریت کارشناسان پشتیبانی و مشاوره ───

    async def get_support_agents(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """دریافت لیست کارشناسان پشتیبانی و مشاوره"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM support_agents"
            params = []
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY sort_order ASC, id ASC"
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_support_agent_by_id(self, agent_id: int) -> Optional[Dict[str, Any]]:
        """دریافت اطلاعات یک کارشناس بر اساس شناسه"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM support_agents WHERE id = ?", (agent_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def add_support_agent(
        self,
        name: str,
        title: str,
        telegram_username: str,
        phone: str,
        working_hours: str = "۹ الی ۲۳",
        sort_order: int = 0,
        is_active: int = 1
    ) -> int:
        """افزودن کارشناس پشتیبانی جدید"""
        # پاکسازی کاراکتر @ اضافی در صورت وجود
        tg = telegram_username.strip()
        if tg.startswith("@"):
            tg = tg[1:]
        elif tg.startswith("https://t.me/"):
            tg = tg.replace("https://t.me/", "")
        elif tg.startswith("t.me/"):
            tg = tg.replace("t.me/", "")

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO support_agents 
                (name, title, telegram_username, phone, working_hours, sort_order, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name.strip(), title.strip(), tg, phone.strip(), working_hours.strip(), sort_order, is_active)
            )
            await db.commit()
            return cursor.lastrowid

    async def update_support_agent(self, agent_id: int, **kwargs) -> bool:
        """ویرایش مشخصات کارشناس پشتیبانی"""
        if not kwargs:
            return False
        if "telegram_username" in kwargs and kwargs["telegram_username"]:
            tg = kwargs["telegram_username"].strip()
            if tg.startswith("@"):
                tg = tg[1:]
            elif tg.startswith("https://t.me/"):
                tg = tg.replace("https://t.me/", "")
            elif tg.startswith("t.me/"):
                tg = tg.replace("t.me/", "")
            kwargs["telegram_username"] = tg

        fields = [f"{k} = ?" for k in kwargs.keys()]
        values = list(kwargs.values()) + [agent_id]
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(f"UPDATE support_agents SET {', '.join(fields)} WHERE id = ?", values)
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error updating support agent {agent_id}: {e}")
                return False

    async def toggle_support_agent_active(self, agent_id: int) -> bool:
        """تغییر وضعیت فعال/غیرفعال بودن کارشناس"""
        agent = await self.get_support_agent_by_id(agent_id)
        if not agent:
            return False
        new_status = 0 if agent.get("is_active", 1) == 1 else 1
        return await self.update_support_agent(agent_id, is_active=new_status)

    async def delete_support_agent(self, agent_id: int) -> bool:
        """حذف کارشناس پشتیبانی"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("DELETE FROM support_agents WHERE id = ?", (agent_id,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Error deleting support agent {agent_id}: {e}")
                return False

    async def seed_default_support_agents(self):
        """عدم ثبت کارشناس پیش‌فرض - ادمین خود کارشناسان را از پنل ثبت می‌کند"""
        # در صورت وجود کارشناسان پیش‌فرض آزمایشی قدیمی، پاکسازی می‌شوند
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "DELETE FROM support_agents WHERE telegram_username IN ('Rezaei_Aikala', 'Mohammadi_Aikala')"
                )
                await db.commit()
            except Exception:
                pass

    # ─── متدهای سیستم ترغیب و سهمیه دانلودر مدیا (یوتیوب و اینستاگرام) ───

    async def get_downloader_user_info(self, user_id: int) -> Dict[str, Any]:
        """دریافت وضعیت دانلود کاربر و تعداد افراد دعوت‌شده"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT download_count, unlocked FROM downloader_users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                download_count = row["download_count"] if row else 0
                unlocked = bool(row["unlocked"]) if row else False

            async with db.execute(
                "SELECT COUNT(*) FROM downloader_referrals WHERE inviter_id = ?",
                (user_id,)
            ) as cursor:
                referral_count = (await cursor.fetchone())[0]

            # اگر حداقل ۵ نفر دعوت کرده باشد، به‌طور خودکار آنلاک می‌شود
            if referral_count >= 5 and not unlocked:
                await db.execute(
                    "INSERT INTO downloader_users (user_id, download_count, unlocked) VALUES (?, 0, 1) "
                    "ON CONFLICT(user_id) DO UPDATE SET unlocked = 1",
                    (user_id,)
                )
                await db.commit()
                unlocked = True

            return {
                "download_count": download_count,
                "unlocked": unlocked,
                "referral_count": referral_count
            }

    async def increment_downloader_count(self, user_id: int) -> int:
        """افزایش تعداد دفعات دانلود کاربر"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO downloader_users (user_id, download_count, unlocked, last_download_at)
                VALUES (?, 1, 0, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET 
                    download_count = download_count + 1,
                    last_download_at = CURRENT_TIMESTAMP
                """,
                (user_id,)
            )
            await db.commit()
            async with db.execute("SELECT download_count FROM downloader_users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else 1

    async def register_downloader_referral(self, inviter_id: int, invited_id: int) -> bool:
        """ثبت دعوت موفق یک کاربر جدید با لینک اشتراک‌گذاری دانلودر"""
        if not inviter_id or not invited_id or inviter_id == invited_id:
            return False
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO downloader_referrals (inviter_id, invited_id) VALUES (?, ?)",
                    (inviter_id, invited_id)
                )
                await db.commit()

                # بررسی آیا تعداد دعوت‌ها به ۵ رسید تا آنلاک شود
                async with db.execute(
                    "SELECT COUNT(*) FROM downloader_referrals WHERE inviter_id = ?",
                    (inviter_id,)
                ) as cursor:
                    c = (await cursor.fetchone())[0]
                    if c >= 5:
                        await db.execute(
                            "INSERT INTO downloader_users (user_id, download_count, unlocked) VALUES (?, 0, 1) "
                            "ON CONFLICT(user_id) DO UPDATE SET unlocked = 1",
                            (inviter_id,)
                        )
                        await db.commit()
                return True
            except Exception:
                # کاربر قبلاً ثبت شده یا خطای کلید یکتا
                return False


