"""
RSI Divergence detector.

Bullish divergence: price makes a lower low, RSI makes a higher low (hidden strength).
Bearish divergence: price makes a higher high, RSI makes a lower high (hidden weakness).

Lookback: last 20 candles.
"""

import numpy as np
import pandas as pd

from .base import BasePattern, PatternResult


def _rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


class RSIDivergencePattern(BasePattern):
    LOOKBACK = 20
    RSI_PERIOD = 14

    @property
    def name(self) -> str:
        return "rsi_divergence"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["1h", "4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        needed = self.LOOKBACK + self.RSI_PERIOD + 5
        if len(df) < needed:
            return self._not_found()

        closes = df["close"]
        rsi = _rsi(closes, self.RSI_PERIOD).dropna()

        if len(rsi) < self.LOOKBACK:
            return self._not_found()

        # Align recent window
        recent_close = closes.iloc[-self.LOOKBACK:].values
        recent_rsi = rsi.iloc[-self.LOOKBACK:].values

        # Compare latest vs mid-window extremes
        mid = self.LOOKBACK // 2

        # --- Bullish divergence: price lower low, RSI higher low ---
        price_low_recent = np.min(recent_close[mid:])
        price_low_past = np.min(recent_close[:mid])
        rsi_low_recent = np.min(recent_rsi[mid:])
        rsi_low_past = np.min(recent_rsi[:mid])

        if price_low_recent < price_low_past and rsi_low_recent > rsi_low_past:
            price_divergence = (price_low_past - price_low_recent) / price_low_past
            rsi_divergence = (rsi_low_recent - rsi_low_past) / (100 - rsi_low_past + 0.01)
            confidence = min(100, 55 + price_divergence * 500 + rsi_divergence * 100)

            if confidence >= 55:
                current_close = float(closes.iloc[-1])
                return self._result(
                    "bullish",
                    confidence,
                    {
                        "price_low_recent": round(float(price_low_recent), 4),
                        "price_low_past": round(float(price_low_past), 4),
                        "rsi_low_recent": round(float(rsi_low_recent), 2),
                        "rsi_low_past": round(float(rsi_low_past), 2),
                        "current_rsi": round(float(recent_rsi[-1]), 2),
                        "support": round(float(price_low_recent), 4),
                        "resistance": round(current_close * 1.04, 4),
                        "current_close": round(current_close, 4),
                    },
                )

        # --- Bearish divergence: price higher high, RSI lower high ---
        price_high_recent = np.max(recent_close[mid:])
        price_high_past = np.max(recent_close[:mid])
        rsi_high_recent = np.max(recent_rsi[mid:])
        rsi_high_past = np.max(recent_rsi[:mid])

        if price_high_recent > price_high_past and rsi_high_recent < rsi_high_past:
            price_divergence = (price_high_recent - price_high_past) / price_high_past
            rsi_divergence = (rsi_high_past - rsi_high_recent) / (rsi_high_past + 0.01)
            confidence = min(100, 55 + price_divergence * 500 + rsi_divergence * 100)

            if confidence >= 55:
                current_close = float(closes.iloc[-1])
                return self._result(
                    "bearish",
                    confidence,
                    {
                        "price_high_recent": round(float(price_high_recent), 4),
                        "price_high_past": round(float(price_high_past), 4),
                        "rsi_high_recent": round(float(rsi_high_recent), 2),
                        "rsi_high_past": round(float(rsi_high_past), 2),
                        "current_rsi": round(float(recent_rsi[-1]), 2),
                        "support": round(current_close * 0.96, 4),
                        "resistance": round(float(price_high_recent), 4),
                        "current_close": round(current_close, 4),
                    },
                )

        return self._not_found()
