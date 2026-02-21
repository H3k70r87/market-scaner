"""
Bull Flag / Bear Flag detector.

Logic (Bull Flag):
- Strong bullish impulse: price rises >3% in the last 5 candles (the pole)
- Followed by a tight consolidation channel: range < 1.5% over next N candles
- Channel should be slightly downward-sloping or horizontal (not reversing)

Bear Flag is the mirror image.
"""

import numpy as np
import pandas as pd

from .base import BasePattern, PatternResult


class FlagsPattern(BasePattern):
    IMPULSE_THRESHOLD = 0.03     # 3% move for the pole
    CHANNEL_WIDTH_MAX = 0.015    # 1.5% max range during consolidation
    POLE_BARS = 5
    CONSOLIDATION_BARS = 10

    @property
    def name(self) -> str:
        return "bull_bear_flag"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["1h", "4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        min_bars = self.POLE_BARS + self.CONSOLIDATION_BARS + 2
        if len(df) < min_bars:
            return self._not_found()

        # Split recent data into pole + consolidation
        consol = df.iloc[-(self.CONSOLIDATION_BARS):]
        pole_end_idx = len(df) - self.CONSOLIDATION_BARS
        pole = df.iloc[max(0, pole_end_idx - self.POLE_BARS): pole_end_idx]

        if len(pole) < self.POLE_BARS:
            return self._not_found()

        pole_open = pole["close"].iloc[0]
        pole_close = pole["close"].iloc[-1]
        pole_move = (pole_close - pole_open) / pole_open

        # Consolidation channel width
        consol_high = consol["high"].max()
        consol_low = consol["low"].min()
        channel_mid = (consol_high + consol_low) / 2
        channel_width = (consol_high - consol_low) / channel_mid if channel_mid > 0 else 1

        # Channel slope (close trend during consolidation)
        consol_slope = (consol["close"].iloc[-1] - consol["close"].iloc[0]) / consol["close"].iloc[0]

        current_close = df["close"].iloc[-1]

        # --- Bull Flag ---
        if pole_move > self.IMPULSE_THRESHOLD and channel_width < self.CHANNEL_WIDTH_MAX:
            # Slope should be neutral or slightly negative (flag dips a bit)
            if consol_slope > 0.01:
                return self._not_found()

            impulse_score = min((pole_move - self.IMPULSE_THRESHOLD) / self.IMPULSE_THRESHOLD, 1.0)
            tightness_score = 1 - channel_width / self.CHANNEL_WIDTH_MAX
            confidence = min(100, 60 + impulse_score * 20 + tightness_score * 20)

            return self._result(
                "bullish",
                confidence,
                {
                    "pole_move_pct": round(pole_move * 100, 2),
                    "channel_width_pct": round(channel_width * 100, 2),
                    "pole_start": round(float(pole_open), 4),
                    "pole_end": round(float(pole_close), 4),
                    "support": round(float(consol_low), 4),
                    "resistance": round(float(consol_high), 4),
                    "current_close": round(float(current_close), 4),
                },
            )

        # --- Bear Flag ---
        if pole_move < -self.IMPULSE_THRESHOLD and channel_width < self.CHANNEL_WIDTH_MAX:
            if consol_slope < -0.01:
                return self._not_found()

            impulse_score = min((abs(pole_move) - self.IMPULSE_THRESHOLD) / self.IMPULSE_THRESHOLD, 1.0)
            tightness_score = 1 - channel_width / self.CHANNEL_WIDTH_MAX
            confidence = min(100, 60 + impulse_score * 20 + tightness_score * 20)

            return self._result(
                "bearish",
                confidence,
                {
                    "pole_move_pct": round(pole_move * 100, 2),
                    "channel_width_pct": round(channel_width * 100, 2),
                    "pole_start": round(float(pole_open), 4),
                    "pole_end": round(float(pole_close), 4),
                    "support": round(float(consol_low), 4),
                    "resistance": round(float(consol_high), 4),
                    "current_close": round(float(current_close), 4),
                },
            )

        return self._not_found()
