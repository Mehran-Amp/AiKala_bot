# -*- coding: utf-8 -*-
import time
import logging
import urllib.request
import json
from typing import Dict, Any, Optional

try:
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
    from telegram.ext import ContextTypes
except (ImportError, ModuleNotFoundError):
    class _MockTelegramObj:
        def __init__(self, *args, **kwargs):
            self.text = args[0] if args else kwargs.get("text", "")
            self.callback_data = kwargs.get("callback_data", "")
            self.args = args
            self.kwargs = kwargs
            self.inline_keyboard = args[0] if (args and isinstance(args[0], list)) else kwargs.get("inline_keyboard", [])
    InlineKeyboardButton = _MockTelegramObj
    InlineKeyboardMarkup = _MockTelegramObj
    Update = _MockTelegramObj
    class ContextTypes:
        DEFAULT_TYPE = Any

logger = logging.getLogger(__name__)

API_URL = "https://api.brsapi.ir/Market/Gold_Currency.php?key=BbpqLA8nmyBc3zQTHdDQAA9BWHaqjyeN"

_CACHE_DATA: Optional[Dict[str, Any]] = None
_CACHE_TIMESTAMP: float = 0.0
CACHE_TTL = 40.0


def fetch_market_data(force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    global _CACHE_DATA, _CACHE_TIMESTAMP
    now = time.time()
    if not force_refresh and _CACHE_DATA and (now - _CACHE_TIMESTAMP < CACHE_TTL):
        return _CACHE_DATA

    try:
        req = urllib.request.Request(
            API_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                raw_json = resp.read().decode("utf-8")
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict) and "currency" in parsed:
                    _CACHE_DATA = parsed
                    _CACHE_TIMESTAMP = now
                    return parsed
    except Exception as e:
        logger.warning(f"Error fetching market currency data: {e}")

    return _CACHE_DATA


def _format_change_badge(val: Any) -> str:
    try:
        pct = float(val)
        if pct > 0:
            return f"🟢 <b>+{pct:.2f}%</b>"
        elif pct < 0:
            return f"🔴 <b>{pct:.2f}%</b>"
        else:
            return "⚪ <b>۰%</b>"
    except Exception:
        return ""


def _fmt_price(raw_p: Any, is_usd: bool = False) -> str:
    if raw_p is None:
        return "-"
    try:
        val = float(raw_p)
        if is_usd:
            return f"${val:,.2f}".rstrip("0").rstrip(".") if "." in f"${val:.2f}" else f"${int(val):,}"
        return f"{int(val):,}"
    except Exception:
        return str(raw_p)


def build_rates_message_and_keyboard() -> tuple[str, InlineKeyboardMarkup]:
    data = fetch_market_data()
    if not data:
        err_msg = (
            "⚠️ <b>خطا در دریافت نرخ‌های زنده</b>\n\n"
            "<blockquote>ارتباط با وب‌سرویس نرخ‌های لحظه‌ای موقتاً برقرار نشد.\n"
            "لطفاً چند لحظه بعد مجدداً دکمه «تلاش مجدد» را لمس کنید.\n"
            "🤖 <b>@AiKala_bot</b></blockquote>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تلاش مجدد", callback_data="refresh_currency_rates")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")]
        ])
        return err_msg, kb

    gold_list = {item.get("symbol"): item for item in data.get("gold", [])}
    curr_list = {item.get("symbol"): item for item in data.get("currency", [])}
    crypto_list = {item.get("symbol"): item for item in data.get("cryptocurrency", [])}

    update_time = ""
    update_date = ""
    for pool in [curr_list.values(), gold_list.values()]:
        for entry in pool:
            if entry.get("time"):
                update_time = entry.get("time")
                update_date = entry.get("date", "")
                break
        if update_time:
            break

    dt_str = update_date if update_date else "امروز"
    tm_str = update_time if update_time else "لحظه‌ای"

    lines = [
        "🏛 <b>تابلو زنده نرخ طلا، ارز و کریپتو</b>",
        f"📅 تاریخ: <code>{dt_str}</code> ▫️ ⏰ ساعت: <code>{tm_str}</code>",
        ""
    ]

    gold_card_lines = ["🟡 <b>بازار طلا و مسکوکات:</b>"]
    gold_items = [
        ("IR_GOLD_18K", "طلای ۱۸ عیار", False, "تومان"),
        ("IR_GOLD_24K", "طلای ۲۴ عیار", False, "تومان"),
        ("XAUUSD", "انس جهانی طلا", True, "دلار"),
    ]
    for sym, title, is_usd, def_unit in gold_items:
        it = gold_list.get(sym)
        if it:
            p_str = _fmt_price(it.get("price"), is_usd=is_usd)
            badge = _format_change_badge(it.get("change_percent"))
            curr_unit = it.get("unit", def_unit)
            unit_suffix = "" if is_usd else f" {curr_unit}"
            gold_card_lines.append(f"▫️ {title}: <code>{p_str}</code>{unit_suffix}  {badge}")

    lines.append(f"<blockquote>" + "\n".join(gold_card_lines) + "</blockquote>")
    lines.append("")

    curr_card_lines = ["💵 <b>اسکناس و ارزهای آزاد:</b>"]
    currencies = [
        ("USD", "🇺🇸 دلار آمریکا (USD)", "تومان"),
        ("USDT_IRT", "🟢 دلار تتر (USDT)", "تومان"),
        ("AED", "🇦🇪 درهم امارات (AED)", "تومان"),
        ("EUR", "🇪🇺 یورو اروپا (EUR)", "تومان"),
        ("GBP", "🇬🇧 پوند انگلیس (GBP)", "تومان"),
        ("CNY", "🇨🇳 یوان چین (CNY)", "تومان"),
    ]
    for sym, title, def_unit in currencies:
        it = curr_list.get(sym)
        if it:
            p_str = _fmt_price(it.get("price"), is_usd=False)
            badge = _format_change_badge(it.get("change_percent"))
            u = it.get("unit", def_unit)
            curr_card_lines.append(f"{title}: <code>{p_str}</code> {u}  {badge}")

    lines.append(f"<blockquote>" + "\n".join(curr_card_lines) + "</blockquote>")
    lines.append("")

    crypto_card_lines = ["🪙 <b>رمزارزهای برتر بازار:</b>"]
    cryptos = [
        ("BTC", "₿ بیت‌کوین (BTC)", True),
        ("ETH", "Ξ اتریوم (ETH)", True),
    ]
    for sym, title, is_usd in cryptos:
        it = crypto_list.get(sym)
        if it:
            p_str = _fmt_price(it.get("price"), is_usd=is_usd)
            badge = _format_change_badge(it.get("change_percent"))
            crypto_card_lines.append(f"{title}: <code>{p_str}</code>  {badge}")

    lines.append(f"<blockquote>" + "\n".join(crypto_card_lines) + "</blockquote>")
    lines.append("")

    footer_lines = [
        "<blockquote>💡 <i>نکته: جهت کپی سریع هر قیمت، روی عدد آن ضربه بزنید.</i>",
        "🔄 <i>بروزرسانی لحظه‌ای بر اساس بازار آزاد</i>",
        "🤖 <b>@AiKala_bot</b></blockquote>"
    ]
    lines.append("\n".join(footer_lines))

    msg_text = "\n".join(lines)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بروزرسانی زنده نرخ‌ها", callback_data="refresh_currency_rates")],
        [
            InlineKeyboardButton("🔍 جستجوی کالا", callback_data="btn_search_prompt"),
            InlineKeyboardButton("📂 دسته‌بندی محصولات", callback_data="cat_back")
        ],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_main")]
    ])

    return msg_text, kb


async def show_currency_rates(update: Update, context: ContextTypes.DEFAULT_TYPE, is_refresh: bool = False):
    if is_refresh:
        fetch_market_data(force_refresh=True)

    text, kb = build_rates_message_and_keyboard()

    if update.callback_query:
        query = update.callback_query
        try:
            if is_refresh:
                await query.answer("✅ آخرین نرخ‌ها با موفقیت بروزرسانی شدند.")
            else:
                await query.answer()

            try:
                from telegram import LinkPreviewOptions
                await query.edit_message_text(
                    text,
                    reply_markup=kb,
                    parse_mode="HTML",
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            except Exception:
                await query.edit_message_text(
                    text,
                    reply_markup=kb,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
        except Exception as e:
            if "Message is not modified" in str(e):
                await query.answer("✅ نرخ‌ها هم‌اکنون آخرین نسخه و بروز هستند.")
            else:
                try:
                    from telegram import LinkPreviewOptions
                    await query.message.reply_text(
                        text,
                        reply_markup=kb,
                        parse_mode="HTML",
                        link_preview_options=LinkPreviewOptions(is_disabled=True)
                    )
                except Exception:
                    await query.message.reply_text(
                        text,
                        reply_markup=kb,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
    else:
        try:
            from telegram import LinkPreviewOptions
            await update.message.reply_text(
                text,
                reply_markup=kb,
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
        except Exception:
            await update.message.reply_text(
                text,
                reply_markup=kb,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
