"""
Market Scanner – main orchestration script.

Runs every 30 minutes via GitHub Actions cron job.
For each configured asset + timeframe combination:
  1. Fetch OHLCV data
  2. Run all enabled pattern detectors
  3. If confidence > min_confidence AND R/R >= min_rr and not duplicate: save alert + send Telegram message
"""

import logging
import sys
import yaml
from datetime import datetime, timezone
from typing import Optional

# Pattern detectors
from src.patterns.double_top_bottom import DoubleTopBottomPattern
from src.patterns.head_and_shoulders import HeadAndShouldersPattern
from src.patterns.flags import FlagsPattern
from src.patterns.triangles import TrianglesPattern
from src.patterns.crosses import CrossesPattern
from src.patterns.rsi_divergence import RSIDivergencePattern
from src.patterns.engulfing import EngulfingPattern
from src.patterns.support_resistance import SupportResistancePattern
from src.patterns.ichimoku import IchimokuPattern
from src.patterns.abc_correction import ABCCorrectionPattern

from src.data.fetcher import fetch_asset_data
from src.storage import supabase_client as db
from src.notifier.telegram import send_alert

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scanner")

# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------
ALL_PATTERNS = {
    "double_top_bottom": DoubleTopBottomPattern(),
    "head_and_shoulders": HeadAndShouldersPattern(),
    "bull_bear_flag": FlagsPattern(),
    "triangles": TrianglesPattern(),
    "golden_death_cross": CrossesPattern(),
    "rsi_divergence": RSIDivergencePattern(),
    "engulfing": EngulfingPattern(),
    "support_resistance_break": SupportResistancePattern(),
    "ichimoku": IchimokuPattern(),
    "abc_correction": ABCCorrectionPattern(),
}


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _compute_rr(signal_type: str, details: dict, current_price: float) -> Optional[float]:
    """
    Compute Risk/Reward ratio from pattern details.
    Returns the ratio as a float (e.g. 3.0 means R/R = 1:3) or None if not computable.
    """
    support = details.get("support")
    resistance = details.get("resistance")
    neckline = details.get("neckline")

    if signal_type == "bullish":
        entry = resistance or neckline or current_price
        sl = support or current_price * 0.96
        tp1 = entry + (entry - sl) * 3.0
    else:  # bearish
        entry = support or neckline or current_price
        sl = resistance or current_price * 1.04
        tp1 = entry - (sl - entry) * 3.0

    risk = abs(entry - sl)
    reward = abs(tp1 - entry)

    if risk == 0:
        return None
    return reward / risk


def scan_asset(
    symbol: str,
    timeframe: str,
    asset_type: str,
    exchange: str,
    enabled_patterns: list[str],
    min_confidence: float,
    min_rr: float,
    cooldown_hours: int,
    czk_conversion: bool = False,
    base_symbol: Optional[str] = None,
) -> list[dict]:
    """
    Fetch data for one asset/timeframe and run all enabled patterns.
    Returns list of alert dicts that passed threshold and dedup check.
    """
    results = []

    logger.info("Scanning %s (%s) on %s", symbol, asset_type, timeframe)
    df = fetch_asset_data(
        symbol, timeframe, asset_type, exchange,
        czk_conversion=czk_conversion,
        base_symbol=base_symbol,
    )

    if df is None or df.empty:
        logger.warning("No data for %s %s – skipping", symbol, timeframe)
        return results

    current_price = float(df["close"].iloc[-1])
    logger.info("  Current price: %.4f | Candles: %d", current_price, len(df))

    for pattern_name in enabled_patterns:
        detector = ALL_PATTERNS.get(pattern_name)
        if detector is None:
            logger.warning("  Unknown pattern: %s", pattern_name)
            continue

        if not detector.supports_timeframe(timeframe):
            continue

        try:
            result = detector.detect(df)
        except Exception as exc:
            logger.error("  Pattern %s raised exception: %s", pattern_name, exc)
            continue

        if not result.found:
            continue

        logger.info(
            "  [%s] %s – type=%s confidence=%.1f",
            pattern_name, symbol, result.type, result.confidence,
        )

        results.append({
            "asset": symbol,
            "timeframe": timeframe,
            "pattern": pattern_name,
            "type": result.type,
            "confidence": result.confidence,
            "price": current_price,
            "details": result.details,
        })

        # Apply confidence threshold and cooldown for actual alerts
        if result.confidence < min_confidence:
            logger.info(
                "    Confidence %.1f < threshold %.1f – no alert sent",
                result.confidence, min_confidence,
            )
            continue

        # Apply R/R filter
        rr = _compute_rr(result.type, result.details, current_price)
        if rr is None or rr < min_rr:
            logger.info(
                "    R/R %.2f < min_rr %.1f – no alert sent",
                rr if rr is not None else 0.0, min_rr,
            )
            continue

        if db.is_duplicate(symbol, timeframe, pattern_name, cooldown_hours):
            logger.info("    Duplicate within %dh – skipping", cooldown_hours)
            continue

        # Extract key_levels and pattern_data from details for JSONB storage
        key_levels = {
            k: result.details.get(k)
            for k in ("support", "resistance", "neckline")
            if result.details.get(k) is not None
        }
        # pattern_data stores all coordinate points needed to redraw the pattern
        pattern_data = {k: v for k, v in result.details.items()}

        # Save to DB
        alert_id = db.save_alert(
            asset=symbol,
            timeframe=timeframe,
            pattern=pattern_name,
            signal_type=result.type,
            confidence=result.confidence,
            price=current_price,
            message_sent=False,
            key_levels=key_levels,
            pattern_data=pattern_data,
        )

        # Send Telegram notification
        sent = send_alert(
            asset=symbol,
            timeframe=timeframe,
            pattern=pattern_name,
            signal_type=result.type,
            confidence=result.confidence,
            price=current_price,
            details=result.details,
        )

        if sent and alert_id:
            db.mark_message_sent(alert_id)
            logger.info("    Alert sent! id=%s", alert_id)
        elif not sent:
            logger.warning("    Failed to send Telegram alert for %s %s %s", symbol, timeframe, pattern_name)

    return results


def run_scan(min_confidence: Optional[float] = None, min_rr: Optional[float] = None) -> list[dict]:
    """
    Main scan loop. Returns all detected patterns (regardless of threshold).
    """
    cfg = load_config()
    scanner_cfg = cfg.get("scanner", {})

    if min_confidence is None:
        min_confidence = float(scanner_cfg.get("min_confidence", 65))

    if min_rr is None:
        min_rr = float(scanner_cfg.get("min_rr", 3.0))

    cooldown_hours = int(scanner_cfg.get("alert_cooldown_hours", 24))
    enabled_patterns = scanner_cfg.get("patterns_enabled", list(ALL_PATTERNS.keys()))

    assets_cfg = cfg.get("assets", {})
    all_results = []

    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("Market Scanner started at %s", start_time.isoformat())
    logger.info("Config: min_confidence=%.0f, min_rr=%.1f, cooldown=%dh, patterns=%s",
                min_confidence, min_rr, cooldown_hours, enabled_patterns)
    logger.info("=" * 60)

    # --- Crypto assets ---
    for asset_cfg in assets_cfg.get("crypto", []):
        symbol = asset_cfg["symbol"]
        exchange = asset_cfg.get("exchange", "kucoin")
        timeframes = asset_cfg.get("timeframes", ["1h"])
        czk_conversion = asset_cfg.get("czk_conversion", False)
        base_symbol = asset_cfg.get("base_symbol")

        for tf in timeframes:
            try:
                results = scan_asset(
                    symbol=symbol,
                    timeframe=tf,
                    asset_type="crypto",
                    exchange=exchange,
                    enabled_patterns=enabled_patterns,
                    min_confidence=min_confidence,
                    min_rr=min_rr,
                    cooldown_hours=cooldown_hours,
                    czk_conversion=czk_conversion,
                    base_symbol=base_symbol,
                )
                all_results.extend(results)
            except Exception as exc:
                logger.error("Unhandled error scanning %s %s: %s", symbol, tf, exc)

    # --- Stock assets ---
    for asset_cfg in assets_cfg.get("stocks", []):
        symbol = asset_cfg["symbol"]
        timeframes = asset_cfg.get("timeframes", ["1d"])

        for tf in timeframes:
            try:
                results = scan_asset(
                    symbol=symbol,
                    timeframe=tf,
                    asset_type="stock",
                    exchange="",
                    enabled_patterns=enabled_patterns,
                    min_confidence=min_confidence,
                    min_rr=min_rr,
                    cooldown_hours=cooldown_hours,
                )
                all_results.extend(results)
            except Exception as exc:
                logger.error("Unhandled error scanning %s %s: %s", symbol, tf, exc)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info("=" * 60)
    logger.info(
        "Scan complete in %.1fs | %d patterns detected | %d above threshold",
        elapsed,
        len(all_results),
        sum(1 for r in all_results if r["confidence"] >= min_confidence),
    )
    logger.info("=" * 60)

    return all_results


if __name__ == "__main__":
    run_scan()
