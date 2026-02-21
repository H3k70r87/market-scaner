"""
Telegram notification module.

- send_alert(): formats and sends a signal message
- run_bot(): starts the interactive bot with /status, /scan, /alerts, /help commands
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

PATTERN_DESCRIPTIONS = {
    "double_top_bottom": {
        "bullish": "Dvě podobná dna s vrcholem mezi nimi – cenový vzor signalizující možný vzestup.",
        "bearish": "Dvě podobné vrcholy s dnem mezi nimi – cenový vzor signalizující možný pokles.",
    },
    "head_and_shoulders": {
        "bullish": "Inverzní hlava a ramena – tři dna, střední nejnižší. Signál možného obratu nahoru.",
        "bearish": "Hlava a ramena – tři vrcholy, střední nejvyšší. Klasický bearish reversal vzor.",
    },
    "bull_bear_flag": {
        "bullish": "Silný vzestupný pohyb následovaný konsolidací – možné pokračování trendu.",
        "bearish": "Silný sestupný pohyb následovaný konsolidací – možné pokračování poklesu.",
    },
    "triangles": {
        "bullish": "Rostoucí dna + horizontální odpor – komprese energie před možným průrazem nahoru.",
        "bearish": "Horizontální podpora + klesající vrcholy – komprese před možným průrazem dolů.",
    },
    "golden_death_cross": {
        "bullish": "EMA50 překřížila EMA200 zdola – Golden Cross, dlouhodobý bullish signál.",
        "bearish": "EMA50 překřížila EMA200 shora – Death Cross, dlouhodobý bearish signál.",
    },
    "rsi_divergence": {
        "bullish": "Cena dělá nové dno, ale RSI nikoliv – skrytá síla, možný obrat nahoru.",
        "bearish": "Cena dělá nové maximum, ale RSI nikoliv – skrytá slabost, možný obrat dolů.",
    },
    "engulfing": {
        "bullish": "Zelená svíčka pohltila předchozí červenou – silný bullish reversal signál.",
        "bearish": "Červená svíčka pohltila předchozí zelenou – silný bearish reversal signál.",
    },
    "support_resistance_break": {
        "bullish": "Průraz klíčové úrovně odporu s vyšším objemem – potvrzení vzestupného pohybu.",
        "bearish": "Průraz klíčové úrovně podpory s vyšším objemem – potvrzení sestupného pohybu.",
    },
}

PATTERN_NAMES_CZ = {
    "double_top_bottom": "Double Top / Bottom",
    "head_and_shoulders": "Hlava a Ramena",
    "bull_bear_flag": "Bull / Bear Flag",
    "triangles": "Trojúhelník",
    "golden_death_cross": "Golden / Death Cross",
    "rsi_divergence": "RSI Divergence",
    "engulfing": "Engulfing svíčka",
    "support_resistance_break": "Průraz S/R úrovně",
}


def _get_token() -> Optional[str]:
    return os.environ.get("TELEGRAM_TOKEN")


def _get_chat_id() -> Optional[str]:
    return os.environ.get("TELEGRAM_CHAT_ID")


def _format_price(price: float, symbol: str) -> str:
    if "USDT" in symbol or price > 100:
        return f"${price:,.2f}"
    return f"${price:.6f}"


def _get_dashboard_url() -> str:
    return os.environ.get("DASHBOARD_URL", "")


def _format_alert_message(
    asset: str,
    timeframe: str,
    pattern: str,
    signal_type: str,
    confidence: float,
    price: float,
    details: dict,
) -> str:
    emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚠️"}.get(signal_type, "⚠️")
    signal_label = {"bullish": "BULLISH SIGNAL", "bearish": "BEARISH SIGNAL", "neutral": "NEUTRAL SIGNAL"}.get(
        signal_type, "SIGNAL"
    )

    pattern_name = PATTERN_NAMES_CZ.get(pattern, pattern)
    description = PATTERN_DESCRIPTIONS.get(pattern, {}).get(signal_type, "Detekován technický vzor.")

    price_str = _format_price(price, asset)
    now_utc = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    # Key levels from details
    resistance = details.get("resistance")
    support = details.get("support")

    levels_lines = ""
    if resistance:
        levels_lines += f"  Odpor: {_format_price(float(resistance), asset)}\n"
    if support:
        levels_lines += f"  Podpora: {_format_price(float(support), asset)}"

    msg = (
        f"{emoji} {signal_label} – {asset} ({timeframe})\n"
        f"📊 Pattern: {pattern_name}\n"
        f"💪 Confidence: {confidence:.0f} %\n"
        f"💰 Cena: {price_str}\n"
        f"\n"
        f"📖 Co to znamená:\n"
        f"{description}\n"
    )

    if levels_lines:
        msg += f"\n📏 Klíčové úrovně:\n{levels_lines}\n"

    dashboard_url = _get_dashboard_url()
    if dashboard_url:
        msg += f"\n🌐 Dashboard: {dashboard_url}"

    msg += f"\n⏰ {now_utc}"
    return msg


def send_alert(
    asset: str,
    timeframe: str,
    pattern: str,
    signal_type: str,
    confidence: float,
    price: float,
    details: dict,
) -> bool:
    """Send a formatted alert message to Telegram. Returns True on success."""
    token = _get_token()
    chat_id = _get_chat_id()

    if not token or not chat_id:
        logger.warning("Telegram credentials not set – skipping notification")
        return False

    text = _format_alert_message(asset, timeframe, pattern, signal_type, confidence, price, details)
    return _send_message(token, chat_id, text)


def _send_message(token: str, chat_id: str, text: str) -> bool:
    """Send a plain text message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    delays = [2, 4, 8]

    for attempt in range(3):
        try:
            resp = requests.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=15,
            )
            if resp.status_code == 200:
                return True
            logger.warning("Telegram API returned %s: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.warning("Telegram send attempt %d failed: %s", attempt + 1, exc)

        if attempt < 2:
            time.sleep(delays[attempt])

    logger.error("Failed to send Telegram message after 3 attempts")
    return False


# ---------------------------------------------------------------------------
# Interactive bot commands (for /scan, /status, /alerts, /help)
# This runs as a separate async process – only invoked when needed.
# ---------------------------------------------------------------------------

async def run_bot(scanner_func=None) -> None:
    """
    Start a Telegram bot that handles commands.
    scanner_func: async callable that performs a scan and returns list of results.
    """
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
    except ImportError:
        logger.error("python-telegram-bot not installed")
        return

    from src.storage import supabase_client as db

    token = _get_token()
    if not token:
        logger.error("TELEGRAM_TOKEN not set – cannot start bot")
        return

    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "📋 <b>Dostupné příkazy</b>\n\n"
            "/status – sledovaná aktiva, počet runů dnes, čas posledního runu\n"
            "/scan – okamžitý scan všech aktiv (i pod 65% confidence)\n"
            "/alerts – posledních 10 alertů\n"
            "/help – tento seznam\n"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        import yaml, os
        try:
            with open("config.yaml") as f:
                cfg = yaml.safe_load(f)
            crypto_assets = [a["symbol"] for a in cfg.get("assets", {}).get("crypto", [])]
            stock_assets = [a["symbol"] for a in cfg.get("assets", {}).get("stocks", [])]
            all_assets = crypto_assets + stock_assets
        except Exception:
            all_assets = ["N/A"]

        stats = db.get_run_stats()
        text = (
            "📡 <b>Status skeneru</b>\n\n"
            f"🔍 Sledovaná aktiva: {', '.join(all_assets)}\n"
            f"📈 Alertů dnes: {stats['runs_today']}\n"
            f"⏰ Poslední alert: {stats['last_run']}\n"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
        alerts = db.get_recent_alerts(10)
        if not alerts:
            await update.message.reply_text("Žádné alertů v databázi.")
            return

        lines = ["📊 <b>Posledních 10 alertů</b>\n"]
        for a in alerts:
            emoji = {"bullish": "🟢", "bearish": "🔴"}.get(a.get("type", ""), "⚠️")
            ts = a.get("detected_at", "")[:16].replace("T", " ")
            lines.append(
                f"{emoji} {a['asset']} ({a['timeframe']}) – {PATTERN_NAMES_CZ.get(a['pattern'], a['pattern'])} "
                f"[{a['confidence']}%] @ ${a['price']:,.2f} [{ts}]"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔄 Spouštím scan... Výsledky přijdou za chvíli.")
        if scanner_func is None:
            await update.message.reply_text("⚠️ Scanner funkce není dostupná.")
            return
        try:
            results = await scanner_func(min_confidence=0)
            if not results:
                await update.message.reply_text("✅ Scan dokončen – žádné vzory nebyly nalezeny.")
                return
            lines = [f"🔍 <b>Scan výsledky ({len(results)} vzorů)</b>\n"]
            for r in results[:20]:
                emoji = {"bullish": "🟢", "bearish": "🔴"}.get(r.get("type", ""), "⚠️")
                lines.append(
                    f"{emoji} {r['asset']} ({r['timeframe']}) – "
                    f"{PATTERN_NAMES_CZ.get(r['pattern'], r['pattern'])} [{r['confidence']:.0f}%]"
                )
            await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        except Exception as exc:
            await update.message.reply_text(f"❌ Chyba při scanu: {exc}")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("alerts", cmd_alerts))
    app.add_handler(CommandHandler("scan", cmd_scan))

    logger.info("Starting Telegram bot...")
    await app.run_polling(allowed_updates=["message"])
