"""
Ascending Triangle / Descending Triangle detector.

Ascending Triangle:
- Flat (horizontal) resistance + rising lows (higher lows trend)
- Price is compressing into the resistance

Descending Triangle:
- Flat support + falling highs (lower highs trend)
- Price is compressing into the support
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from .base import BasePattern, PatternResult


class TrianglesPattern(BasePattern):
    LOOKBACK = 50
    FLAT_TOLERANCE = 0.015   # 1.5% tolerance for "flat" level
    MIN_TOUCHES = 3

    @property
    def name(self) -> str:
        return "triangles"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        if len(df) < self.LOOKBACK:
            return self._not_found()

        data = df.tail(self.LOOKBACK).copy()
        highs = data["high"].values
        lows = data["low"].values
        closes = data["close"].values

        order = 4
        peak_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
        trough_idx = argrelextrema(lows, np.less_equal, order=order)[0]

        result = self._check_ascending(highs, lows, closes, peak_idx, trough_idx)
        if result.found:
            return result

        return self._check_descending(highs, lows, closes, peak_idx, trough_idx)

    def _check_ascending(self, highs, lows, closes, peak_idx, trough_idx) -> PatternResult:
        """Flat resistance + rising lows."""
        if len(peak_idx) < self.MIN_TOUCHES or len(trough_idx) < 2:
            return self._not_found()

        peak_prices = highs[peak_idx]
        resistance_level = np.median(peak_prices[-self.MIN_TOUCHES:])
        deviations = np.abs(peak_prices[-self.MIN_TOUCHES:] - resistance_level) / resistance_level

        if deviations.mean() > self.FLAT_TOLERANCE:
            return self._not_found()

        # Check rising lows
        trough_prices = lows[trough_idx]
        if len(trough_prices) < 2:
            return self._not_found()

        trough_slope = np.polyfit(range(len(trough_prices)), trough_prices, 1)[0]
        if trough_slope <= 0:
            return self._not_found()

        # Confirm price is near the resistance
        current_close = closes[-1]
        proximity = abs(current_close - resistance_level) / resistance_level
        if proximity > 0.03:
            return self._not_found()

        flatness_score = 1 - deviations.mean() / self.FLAT_TOLERANCE
        slope_score = min(trough_slope / lows.mean() * 100, 1.0)
        confidence = min(100, 60 + flatness_score * 20 + slope_score * 20)

        support = float(trough_prices[-1])
        return self._result(
            "bullish",
            confidence,
            {
                "resistance": round(float(resistance_level), 4),
                "support": round(support, 4),
                "rising_low_slope": round(float(trough_slope), 6),
                "touches": int(min(len(peak_idx), self.MIN_TOUCHES)),
                "current_close": round(float(current_close), 4),
            },
        )

    def _check_descending(self, highs, lows, closes, peak_idx, trough_idx) -> PatternResult:
        """Flat support + falling highs."""
        if len(trough_idx) < self.MIN_TOUCHES or len(peak_idx) < 2:
            return self._not_found()

        trough_prices = lows[trough_idx]
        support_level = np.median(trough_prices[-self.MIN_TOUCHES:])
        deviations = np.abs(trough_prices[-self.MIN_TOUCHES:] - support_level) / support_level

        if deviations.mean() > self.FLAT_TOLERANCE:
            return self._not_found()

        # Check falling highs
        peak_prices = highs[peak_idx]
        if len(peak_prices) < 2:
            return self._not_found()

        peak_slope = np.polyfit(range(len(peak_prices)), peak_prices, 1)[0]
        if peak_slope >= 0:
            return self._not_found()

        current_close = closes[-1]
        proximity = abs(current_close - support_level) / support_level
        if proximity > 0.03:
            return self._not_found()

        flatness_score = 1 - deviations.mean() / self.FLAT_TOLERANCE
        slope_score = min(abs(peak_slope) / highs.mean() * 100, 1.0)
        confidence = min(100, 60 + flatness_score * 20 + slope_score * 20)

        resistance = float(peak_prices[-1])
        return self._result(
            "bearish",
            confidence,
            {
                "support": round(float(support_level), 4),
                "resistance": round(resistance, 4),
                "falling_high_slope": round(float(peak_slope), 6),
                "touches": int(min(len(trough_idx), self.MIN_TOUCHES)),
                "current_close": round(float(current_close), 4),
            },
        )
