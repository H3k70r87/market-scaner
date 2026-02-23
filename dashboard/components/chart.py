"""
Interactive Plotly candlestick chart with indicator overlays
and pattern visualization.

create_chart(df, indicators, selected_indicators, alert) -> go.Figure
"""

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import argrelextrema

from dashboard.utils.indicators import compute_all

# Indicator display config
INDICATOR_COLORS = {
    "ema20": ("EMA 20", "yellow", "solid"),
    "ema50": ("EMA 50", "#4da6ff", "solid"),
    "ema200": ("EMA 200", "#ff4d4d", "solid"),
}

PATTERN_LABELS = {
    "head_and_shoulders":       "H&S",
    "double_top_bottom":        "Double Top/Bot",
    "bull_bear_flag":           "Flag",
    "triangles":                "Triangle",
    "golden_death_cross":       "Cross",
    "rsi_divergence":           "RSI Div",
    "engulfing":                "Engulfing",
    "support_resistance_break": "S/R Break",
    "ichimoku":                 "Ichimoku",
    "abc_correction":           "ABC Korekce",
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
        _add_pattern_overlay(fig, df, alert, indic, show_rsi, show_volume)

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
    rsi_row = None
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


# ---------------------------------------------------------------------------
# Pattern overlay dispatcher
# ---------------------------------------------------------------------------

def _add_pattern_overlay(
    fig: go.Figure,
    df: pd.DataFrame,
    alert: dict,
    indic: dict,
    show_rsi: bool,
    show_volume: bool,
) -> None:
    """Add pattern-specific visual annotations to the chart."""
    pattern     = alert.get("pattern", "")
    pattern_data = alert.get("pattern_data") or {}
    key_levels  = alert.get("key_levels") or {}
    signal_type = alert.get("type", "neutral")
    confidence  = float(alert.get("confidence", 0))
    asset       = alert.get("asset", "")

    color       = "#26a69a" if signal_type == "bullish" else "#ef5350"
    color_fill  = "38,166,154" if signal_type == "bullish" else "239,83,80"

    # Merge levels for convenience
    levels = {**pattern_data, **key_levels}

    # ---- Horizontal key levels (support / resistance / neckline) ----
    drawn_levels: set[float] = set()
    for level_key, label in [("resistance", "Odpor"), ("support", "Podpora"), ("neckline", "Neckline")]:
        val = levels.get(level_key)
        if val and float(val) not in drawn_levels:
            drawn_levels.add(float(val))
            fig.add_hline(
                y=float(val),
                line_color=color,
                line_dash="dash",
                line_width=1.2,
                annotation_text=f"{label}: {float(val):,.4f}",
                annotation_position="right",
                annotation_font_color=color,
                annotation_bgcolor="rgba(0,0,0,0.55)",
                row=1, col=1,
            )

    # ---- Pattern-specific drawing ----
    if pattern == "head_and_shoulders":
        _draw_hs(fig, df, levels, signal_type, color)

    elif pattern == "double_top_bottom":
        _draw_double_top_bottom(fig, df, levels, signal_type, color)

    elif pattern == "bull_bear_flag":
        _draw_flag(fig, df, levels, signal_type, color, color_fill)

    elif pattern == "triangles":
        _draw_triangle(fig, df, levels, signal_type, color)

    elif pattern == "golden_death_cross":
        _draw_cross(fig, df, levels, signal_type, color)

    elif pattern == "rsi_divergence":
        rsi_row = (3 if show_volume else 2) if show_rsi else None
        _draw_rsi_divergence(fig, df, levels, signal_type, color, indic, rsi_row)

    elif pattern == "engulfing":
        _draw_engulfing(fig, df, levels, signal_type, color)

    elif pattern == "support_resistance_break":
        _draw_sr_break(fig, df, levels, signal_type, color)

    elif pattern == "ichimoku":
        _draw_ichimoku(fig, df, levels, signal_type, color, color_fill)

    elif pattern == "abc_correction":
        _draw_abc(fig, df, levels, signal_type, color, color_fill)

    # ---- Pattern name badge – top-left corner ----
    label_short = PATTERN_LABELS.get(pattern, pattern)
    emoji = "🟢" if signal_type == "bullish" else "🔴"
    signal_cz = "BULLISH" if signal_type == "bullish" else "BEARISH"

    fig.add_annotation(
        text=(
            f"<b>{emoji} {label_short}</b><br>"
            f"<span style='font-size:11px'>{signal_cz} · {confidence:.0f}% conf</span>"
        ),
        xref="paper", yref="paper",
        x=0.01, y=0.97,
        align="left",
        showarrow=False,
        font=dict(color=color, size=13),
        bgcolor="rgba(0,0,0,0.65)",
        bordercolor=color,
        borderwidth=1.5,
        borderpad=6,
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe_x(df: pd.DataFrame, idx: int):
    """Return DataFrame index value clamped to valid range."""
    idx = max(0, min(idx, len(df) - 1))
    return df.index[idx]


def _bar_width(df: pd.DataFrame) -> pd.Timedelta:
    """Approximate single-bar width for rectangle x-offsets."""
    if len(df) >= 2:
        return (df.index[1] - df.index[0]) * 0.4
    return pd.Timedelta(hours=1)


# ---------------------------------------------------------------------------
# Pattern draw functions
# ---------------------------------------------------------------------------

def _draw_hs(fig, df, data, signal_type, color):
    """
    Head & Shoulders – connecting line through 3 key points.
    X-positions come from *_bar indices saved by the detector – guaranteed correct.
    Falls back to argmax/argmin scan only if indices are missing (old DB records).
    """
    ls    = data.get("left_shoulder")
    head  = data.get("head")
    rs    = data.get("right_shoulder")

    if not all([ls, head, rs]):
        return

    n = len(df)

    raw_ls_i   = data.get("ls_bar")
    raw_head_i = data.get("head_bar")
    raw_rs_i   = data.get("rs_bar")

    if raw_ls_i is not None and raw_head_i is not None and raw_rs_i is not None:
        ls_i   = max(0, min(int(raw_ls_i),   n - 1))
        head_i = max(0, min(int(raw_head_i), n - 1))
        rs_i   = max(0, min(int(raw_rs_i),   n - 1))
    else:
        # Fallback for old DB records
        scan   = df["high"].values if signal_type == "bearish" else df["low"].values
        window = min(60, n)
        segment = scan[-window:]
        head_i  = (int(np.argmax(segment)) if signal_type == "bearish" else int(np.argmin(segment))) + (n - window)
        ls_i    = max(0, head_i - window // 3)
        rs_i    = min(n - 1, head_i + window // 3)

    points_x = [_safe_x(df, ls_i), _safe_x(df, head_i), _safe_x(df, rs_i)]
    points_y = [float(ls), float(head), float(rs)]

    # Connecting line through the three shoulder/head points
    fig.add_trace(
        go.Scatter(
            x=points_x, y=points_y,
            mode="lines+markers",
            name="H&S body",
            line=dict(color=color, width=2),
            marker=dict(size=9, color=color, symbol="circle"),
            hovertemplate="H&S: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # Labels for each point
    for x, y, lbl in zip(points_x, points_y, ["L. Rameno", "Hlava", "P. Rameno"]):
        ay = -30 if signal_type == "bearish" else 30
        fig.add_annotation(
            x=x, y=y, text=lbl,
            showarrow=True, arrowhead=2, arrowcolor=color, ay=ay,
            font=dict(color=color, size=10),
            bgcolor="rgba(0,0,0,0.5)",
            row=1, col=1,
        )


def _draw_double_top_bottom(fig, df, data, signal_type, color):
    """
    Mark the two peaks/troughs with annotated dots and a connecting line.
    X-positions come from *_bar indices saved by the detector – guaranteed correct.
    Falls back to argrelextrema scan only if indices are missing (old DB records).
    """
    if signal_type == "bearish":
        p1 = data.get("peak1")
        p2 = data.get("peak2")
        label = "Vrchol"
        bar1_key, bar2_key = "peak1_bar", "peak2_bar"
    else:
        p1 = data.get("trough1")
        p2 = data.get("trough2")
        label = "Dno"
        bar1_key, bar2_key = "trough1_bar", "trough2_bar"

    if not p1 or not p2:
        return

    n = len(df)

    # --- Prefer saved bar indices (exact) ---
    raw_i1 = data.get(bar1_key)
    raw_i2 = data.get(bar2_key)

    if raw_i1 is not None and raw_i2 is not None:
        # Indices are from the detector's df slice – use directly (clamped to safety)
        i1 = max(0, min(int(raw_i1), n - 1))
        i2 = max(0, min(int(raw_i2), n - 1))
    else:
        # Fallback for old DB records without bar indices
        scan   = df["high"].values if signal_type == "bearish" else df["low"].values
        window = min(80, n)
        seg    = scan[-window:]
        if signal_type == "bearish":
            ext = argrelextrema(seg, np.greater_equal, order=5)[0]
        else:
            ext = argrelextrema(seg, np.less_equal, order=5)[0]
        if len(ext) >= 2:
            i1 = int(ext[-2]) + (n - window)
            i2 = int(ext[-1]) + (n - window)
        else:
            i1, i2 = n - 20, n - 5

    x1, x2 = _safe_x(df, i1), _safe_x(df, i2)

    # Connecting line between the two points
    fig.add_trace(
        go.Scatter(
            x=[x1, x2], y=[float(p1), float(p2)],
            mode="lines+markers",
            name=f"Double {label}",
            line=dict(color=color, width=2, dash="dot"),
            marker=dict(size=10, color=color, symbol="circle"),
            hovertemplate=f"{label}: %{{y:.4f}}<extra></extra>",
        ),
        row=1, col=1,
    )

    # Annotate each point
    ay = -35 if signal_type == "bearish" else 35
    for x, p, n_lbl in [(x1, p1, f"1. {label}"), (x2, p2, f"2. {label}")]:
        fig.add_annotation(
            x=x, y=float(p), text=n_lbl,
            showarrow=True, arrowhead=2, arrowcolor=color, ay=ay,
            font=dict(color=color, size=10),
            bgcolor="rgba(0,0,0,0.5)",
            row=1, col=1,
        )


def _draw_flag(fig, df, data, signal_type, color, color_fill):
    """Filled rectangle around the flag consolidation zone + pole annotation."""
    support    = data.get("support")
    resistance = data.get("resistance")
    if not support or not resistance:
        return

    n       = len(df)
    bw      = _bar_width(df)
    x_start = _safe_x(df, max(0, n - 12))
    x_end   = _safe_x(df, n - 1)

    # Consolidation rectangle
    fig.add_shape(
        type="rect",
        x0=x_start, x1=x_end,
        y0=float(support), y1=float(resistance),
        line=dict(color=color, width=1.5, dash="dot"),
        fillcolor=f"rgba({color_fill},0.12)",
        row=1, col=1,
    )

    # Pole: mark the start of the impulse move
    pole_start = data.get("pole_start")
    pole_end   = data.get("pole_end")
    if pole_start and pole_end:
        pole_x_start = _safe_x(df, max(0, n - 12 - 5))
        pole_x_end   = _safe_x(df, max(0, n - 12))
        fig.add_shape(
            type="line",
            x0=pole_x_start, x1=pole_x_end,
            y0=float(pole_start), y1=float(pole_end),
            line=dict(color=color, width=2.5),
            row=1, col=1,
        )
        fig.add_annotation(
            x=pole_x_start, y=float(pole_start),
            text="Stožár", showarrow=False,
            font=dict(color=color, size=10),
            bgcolor="rgba(0,0,0,0.5)",
            row=1, col=1,
        )

    fig.add_annotation(
        x=x_end, y=float(resistance),
        text="📌 Flag zóna",
        showarrow=False,
        font=dict(color=color, size=11),
        bgcolor="rgba(0,0,0,0.5)",
        xanchor="right",
        row=1, col=1,
    )


def _draw_triangle(fig, df, data, signal_type, color):
    """
    Two converging trendlines forming the triangle.

    Bearish (descending triangle): flat support + falling resistance
      - resistance_start (oldest/highest peak) → resistance (latest/lowest peak)
    Bullish (ascending triangle): flat resistance + rising support
      - support_start (oldest/lowest trough) → support (latest/highest trough)

    Falls back to ±3% synthetic offset for old DB records without *_start values.
    """
    n          = len(df)
    window     = min(50, n)
    x_start    = _safe_x(df, n - window)
    x_end      = _safe_x(df, n - 1)
    resistance = data.get("resistance")
    support    = data.get("support")

    if not resistance or not support:
        return

    if signal_type == "bullish":
        # Flat resistance line (horizontal)
        fig.add_shape(
            type="line", x0=x_start, x1=x_end,
            y0=float(resistance), y1=float(resistance),
            line=dict(color=color, width=2, dash="dash"), row=1, col=1,
        )
        # Rising support line: support_start (oldest low) → support (latest low)
        support_start = data.get("support_start")
        if support_start:
            y0_support = float(support_start)
        else:
            # Fallback for old DB records
            y0_support = float(support) * 0.97
        fig.add_shape(
            type="line", x0=x_start, x1=x_end,
            y0=y0_support, y1=float(support),
            line=dict(color=color, width=2, dash="dash"), row=1, col=1,
        )
    else:
        # Flat support line (horizontal)
        fig.add_shape(
            type="line", x0=x_start, x1=x_end,
            y0=float(support), y1=float(support),
            line=dict(color=color, width=2, dash="dash"), row=1, col=1,
        )
        # Falling resistance line: resistance_start (oldest high) → resistance (latest high)
        resistance_start = data.get("resistance_start")
        if resistance_start:
            y0_resistance = float(resistance_start)
        else:
            # Fallback for old DB records
            y0_resistance = float(resistance) * 1.03
        fig.add_shape(
            type="line", x0=x_start, x1=x_end,
            y0=y0_resistance, y1=float(resistance),
            line=dict(color=color, width=2, dash="dash"), row=1, col=1,
        )

    # Label at the apex (convergence point)
    apex_y = (float(resistance) + float(support)) / 2
    fig.add_annotation(
        x=x_end, y=apex_y,
        text="📐 Apex",
        showarrow=True, arrowhead=2, arrowcolor=color, ax=30,
        font=dict(color=color, size=11),
        bgcolor="rgba(0,0,0,0.5)",
        row=1, col=1,
    )


def _draw_cross(fig, df, data, signal_type, color):
    """Mark the EMA50/200 crossover with a vertical line + annotation."""
    ema50 = data.get("ema50")
    if not ema50:
        return

    n       = len(df)
    x_cross = _safe_x(df, n - 1)
    label   = "✦ Golden Cross" if signal_type == "bullish" else "✦ Death Cross"

    # Vertical line at crossover
    fig.add_vline(
        x=x_cross,
        line_color=color,
        line_width=1.5,
        line_dash="dot",
        row=1, col=1,
    )

    fig.add_annotation(
        x=x_cross, y=float(ema50),
        text=label,
        showarrow=True, arrowhead=2, arrowcolor=color, ay=-40,
        font=dict(color=color, size=12, family="monospace"),
        bgcolor="rgba(0,0,0,0.6)",
        bordercolor=color,
        row=1, col=1,
    )


def _draw_rsi_divergence(fig, df, data, signal_type, color, indic, rsi_row):
    """
    Draw divergence lines both on price chart and RSI subplot.
    Bullish: price makes lower low, RSI makes higher low  → lines go opposite way.
    Bearish: price makes higher high, RSI makes lower high → lines go opposite way.
    """
    n   = len(df)
    rsi = indic.get("rsi")

    if rsi is None or rsi.dropna().empty:
        return

    # Find two comparison points (current vs ~20 bars ago)
    lookback = min(20, n - 2)
    i_curr   = n - 1
    i_prev   = n - 1 - lookback

    # Price line on candlestick
    if signal_type == "bullish":
        # price: lower low
        y_prev_price = float(df["low"].iloc[i_prev])
        y_curr_price = float(df["low"].iloc[i_curr])
        # RSI: higher low
        rsi_vals = rsi.values
        y_prev_rsi = float(rsi_vals[i_prev]) if not np.isnan(rsi_vals[i_prev]) else 50
        y_curr_rsi = float(rsi_vals[i_curr]) if not np.isnan(rsi_vals[i_curr]) else 50
    else:
        # price: higher high
        y_prev_price = float(df["high"].iloc[i_prev])
        y_curr_price = float(df["high"].iloc[i_curr])
        # RSI: lower high
        rsi_vals = rsi.values
        y_prev_rsi = float(rsi_vals[i_prev]) if not np.isnan(rsi_vals[i_prev]) else 50
        y_curr_rsi = float(rsi_vals[i_curr]) if not np.isnan(rsi_vals[i_curr]) else 50

    x_prev = _safe_x(df, i_prev)
    x_curr = _safe_x(df, i_curr)

    # Price divergence line
    fig.add_trace(
        go.Scatter(
            x=[x_prev, x_curr],
            y=[y_prev_price, y_curr_price],
            mode="lines+markers",
            name="Divergence (cena)",
            line=dict(color=color, width=2, dash="dot"),
            marker=dict(size=8, color=color),
            hovertemplate="Div cena: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # RSI divergence line (only if RSI subplot is visible)
    if rsi_row is not None:
        fig.add_trace(
            go.Scatter(
                x=[x_prev, x_curr],
                y=[y_prev_rsi, y_curr_rsi],
                mode="lines+markers",
                name="Divergence (RSI)",
                line=dict(color=color, width=2, dash="dot"),
                marker=dict(size=8, color=color),
                hovertemplate="Div RSI: %{y:.1f}<extra></extra>",
            ),
            row=rsi_row, col=1,
        )

    # Label
    lbl = "↗ Bullish Div" if signal_type == "bullish" else "↘ Bearish Div"
    fig.add_annotation(
        x=x_curr, y=y_curr_price,
        text=lbl,
        showarrow=True, arrowhead=2, arrowcolor=color,
        ay=-40 if signal_type == "bullish" else 40,
        font=dict(color=color, size=11),
        bgcolor="rgba(0,0,0,0.55)",
        row=1, col=1,
    )


def _draw_engulfing(fig, df, data, signal_type, color):
    """
    Highlight the two engulfing candles with rectangles spanning their full high-low range.
    Uses bar-width offset so x0 != x1.
    """
    n  = len(df)
    if n < 2:
        return

    bw = _bar_width(df)

    for offset, lbl in [(2, "Předchozí"), (1, "Engulfing")]:
        i    = n - offset
        x    = df.index[i]
        high = float(df["high"].iloc[i])
        low  = float(df["low"].iloc[i])

        fig.add_shape(
            type="rect",
            x0=x - bw, x1=x + bw,
            y0=low, y1=high,
            line=dict(color=color, width=2),
            fillcolor=f"rgba({'38,166,154' if signal_type=='bullish' else '239,83,80'},0.15)",
            row=1, col=1,
        )

        fig.add_annotation(
            x=x, y=high if signal_type == "bearish" else low,
            text=lbl,
            showarrow=True, arrowhead=2, arrowcolor=color,
            ay=-25 if signal_type == "bearish" else 25,
            font=dict(color=color, size=10),
            bgcolor="rgba(0,0,0,0.5)",
            row=1, col=1,
        )


def _draw_sr_break(fig, df, data, signal_type, color):
    """Arrow and vertical marker at S/R breakout point."""
    n     = len(df)
    level = data.get("level_price") or data.get("resistance") or data.get("support")
    if not level:
        return

    x  = _safe_x(df, n - 1)
    ay = -45 if signal_type == "bullish" else 45

    # Vertical line at breakout bar
    fig.add_vline(
        x=x,
        line_color=color,
        line_width=1.5,
        line_dash="dot",
        row=1, col=1,
    )

    fig.add_annotation(
        x=x, y=float(level),
        text=f"{'↑ Průraz nahoru' if signal_type=='bullish' else '↓ Průraz dolů'}",
        showarrow=True, arrowhead=3, arrowcolor=color, ay=ay,
        font=dict(color=color, size=12),
        bgcolor="rgba(0,0,0,0.6)",
        bordercolor=color,
        row=1, col=1,
    )


def _draw_ichimoku(fig, df, data, signal_type, color, color_fill):
    """
    Draw Ichimoku cloud (Kumo) + Tenkan-sen + Kijun-sen lines.
    Cloud is filled between Senkou Span A and B.
    """
    n         = len(df)
    tenkan_v  = data.get("tenkan")
    kijun_v   = data.get("kijun")
    span_a_v  = data.get("senkou_a")
    span_b_v  = data.get("senkou_b")

    if not all([tenkan_v, kijun_v, span_a_v, span_b_v]):
        return

    # Recompute Ichimoku lines on the visible df for proper rendering
    TENKAN_P  = 9
    KIJUN_P   = 26
    SENKOU_BP = 52
    SHIFT     = 26

    def midpoint(h, l, p):
        return (h.rolling(p).max() + l.rolling(p).min()) / 2

    highs  = df["high"]
    lows   = df["low"]

    tenkan  = midpoint(highs, lows, TENKAN_P)
    kijun   = midpoint(highs, lows, KIJUN_P)
    span_a  = ((tenkan + kijun) / 2).shift(SHIFT)
    span_b  = midpoint(highs, lows, SENKOU_BP).shift(SHIFT)

    # --- Tenkan-sen (fast line) ---
    fig.add_trace(
        go.Scatter(
            x=df.index, y=tenkan,
            name="Tenkan-sen (9)",
            line=dict(color="#e91e8c", width=1.2),
            hovertemplate="Tenkan: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # --- Kijun-sen (base line) ---
    fig.add_trace(
        go.Scatter(
            x=df.index, y=kijun,
            name="Kijun-sen (26)",
            line=dict(color="#1e88e5", width=1.5),
            hovertemplate="Kijun: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # --- Cloud: Senkou Span A (upper/lower boundary) ---
    fig.add_trace(
        go.Scatter(
            x=df.index, y=span_a,
            name="Span A",
            line=dict(color="rgba(38,166,154,0.6)", width=0.8),
            hovertemplate="Span A: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # --- Cloud: Senkou Span B + fill between A and B ---
    fig.add_trace(
        go.Scatter(
            x=df.index, y=span_b,
            name="Span B",
            line=dict(color="rgba(239,83,80,0.6)", width=0.8),
            fill="tonexty",
            fillcolor=(
                "rgba(38,166,154,0.12)" if signal_type == "bullish"
                else "rgba(239,83,80,0.12)"
            ),
            hovertemplate="Span B: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # --- TK Cross annotation ---
    x_cross = _safe_x(df, n - 1)
    cross_price = float(tenkan.iloc[-1]) if not pd.isna(tenkan.iloc[-1]) else float(kijun_v)
    lbl = "✦ TK Cross Bullish" if signal_type == "bullish" else "✦ TK Cross Bearish"

    fig.add_annotation(
        x=x_cross, y=cross_price,
        text=lbl,
        showarrow=True, arrowhead=2, arrowcolor=color,
        ay=-45 if signal_type == "bullish" else 45,
        font=dict(color=color, size=12, family="monospace"),
        bgcolor="rgba(0,0,0,0.65)",
        bordercolor=color,
        row=1, col=1,
    )


def _draw_abc(fig, df, data, signal_type, color, color_fill):
    """
    Draw ABC correction wave:
    - Lines A→B→C connecting the three pivot points
    - Labels A, B, C at each pivot
    - Fibonacci retracement zone (38.2% and 61.8%) shaded between A and C
    - TP target annotation
    """
    origin_p = data.get("origin_price")
    price_a  = data.get("wave_a_price")
    price_b  = data.get("wave_b_price")
    price_c  = data.get("wave_c_price")
    tp       = data.get("tp_target")

    if not all([origin_p, price_a, price_b, price_c]):
        return

    n      = len(df)
    window = min(60, n)

    # Approximate x positions for O, A, B, C by scanning recent bars
    if signal_type == "bullish":
        # Bullish ABC: O=peak, A=trough, B=peak, C=trough
        troughs = argrelextrema(df["low"].values[-window:], np.less_equal, order=4)[0]
        peaks   = argrelextrema(df["high"].values[-window:], np.greater_equal, order=4)[0]
        offset  = n - window

        i_a = (int(troughs[-2]) + offset) if len(troughs) >= 2 else n - window // 2
        i_b = (int(peaks[-1])   + offset) if len(peaks)   >= 1 else n - window // 4
        i_c = (int(troughs[-1]) + offset) if len(troughs) >= 1 else n - 3
        i_o = max(0, i_a - window // 4)
    else:
        # Bearish ABC: O=trough, A=peak, B=trough, C=peak
        peaks   = argrelextrema(df["high"].values[-window:], np.greater_equal, order=4)[0]
        troughs = argrelextrema(df["low"].values[-window:],  np.less_equal,    order=4)[0]
        offset  = n - window

        i_a = (int(peaks[-2])   + offset) if len(peaks)   >= 2 else n - window // 2
        i_b = (int(troughs[-1]) + offset) if len(troughs) >= 1 else n - window // 4
        i_c = (int(peaks[-1])   + offset) if len(peaks)   >= 1 else n - 3
        i_o = max(0, i_a - window // 4)

    x_o = _safe_x(df, i_o)
    x_a = _safe_x(df, i_a)
    x_b = _safe_x(df, i_b)
    x_c = _safe_x(df, i_c)

    # --- Wave lines: O→A→B→C ---
    fig.add_trace(
        go.Scatter(
            x=[x_o, x_a, x_b, x_c],
            y=[float(origin_p), float(price_a), float(price_b), float(price_c)],
            mode="lines+markers+text",
            name="ABC vlny",
            line=dict(color=color, width=2),
            marker=dict(size=10, color=color, symbol="circle"),
            text=["O", "A", "B", "C"],
            textposition=["top center", "bottom center", "top center", "bottom center"]
                         if signal_type == "bullish"
                         else ["bottom center", "top center", "bottom center", "top center"],
            textfont=dict(color=color, size=13),
            hovertemplate="ABC: %{y:.4f}<extra></extra>",
        ),
        row=1, col=1,
    )

    # --- Fibonacci retracement zone (38.2% – 61.8% of wave A) ---
    wave_a_size = abs(float(price_a) - float(origin_p))
    if signal_type == "bullish":
        fib_382 = float(price_a) + wave_a_size * 0.382
        fib_618 = float(price_a) + wave_a_size * 0.618
    else:
        fib_382 = float(price_a) - wave_a_size * 0.382
        fib_618 = float(price_a) - wave_a_size * 0.618

    fib_lo = min(fib_382, fib_618)
    fib_hi = max(fib_382, fib_618)

    fig.add_hrect(
        y0=fib_lo, y1=fib_hi,
        fillcolor=f"rgba({color_fill},0.1)",
        line_width=0,
        annotation_text="Fib 38.2–61.8% (B zóna)",
        annotation_position="right",
        annotation_font_color=color,
        annotation_font_size=10,
        row=1, col=1,
    )

    # --- TP target annotation ---
    if tp:
        ay = -50 if signal_type == "bullish" else 50
        fig.add_annotation(
            x=x_c, y=float(tp),
            text=f"🎯 TP cíl: {float(tp):,.4f}",
            showarrow=True, arrowhead=2, arrowcolor=color, ay=ay,
            font=dict(color=color, size=11),
            bgcolor="rgba(0,0,0,0.6)",
            bordercolor=color,
            row=1, col=1,
        )
