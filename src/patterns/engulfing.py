"""
Bearish / Bullish Engulfing candlestick pattern.

Bullish Engulfing:
- Previous candle is bearish (red)
- Current candle is bullish (green) and completely engulfs the previous body

Bearish Engulfing:
- Previous candle is bullish (green)
- Current candle is bearish (red) and completely engulfs the previous body

Best on 4h or daily charts.

Podpora a odpor jsou odvozeny ze skutečných swing high/low z posledních N svíček:
- Odpor (bullish): nejbližší lokální maximum NAD aktuální cenou (kde cena může narazit)
- Podpora (bearish): nejbližší lokální minimum POD aktuální cenou (kde může hledat dno)
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from .base import BasePattern, PatternResult


def _nearest_swing_high(df: pd.DataFrame, current_close: float, lookback: int = 50) -> float:
    """
    Vrátí nejbližší swing high NAD aktuální cenou z posledních `lookback` svíček.
    Pokud žádný neexistuje, vrátí nejvyšší high z okna.
    """
    window = df.tail(lookback)
    highs = window["high"].values
    peak_idx = argrelextrema(highs, np.greater_equal, order=3)[0]
    above = [highs[i] for i in peak_idx if highs[i] > current_close]
    if above:
        return float(min(above))  # nejbližší nad cenou
    return float(highs.max())


def _nearest_swing_low(df: pd.DataFrame, current_close: float, lookback: int = 50) -> float:
    """
    Vrátí nejbližší swing low POD aktuální cenou z posledních `lookback` svíček.
    Pokud žádný neexistuje, vrátí nejnižší low z okna.
    """
    window = df.tail(lookback)
    lows = window["low"].values
    trough_idx = argrelextrema(lows, np.less_equal, order=3)[0]
    below = [lows[i] for i in trough_idx if lows[i] < current_close]
    if below:
        return float(max(below))  # nejbližší pod cenou
    return float(lows.min())


class EngulfingPattern(BasePattern):
    MIN_BODY_RATIO = 0.5      # current body must be at least 50% larger than previous
    TREND_LOOKBACK = 10       # bars to determine prior trend

    @property
    def name(self) -> str:
        return "engulfing"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        if len(df) < self.TREND_LOOKBACK + 2:
            return self._not_found()

        prev = df.iloc[-2]
        curr = df.iloc[-1]

        prev_body = prev["close"] - prev["open"]
        curr_body = curr["close"] - curr["open"]

        prev_body_size = abs(prev_body)
        curr_body_size = abs(curr_body)

        if prev_body_size == 0 or curr_body_size == 0:
            return self._not_found()

        # Engulfing: current body must fully contain previous body
        prev_top = max(prev["open"], prev["close"])
        prev_bot = min(prev["open"], prev["close"])
        curr_top = max(curr["open"], curr["close"])
        curr_bot = min(curr["open"], curr["close"])

        fully_engulfs = curr_top >= prev_top and curr_bot <= prev_bot
        if not fully_engulfs:
            return self._not_found()

        # Size ratio for confidence
        size_ratio = curr_body_size / prev_body_size

        # Prior trend confirmation
        trend_prices = df["close"].iloc[-(self.TREND_LOOKBACK + 2):-2]
        trend_slope = (trend_prices.iloc[-1] - trend_prices.iloc[0]) / trend_prices.iloc[0]

        current_close = float(curr["close"])

        # Bullish Engulfing: previous bearish, current bullish
        if prev_body < 0 and curr_body > 0:
            # Better if it appears at end of downtrend
            trend_bonus = max(0, -trend_slope) * 200
            size_bonus = min(20, (size_ratio - 1) * 20)
            confidence = min(100, 60 + trend_bonus + size_bonus)

            # Podpora = spodek engulfing svíčky (skutečné dno vzoru)
            support_level = round(float(curr_bot), 4)
            # Odpor = nejbližší swing high NAD cenou (skutečná TA úroveň)
            resistance_level = round(_nearest_swing_high(df, current_close), 4)

            return self._result(
                "bullish",
                confidence,
                {
                    "prev_open": round(float(prev["open"]), 4),
                    "prev_close": round(float(prev["close"]), 4),
                    "curr_open": round(float(curr["open"]), 4),
                    "curr_close": round(float(current_close), 4),
                    "size_ratio": round(size_ratio, 2),
                    "prior_trend_pct": round(trend_slope * 100, 2),
                    "support": support_level,
                    "resistance": resistance_level,
                    "current_close": round(current_close, 4),
                },
            )

        # Bearish Engulfing: previous bullish, current bearish
        if prev_body > 0 and curr_body < 0:
            trend_bonus = max(0, trend_slope) * 200
            size_bonus = min(20, (size_ratio - 1) * 20)
            confidence = min(100, 60 + trend_bonus + size_bonus)

            # Odpor = vršek engulfing svíčky (skutečný strop vzoru)
            resistance_level = round(float(curr_top), 4)
            # Podpora = nejbližší swing low POD cenou (skutečná TA úroveň)
            support_level = round(_nearest_swing_low(df, current_close), 4)

            return self._result(
                "bearish",
                confidence,
                {
                    "prev_open": round(float(prev["open"]), 4),
                    "prev_close": round(float(prev["close"]), 4),
                    "curr_open": round(float(curr["open"]), 4),
                    "curr_close": round(float(current_close), 4),
                    "size_ratio": round(size_ratio, 2),
                    "prior_trend_pct": round(trend_slope * 100, 2),
                    "support": support_level,
                    "resistance": resistance_level,
                    "current_close": round(current_close, 4),
                },
            )

        return self._not_found()
