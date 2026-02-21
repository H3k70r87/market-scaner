"""
Bearish / Bullish Engulfing candlestick pattern.

Bullish Engulfing:
- Previous candle is bearish (red)
- Current candle is bullish (green) and completely engulfs the previous body

Bearish Engulfing:
- Previous candle is bullish (green)
- Current candle is bearish (red) and completely engulfs the previous body

Best on 4h or daily charts.
"""

import pandas as pd

from .base import BasePattern, PatternResult


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
                    "support": round(float(curr_bot), 4),
                    "resistance": round(current_close * 1.03, 4),
                    "current_close": round(current_close, 4),
                },
            )

        # Bearish Engulfing: previous bullish, current bearish
        if prev_body > 0 and curr_body < 0:
            trend_bonus = max(0, trend_slope) * 200
            size_bonus = min(20, (size_ratio - 1) * 20)
            confidence = min(100, 60 + trend_bonus + size_bonus)

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
                    "support": round(current_close * 0.97, 4),
                    "resistance": round(float(curr_top), 4),
                    "current_close": round(current_close, 4),
                },
            )

        return self._not_found()
