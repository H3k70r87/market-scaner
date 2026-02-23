"""
Crypto & Stock Analyzer – Streamlit Dashboard
Deployed on Streamlit Community Cloud (free tier).

Secrets are loaded via st.secrets (set in Streamlit Cloud UI):
  SUPABASE_URL, SUPABASE_KEY
"""

import sys
import os

# Ensure project root is on path so src.* imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

# ---- Page config (must be first Streamlit call) ----
st.set_page_config(
    page_title="Crypto & Stock Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

import pandas as pd

from dashboard.components.asset_selector import render_sidebar
from dashboard.components.chart import create_chart
from dashboard.components.pattern_description import render_pattern_card
from dashboard.components.alert_feed import render_alert_feed
from dashboard.utils.indicators import compute_all, get_current_indicators
from src.data.fetcher import fetch_asset_data
from src.storage import supabase_client as db

PATTERN_NAMES_CZ = {
    "double_top_bottom": "Double Top/Bottom",
    "head_and_shoulders": "Hlava a Ramena",
    "bull_bear_flag": "Bull/Bear Flag",
    "triangles": "Trojúhelník",
    "golden_death_cross": "Golden/Death Cross",
    "rsi_divergence": "RSI Divergence",
    "engulfing": "Engulfing",
    "support_resistance_break": "S/R Průraz",
    "ichimoku": "Ichimoku Cloud",
    "abc_correction": "ABC Korekce",
}

# Pattern weights (mirrors main.py PATTERN_WEIGHTS – kept in sync manually)
PATTERN_WEIGHTS = {
    "head_and_shoulders":       10,
    "double_top_bottom":         9,
    "golden_death_cross":        9,
    "triangles":                 8,
    "support_resistance_break":  8,
    "ichimoku":                  7,
    "abc_correction":            7,
    "bull_bear_flag":            6,
    "rsi_divergence":            5,
    "engulfing":                 4,
}

# Short descriptions for the Patterny tab
PATTERN_SHORT_DESC = {
    "head_and_shoulders":      "3 vrcholy/dna – střední nejvyšší/nejnižší. Klasický reversal.",
    "double_top_bottom":       "2 symetrické vrcholy/dna s neckline. Spolehlivý reversal.",
    "golden_death_cross":      "EMA50 kříží EMA200 – dlouhodobý trend. 210 svíček kontext.",
    "triangles":               "Konvergující trendové čáry – komprese před průrazem.",
    "support_resistance_break":"Průraz S/R úrovně s potvrzením objemu.",
    "ichimoku":                "TK Cross + cloud + Chikou – komplexní multi-indikátor.",
    "abc_correction":          "Elliott Wave ABC korekce – příležitost po konci vlny C.",
    "bull_bear_flag":          "Silný pohyb + konsolidace – continuation pattern.",
    "rsi_divergence":          "Divergence ceny a RSI – včasný signál obratu.",
    "engulfing":               "Pohlcující svíčka – rychlý reversal signál ze 2 svíček.",
}

PATTERN_TYPE = {
    "head_and_shoulders":      "Reversal",
    "double_top_bottom":       "Reversal",
    "golden_death_cross":      "Trend",
    "triangles":               "Continuation / Reversal",
    "support_resistance_break":"Continuation",
    "ichimoku":                "Trend / Multi",
    "abc_correction":          "Reversal (Elliott)",
    "bull_bear_flag":          "Continuation",
    "rsi_divergence":          "Reversal (Momentum)",
    "engulfing":               "Reversal (Svíčkový)",
}

PATTERN_LOOKBACK = {
    "head_and_shoulders":      "~60 svíček",
    "double_top_bottom":       "~50 svíček",
    "golden_death_cross":      "210 svíček",
    "triangles":               "~40 svíček",
    "support_resistance_break":"~30 svíček",
    "ichimoku":                "~52 svíček",
    "abc_correction":          "~60 svíček",
    "bull_bear_flag":          "~17 svíček",
    "rsi_divergence":          "~30 svíček",
    "engulfing":               "2 svíčky",
}


# ---- Cached data loaders ----

@st.cache_data(ttl=300)
def load_ohlcv(
    symbol: str,
    timeframe: str,
    asset_type: str,
    exchange: str,
    czk_conversion: bool = False,
    base_symbol: str | None = None,
) -> pd.DataFrame:
    """Fetch OHLCV data with 5-minute cache."""
    try:
        df = fetch_asset_data(
            symbol, timeframe, asset_type, exchange,
            czk_conversion=czk_conversion,
            base_symbol=base_symbol,
        )
        return df
    except Exception as exc:
        st.warning(f"Chyba při načítání dat: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def load_recent_alerts(asset: str, limit: int = 5) -> list[dict]:
    """Fetch recent alerts with 1-minute cache."""
    try:
        return db.get_recent_alerts(limit=limit, asset=asset)
    except Exception:
        return []


@st.cache_data(ttl=60)
def load_alerts_7d(asset: str) -> list[dict]:
    try:
        return db.get_alerts_last_n_days(asset, days=7)
    except Exception:
        return []


@st.cache_data(ttl=60)
def load_all_alerts_for_stats(asset: str) -> list[dict]:
    """Fetch up to 200 most recent alerts for a given asset (for Patterny tab stats)."""
    try:
        return db.get_recent_alerts(limit=200, asset=asset)
    except Exception:
        return []


# ---- Helpers ----

def _fmt_price(price: float, asset: str) -> str:
    if price is None:
        return "N/A"
    if "USDT" in asset or price > 100:
        return f"${price:,.2f}"
    return f"${price:.6f}"


def _render_sidebar_alerts(asset: str) -> None:
    """Render the last 5 alerts in the sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Poslední alerty")
    alerts = load_recent_alerts(asset, limit=5)
    if not alerts:
        st.sidebar.caption("Žádné alerty.")
        return
    for a in alerts:
        emoji = "🟢" if a.get("type") == "bullish" else "🔴" if a.get("type") == "bearish" else "⚠️"
        ts = (a.get("detected_at") or "")[:10]
        pattern_short = PATTERN_NAMES_CZ.get(a.get("pattern", ""), a.get("pattern", ""))[:14]
        conf = a.get("confidence", 0)
        color = "green" if a.get("type") == "bullish" else "red"
        st.sidebar.markdown(
            f":{color}[{emoji} **{a.get('asset','')}** {pattern_short} {conf:.0f}%]  \n"
            f"<small>{ts}</small>",
            unsafe_allow_html=True,
        )


def _render_metric_row(df: pd.DataFrame, asset: str, alerts_7d: list[dict]) -> None:
    """Render the 4-column metrics row."""
    if df is None or df.empty:
        st.warning("Data nejsou k dispozici.")
        return

    indic = get_current_indicators(df)
    current_price = float(df["close"].iloc[-1])
    change_pct = indic.get("change_pct", 0.0)
    rsi_val = indic.get("rsi")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label=f"💰 {asset}",
            value=_fmt_price(current_price, asset),
            delta=f"{change_pct:+.2f}%",
        )

    with col2:
        if rsi_val is not None:
            rsi_color = "🔴" if rsi_val > 70 else ("🟢" if rsi_val < 30 else "⚪")
            rsi_status = "Překoupen" if rsi_val > 70 else ("Přeprodán" if rsi_val < 30 else "Neutrální")
            st.metric(
                label=f"📉 RSI (14) {rsi_color}",
                value=f"{rsi_val:.1f}",
                delta=rsi_status,
            )
        else:
            st.metric(label="📉 RSI (14)", value="N/A")

    with col3:
        n_patterns = len(alerts_7d)
        st.metric(label="📊 Patterny (7 dní)", value=str(n_patterns))

    with col4:
        if alerts_7d:
            last = alerts_7d[0]
            last_pattern = PATTERN_NAMES_CZ.get(last.get("pattern", ""), last.get("pattern", ""))
            last_type = last.get("type", "")
            emoji = "🟢" if last_type == "bullish" else "🔴"
            st.metric(
                label="🔔 Poslední pattern",
                value=last_pattern[:18],
                delta=f"{emoji} {last_type}",
            )
        else:
            st.metric(label="🔔 Poslední pattern", value="Žádný")


# ---- Main App ----

def main():
    # ---- Sidebar ----
    asset, timeframe, n_candles, selected_indicators = render_sidebar()

    meta = st.session_state.get("_asset_meta", {})
    asset_type = meta.get("type", "crypto")
    exchange = meta.get("exchange", "kucoin")
    czk_conversion = meta.get("czk_conversion", False)
    base_symbol = meta.get("base_symbol")

    _render_sidebar_alerts(asset)

    # ---- Load data ----
    with st.spinner(f"Načítám data pro {asset} ({timeframe})…"):
        df_full = load_ohlcv(asset, timeframe, asset_type, exchange, czk_conversion, base_symbol)

    if df_full is None or df_full.empty:
        st.error("Nepodařilo se načíst OHLCV data. Zkontroluj připojení nebo změň aktivum.")
        return

    # df_full contains all fetched candles (200) – used for chart so bar indices
    # from pattern detector (which also works on 200 candles) are always correct.
    # n_candles from sidebar is kept for metric calculations only (recent close etc.).
    df = df_full.tail(n_candles).copy()   # for metrics / indicators sidebar display
    df_chart = df_full.copy()             # always full dataset for chart + pattern overlay

    alerts_7d = load_alerts_7d(asset)
    recent_alerts = load_recent_alerts(asset, limit=1)
    latest_alert = recent_alerts[0] if recent_alerts else None

    # ---- Title ----
    st.markdown(f"## {asset} · {timeframe}")

    # ---- Metric row ----
    _render_metric_row(df, asset, alerts_7d)

    st.markdown("---")

    # ---- Tabs: Graf / Popis / Historie / Patterny ----
    tab_chart, tab_desc, tab_history, tab_patterns = st.tabs([
        "📈 Graf", "📖 Pattern popis", "📜 Historie alertů", "📚 Patterny"
    ])

    with tab_chart:
        # Check if a pattern from history was selected
        selected_alert_for_chart = st.session_state.get("_selected_alert_for_chart", latest_alert)

        try:
            fig = create_chart(df_chart, selected_indicators, alert=selected_alert_for_chart)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as exc:
            st.error(f"Chyba při vykreslování grafu: {exc}")

        if selected_alert_for_chart and selected_alert_for_chart != latest_alert:
            if st.button("🔙 Zpět na poslední alert"):
                st.session_state["_selected_alert_for_chart"] = None
                st.rerun()

    with tab_desc:
        indic_current = get_current_indicators(df)
        render_pattern_card(latest_alert, indic_current)

    with tab_history:
        selected_from_feed = render_alert_feed(asset)
        if selected_from_feed:
            st.session_state["_selected_alert_for_chart"] = selected_from_feed
            st.info(f"Pattern zobrazen v záložce Graf: {PATTERN_NAMES_CZ.get(selected_from_feed.get('pattern',''), '')}")

    with tab_patterns:
        _render_patterns_tab(asset)


def _render_patterns_tab(asset: str) -> None:
    """Render the Patterny overview tab."""
    st.markdown("### 📚 Přehled patternů")
    st.caption(
        "Přehled všech detekovaných vzorů, jejich váhy při conflict resolution "
        "a statistiky ze scannerových alertů."
    )

    # ---- Build static overview table ----
    rows = []
    for key in PATTERN_WEIGHTS:
        rows.append({
            "Pattern": PATTERN_NAMES_CZ.get(key, key),
            "Typ": PATTERN_TYPE.get(key, "–"),
            "Lookback": PATTERN_LOOKBACK.get(key, "–"),
            "Váha ⚖️": PATTERN_WEIGHTS[key],
            "Popis": PATTERN_SHORT_DESC.get(key, "–"),
        })

    df_patterns = pd.DataFrame(rows)

    # Weight bar as colored background via styler
    def _style_weight(val):
        pct = int(val / 10 * 100)
        return (
            f"background: linear-gradient(90deg, "
            f"#1f6feb {pct}%, transparent {pct}%);"
            f"color: white; font-weight: bold; text-align: center;"
        )

    styled = (
        df_patterns.style
        .applymap(_style_weight, subset=["Váha ⚖️"])
        .set_properties(subset=["Popis"], **{"font-size": "0.85em", "color": "#aaa"})
        .set_properties(subset=["Pattern"], **{"font-weight": "bold"})
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ---- Statistics from DB ----
    st.markdown(f"#### 📊 Statistiky alertů – {asset}")

    all_alerts = load_all_alerts_for_stats(asset)

    if not all_alerts:
        st.info("Pro toto aktivum zatím nejsou žádné alerty v databázi.")
        return

    df_alerts = pd.DataFrame(all_alerts)

    # Count per pattern
    st.markdown("**Počet alertů dle patternu**")
    col_a, col_b = st.columns([2, 1])

    with col_a:
        pattern_counts = (
            df_alerts.groupby("pattern")
            .size()
            .reset_index(name="Počet")
            .sort_values("Počet", ascending=False)
        )
        pattern_counts["Pattern"] = pattern_counts["pattern"].map(
            lambda x: PATTERN_NAMES_CZ.get(x, x)
        )
        pattern_counts = pattern_counts[["Pattern", "Počet"]]
        st.dataframe(pattern_counts, use_container_width=True, hide_index=True)

    with col_b:
        # Bullish vs bearish split
        st.markdown("**Směr signálů**")
        type_counts = df_alerts["type"].value_counts()
        bullish_n = int(type_counts.get("bullish", 0))
        bearish_n = int(type_counts.get("bearish", 0))
        total_n = bullish_n + bearish_n
        if total_n > 0:
            st.metric("🟢 Bullish", f"{bullish_n}",
                      delta=f"{bullish_n / total_n * 100:.0f} %")
            st.metric("🔴 Bearish", f"{bearish_n}",
                      delta=f"{bearish_n / total_n * 100:.0f} %")
            st.metric("Celkem alertů", f"{total_n}")

    st.markdown("---")

    # Average confidence per pattern
    st.markdown("**Průměrná spolehlivost (confidence) dle patternu**")
    if "confidence" in df_alerts.columns:
        conf_stats = (
            df_alerts.groupby("pattern")["confidence"]
            .agg(["mean", "min", "max", "count"])
            .reset_index()
            .sort_values("mean", ascending=False)
        )
        conf_stats.columns = ["pattern", "Průměr %", "Min %", "Max %", "Počet"]
        conf_stats["Pattern"] = conf_stats["pattern"].map(
            lambda x: PATTERN_NAMES_CZ.get(x, x)
        )
        conf_stats["Průměr %"] = conf_stats["Průměr %"].round(1)
        conf_stats["Min %"] = conf_stats["Min %"].round(1)
        conf_stats["Max %"] = conf_stats["Max %"].round(1)
        conf_stats = conf_stats[["Pattern", "Průměr %", "Min %", "Max %", "Počet"]]

        def _style_conf(val):
            try:
                v = float(val)
                if v >= 80:
                    color = "#238636"
                elif v >= 65:
                    color = "#9e6a03"
                else:
                    color = "#da3633"
                return f"color: {color}; font-weight: bold;"
            except Exception:
                return ""

        styled_conf = conf_stats.style.applymap(_style_conf, subset=["Průměr %"])
        st.dataframe(styled_conf, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Conflict resolution legend
    st.markdown("#### ⚖️ Jak funguje Conflict Resolution")
    st.markdown(
        """
Když scanner detekuje zároveň **bullish** i **bearish** signal na stejném aktivu a timeframe,
rozhoduje se pomocí skórovacího systému:

```
skóre = Váha patternu × Confidence (%) × R/R poměr
```

Strana (bullish / bearish) s **vyšším celkovým skóre** vyhraje.
Z vítězné strany se odešle **nejsilnější individuální kandidát**.
Do zprávy se přidá poznámka o protichůdném signálu.
        """
    )

    # Weights legend table (compact)
    weights_df = pd.DataFrame([
        {"Pattern": PATTERN_NAMES_CZ.get(k, k), "Váha": v}
        for k, v in PATTERN_WEIGHTS.items()
    ])
    st.dataframe(
        weights_df.style.background_gradient(subset=["Váha"], cmap="Blues"),
        use_container_width=False,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
