"""
Technical indicator calculations for the dashboard.
All functions accept a pandas DataFrame with columns [open, high, low, close, volume].
"""

import numpy as np
import pandas as pd


def add_ema(df: pd.DataFrame, period: int, col: str = "close") -> pd.Series:
    """Exponential Moving Average."""
    return df[col].ewm(span=period, adjust=False).mean()


def add_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std: float = 2.0, col: str = "close"
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper_band, middle_band, lower_band)."""
    mid = df[col].rolling(period).mean()
    sigma = df[col].rolling(period).std()
    upper = mid + std * sigma
    lower = mid - std * sigma
    return upper, mid, lower


def add_rsi(df: pd.DataFrame, period: int = 14, col: str = "close") -> pd.Series:
    """Relative Strength Index."""
    delta = df[col].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    col: str = "close",
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    ema_fast = df[col].ewm(span=fast, adjust=False).mean()
    ema_slow = df[col].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram


def compute_all(df: pd.DataFrame) -> dict:
    """
    Compute all indicators and return as a dict of Series.
    Used by the dashboard to add indicator traces to the chart.
    """
    if df is None or df.empty or len(df) < 20:
        return {}

    result = {}

    try:
        result["ema20"] = add_ema(df, 20)
        result["ema50"] = add_ema(df, 50)
        result["ema200"] = add_ema(df, 200)
        result["bb_upper"], result["bb_mid"], result["bb_lower"] = add_bollinger_bands(df)
        result["rsi"] = add_rsi(df)
        result["macd"], result["macd_signal"], result["macd_hist"] = add_macd(df)
    except Exception:
        pass

    return result


def get_current_indicators(df: pd.DataFrame) -> dict:
    """
    Returns a flat dict of current indicator values for the metrics row.
    """
    if df is None or df.empty:
        return {}

    indicators = compute_all(df)
    current = {}

    for key, series in indicators.items():
        if series is not None and not series.empty:
            val = series.dropna()
            current[key] = float(val.iloc[-1]) if not val.empty else None

    # 24h change
    if len(df) >= 2:
        price_now = float(df["close"].iloc[-1])
        # For 1d timeframe: yesterday's close; for intraday: first candle of "day"
        price_prev = float(df["close"].iloc[-2])
        current["change_pct"] = (price_now - price_prev) / price_prev * 100
    else:
        current["change_pct"] = 0.0

    return current
