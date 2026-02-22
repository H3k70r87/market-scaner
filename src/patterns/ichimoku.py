"""
Ichimoku Cloud pattern detector.

Logika detekce:
- Spočítá všechny 5 složek Ichimoku: Tenkan-sen, Kijun-sen, Senkou Span A, Senkou Span B, Chikou Span
- Bullish signál (silný TK Cross):
    * Tenkan překříží Kijun zdola (TK Cross)
    * Cena je NAD cloudem (Senkou Span A > Senkou Span B → zelený cloud)
    * Chikou Span je nad cenou před 26 svíčkami
    * Cloud je bullish (Span A > Span B)
- Bearish signál (silný TK Cross):
    * Tenkan překříží Kijun shora (TK Cross)
    * Cena je POD cloudem (Senkou Span B > Senkou Span A → červený cloud)
    * Chikou Span je pod cenou před 26 svíčkami
    * Cloud je bearish (Span B > Span A)

Confidence:
    - Základní TK cross: 60
    - Cena nad/pod cloudem: +15
    - Chikou potvrzení: +15
    - Cloud barva souhlasí: +10
"""

import numpy as np
import pandas as pd

from .base import BasePattern, PatternResult


class IchimokuPattern(BasePattern):
    # Standardní Ichimoku parametry
    TENKAN_PERIOD = 9
    KIJUN_PERIOD = 26
    SENKOU_B_PERIOD = 52
    CHIKOU_SHIFT = 26          # Chikou je posunutý 26 svíček zpět
    CLOUD_SHIFT = 26           # Cloud se kreslí 26 svíček dopředu (my čteme historii)

    @property
    def name(self) -> str:
        return "ichimoku"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        min_bars = self.SENKOU_B_PERIOD + self.CLOUD_SHIFT + 5
        if len(df) < min_bars:
            return self._not_found()

        closes = df["close"]
        highs = df["high"]
        lows = df["low"]

        # --- Výpočet složek ---
        tenkan = self._midpoint(highs, lows, self.TENKAN_PERIOD)
        kijun = self._midpoint(highs, lows, self.KIJUN_PERIOD)

        # Senkou Span A = průměr Tenkan + Kijun, posunutý o 26 dopředu
        # V historii: čteme hodnotu, která platila pro aktuální svíčku → index -26
        span_a = ((tenkan + kijun) / 2).shift(self.CLOUD_SHIFT)

        # Senkou Span B = midpoint za 52 period, posunutý o 26
        span_b = self._midpoint(highs, lows, self.SENKOU_B_PERIOD).shift(self.CLOUD_SHIFT)

        # Chikou Span = aktuální close posunutý 26 zpět
        chikou = closes.shift(-self.CHIKOU_SHIFT)

        # Pracujeme s posledními hodnotami
        # Index -1 = aktuální svíčka, -2 = předchozí (pro cross detekci)
        idx_curr = -1
        idx_prev = -2

        t_curr = tenkan.iloc[idx_curr]
        t_prev = tenkan.iloc[idx_prev]
        k_curr = kijun.iloc[idx_curr]
        k_prev = kijun.iloc[idx_prev]

        sa_curr = span_a.iloc[idx_curr]
        sb_curr = span_b.iloc[idx_curr]

        close_curr = closes.iloc[idx_curr]

        # Chikou: aktuální close vs. close před 26 svíčkami
        # Použijeme přímo historickou hodnotu – chikou_ref je close[−27]
        if len(closes) > self.CHIKOU_SHIFT + 1:
            chikou_ref_close = closes.iloc[-self.CHIKOU_SHIFT - 1]
            if pd.isna(chikou_ref_close):
                chikou_ref_close = None
        else:
            chikou_ref_close = None

        # Kontrola NaN
        if any(pd.isna(v) for v in [t_curr, t_prev, k_curr, k_prev, sa_curr, sb_curr]):
            return self._not_found()

        # Cloud top a bottom (aktuální)
        cloud_top = max(sa_curr, sb_curr)
        cloud_bottom = min(sa_curr, sb_curr)

        # Příliš úzký cloud = neurčitý trh (flat konsolidace) → přeskočit
        # Minimální šířka cloudu: 0.2 % aktuální ceny
        MIN_CLOUD_WIDTH_PCT = 0.002
        cloud_width = cloud_top - cloud_bottom
        if cloud_width < close_curr * MIN_CLOUD_WIDTH_PCT:
            return self._not_found()

        # --- Bullish TK Cross ---
        bullish_cross = (t_prev <= k_prev) and (t_curr > k_curr)
        # --- Bearish TK Cross ---
        bearish_cross = (t_prev >= k_prev) and (t_curr < k_curr)

        if not bullish_cross and not bearish_cross:
            return self._not_found()

        if bullish_cross:
            confidence = 60.0

            # Cena nad cloudem
            above_cloud = close_curr > cloud_top
            if above_cloud:
                confidence += 15

            # Chikou potvrzení (Chikou nad cenou před 26 svíčkami)
            chikou_bullish = (chikou_ref_close is not None) and (close_curr > float(chikou_ref_close))
            if chikou_bullish:
                confidence += 15

            # Cloud je zelený (bullish cloud)
            cloud_bullish = sa_curr > sb_curr
            if cloud_bullish:
                confidence += 10

            confidence = min(100.0, confidence)

            return self._result(
                "bullish",
                confidence,
                {
                    "tenkan": round(float(t_curr), 4),
                    "kijun": round(float(k_curr), 4),
                    "senkou_a": round(float(sa_curr), 4),
                    "senkou_b": round(float(sb_curr), 4),
                    "cloud_top": round(float(cloud_top), 4),
                    "cloud_bottom": round(float(cloud_bottom), 4),
                    "above_cloud": above_cloud,
                    "cloud_bullish": cloud_bullish,
                    "chikou_bullish": chikou_bullish,
                    "support": round(float(cloud_bottom), 4),
                    "resistance": round(float(cloud_top), 4),
                    "current_close": round(float(close_curr), 4),
                },
            )

        else:  # bearish_cross
            confidence = 60.0

            # Cena pod cloudem
            below_cloud = close_curr < cloud_bottom
            if below_cloud:
                confidence += 15

            # Chikou potvrzení (Chikou pod cenou před 26 svíčkami)
            chikou_bearish = (chikou_ref_close is not None) and (close_curr < float(chikou_ref_close))
            if chikou_bearish:
                confidence += 15

            # Cloud je červený (bearish cloud)
            cloud_bearish = sb_curr > sa_curr
            if cloud_bearish:
                confidence += 10

            confidence = min(100.0, confidence)

            return self._result(
                "bearish",
                confidence,
                {
                    "tenkan": round(float(t_curr), 4),
                    "kijun": round(float(k_curr), 4),
                    "senkou_a": round(float(sa_curr), 4),
                    "senkou_b": round(float(sb_curr), 4),
                    "cloud_top": round(float(cloud_top), 4),
                    "cloud_bottom": round(float(cloud_bottom), 4),
                    "below_cloud": below_cloud,
                    "cloud_bearish": cloud_bearish,
                    "chikou_bearish": chikou_bearish,
                    "support": round(float(cloud_bottom), 4),
                    "resistance": round(float(cloud_top), 4),
                    "current_close": round(float(close_curr), 4),
                },
            )

    @staticmethod
    def _midpoint(highs: pd.Series, lows: pd.Series, period: int) -> pd.Series:
        """Highest high + Lowest low za N period, děleno 2."""
        return (highs.rolling(period).max() + lows.rolling(period).min()) / 2
