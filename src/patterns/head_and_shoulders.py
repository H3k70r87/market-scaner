"""
Head and Shoulders / Inverse Head and Shoulders detector.

Logic (H&S):
- Three peaks: left shoulder, head (highest), right shoulder
- Head is the highest; shoulders are within ±3% of each other
- Neckline connects the two troughs between peaks
- Confirmed by close below neckline

Inverse H&S is the mirror image (three troughs, middle is lowest).
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from .base import BasePattern, PatternResult


class HeadAndShouldersPattern(BasePattern):
    SHOULDER_TOLERANCE = 0.03  # 3% tolerance between shoulders

    @property
    def name(self) -> str:
        return "head_and_shoulders"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        if len(df) < 40:
            return self._not_found()

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values

        order = 5
        peak_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
        trough_idx = argrelextrema(lows, np.less_equal, order=order)[0]

        result = self._check_hs(highs, lows, closes, peak_idx, trough_idx)
        if result.found:
            return result

        return self._check_inverse_hs(highs, lows, closes, peak_idx, trough_idx)

    def _check_hs(self, highs, lows, closes, peak_idx, trough_idx) -> PatternResult:
        if len(peak_idx) < 3 or len(trough_idx) < 2:
            return self._not_found()

        # Use the three most recent peaks
        ls_i, head_i, rs_i = peak_idx[-3], peak_idx[-2], peak_idx[-1]
        ls, head, rs = highs[ls_i], highs[head_i], highs[rs_i]

        # Head must be the highest
        if not (head > ls and head > rs):
            return self._not_found()

        # Shoulders within ±3%
        avg_shoulder = (ls + rs) / 2
        if abs(ls - rs) / avg_shoulder > self.SHOULDER_TOLERANCE:
            return self._not_found()

        # Find troughs between ls-head and head-rs for neckline
        t1_candidates = [t for t in trough_idx if ls_i < t < head_i]
        t2_candidates = [t for t in trough_idx if head_i < t < rs_i]
        if not t1_candidates or not t2_candidates:
            return self._not_found()

        t1 = lows[t1_candidates[-1]]
        t2 = lows[t2_candidates[0]]
        neckline = (t1 + t2) / 2

        current_close = closes[-1]
        if current_close >= neckline:
            return self._not_found()

        symmetry = 1 - abs(ls - rs) / avg_shoulder / self.SHOULDER_TOLERANCE
        head_prominence = (head - avg_shoulder) / head
        break_depth = (neckline - current_close) / neckline
        confidence = min(100, 55 + symmetry * 15 + head_prominence * 100 * 5 + min(break_depth * 300, 15))

        return self._result(
            "bearish",
            confidence,
            {
                "left_shoulder": round(float(ls), 4),
                "head": round(float(head), 4),
                "right_shoulder": round(float(rs), 4),
                "neckline": round(float(neckline), 4),
                "current_close": round(float(current_close), 4),
                "support": round(float(neckline), 4),
                "resistance": round(float(head), 4),
            },
        )

    def _check_inverse_hs(self, highs, lows, closes, peak_idx, trough_idx) -> PatternResult:
        if len(trough_idx) < 3 or len(peak_idx) < 2:
            return self._not_found()

        ls_i, head_i, rs_i = trough_idx[-3], trough_idx[-2], trough_idx[-1]
        ls, head, rs = lows[ls_i], lows[head_i], lows[rs_i]

        # Head (middle trough) must be the lowest
        if not (head < ls and head < rs):
            return self._not_found()

        avg_shoulder = (ls + rs) / 2
        if abs(ls - rs) / avg_shoulder > self.SHOULDER_TOLERANCE:
            return self._not_found()

        p1_candidates = [p for p in peak_idx if ls_i < p < head_i]
        p2_candidates = [p for p in peak_idx if head_i < p < rs_i]
        if not p1_candidates or not p2_candidates:
            return self._not_found()

        n1 = highs[p1_candidates[-1]]
        n2 = highs[p2_candidates[0]]
        neckline = (n1 + n2) / 2

        current_close = closes[-1]
        if current_close <= neckline:
            return self._not_found()

        symmetry = 1 - abs(ls - rs) / avg_shoulder / self.SHOULDER_TOLERANCE
        head_depth = (avg_shoulder - head) / avg_shoulder
        break_height = (current_close - neckline) / neckline
        confidence = min(100, 55 + symmetry * 15 + head_depth * 100 * 5 + min(break_height * 300, 15))

        return self._result(
            "bullish",
            confidence,
            {
                "left_shoulder": round(float(ls), 4),
                "head": round(float(head), 4),
                "right_shoulder": round(float(rs), 4),
                "neckline": round(float(neckline), 4),
                "current_close": round(float(current_close), 4),
                "support": round(float(head), 4),
                "resistance": round(float(neckline), 4),
            },
        )
