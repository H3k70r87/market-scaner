"""
Golden Cross / Death Cross detector.

Golden Cross: EMA50 crosses above EMA200 (bullish)
Death Cross:  EMA50 crosses below EMA200 (bearish)

Confirmation: volume on cross candle is above average.
"""

import pandas as pd

from .base import BasePattern, PatternResult


class CrossesPattern(BasePattern):
    EMA_FAST = 50
    EMA_SLOW = 200
    VOLUME_MULTIPLIER = 1.2   # volume must be > 1.2× 20-bar average at the cross

    @property
    def name(self) -> str:
        return "golden_death_cross"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        required = self.EMA_SLOW + 10
        if len(df) < required:
            return self._not_found()

        closes = df["close"]
        volumes = df["volume"]

        ema_fast = closes.ewm(span=self.EMA_FAST, adjust=False).mean()
        ema_slow = closes.ewm(span=self.EMA_SLOW, adjust=False).mean()

        prev_diff = ema_fast.iloc[-2] - ema_slow.iloc[-2]
        curr_diff = ema_fast.iloc[-1] - ema_slow.iloc[-1]

        # Detect crossover
        crossed = (prev_diff < 0 and curr_diff > 0) or (prev_diff > 0 and curr_diff < 0)
        if not crossed:
            return self._not_found()

        # Volume confirmation
        avg_volume = volumes.iloc[-21:-1].mean()
        cross_volume = volumes.iloc[-1]
        volume_ratio = cross_volume / avg_volume if avg_volume > 0 else 0
        volume_confirmed = volume_ratio >= self.VOLUME_MULTIPLIER

        current_close = float(closes.iloc[-1])
        ema50_val = float(ema_fast.iloc[-1])
        ema200_val = float(ema_slow.iloc[-1])

        base_confidence = 65
        volume_bonus = min(15, (volume_ratio - 1) * 30) if volume_confirmed else 0
        separation = abs(curr_diff) / ema_slow.iloc[-1] * 100
        separation_bonus = min(10, separation * 20)
        confidence = min(100, base_confidence + volume_bonus + separation_bonus)

        if prev_diff < 0 and curr_diff > 0:
            # Golden Cross
            return self._result(
                "bullish",
                confidence,
                {
                    "ema50": round(ema50_val, 4),
                    "ema200": round(ema200_val, 4),
                    "volume_ratio": round(volume_ratio, 2),
                    "volume_confirmed": volume_confirmed,
                    "support": round(ema200_val, 4),
                    "resistance": round(current_close * 1.05, 4),
                    "current_close": round(current_close, 4),
                    "cross_type": "golden",
                },
            )
        else:
            # Death Cross
            return self._result(
                "bearish",
                confidence,
                {
                    "ema50": round(ema50_val, 4),
                    "ema200": round(ema200_val, 4),
                    "volume_ratio": round(volume_ratio, 2),
                    "volume_confirmed": volume_confirmed,
                    "support": round(current_close * 0.95, 4),
                    "resistance": round(ema200_val, 4),
                    "current_close": round(current_close, 4),
                    "cross_type": "death",
                },
            )
