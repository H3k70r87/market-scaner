"""
Sidebar asset selector component.
Returns (symbol, timeframe, n_candles, selected_indicators, refresh_clicked).
"""

from typing import Optional
import yaml
import streamlit as st


def _load_config() -> dict:
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def render_sidebar() -> tuple[str, str, int, list[str]]:
    """
    Render the sidebar controls.

    Returns:
        (asset_symbol, timeframe, n_candles, selected_indicators)
    """
    cfg = _load_config()
    dash_cfg = cfg.get("dashboard", {})

    st.sidebar.title("📊 " + dash_cfg.get("title", "Crypto & Stock Analyzer"))
    st.sidebar.markdown("---")

    # Build asset list
    assets_cfg = cfg.get("assets", {})
    asset_list = []
    asset_meta = {}  # symbol -> {type, exchange, timeframes}

    for item in assets_cfg.get("crypto", []):
        sym = item["symbol"]
        asset_list.append(sym)
        asset_meta[sym] = {
            "type": "crypto",
            "exchange": item.get("exchange", "kucoin"),
            "timeframes": item.get("timeframes", ["1h", "4h", "1d"]),
            "czk_conversion": item.get("czk_conversion", False),
            "base_symbol": item.get("base_symbol"),
        }

    for item in assets_cfg.get("stocks", []):
        sym = item["symbol"]
        asset_list.append(sym)
        asset_meta[sym] = {
            "type": "stock",
            "exchange": "",
            "timeframes": item.get("timeframes", ["1d"]),
        }

    if not asset_list:
        asset_list = ["BTC/USDT"]

    st.sidebar.subheader("🔍 Výběr aktiva")
    selected_asset = st.sidebar.selectbox("Aktivum", asset_list, key="asset_select")

    # Timeframe options based on selected asset
    meta = asset_meta.get(selected_asset, {})
    available_tfs = meta.get("timeframes", ["1d"])
    selected_tf = st.sidebar.selectbox("Timeframe", available_tfs, key="tf_select")

    # Number of candles
    n_candles = st.sidebar.selectbox(
        "Počet svíček",
        options=[50, 100, 200],
        index=1,
        key="n_candles",
    )

    # Indicators
    st.sidebar.subheader("📈 Indikátory")
    available_indicators = ["EMA20", "EMA50", "EMA200", "BB", "Volume", "RSI"]
    selected_indicators = st.sidebar.multiselect(
        "Zobrazit indikátory",
        available_indicators,
        default=["EMA50", "EMA200", "Volume", "RSI"],
        key="indicators",
    )

    st.sidebar.markdown("---")

    # Refresh button
    if st.sidebar.button("🔄 Refresh dat", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # Store meta for use by caller
    st.session_state["_asset_meta"] = asset_meta.get(selected_asset, {})

    return selected_asset, selected_tf, n_candles, selected_indicators
