"""
Alert feed component – displays historical alerts with filters.
render_alert_feed(asset) -> Optional[dict]  (returns selected alert or None)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import streamlit as st

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


@st.cache_data(ttl=60)
def _load_alerts(asset: str, timeframe: str, pattern: str, date_from: str, date_to: str) -> list[dict]:
    return db.get_alerts_for_asset(
        asset=asset,
        timeframe=timeframe or None,
        pattern=pattern or None,
        date_from=date_from or None,
        date_to=date_to or None,
        limit=200,
    )


def _fmt(val, price: float) -> str:
    """Format a price value based on magnitude of the detection price."""
    if val is None:
        return "–"
    try:
        v = float(val)
        if price > 1000:
            return f"{v:,.0f}"
        elif price > 1:
            return f"{v:,.2f}"
        else:
            return f"{v:.6f}"
    except Exception:
        return "–"


def render_alert_feed(asset: str) -> Optional[dict]:
    """
    Render the alert history table with filters.

    Args:
        asset: Currently selected asset symbol

    Returns:
        Selected alert dict if user clicks one, else None
    """
    st.markdown("### 📜 Historie alertů")

    if not asset:
        st.warning("Vyberte aktivum v sidebaru.")
        return None

    # ---- Filters ----
    col1, col2, col3 = st.columns(3)
    with col1:
        tf_filter = st.selectbox(
            "Timeframe",
            options=["Vše", "1h", "4h", "1d"],
            key="alert_feed_tf",
        )
    with col2:
        pattern_options = ["Vše"] + list(PATTERN_NAMES_CZ.keys())
        pattern_filter = st.selectbox(
            "Pattern",
            options=pattern_options,
            format_func=lambda x: "Vše" if x == "Vše" else PATTERN_NAMES_CZ.get(x, x),
            key="alert_feed_pattern",
        )
    with col3:
        date_options = {"Posledních 7 dní": 7, "Posledních 30 dní": 30, "Vše": 0}
        date_sel = st.selectbox("Období", list(date_options.keys()), key="alert_feed_date")

    now = datetime.now(timezone.utc)
    days = date_options[date_sel]
    date_from = (now - timedelta(days=days)).isoformat() if days > 0 else ""
    date_to = ""

    tf_val      = "" if tf_filter == "Vše" else tf_filter
    pattern_val = "" if pattern_filter == "Vše" else pattern_filter

    # ---- Load data ----
    alerts = _load_alerts(asset, tf_val, pattern_val, date_from, date_to)

    if not alerts:
        st.info("Žádné alerty pro vybraná kritéria.")
        return None

    # ---- Build DataFrame ----
    rows = []
    for a in alerts:
        emoji   = "🟢" if a.get("type") == "bullish" else "🔴" if a.get("type") == "bearish" else "⚠️"
        ts      = (a.get("detected_at") or "")[:16].replace("T", " ")
        price   = float(a.get("price", 0))
        pd_data = a.get("pattern_data") or {}
        kl_data = a.get("key_levels")   or {}
        levels  = {**pd_data, **kl_data}

        entry_val = levels.get("entry")
        sl_val    = levels.get("sl")
        tp1_val   = levels.get("tp1")
        tp2_val   = levels.get("tp2")
        rr_val    = levels.get("rr")

        rows.append({
            "":        emoji,
            "Datum":   ts,
            "TF":      a.get("timeframe", ""),
            "Pattern": PATTERN_NAMES_CZ.get(a.get("pattern", ""), a.get("pattern", "")),
            "Směr":    (a.get("type") or "").capitalize(),
            "Conf %":  float(a.get("confidence", 0)),
            "Cena":    price,
            "Vstup":   _fmt(entry_val, price),
            "SL":      _fmt(sl_val, price),
            "TP1":     _fmt(tp1_val, price),
            "TP2":     _fmt(tp2_val, price),
            "R/R":     f"1:{float(rr_val):.1f}" if rr_val else "–",
            "_id":     a.get("id"),
        })

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_id"])

    # ---- Colour styling ----
    def row_color(row):
        if row["Směr"] == "Bullish":
            return ["background-color: rgba(38,166,154,0.15)"] * len(row)
        elif row["Směr"] == "Bearish":
            return ["background-color: rgba(239,83,80,0.15)"] * len(row)
        return [""] * len(row)

    styled = (
        display_df.style
        .apply(row_color, axis=1)
        .format({"Conf %": "{:.0f}", "Cena": "{:,.4f}"})
    )

    # ---- Selection ----
    selected_idx = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="alert_feed_table",
    )

    # ---- Legend ----
    st.caption(
        "💡 Vstup, SL, TP1, TP2 jsou hodnoty **v době detekce patternu** (uložené scannerem). "
        "Starší alerty (před touto aktualizací) tyto hodnoty nemají (zobrazí se –)."
    )

    # Return the selected alert dict
    sel      = selected_idx.get("selection", {}) if isinstance(selected_idx, dict) else {}
    rows_sel = sel.get("rows", [])
    if rows_sel:
        selected_row_idx = rows_sel[0]
        alert_id = df.iloc[selected_row_idx]["_id"]
        for a in alerts:
            if a.get("id") == alert_id:
                return a

    return None
