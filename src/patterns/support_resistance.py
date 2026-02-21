"""
Support / Resistance Break detector.

Logic:
- Find price levels touched 3+ times in the last 50 candles (within ±0.5% tolerance)
- Detect if the current candle breaks through such a level
- Confirm with volume > 1.5× 20-bar average
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from .base import BasePattern, PatternResult


class SupportResistancePattern(BasePattern):
    LOOKBACK = 50
    MIN_TOUCHES = 3
    LEVEL_TOLERANCE = 0.005   # 0.5% tolerance for clustering touches
    VOLUME_MULTIPLIER = 1.5

    @property
    def name(self) -> str:
        return "support_resistance_break"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["1h", "4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        if len(df) < self.LOOKBACK + 5:
            return self._not_found()

        data = df.tail(self.LOOKBACK + 5)
        # Use LOOKBACK bars (excluding latest 2 for confirmation)
        history = data.iloc[:-2]
        current = data.iloc[-1]
        prev = data.iloc[-2]

        highs = history["high"].values
        lows = history["low"].values
        closes = history["close"].values
        volumes = data["volume"].values

        # Candidate levels: local peaks and troughs
        order = 3
        peak_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
        trough_idx = argrelextrema(lows, np.less_equal, order=order)[0]

        candidate_levels = []
        for idx in peak_idx:
            candidate_levels.append(("resistance", highs[idx]))
        for idx in trough_idx:
            candidate_levels.append(("support", lows[idx]))

        if not candidate_levels:
            return self._not_found()

        # Cluster nearby levels
        levels = self._cluster_levels(candidate_levels, closes)

        # Current close and volume
        current_close = float(current["close"])
        prev_close = float(prev["close"])
        avg_volume = np.mean(volumes[-21:-1]) if len(volumes) > 21 else np.mean(volumes[:-1])
        current_volume = float(current["volume"])
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        volume_confirmed = volume_ratio >= self.VOLUME_MULTIPLIER

        for level_type, price, touches in levels:
            if touches < self.MIN_TOUCHES:
                continue

            # Breakout: previous close was on one side, current is on the other
            if level_type == "resistance":
                broke_up = prev_close < price and current_close > price
                if broke_up:
                    touch_score = min(touches / 5, 1.0)
                    vol_score = min((volume_ratio - 1) / 2, 1.0) if volume_confirmed else 0
                    confidence = min(100, 60 + touch_score * 20 + vol_score * 20)
                    return self._result(
                        "bullish",
                        confidence,
                        {
                            "level_type": "resistance",
                            "level_price": round(price, 4),
                            "touches": touches,
                            "volume_ratio": round(volume_ratio, 2),
                            "volume_confirmed": volume_confirmed,
                            "support": round(price, 4),
                            "resistance": round(price * 1.03, 4),
                            "current_close": round(current_close, 4),
                        },
                    )
            elif level_type == "support":
                broke_down = prev_close > price and current_close < price
                if broke_down:
                    touch_score = min(touches / 5, 1.0)
                    vol_score = min((volume_ratio - 1) / 2, 1.0) if volume_confirmed else 0
                    confidence = min(100, 60 + touch_score * 20 + vol_score * 20)
                    return self._result(
                        "bearish",
                        confidence,
                        {
                            "level_type": "support",
                            "level_price": round(price, 4),
                            "touches": touches,
                            "volume_ratio": round(volume_ratio, 2),
                            "volume_confirmed": volume_confirmed,
                            "support": round(price * 0.97, 4),
                            "resistance": round(price, 4),
                            "current_close": round(current_close, 4),
                        },
                    )

        return self._not_found()

    def _cluster_levels(self, candidates: list, closes: np.ndarray) -> list:
        """Cluster candidate levels into significant price levels with touch counts."""
        if not candidates:
            return []

        price_range = closes.max() - closes.min()
        if price_range == 0:
            return []

        clustered = []
        used = [False] * len(candidates)

        for i, (ltype, price) in enumerate(candidates):
            if used[i]:
                continue
            cluster_prices = [price]
            cluster_types = [ltype]
            used[i] = True

            for j, (ltype2, price2) in enumerate(candidates):
                if used[j]:
                    continue
                if abs(price - price2) / price < self.LEVEL_TOLERANCE:
                    cluster_prices.append(price2)
                    cluster_types.append(ltype2)
                    used[j] = True

            avg_price = np.mean(cluster_prices)
            touches = len(cluster_prices)
            # Determine dominant type
            n_resist = cluster_types.count("resistance")
            n_support = cluster_types.count("support")
            dominant = "resistance" if n_resist >= n_support else "support"
            clustered.append((dominant, avg_price, touches))

        # Sort by touches descending
        clustered.sort(key=lambda x: x[2], reverse=True)
        return clustered
