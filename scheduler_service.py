# -*- coding: utf-8 -*-
"""
scheduler_service.py
سرویس زمان‌بندی خودکار:
1. به‌روزرسانی ۲ ساعته قیمت‌های زنده (سبک، سریع و امن)
2. به‌روزرسانی هفتگی کاتالوگ پایه و بازسازی درخت دسته‌بندی
"""

import time
import threading
import sync_prices
import sync_catalog
import db_bridge

def start_background_scheduler():
    def worker():
        print("🚀 [SCHEDULER] Automated background scheduler started.")
        # بررسی اولیه قیمت‌ها
        sync_prices.update_live_prices()
        
        last_weekly_check = time.time()
        
        while True:
            try:
                # هر 2 ساعت (7200 ثانیه)
                time.sleep(7200)
                print("⏰ [SCHEDULER] Running 2-hour live price synchronization...")
                sync_prices.update_live_prices()

                # هر 7 روز یک‌بار بازسازی درخت کاتالوگ، موجودی و دسته‌بندی‌ها
                if time.time() - last_weekly_check >= 7 * 86400:
                    print("📅 [SCHEDULER] Running weekly catalog rebuild, inventory and categorization...")
                    sync_catalog.run_full_catalog_and_category_sync()
                    last_weekly_check = time.time()

            except Exception as e:
                print("❌ [SCHEDULER] Error in automated scheduler:", e)
                time.sleep(60)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    start_background_scheduler()
    while True:
        time.sleep(1)
