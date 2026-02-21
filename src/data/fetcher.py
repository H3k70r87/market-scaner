"""
Data fetcher for stocks (yfinance) and crypto (ccxt – KuCoin public API).
Returns normalized OHLCV DataFrames with columns: open, high, low, close, volume.

NOTE: Binance blocks GitHub Actions servers (HTTP 451 geo-restriction).
      We use KuCoin instead – no API key required, no geo-restrictions.
      Coinmate does not support OHLCV via ccxt.
      BTC/CZK and ETH/CZK are fetched as USDT pairs and converted via CNB rate.
"""

import logging
import time
from typing import Optional

import ccxt
import pandas as pd
import requests
import yfinance as yf

# Cache for CNB USD/CZK rate (valid 1 hour)
_czk_rate_cache: dict = {"rate": None, "ts": 0}

logger = logging.getLogger(__name__)

# Browser-like User-Agent – prevents Yahoo Finance from blocking requests
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
})

# Timeframe mappings
CCXT_TIMEFRAME_MAP = {
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

# Number of candles to fetch per timeframe
CANDLE_COUNTS = {
    "1h": 200,
    "4h": 200,
    "1d": 200,
}


def _retry(func, *args, max_attempts: int = 3, **kwargs):
    """Exponential backoff retry wrapper."""
    delays = [2, 4, 8]
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_attempts - 1:
                raise
            wait = delays[attempt]
            logger.warning(
                "Attempt %d/%d failed: %s – retrying in %ds",
                attempt + 1, max_attempts, exc, wait,
            )
            time.sleep(wait)


def _resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """Resample 1h OHLCV DataFrame to 4h candles."""
    df = df_1h.copy()
    df.index = pd.to_datetime(df.index)
    ohlcv_4h = df.resample("4h").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    ).dropna()
    return ohlcv_4h


def fetch_stock_data(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Fetch stock OHLCV data via yfinance with browser User-Agent.
    """
    try:
        if timeframe in ("1h", "4h"):
            interval = "1h"
            period = "60d"
        else:
            interval = "1d"
            period = "1y"

        def _download():
            ticker = yf.Ticker(symbol, session=_SESSION)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            return df

        df = _retry(_download)

        if df is None or df.empty:
            logger.warning("No data returned for stock %s (%s)", symbol, timeframe)
            return None

        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.to_datetime(df.index, utc=True)

        if timeframe == "4h":
            df = _resample_to_4h(df)

        n = CANDLE_COUNTS.get(timeframe, 200)
        df = df.tail(n)

        logger.info("Fetched %d candles for %s (%s)", len(df), symbol, timeframe)
        return df

    except Exception as exc:
        logger.error("Failed to fetch stock data for %s (%s): %s", symbol, timeframe, exc)
        return None


def fetch_crypto_data(symbol: str, exchange_id: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Fetch crypto OHLCV data via ccxt.
    Default exchange: KuCoin (no geo-restrictions, no API key needed).
    Binance is blocked on GitHub Actions (HTTP 451).
    """
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange: ccxt.Exchange = exchange_class({"enableRateLimit": True})

        ccxt_tf = CCXT_TIMEFRAME_MAP.get(timeframe, timeframe)
        limit = CANDLE_COUNTS.get(timeframe, 200)

        def _fetch():
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=ccxt_tf, limit=limit)
            return ohlcv

        ohlcv = _retry(_fetch)

        if not ohlcv:
            logger.warning("No data returned for crypto %s (%s)", symbol, timeframe)
            return None

        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        df = df.astype(float)

        logger.info("Fetched %d candles for %s (%s)", len(df), symbol, timeframe)
        return df

    except Exception as exc:
        logger.error(
            "Failed to fetch crypto data for %s/%s (%s): %s",
            symbol, exchange_id, timeframe, exc,
        )
        return None


def get_usd_czk_rate() -> Optional[float]:
    """
    Fetch current USD/CZK exchange rate from CNB (Czech National Bank) public API.
    Free, no API key required. Cached for 1 hour.
    """
    now = time.time()
    if _czk_rate_cache["rate"] and now - _czk_rate_cache["ts"] < 3600:
        return _czk_rate_cache["rate"]

    try:
        # CNB daily FX rates – plain text format
        resp = requests.get(
            "https://www.cnb.cz/en/financial-markets/foreign-exchange-market/"
            "central-bank-exchange-rate-fixing/central-bank-exchange-rate-fixing/"
            "daily.txt",
            timeout=10,
        )
        resp.raise_for_status()
        # Format: Country|Currency|Amount|Code|Rate
        for line in resp.text.splitlines():
            parts = line.split("|")
            if len(parts) == 5 and parts[3] == "USD":
                amount = float(parts[2])
                rate = float(parts[4].replace(",", "."))
                usd_czk = rate / amount
                _czk_rate_cache["rate"] = usd_czk
                _czk_rate_cache["ts"] = now
                logger.info("USD/CZK rate from CNB: %.2f", usd_czk)
                return usd_czk
    except Exception as exc:
        logger.error("Failed to fetch USD/CZK rate from CNB: %s", exc)

    # Fallback: approximate rate
    logger.warning("Using fallback USD/CZK rate: 23.0")
    return 23.0


def fetch_czk_data(base_symbol: str, exchange_id: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Fetch USDT pair (e.g. BTC/USDT) and convert all price columns to CZK
    using the current USD/CZK rate from CNB.
    """
    df = fetch_crypto_data(base_symbol, exchange_id, timeframe)
    if df is None or df.empty:
        return None

    rate = get_usd_czk_rate()
    if rate is None:
        return None

    price_cols = ["open", "high", "low", "close"]
    df[price_cols] = df[price_cols] * rate
    logger.info(
        "Converted %s → CZK at rate %.2f (source: CNB)", base_symbol, rate
    )
    return df


def fetch_asset_data(
    symbol: str,
    timeframe: str,
    asset_type: str,
    exchange: str = "kucoin",
    czk_conversion: bool = False,
    base_symbol: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Unified entry point. Returns a normalized OHLCV DataFrame or None.

    Args:
        symbol: Display symbol (e.g. 'BTC/CZK')
        timeframe: '1h', '4h', or '1d'
        asset_type: 'stock' or 'crypto'
        exchange: Exchange id for crypto (default 'kucoin')
        czk_conversion: If True, fetch base_symbol in USDT and convert to CZK via CNB
        base_symbol: USDT pair to fetch when czk_conversion=True (e.g. 'BTC/USDT')
    """
    if czk_conversion and base_symbol:
        return fetch_czk_data(base_symbol, exchange, timeframe)
    elif asset_type == "stock":
        return fetch_stock_data(symbol, timeframe)
    elif asset_type == "crypto":
        return fetch_crypto_data(symbol, exchange, timeframe)
    else:
        logger.error("Unknown asset_type: %s", asset_type)
        return None
