"""
Data fetcher for stocks (yfinance) and crypto (ccxt/Binance public API).
Returns normalized OHLCV DataFrames with columns: open, high, low, close, volume.
"""

import logging
import time
from typing import Optional

import ccxt
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Timeframe mappings
YFINANCE_INTERVAL_MAP = {
    "1h": "1h",
    "4h": "1h",   # yfinance has no 4h; fetch 1h and resample
    "1d": "1d",
}

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
    Fetch stock OHLCV data via yfinance.

    Args:
        symbol: Ticker symbol, e.g. 'AAPL'
        timeframe: One of '1h', '4h', '1d'

    Returns:
        DataFrame with columns [open, high, low, close, volume] or None on failure.
    """
    try:
        if timeframe in ("1h", "4h"):
            interval = "1h"
            period = "60d"
        else:
            interval = "1d"
            period = "1y"

        def _download():
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            return df

        df = _retry(_download)

        if df is None or df.empty:
            logger.warning("No data returned for stock %s (%s)", symbol, timeframe)
            return None

        # Normalize column names
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.to_datetime(df.index, utc=True)

        if timeframe == "4h":
            df = _resample_to_4h(df)

        # Keep last N candles
        n = CANDLE_COUNTS.get(timeframe, 200)
        df = df.tail(n)

        logger.info("Fetched %d candles for %s (%s)", len(df), symbol, timeframe)
        return df

    except Exception as exc:
        logger.error("Failed to fetch stock data for %s (%s): %s", symbol, timeframe, exc)
        return None


def fetch_crypto_data(symbol: str, exchange_id: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Fetch crypto OHLCV data via ccxt (Binance public API – no API key required).

    Args:
        symbol: Trading pair, e.g. 'BTC/USDT'
        exchange_id: Exchange name, e.g. 'binance'
        timeframe: One of '1h', '4h', '1d'

    Returns:
        DataFrame with columns [open, high, low, close, volume] or None on failure.
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


def fetch_asset_data(
    symbol: str, timeframe: str, asset_type: str, exchange: str = "binance"
) -> Optional[pd.DataFrame]:
    """
    Unified entry point. Returns a normalized OHLCV DataFrame or None.

    Args:
        symbol: Ticker or trading pair
        timeframe: '1h', '4h', or '1d'
        asset_type: 'stock' or 'crypto'
        exchange: Exchange id for crypto (default 'binance')
    """
    if asset_type == "stock":
        return fetch_stock_data(symbol, timeframe)
    elif asset_type == "crypto":
        return fetch_crypto_data(symbol, exchange, timeframe)
    else:
        logger.error("Unknown asset_type: %s", asset_type)
        return None
