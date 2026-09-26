"""
AiKala Master Runner (run_master.py)
====================================
مدیریت و نظارت یکپارچه بر سرویس‌های اصلی @AiKala_bot هوشمند کالا
شامل:
۱. 🤖 ربات تلگرام @AiKala_bot هوشمند کالا (bot.py)
۲. 📡 مانیتور و پابلیشر خودکار کانال آلبوم‌ها (channel_monitor.py)

قابلیت‌ها:
- ناظر هوشمند با راه‌اندازی مجدد خودکار (Watchdog Supervisor with Auto-Restart)
- جلوگیری از حلقه کرش با تاخیر تصاعدی (Exponential Backoff / Crash-loop Protection)
- بررسی پیش‌پرواز فایل‌ها و سلامت نحوی (Pre-flight Syntax Check)
- مدیریت سیگنال‌های سیستمی و خاموش‌سازی تمیز (Graceful SIGINT / SIGTERM Handling)
- امکان تفکیک سرویس‌ها از طریق آرگومان‌های خط فرمان (--bot-only, --monitor-only, --check)
"""

import os
import sys
import time
import signal
import logging
import argparse
import subprocess
import py_compile
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import config
except ImportError:
    config = None

# ─── تنظیمات لاگینگ یکپارچه ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | [MASTER] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout
)
logger = logging.getLogger("MasterRunner")

# حذف لاگ‌های مکرر و اسپم شبکه (api.telegram.org و ارتباطات وب)
for _noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ─── تعریف سرویس‌های هسته ───
CORE_SERVICES: List[Dict[str, Any]] = [
    {
        "id": "bot",
        "name": "🤖 Telegram Bot (@AiKala_bot)",
        "script": "bot.py",
        "critical": True,
        "env_check": "TELEGRAM_BOT_TOKEN"
    },
    {
        "id": "scheduler",
        "name": "⏰ Catalog & Price Scheduler Service",
        "script": "scheduler_service.py",
        "critical": False,
        "env_check": None
    },
    {
        "id": "monitor",
        "name": "📡 Channel Monitor & Reposter (@AiKala_Image)",
        "script": "channel_monitor.py",
        "critical": False,
        "env_check": "TELEGRAM_BOT_TOKEN"
    }
]

# وضعیت جهانی پروسس‌ها جهت دسترسی در سیگنال هندلر
ACTIVE_WORKERS: List[Dict[str, Any]] = []
SHUTDOWN_REQUESTED = False


def check_preflight_syntax(scripts: List[str]) -> bool:
    """Pre-flight syntax validation of python core files."""
    modules_to_check = sorted(list(set(scripts + [
        "guidbuy.py", "support_service.py", "keyboards.py", "database.py",
        "order_flow.py", "photo_service.py", "order_tracking.py",
        "scheduler_service.py", "sync_prices.py", "sync_catalog.py",
        "laptop_extractor.py", "admin_panel.py", "channel_monitor.py"
    ])))
    failed = []

    for mod in modules_to_check:
        if not os.path.exists(mod):
            continue
        try:
            py_compile.compile(mod, doraise=True)
        except py_compile.PyCompileError as e:
            logger.error(f"   ✗ Syntax error in file {mod}: {e}")
            failed.append(mod)

    if failed:
        logger.error(f"❌ {len(failed)} module(s) failed syntax validation. Aborting launch.")
        return False

    logger.info(f"✅ Pre-flight syntax check: All {len(modules_to_check)} core modules verified (Syntax OK).")
    return True


def start_process(script_name: str) -> subprocess.Popen:
    """اجرای اسکریپت در پروسس مستقل با بافر آنی خروجی بدون تاخیر لاگ"""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(
        [sys.executable, "-u", script_name],
        stdout=None,
        stderr=None,
        env=env
    )


def signal_handler(signum, frame):
    """مدیریت سیگنال‌های SIGINT و SIGTERM جهت خاموش‌سازی ایمن و هماهنگ"""
    global SHUTDOWN_REQUESTED
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
    logger.info(f"\n🛑 Received signal {sig_name}. Gracefully stopping all services...")
    SHUTDOWN_REQUESTED = True

    for item in ACTIVE_WORKERS:
        proc = item.get("process")
        cfg = item.get("config", {})
        if proc and proc.poll() is None:
            logger.info(f"Stopping {cfg.get('name', 'service')} (PID: {proc.pid})...")
            try:
                proc.terminate()
            except Exception as e:
                logger.error(f"Error terminating {cfg.get('name')}: {e}")

    # مهلت ۵ ثانیه‌ای برای خاتمه تمیز
    deadline = time.time() + 5
    for item in ACTIVE_WORKERS:
        proc = item.get("process")
        cfg = item.get("config", {})
        if proc:
            while time.time() < deadline and proc.poll() is None:
                time.sleep(0.2)
            if proc.poll() is None:
                logger.warning(f"⚠️ Force-killing unresponsive {cfg.get('name')} (PID: {proc.pid})...")
                try:
                    proc.kill()
                except Exception:
                    pass

    logger.info("👋 All @AiKala_bot master services shut down cleanly. Exiting.")
    sys.exit(0)


def print_status_table():
    """چاپ وضعیت جاری سرویس‌ها و زمان فعال بودن"""
    logger.info("─── 📊 Active Services Status Report ───")
    now = time.time()
    for item in ACTIVE_WORKERS:
        cfg = item["config"]
        proc = item["process"]
        status = "🟢 Running" if proc.poll() is None else f"🔴 Stopped ({proc.returncode})"
        pid = proc.pid if proc.poll() is None else "-"
        uptime_sec = int(now - item["start_time"]) if proc.poll() is None else 0
        hours, rem = divmod(uptime_sec, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s" if uptime_sec > 0 else "0s"
        logger.info(
            f"• {cfg['name']} | PID: {pid} | Status: {status} | "
            f"Uptime: {uptime_str} | Restarts: {item['restart_count']}"
        )
    logger.info("──────────────────────────────────────────")


def main():
    parser = argparse.ArgumentParser(
        description="AiKala Master Runner - Supervised multi-service manager for @AiKala_bot"
    )
    parser.add_argument("--bot-only", action="store_true", help="Run Telegram bot only")
    parser.add_argument("--scheduler-only", action="store_true", help="Run catalog & price scheduler only")
    parser.add_argument("--monitor-only", action="store_true", help="Run channel monitor & reposter only")
    parser.add_argument("--no-restart", action="store_true", help="Do not auto-restart exited processes")
    parser.add_argument("--check", action="store_true", help="Perform pre-flight syntax check and exit")
    args = parser.parse_args()

    # انتخاب سرویس‌های هدف
    selected_services = []
    if args.bot_only:
        selected_services = [s for s in CORE_SERVICES if s["id"] == "bot"]
    elif args.scheduler_only:
        selected_services = [s for s in CORE_SERVICES if s["id"] == "scheduler"]
    elif args.monitor_only:
        selected_services = [s for s in CORE_SERVICES if s["id"] == "monitor"]
    else:
        selected_services = CORE_SERVICES

    # چاپ بنر آغازین جمع‌وجور و حرفه‌ای
    sep = "━" * 60
    print(f"\n{sep}")
    print("🚀 AiKala Master Runner - Unified Process Supervisor")
    print(f"⏱ Started At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🛡 Log Filter: Suppressed noisy network/polling requests (api.telegram.org)")
    print(f"{sep}")

    # تست اولیه سلامت سینتکس
    scripts_to_check = [s["script"] for s in selected_services]
    if not check_preflight_syntax(scripts_to_check):
        logger.error("❌ Launch aborted due to syntax errors.")
        sys.exit(1)

    if args.check:
        logger.info("✅ All pre-flight checks completed successfully.")
        sys.exit(0)

    # ثبت سیگنال‌های سیستمی
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, signal_handler)

    # بررسی متغیرهای محیطی با هشدارهای آموزنده
    bot_token = getattr(config, "TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    if not bot_token and not args.scheduler_only:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN is not configured! bot.py will wait for credentials.")

    # راه‌اندازی اولیه سرویس‌ها
    logger.info("🌟 Bootstrapping selected services:")
    for s in selected_services:
        p = start_process(s["script"])
        worker_state = {
            "config": s,
            "process": p,
            "start_time": time.time(),
            "restart_count": 0,
            "last_crash_time": 0.0,
            "backoff_delay": 2.0,
        }
        ACTIVE_WORKERS.append(worker_state)
        logger.info(f"   🟢 {s['name']} (PID: {p.pid})")
        time.sleep(1.0)

    print(f"{sep}")
    logger.info("✅ All services are ACTIVE and monitored by Master Watchdog.")
    logger.info("💡 Press Ctrl+C at any time to gracefully terminate all processes.\n")

    last_heartbeat = time.time()
    heartbeat_interval = 1800  # هر ۳۰ دقیقه گزارش وضعیت کامل

    # حلقه نظارت هوشمند (Watchdog Supervisor Loop)
    while not SHUTDOWN_REQUESTED:
        now = time.time()

        # گزارش دوره‌ای سلامت
        if now - last_heartbeat >= heartbeat_interval:
            print_status_table()
            last_heartbeat = now

        for item in ACTIVE_WORKERS:
            proc = item["process"]
            cfg = item["config"]

            # بررسی اینکه آیا پروسس زنده است
            ret = proc.poll()
            if ret is not None:
                exit_code = ret
                item["restart_count"] += 1
                crash_time = now

                # مدیریت تاخیر تصاعدی (Exponential Backoff) برای جلوگیری از اسپم CPU و لاگ
                if crash_time - item["last_crash_time"] < 30:
                    item["backoff_delay"] = min(item["backoff_delay"] * 1.5, 60.0)
                else:
                    item["backoff_delay"] = 2.0

                item["last_crash_time"] = crash_time

                logger.warning(
                    f"⚠️ Service '{cfg['name']}' exited unexpectedly with return code {exit_code}!\n"
                    f"   Total restarts: {item['restart_count']} | Backoff delay: {item['backoff_delay']:.1f}s"
                )

                if args.no_restart:
                    logger.info("Flag --no-restart is active. Service will not be revived.")
                    continue

                time.sleep(item["backoff_delay"])
                logger.info(f"🔄 Reviving service: {cfg['name']} ({cfg['script']})...")
                item["process"] = start_process(cfg["script"])
                item["start_time"] = time.time()
                logger.info(f"✅ Service '{cfg['name']}' revived successfully (PID: {item['process'].pid}).")

            else:
                # ریست کردن تاخیر اگر پروسس بیش از ۲ دقیقه پایدار کار کرده باشد
                if now - item["start_time"] > 120 and item["backoff_delay"] > 2.0:
                    item["backoff_delay"] = 2.0

        time.sleep(2)


if __name__ == "__main__":
    main()
