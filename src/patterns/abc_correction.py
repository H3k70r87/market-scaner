"""
ABC Correction (Elliott Wave ABC) pattern detector.

Logika detekce:
- Hledá tříbodový korekční vzor A-B-C po předchozím impulzním pohybu
- Vlna A: první zpětný pohyb po impulzu (retracement)
- Vlna B: korekce zpět (retracement vlny A, typicky 38-61.8% Fibonacci)
- Vlna C: druhý sestupný/vzestupný pohyb, typicky stejně dlouhý jako A (nebo 1.0-1.618× délky A)

Bullish ABC (nákupní příležitost):
    - Předchozí trend: bearish (cena klesala)
    - A: pokles (prodloužení trendu dolů)
    - B: odraz nahoru (38–61.8 % délky A)
    - C: další pokles, blízko délce A
    - Signál: cena dokončila C, očekáváme obrat nahoru
    - Vstup: u konce C vlny (aktuální cena)
    - SL: mírně pod minimem C
    - TP: projekce zpět k počátku A

Bearish ABC (prodejní příležitost):
    - Předchozí trend: bullish (cena rostla)
    - A: vzestup (prodloužení trendu nahoru)
    - B: odraz dolů (38–61.8 % délky A)
    - C: další vzestup, blízko délce A
    - Signál: cena dokončila C, očekáváme obrat dolů
    - Vstup: u konce C vlny (aktuální cena)
    - SL: mírně nad maximem C
    - TP: projekce zpět k počátku A

Confidence:
    - Základní detekce A-B-C struktury: 60
    - B retracement v Fibonacci pásmu 38.2–61.8 %: +15
    - C blízký 100 % délky A (±10 %): +15
    - C nedosáhlo přes minimum/maximum A: +10 (čistý ABC, ne extended)
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from .base import BasePattern, PatternResult


class ABCCorrectionPattern(BasePattern):
    LOOKBACK = 80                  # kolik svíček zpět prohledáváme
    ORDER = 5                      # order pro lokální extrémy
    B_FIB_MIN = 0.382              # minimální Fibonacci retracement pro B
    B_FIB_MAX = 0.618              # maximální Fibonacci retracement pro B
    C_LENGTH_MIN = 0.786           # C musí být alespoň 78.6 % délky A
    C_LENGTH_MAX = 1.618           # C nesmí přesáhnout 161.8 % délky A
    MIN_MOVE_PCT = 0.02            # minimální velikost vlny A (2 %)

    @property
    def name(self) -> str:
        return "abc_correction"

    @property
    def supported_timeframes(self) -> list[str]:
        return ["4h", "1d"]

    def detect(self, df: pd.DataFrame) -> PatternResult:
        if len(df) < self.LOOKBACK + 10:
            return self._not_found()

        data = df.tail(self.LOOKBACK).copy()
        highs = data["high"].values
        lows = data["low"].values
        closes = data["close"].values

        # Lokální maxima a minima
        peak_idx = argrelextrema(highs, np.greater_equal, order=self.ORDER)[0]
        trough_idx = argrelextrema(lows, np.less_equal, order=self.ORDER)[0]

        if len(peak_idx) < 2 or len(trough_idx) < 2:
            return self._not_found()

        current_close = float(closes[-1])

        # --- Bullish ABC ---
        # Sekvence: Peak (origin) → Trough A → Peak B → Trough C (aktuální)
        result = self._detect_bullish(highs, lows, closes, peak_idx, trough_idx, current_close)
        if result.found:
            return result

        # --- Bearish ABC ---
        # Sekvence: Trough (origin) → Peak A → Trough B → Peak C (aktuální)
        result = self._detect_bearish(highs, lows, closes, peak_idx, trough_idx, current_close)
        if result.found:
            return result

        return self._not_found()

    def _detect_bullish(self, highs, lows, closes, peak_idx, trough_idx, current_close) -> PatternResult:
        """
        Bullish ABC: hledáme peak → trough_A → peak_B → trough_C
        C vlna = potenciální nákupní příležitost (očekáváme obrat nahoru)
        """
        # Potřebujeme alespoň 2 troughs a 1 peak mezi nimi
        for i in range(len(trough_idx) - 1):
            trough_a_idx = trough_idx[i]
            trough_c_idx = trough_idx[i + 1]

            # Trough C musí být v posledních 15 svíčkách (čerstvý signál)
            if trough_c_idx < len(lows) - 15:
                continue

            # Najdi peak B mezi troughs A a C
            peaks_between = [p for p in peak_idx if trough_a_idx < p < trough_c_idx]
            if not peaks_between:
                continue
            peak_b_idx = peaks_between[-1]  # Bereme nejnovější peak

            # Najdi origin peak před trough A (pro určení předchozího trendu)
            peaks_before = [p for p in peak_idx if p < trough_a_idx]
            if not peaks_before:
                continue
            origin_idx = peaks_before[-1]

            # Hodnoty bodů
            origin_price = float(highs[origin_idx])
            price_a = float(lows[trough_a_idx])
            price_b = float(highs[peak_b_idx])
            price_c = float(lows[trough_c_idx])

            # Vlna A: pokles z origin na A
            wave_a_size = origin_price - price_a
            if wave_a_size <= 0:
                continue

            # Minimální velikost pohybu
            if wave_a_size / origin_price < self.MIN_MOVE_PCT:
                continue

            # Vlna B: odraz z A na B (B musí být pod origin)
            wave_b_size = price_b - price_a
            if wave_b_size <= 0 or price_b >= origin_price:
                continue

            # B Fibonacci retracement vlny A
            b_retracement = wave_b_size / wave_a_size
            if not (self.B_FIB_MIN <= b_retracement <= self.B_FIB_MAX):
                continue

            # Vlna C: pokles z B na C
            wave_c_size = price_b - price_c
            if wave_c_size <= 0:
                continue

            # C délka relativně k A
            c_to_a_ratio = wave_c_size / wave_a_size
            if not (self.C_LENGTH_MIN <= c_to_a_ratio <= self.C_LENGTH_MAX):
                continue

            # Aktuální cena musí být blízko C (max 2 % od C minima)
            proximity = abs(current_close - price_c) / price_c
            if proximity > 0.03:
                continue

            # Confidence výpočet
            confidence = 60.0

            # B v ideálním Fibonacci pásmu
            if 0.50 <= b_retracement <= 0.618:
                confidence += 15
            elif self.B_FIB_MIN <= b_retracement < 0.50:
                confidence += 8

            # C blízko 100 % délky A
            if 0.90 <= c_to_a_ratio <= 1.10:
                confidence += 15
            elif self.C_LENGTH_MIN <= c_to_a_ratio < 0.90:
                confidence += 8

            # C nedosáhlo přes minimum A (čistý ABC)
            if price_c > price_a:
                confidence += 10

            confidence = min(100.0, confidence)

            # TP = projekce zpět k origin (kde začal pokles)
            tp_target = origin_price

            return self._result(
                "bullish",
                confidence,
                {
                    "origin_price": round(origin_price, 4),
                    "wave_a_price": round(price_a, 4),
                    "wave_b_price": round(price_b, 4),
                    "wave_c_price": round(price_c, 4),
                    "wave_a_size_pct": round(wave_a_size / origin_price * 100, 2),
                    "b_retracement_pct": round(b_retracement * 100, 2),
                    "c_to_a_ratio": round(c_to_a_ratio, 3),
                    "tp_target": round(tp_target, 4),
                    "support": round(price_c * 0.99, 4),       # SL těsně pod C
                    "resistance": round(price_b, 4),            # První odpor = B vrchol
                    "neckline": round(price_b, 4),
                    "current_close": round(current_close, 4),
                },
            )

        return self._not_found()

    def _detect_bearish(self, highs, lows, closes, peak_idx, trough_idx, current_close) -> PatternResult:
        """
        Bearish ABC: hledáme trough → peak_A → trough_B → peak_C
        C vlna = potenciální prodejní příležitost (očekáváme obrat dolů)
        """
        for i in range(len(peak_idx) - 1):
            peak_a_idx = peak_idx[i]
            peak_c_idx = peak_idx[i + 1]

            # Peak C musí být v posledních 15 svíčkách
            if peak_c_idx < len(highs) - 15:
                continue

            # Najdi trough B mezi peaks A a C
            troughs_between = [t for t in trough_idx if peak_a_idx < t < peak_c_idx]
            if not troughs_between:
                continue
            trough_b_idx = troughs_between[-1]

            # Najdi origin trough před peak A
            troughs_before = [t for t in trough_idx if t < peak_a_idx]
            if not troughs_before:
                continue
            origin_idx = troughs_before[-1]

            # Hodnoty bodů
            origin_price = float(lows[origin_idx])
            price_a = float(highs[peak_a_idx])
            price_b = float(lows[trough_b_idx])
            price_c = float(highs[peak_c_idx])

            # Vlna A: vzestup z origin na A
            wave_a_size = price_a - origin_price
            if wave_a_size <= 0:
                continue

            # Minimální velikost pohybu
            if wave_a_size / origin_price < self.MIN_MOVE_PCT:
                continue

            # Vlna B: pokles z A na B (B musí být nad origin)
            wave_b_size = price_a - price_b
            if wave_b_size <= 0 or price_b <= origin_price:
                continue

            # B Fibonacci retracement vlny A
            b_retracement = wave_b_size / wave_a_size
            if not (self.B_FIB_MIN <= b_retracement <= self.B_FIB_MAX):
                continue

            # Vlna C: vzestup z B na C
            wave_c_size = price_c - price_b
            if wave_c_size <= 0:
                continue

            # C délka relativně k A
            c_to_a_ratio = wave_c_size / wave_a_size
            if not (self.C_LENGTH_MIN <= c_to_a_ratio <= self.C_LENGTH_MAX):
                continue

            # Aktuální cena musí být blízko C (max 3 % od C maxima)
            proximity = abs(current_close - price_c) / price_c
            if proximity > 0.03:
                continue

            # Confidence výpočet
            confidence = 60.0

            # B v ideálním Fibonacci pásmu
            if 0.50 <= b_retracement <= 0.618:
                confidence += 15
            elif self.B_FIB_MIN <= b_retracement < 0.50:
                confidence += 8

            # C blízko 100 % délky A
            if 0.90 <= c_to_a_ratio <= 1.10:
                confidence += 15
            elif self.C_LENGTH_MIN <= c_to_a_ratio < 0.90:
                confidence += 8

            # C nepřesáhlo maximum A (čistý ABC)
            if price_c < price_a:
                confidence += 10

            confidence = min(100.0, confidence)

            # TP = projekce zpět k origin (kde začal vzestup)
            tp_target = origin_price

            return self._result(
                "bearish",
                confidence,
                {
                    "origin_price": round(origin_price, 4),
                    "wave_a_price": round(price_a, 4),
                    "wave_b_price": round(price_b, 4),
                    "wave_c_price": round(price_c, 4),
                    "wave_a_size_pct": round(wave_a_size / origin_price * 100, 2),
                    "b_retracement_pct": round(b_retracement * 100, 2),
                    "c_to_a_ratio": round(c_to_a_ratio, 3),
                    "tp_target": round(tp_target, 4),
                    "support": round(price_b, 4),               # První podpora = B dno
                    "resistance": round(price_c * 1.01, 4),     # SL těsně nad C
                    "neckline": round(price_b, 4),
                    "current_close": round(current_close, 4),
                },
            )

        return self._not_found()
