"""
Double Top / Double Bottom detector.

Logic:
- Find two similar peaks (tops) or troughs (bottoms) within ±2% of each other.
- Verify a valley/peak between them (the "neckline" area).
- Confirm breakout through the neckline.
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from .base import BasePattern, PatternResult


class DoubleTopBottomPattern(BasePattern):
    TOLERANCE = 0.02  # 2% price tolerance between the two peaks/troughs

    @property
    def name(self) -> str:
        return "double_top_bottom"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["1h", "4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        if len(df) < 30:
            return self._not_found()

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values

        # Find local maxima and minima (order=5: at least 5 bars on each side)
        order = 5
        peak_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
        trough_idx = argrelextrema(lows, np.less_equal, order=order)[0]

        # --- Double Top ---
        result = self._check_double_top(highs, lows, closes, peak_idx, trough_idx)
        if result.found:
            return result

        # --- Double Bottom ---
        result = self._check_double_bottom(highs, lows, closes, peak_idx, trough_idx)
        return result

    def _check_double_top(self, highs, lows, closes, peak_idx, trough_idx) -> PatternResult:
        if len(peak_idx) < 2 or len(trough_idx) < 1:
            return self._not_found()

        # Use the two most recent peaks
        p1_i, p2_i = peak_idx[-2], peak_idx[-1]
        p1, p2 = highs[p1_i], highs[p2_i]

        # Check peaks are within tolerance
        avg_peak = (p1 + p2) / 2
        if abs(p1 - p2) / avg_peak > self.TOLERANCE:
            return self._not_found()

        # Find a trough between the two peaks
        troughs_between = [t for t in trough_idx if p1_i < t < p2_i]
        if not troughs_between:
            return self._not_found()

        neckline = lows[troughs_between[0]]

        # Confirm neckline break: current close below neckline
        current_close = closes[-1]
        if current_close >= neckline:
            return self._not_found()

        # Calculate confidence
        peak_similarity = 1 - abs(p1 - p2) / avg_peak / self.TOLERANCE
        break_depth = (neckline - current_close) / neckline
        confidence = min(100, 60 + peak_similarity * 20 + min(break_depth * 200, 20))

        return self._result(
            "bearish",
            confidence,
            {
                "peak1": round(float(p1), 4),
                "peak2": round(float(p2), 4),
                "peak1_bar": int(p1_i),   # index v df pro přesné zakreslení
                "peak2_bar": int(p2_i),   # index v df pro přesné zakreslení
                "neckline": round(float(neckline), 4),
                "current_close": round(float(current_close), 4),
                "support": round(float(neckline), 4),
                "resistance": round(float(avg_peak), 4),
            },
        )

    def _check_double_bottom(self, highs, lows, closes, peak_idx, trough_idx) -> PatternResult:
        if len(trough_idx) < 2 or len(peak_idx) < 1:
            return self._not_found()

        t1_i, t2_i = trough_idx[-2], trough_idx[-1]
        t1, t2 = lows[t1_i], lows[t2_i]

        avg_trough = (t1 + t2) / 2
        if abs(t1 - t2) / avg_trough > self.TOLERANCE:
            return self._not_found()

        # Find a peak between the two troughs (neckline)
        peaks_between = [p for p in peak_idx if t1_i < p < t2_i]
        if not peaks_between:
            return self._not_found()

        neckline = highs[peaks_between[0]]
        current_close = closes[-1]

        # Confirm neckline break: current close above neckline
        if current_close <= neckline:
            return self._not_found()

        trough_similarity = 1 - abs(t1 - t2) / avg_trough / self.TOLERANCE
        break_height = (current_close - neckline) / neckline
        confidence = min(100, 60 + trough_similarity * 20 + min(break_height * 200, 20))

        return self._result(
            "bullish",
            confidence,
            {
                "trough1": round(float(t1), 4),
                "trough2": round(float(t2), 4),
                "trough1_bar": int(t1_i),   # index v df pro přesné zakreslení
                "trough2_bar": int(t2_i),   # index v df pro přesné zakreslení
                "neckline": round(float(neckline), 4),
                "current_close": round(float(current_close), 4),
                "support": round(float(avg_trough), 4),
                "resistance": round(float(neckline), 4),
            },
        )
