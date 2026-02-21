"""
Interactive Plotly candlestick chart with indicator overlays
and pattern visualization.

create_chart(df, indicators, selected_indicators, alert) -> go.Figure
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dashboard.utils.indicators import compute_all

# Indicator display config
INDICATOR_COLORS = {
    "ema20": ("EMA 20", "yellow", "solid"),
    "ema50": ("EMA 50", "#4da6ff", "solid"),
    "ema200": ("EMA 200", "#ff4d4d", "solid"),
}


def create_chart(
    df: pd.DataFrame,
    selected_indicators: list[str],
    alert: Optional[dict] = None,
) -> go.Figure:
    """
    Build a full interactive chart with:
      - Candlestick OHLCV
      - Selected indicator overlays
      - Volume subplot
      - RSI subplot
      - Pattern overlay (if alert provided and within visible range)

    Args:
        df: OHLCV DataFrame
        selected_indicators: list of indicator names to show (e.g. ['EMA20','EMA50','BB','Volume'])
        alert: Supabase alert dict with pattern_data and key_levels

    Returns:
        plotly Figure
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", title="Žádná data")
        return fig

    show_volume = "Volume" in selected_indicators
    show_rsi = "RSI" in selected_indicators

    # Build subplot layout
    row_count = 1
    row_heights = [0.6]
    subplot_titles = ["Cena"]

    if show_volume:
        row_count += 1
        row_heights.append(0.2)
        subplot_titles.append("Volume")

    if show_rsi:
        row_count += 1
        row_heights.append(0.2)
        subplot_titles.append("RSI")

    fig = make_subplots(
        rows=row_count,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    # ---- Candlestick ----
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLCV",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    # ---- Compute indicators ----
    indic = compute_all(df)

    # ---- EMA overlays ----
    for key, (label, color, dash) in INDICATOR_COLORS.items():
        display_name = key.upper().replace("EMA", "EMA ")
        if display_name in selected_indicators and key in indic and indic[key] is not None:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=indic[key],
                    name=label,
                    line=dict(color=color, width=1.2, dash=dash),
                    hovertemplate=f"{label}: %{{y:.4f}}<extra></extra>",
                ),
                row=1, col=1,
            )

    # ---- Bollinger Bands ----
    if "BB" in selected_indicators and "bb_upper" in indic:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indic["bb_upper"],
                name="BB Upper", line=dict(color="#4da6ff", width=1, dash="dot"),
                hovertemplate="BB Upper: %{y:.4f}<extra></extra>",
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indic["bb_lower"],
                name="BB Lower", line=dict(color="#4da6ff", width=1, dash="dot"),
                fill="tonexty",
                fillcolor="rgba(77, 166, 255, 0.07)",
                hovertemplate="BB Lower: %{y:.4f}<extra></extra>",
            ),
            row=1, col=1,
        )

    # ---- Pattern overlay ----
    if alert:
        _add_pattern_overlay(fig, df, alert)

    # ---- Volume subplot ----
    vol_row = None
    if show_volume:
        vol_row = 2
        colors = [
            "#26a69a" if c >= o else "#ef5350"
            for c, o in zip(df["close"], df["open"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index, y=df["volume"],
                name="Volume",
                marker_color=colors,
                opacity=0.7,
                hovertemplate="Volume: %{y:,.0f}<extra></extra>",
            ),
            row=vol_row, col=1,
        )

    # ---- RSI subplot ----
    if show_rsi and "rsi" in indic:
        rsi_row = vol_row + 1 if vol_row else 2
        fig.add_trace(
            go.Scatter(
                x=df.index, y=indic["rsi"],
                name="RSI",
                line=dict(color="#9b59b6", width=1.5),
                hovertemplate="RSI: %{y:.1f}<extra></extra>",
            ),
            row=rsi_row, col=1,
        )
        # Reference lines 30 and 70
        fig.add_hline(y=70, line_color="rgba(255,80,80,0.5)", line_dash="dash", row=rsi_row, col=1)
        fig.add_hline(y=30, line_color="rgba(80,255,130,0.5)", line_dash="dash", row=rsi_row, col=1)

    # ---- Layout ----
    total_height = 500 + (150 if show_volume else 0) + (150 if show_rsi else 0)
    fig.update_layout(
        template="plotly_dark",
        height=total_height,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.07)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.07)")

    return fig


def _add_pattern_overlay(fig: go.Figure, df: pd.DataFrame, alert: dict) -> None:
    """Add pattern-specific visual annotations to the chart."""
    pattern = alert.get("pattern", "")
    pattern_data = alert.get("pattern_data") or {}
    key_levels = alert.get("key_levels") or {}
    signal_type = alert.get("type", "neutral")
    confidence = alert.get("confidence", 0)

    color = "#26a69a" if signal_type == "bullish" else "#ef5350"

    # ---- Horizontal key levels ----
    for level_key, label in [("resistance", "Odpor"), ("support", "Podpora"), ("neckline", "Neckline")]:
        val = key_levels.get(level_key) or pattern_data.get(level_key)
        if val:
            fig.add_hline(
                y=float(val),
                line_color=color,
                line_dash="dash",
                line_width=1,
                annotation_text=f"{label}: {float(val):,.4f}",
                annotation_position="right",
                annotation_font_color=color,
                row=1, col=1,
            )

    # ---- Pattern-specific drawing ----
    if pattern == "head_and_shoulders":
        _draw_hs(fig, df, pattern_data, signal_type, color)

    elif pattern == "double_top_bottom":
        _draw_double_top_bottom(fig, df, pattern_data, signal_type, color)

    elif pattern == "bull_bear_flag":
        _draw_flag(fig, df, pattern_data, signal_type, color)

    elif pattern == "triangles":
        _draw_triangle(fig, df, pattern_data, signal_type, color)

    elif pattern == "golden_death_cross":
        _draw_cross(fig, df, pattern_data, signal_type, color)

    elif pattern == "engulfing":
        _draw_engulfing(fig, df, pattern_data, signal_type, color)

    elif pattern == "support_resistance_break":
        _draw_sr_break(fig, df, pattern_data, signal_type, color)

    # ---- Pattern name annotation top-left of chart ----
    pattern_labels = {
        "head_and_shoulders": "H&S", "double_top_bottom": "Double Top/Bot",
        "bull_bear_flag": "Flag", "triangles": "Triangle",
        "golden_death_cross": "Cross", "rsi_divergence": "RSI Div",
        "engulfing": "Engulfing", "support_resistance_break": "S/R Break",
    }
    label = pattern_labels.get(pattern, pattern)
    fig.add_annotation(
        text=f"{'🟢' if signal_type=='bullish' else '🔴'} {label} ({confidence:.0f}%)",
        xref="paper", yref="paper",
        x=0.01, y=0.97,
        showarrow=False,
        font=dict(color=color, size=13),
        bgcolor="rgba(0,0,0,0.5)",
        bordercolor=color,
        borderwidth=1,
    )


def _safe_x(df: pd.DataFrame, idx: int):
    """Return DataFrame index value clamped to valid range."""
    idx = max(0, min(idx, len(df) - 1))
    return df.index[idx]


def _draw_hs(fig, df, data, signal_type, color):
    """Head & Shoulders connecting lines."""
    # Expect data keys: left_shoulder, head, right_shoulder (price values)
    # We approximate bar positions by scanning the last 60 bars
    ls = data.get("left_shoulder")
    head = data.get("head")
    rs = data.get("right_shoulder")
    neckline = data.get("neckline")

    if not all([ls, head, rs]):
        return

    n = len(df)
    scan = df["high"].values if signal_type == "bearish" else df["low"].values
    # Find approximate indices for the three points in last 60 bars
    window = min(60, n)
    segment = scan[-window:]

    if signal_type == "bearish":
        import numpy as np
        head_i = int(np.argmax(segment)) + (n - window)
        ls_i = max(0, head_i - window // 3)
        rs_i = min(n - 1, head_i + window // 3)
    else:
        import numpy as np
        head_i = int(np.argmin(segment)) + (n - window)
        ls_i = max(0, head_i - window // 3)
        rs_i = min(n - 1, head_i + window // 3)

    points_x = [_safe_x(df, ls_i), _safe_x(df, head_i), _safe_x(df, rs_i)]
    points_y = [ls, head, rs]

    fig.add_trace(
        go.Scatter(
            x=points_x, y=points_y,
            mode="lines+markers",
            name="H&S Points",
            line=dict(color=color, width=2),
            marker=dict(size=8, color=color),
            hovertemplate="H&S: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )


def _draw_double_top_bottom(fig, df, data, signal_type, color):
    """Mark the two peaks/troughs."""
    if signal_type == "bearish":
        p1 = data.get("peak1")
        p2 = data.get("peak2")
        label = "Peak"
    else:
        p1 = data.get("trough1")
        p2 = data.get("trough2")
        label = "Trough"

    if not p1 or not p2:
        return

    n = len(df)
    scan = df["high"].values if signal_type == "bearish" else df["low"].values
    window = min(80, n)
    seg = scan[-window:]

    import numpy as np
    from scipy.signal import argrelextrema
    if signal_type == "bearish":
        ext = argrelextrema(seg, np.greater_equal, order=5)[0]
    else:
        ext = argrelextrema(seg, np.less_equal, order=5)[0]

    if len(ext) >= 2:
        i1 = ext[-2] + (n - window)
        i2 = ext[-1] + (n - window)
    else:
        i1, i2 = n - 20, n - 5

    for i, price in [(i1, p1), (i2, p2)]:
        fig.add_annotation(
            x=_safe_x(df, i), y=float(price),
            text=label,
            showarrow=True,
            arrowhead=2,
            arrowcolor=color,
            font=dict(color=color),
            row=1, col=1,
        )


def _draw_flag(fig, df, data, signal_type, color):
    """Rectangle around the consolidation zone."""
    support = data.get("support")
    resistance = data.get("resistance")
    if not support or not resistance:
        return

    n = len(df)
    # Consolidation is the last ~10 bars
    x_start = _safe_x(df, max(0, n - 12))
    x_end = _safe_x(df, n - 1)

    fig.add_shape(
        type="rect",
        x0=x_start, x1=x_end,
        y0=float(support), y1=float(resistance),
        line=dict(color=color, width=1.5, dash="dot"),
        fillcolor=f"rgba({'38,166,154' if signal_type=='bullish' else '239,83,80'},0.1)",
        row=1, col=1,
    )
    fig.add_annotation(
        x=x_end, y=float(resistance),
        text="Flag zone",
        showarrow=False,
        font=dict(color=color, size=10),
        row=1, col=1,
    )


def _draw_triangle(fig, df, data, signal_type, color):
    """Draw two converging trendlines."""
    n = len(df)
    window = min(50, n)
    x_start = _safe_x(df, n - window)
    x_end = _safe_x(df, n - 1)

    resistance = data.get("resistance")
    support = data.get("support")

    if not resistance or not support:
        return

    import numpy as np
    if signal_type == "bullish":
        # Flat resistance + rising support
        fig.add_shape(
            type="line", x0=x_start, x1=x_end,
            y0=float(resistance), y1=float(resistance),
            line=dict(color=color, width=1.5, dash="dash"), row=1, col=1,
        )
        slope_start = float(support) * 0.97
        fig.add_shape(
            type="line", x0=x_start, x1=x_end,
            y0=slope_start, y1=float(support),
            line=dict(color=color, width=1.5, dash="dash"), row=1, col=1,
        )
    else:
        # Flat support + falling resistance
        fig.add_shape(
            type="line", x0=x_start, x1=x_end,
            y0=float(support), y1=float(support),
            line=dict(color=color, width=1.5, dash="dash"), row=1, col=1,
        )
        slope_start = float(resistance) * 1.03
        fig.add_shape(
            type="line", x0=x_start, x1=x_end,
            y0=slope_start, y1=float(resistance),
            line=dict(color=color, width=1.5, dash="dash"), row=1, col=1,
        )


def _draw_cross(fig, df, data, signal_type, color):
    """Mark the EMA crossover point."""
    ema50 = data.get("ema50")
    if not ema50:
        return

    n = len(df)
    x_cross = _safe_x(df, n - 1)

    fig.add_annotation(
        x=x_cross, y=float(ema50),
        text="✕ Cross",
        showarrow=True,
        arrowhead=2,
        arrowcolor=color,
        font=dict(color=color, size=12),
        row=1, col=1,
    )


def _draw_engulfing(fig, df, data, signal_type, color):
    """Highlight the two engulfing candles."""
    n = len(df)
    if n < 2:
        return

    for offset, label in [(2, "Prev"), (1, "Engulf")]:
        i = n - offset
        x = _safe_x(df, i)
        high = float(df["high"].iloc[i])
        low = float(df["low"].iloc[i])

        fig.add_shape(
            type="rect",
            x0=x, x1=x,
            y0=low, y1=high,
            line=dict(color=color, width=3),
            row=1, col=1,
        )

    fig.add_annotation(
        x=_safe_x(df, n - 1), y=float(df["high"].iloc[-1]),
        text="Engulf",
        showarrow=True, arrowhead=2,
        arrowcolor=color,
        font=dict(color=color, size=11),
        row=1, col=1,
    )


def _draw_sr_break(fig, df, data, signal_type, color):
    """Arrow at S/R breakout point."""
    n = len(df)
    level = data.get("level_price") or data.get("resistance") or data.get("support")
    if not level:
        return

    x = _safe_x(df, n - 1)
    direction = "up" if signal_type == "bullish" else "down"
    ay = -40 if signal_type == "bullish" else 40

    fig.add_annotation(
        x=x, y=float(level),
        text=f"{'↑' if direction=='up' else '↓'} Průraz",
        showarrow=True,
        arrowhead=2,
        arrowcolor=color,
        ay=ay,
        font=dict(color=color, size=13),
        row=1, col=1,
    )
