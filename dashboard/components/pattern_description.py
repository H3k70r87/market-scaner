"""
Pattern description card with explanation, TP/SL recommendations and indicator table.
Rendered via render_pattern_card(alert, current_indicators).
"""

import streamlit as st

PATTERN_NAMES_CZ = {
    "double_top_bottom": "Double Top / Bottom",
    "head_and_shoulders": "Hlava a Ramena (H&S)",
    "bull_bear_flag": "Bull / Bear Flag",
    "triangles": "Trojúhelník",
    "golden_death_cross": "Golden / Death Cross",
    "rsi_divergence": "RSI Divergence",
    "engulfing": "Engulfing svíčka",
    "support_resistance_break": "Průraz S/R úrovně",
    "ichimoku": "Ichimoku Cloud",
    "abc_correction": "ABC Korekce (Elliott)",
}

PATTERN_EXPLANATIONS = {
    "double_top_bottom": {
        "bullish": (
            "Double Bottom (dvojité dno) vzniká, když cena dvakrát testuje stejnou úroveň podpory "
            "a nedokáže ji prorazit. Formace signalizuje vyčerpání prodejního tlaku a potenciální obrat trendu nahoru. "
            "Potvrzením vzoru je průraz neckline (linie spojující vrchol mezi oběma dny) s vyšším objemem."
        ),
        "bearish": (
            "Double Top (dvojitý vrchol) vzniká, když cena dvakrát testuje stejnou úroveň odporu "
            "a nedokáže ji překonat. Formace signalizuje vyčerpání kupního tlaku a potenciální obrat trendu dolů. "
            "Potvrzením vzoru je průraz neckline (linie spojující dno mezi oběma vrcholy) s vyšším objemem."
        ),
    },
    "head_and_shoulders": {
        "bullish": (
            "Inverzní Hlava a ramena je silný bullish reversal pattern. Skládá se ze tří den: "
            "levé rameno, hlava (nejnižší bod) a pravé rameno – přičemž ramena jsou přibližně stejně hluboká. "
            "Průraz neckline (linie spojující vrcholy mezi rамeny) potvrzuje změnu trendu z bearish na bullish."
        ),
        "bearish": (
            "Hlava a ramena je jeden z nejspolehlivějších bearish reversal patternů. Skládá se ze tří vrcholů: "
            "levé rameno, hlava (nejvyšší bod) a pravé rameno – přičemž ramena jsou přibližně stejně vysoká. "
            "Průraz neckline (linie spojující dna mezi rамeny) potvrzuje změnu trendu z bullish na bearish."
        ),
    },
    "bull_bear_flag": {
        "bullish": (
            "Bull Flag (bullish vlajka) vzniká po silném vzestupném pohybu (stožár vlajky) "
            "následovaném krátkodobou konsolidací v úzkém sestupném nebo horizontálním kanálu (vlajka). "
            "Tento pattern signalizuje dočasné 'nadechnutí' před pokračováním vzestupného trendu. "
            "Průraz horní hranice kanálu potvrzuje vstup."
        ),
        "bearish": (
            "Bear Flag (bearish vlajka) vzniká po silném sestupném pohybu (stožár vlajky) "
            "následovaném krátkodobou konsolidací v úzkém vzestupném nebo horizontálním kanálu (vlajka). "
            "Pattern signalizuje dočasné 'oddechnutí' před pokračováním sestupného trendu. "
            "Průraz dolní hranice kanálu potvrzuje vstup."
        ),
    },
    "triangles": {
        "bullish": (
            "Vzestupný trojúhelník (Ascending Triangle) je bullish continuation pattern. "
            "Vzniká, když cena opakovaně testuje horizontální úroveň odporu při zároveň rostoucích dnech. "
            "Komrese ceny naznačuje akumulaci a při průrazu odporu s vyšším objemem dochází k impulznímu pohybu nahoru."
        ),
        "bearish": (
            "Sestupný trojúhelník (Descending Triangle) je bearish continuation pattern. "
            "Vzniká, když cena opakovaně testuje horizontální úroveň podpory při zároveň klesajících vrcholech. "
            "Komprese ceny naznačuje distribuci a při průrazu podpory s vyšším objemem dochází k impulznímu pohybu dolů."
        ),
    },
    "golden_death_cross": {
        "bullish": (
            "Golden Cross nastane, když krátkodobá EMA50 překříží EMA200 zdola nahoru. "
            "Jde o jeden z nejznámějších dlouhodobých bullish signálů v technické analýze. "
            "Potvrzuje změnu střednědobého až dlouhodobého trendu z bearish na bullish. "
            "Nejspolehlivější, když je doprovázen vyšším objemem obchodování."
        ),
        "bearish": (
            "Death Cross nastane, když krátkodobá EMA50 překříží EMA200 shora dolů. "
            "Jde o jeden z nejznámějších dlouhodobých bearish signálů v technické analýze. "
            "Potvrzuje změnu střednědobého až dlouhodobého trendu z bullish na bearish. "
            "Nejspolehlivější, když je doprovázen vyšším objemem obchodování."
        ),
    },
    "rsi_divergence": {
        "bullish": (
            "Bullish RSI Divergence nastane, když cena vytváří nová minima, ale RSI indikátor nikoliv. "
            "Tato divergence signalizuje skrytou sílu trhu – prodejci ztrácejí momentum i přes nová cenová dna. "
            "Jde o včasný signál potenciálního obratu trendu nahoru, zvláště pokud je RSI pod úrovní 30."
        ),
        "bearish": (
            "Bearish RSI Divergence nastane, když cena vytváří nová maxima, ale RSI indikátor nikoliv. "
            "Tato divergence signalizuje skrytou slabost trhu – kupci ztrácejí momentum i přes nová cenová maxima. "
            "Jde o včasný signál potenciálního obratu trendu dolů, zvláště pokud je RSI nad úrovní 70."
        ),
    },
    "engulfing": {
        "bullish": (
            "Bullish Engulfing je silný reverzní svíčkový pattern. Nastane, když zelená (bullish) svíčka "
            "svým tělem kompletně pohltí předchozí červenou (bearish) svíčku. "
            "Pattern naznačuje, že kupci převzali kontrolu a je zvláště spolehlivý na konci sestupného trendu "
            "nebo na úrovni klíčové podpory."
        ),
        "bearish": (
            "Bearish Engulfing je silný reverzní svíčkový pattern. Nastane, když červená (bearish) svíčka "
            "svým tělem kompletně pohltí předchozí zelenou (bullish) svíčku. "
            "Pattern naznačuje, že prodejci převzali kontrolu a je zvláště spolehlivý na konci vzestupného trendu "
            "nebo na úrovni klíčového odporu."
        ),
    },
    "support_resistance_break": {
        "bullish": (
            "Průraz odporu (Resistance Break) nastane, když cena prorazí klíčovou úroveň, "
            "která byla v minulosti testována třikrát a více. Průraz s objemem výrazně přesahujícím průměr "
            "potvrzuje sílu pohybu. Proražená úroveň odporu se typicky stává novou úrovní podpory."
        ),
        "bearish": (
            "Průraz podpory (Support Break) nastane, když cena prorazí klíčovou úroveň, "
            "která byla v minulosti testována třikrát a více. Průraz s objemem výrazně přesahujícím průměr "
            "potvrzuje sílu pohybu. Proražená úroveň podpory se typicky stává novým odporem."
        ),
    },
    "ichimoku": {
        "bullish": (
            "Ichimoku Cloud TK Cross (bullish) nastane, když Tenkan-sen (9-period midpoint) překříží Kijun-sen "
            "(26-period midpoint) zdola nahoru. Signál je nejsilnější, když k překřížení dojde NAD cloudem "
            "(Kumo) – to označuje tzv. 'silný TK Cross'. Chikou Span (lagging line) nad cenou před 26 svíčkami "
            "potvrzuje momentum. Zelený cloud (Senkou Span A > Span B) naznačuje bullish trend."
        ),
        "bearish": (
            "Ichimoku Cloud TK Cross (bearish) nastane, když Tenkan-sen překříží Kijun-sen shora dolů. "
            "Signál je nejsilnější, když k překřížení dojde POD cloudem (Kumo) – tzv. 'silný TK Cross'. "
            "Chikou Span pod cenou před 26 svíčkami potvrzuje bearish momentum. "
            "Červený cloud (Senkou Span B > Span A) naznačuje bearish trend."
        ),
    },
    "abc_correction": {
        "bullish": (
            "ABC Korekce (Elliottova vlnová teorie) – bullish. Po předchozím poklesu vzniká tříbodová korekční "
            "struktura: vlna A (pokles), vlna B (odraz 38–61.8 % Fibonacci délky A) a vlna C (další pokles, "
            "přibližně stejně dlouhý jako A). Dokončení vlny C signalizuje vyčerpání prodejního tlaku "
            "a potenciální obrat trendu nahoru. Vstup je u konce C vlny, TP cíl je návrat k počátku pohybu."
        ),
        "bearish": (
            "ABC Korekce (Elliottova vlnová teorie) – bearish. Po předchozím vzestupu vzniká tříbodová korekční "
            "struktura: vlna A (vzestup), vlna B (pokles 38–61.8 % Fibonacci délky A) a vlna C (další vzestup, "
            "přibližně stejně dlouhý jako A). Dokončení vlny C signalizuje vyčerpání kupního tlaku "
            "a potenciální obrat trendu dolů. Vstup je u konce C vlny, TP cíl je návrat k počátku pohybu."
        ),
    },
}

DISCLAIMER = (
    "⚠️ **Toto není finanční poradenství.** Technická analýza není zárukou budoucího vývoje. "
    "Vždy obchodujte s rizikem, které jste schopni unést."
)


def _fmt_price(price: float, asset: str) -> str:
    if price is None:
        return "N/A"
    if "USDT" in asset or price > 100:
        return f"${price:,.2f}"
    return f"${price:.6f}"


def _compute_rr(entry: float, sl: float, tp1: float) -> str:
    if not all([entry, sl, tp1]):
        return "N/A"
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    if risk == 0:
        return "N/A"
    return f"1 : {reward / risk:.2f}"


def render_pattern_card(alert: dict, current_indicators: dict) -> None:
    """
    Render the full pattern description card in Streamlit.

    Args:
        alert: Supabase alert record dict
        current_indicators: dict from indicators.get_current_indicators()
    """
    if not alert:
        st.info("Žádný nedávný pattern k zobrazení.")
        return

    pattern = alert.get("pattern", "")
    signal_type = alert.get("type", "neutral")
    confidence = float(alert.get("confidence", 0))
    price = float(alert.get("price", 0))
    asset = alert.get("asset", "")
    detected_at = alert.get("detected_at", "")[:16].replace("T", " ")
    key_levels = alert.get("key_levels") or {}
    pattern_data = alert.get("pattern_data") or {}

    # Merge key_levels and pattern_data for level lookup
    levels = {**pattern_data, **key_levels}

    emoji = "🟢" if signal_type == "bullish" else "🔴" if signal_type == "bearish" else "⚠️"
    type_label = signal_type.upper()
    pattern_name = PATTERN_NAMES_CZ.get(pattern, pattern)

    # ---- Header ----
    st.markdown(f"### {emoji} {pattern_name} – {type_label}")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.progress(int(confidence), text=f"Confidence: {confidence:.0f} %")
    with col2:
        st.metric("Cena při detekci", _fmt_price(price, asset))
    with col3:
        st.caption(f"⏰ {detected_at} UTC")

    st.divider()

    # ---- What is this pattern ----
    explanation = (
        PATTERN_EXPLANATIONS.get(pattern, {}).get(signal_type)
        or "Detekován technický vzor."
    )
    st.markdown("#### 📖 Co je tento pattern")
    st.markdown(explanation)

    st.divider()

    # ---- Trade setup ----
    st.markdown("#### 🎯 Možný postup")

    support = levels.get("support")
    resistance = levels.get("resistance")
    neckline = levels.get("neckline")

    if signal_type == "bullish":
        entry = resistance or neckline or price
        sl = support or price * 0.96
        tp1 = entry + (entry - sl) * 3.0 if entry and sl else None
        tp2 = entry + (entry - sl) * 5.0 if entry and sl else None

        cols = st.columns(2)
        with cols[0]:
            st.markdown(f"**Možný vstup (Long):** {_fmt_price(entry, asset)}")
            st.markdown(f"**Stop Loss:** {_fmt_price(sl, asset)}")
            st.markdown(f"**Take Profit 1:** {_fmt_price(tp1, asset)}")
            st.markdown(f"**Take Profit 2:** {_fmt_price(tp2, asset)}")
        with cols[1]:
            st.markdown(f"**Risk/Reward:** {_compute_rr(entry, sl, tp1)}")
            rsi_val = current_indicators.get("rsi")
            rsi_hint = ""
            if rsi_val:
                if rsi_val < 30:
                    rsi_hint = "RSI přeprodán – potvrzuje bullish setup"
                elif rsi_val > 70:
                    rsi_hint = "RSI překoupen – opatrnost, možná korekce"
                else:
                    rsi_hint = "RSI neutrální"
            st.markdown(f"**Potvrzení signálu:** Čekej na průraz {_fmt_price(resistance or neckline, asset)} "
                        f"s objemem > 1.5× průměr. {rsi_hint}")

    else:  # bearish
        entry = support or neckline or price
        sl = resistance or price * 1.04
        tp1 = entry - (sl - entry) * 3.0 if entry and sl else None
        tp2 = entry - (sl - entry) * 5.0 if entry and sl else None

        cols = st.columns(2)
        with cols[0]:
            st.markdown(f"**Možný vstup (Short):** {_fmt_price(entry, asset)}")
            st.markdown(f"**Stop Loss:** {_fmt_price(sl, asset)}")
            st.markdown(f"**Take Profit 1:** {_fmt_price(tp1, asset)}")
            st.markdown(f"**Take Profit 2:** {_fmt_price(tp2, asset)}")
        with cols[1]:
            st.markdown(f"**Risk/Reward:** {_compute_rr(entry, sl, tp1)}")
            rsi_val = current_indicators.get("rsi")
            rsi_hint = ""
            if rsi_val:
                if rsi_val > 70:
                    rsi_hint = "RSI překoupen – potvrzuje bearish setup"
                elif rsi_val < 30:
                    rsi_hint = "RSI přeprodán – opatrnost, možný odraz"
                else:
                    rsi_hint = "RSI neutrální"
            st.markdown(f"**Potvrzení signálu:** Čekej na průraz {_fmt_price(support or neckline, asset)} "
                        f"s objemem > 1.5× průměr. {rsi_hint}")

    st.warning(DISCLAIMER)

    st.divider()

    # ---- Indicator values table ----
    st.markdown("#### 📊 Technické indikátory v době detekce")

    ind_rows = []
    if current_indicators.get("rsi") is not None:
        rsi = current_indicators["rsi"]
        status = "Překoupen" if rsi > 70 else ("Přeprodán" if rsi < 30 else "Neutrální")
        ind_rows.append({"Indikátor": "RSI (14)", "Hodnota": f"{rsi:.1f}", "Status": status})

    if current_indicators.get("ema20") and current_indicators.get("ema50"):
        ratio = current_indicators["ema20"] / current_indicators["ema50"]
        status = "EMA20 nad EMA50" if ratio > 1 else "EMA20 pod EMA50"
        ind_rows.append({"Indikátor": "EMA20/EMA50 ratio", "Hodnota": f"{ratio:.4f}", "Status": status})

    if current_indicators.get("ema50") and current_indicators.get("ema200"):
        ratio = current_indicators["ema50"] / current_indicators["ema200"]
        status = "EMA50 nad EMA200 (bullish)" if ratio > 1 else "EMA50 pod EMA200 (bearish)"
        ind_rows.append({"Indikátor": "EMA50/EMA200 ratio", "Hodnota": f"{ratio:.4f}", "Status": status})

    if current_indicators.get("macd") is not None:
        macd = current_indicators["macd"]
        signal = current_indicators.get("macd_signal", 0) or 0
        status = "Bullish" if macd > signal else "Bearish"
        ind_rows.append({"Indikátor": "MACD", "Hodnota": f"{macd:.4f}", "Status": status})

    if ind_rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(ind_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("Indikátory nejsou k dispozici.")
