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
}


# ---- Cached data loaders ----

@st.cache_data(ttl=300)
def load_ohlcv(symbol: str, timeframe: str, asset_type: str, exchange: str) -> pd.DataFrame:
    """Fetch OHLCV data with 5-minute cache."""
    try:
        df = fetch_asset_data(symbol, timeframe, asset_type, exchange)
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
    exchange = meta.get("exchange", "binance")

    _render_sidebar_alerts(asset)

    # ---- Load data ----
    with st.spinner(f"Načítám data pro {asset} ({timeframe})…"):
        df_full = load_ohlcv(asset, timeframe, asset_type, exchange)

    if df_full is None or df_full.empty:
        st.error("Nepodařilo se načíst OHLCV data. Zkontroluj připojení nebo změň aktivum.")
        return

    # Slice to requested candle count
    df = df_full.tail(n_candles).copy()

    alerts_7d = load_alerts_7d(asset)
    recent_alerts = load_recent_alerts(asset, limit=1)
    latest_alert = recent_alerts[0] if recent_alerts else None

    # ---- Title ----
    st.markdown(f"## {asset} · {timeframe}")

    # ---- Metric row ----
    _render_metric_row(df, asset, alerts_7d)

    st.markdown("---")

    # ---- Tabs: Graf / Popis / Historie ----
    tab_chart, tab_desc, tab_history = st.tabs(["📈 Graf", "📖 Pattern popis", "📜 Historie alertů"])

    with tab_chart:
        # Check if a pattern from history was selected
        selected_alert_for_chart = st.session_state.get("_selected_alert_for_chart", latest_alert)

        try:
            fig = create_chart(df, selected_indicators, alert=selected_alert_for_chart)
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


if __name__ == "__main__":
    main()
