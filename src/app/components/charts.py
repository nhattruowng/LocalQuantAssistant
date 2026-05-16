"""Plotly chart components for the dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def candlestick_chart(features: pd.DataFrame) -> go.Figure:
    """Build candlestick chart with EMA overlays and volume."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
    )
    fig.add_trace(
        go.Candlestick(
            x=features["timestamp"],
            open=features["open"],
            high=features["high"],
            low=features["low"],
            close=features["close"],
            name="Candles",
        ),
        row=1,
        col=1,
    )
    for column, color in [("ema_20", "#2563eb"), ("ema_50", "#f97316"), ("ema_200", "#7c3aed")]:
        if column in features:
            fig.add_trace(
                go.Scatter(
                    x=features["timestamp"],
                    y=features[column],
                    name=column.upper(),
                    mode="lines",
                    line={"width": 1.4, "color": color},
                ),
                row=1,
                col=1,
            )
    fig.add_trace(
        go.Bar(
            x=features["timestamp"],
            y=features["volume"],
            name="Volume",
            marker_color="#94a3b8",
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        height=620,
        margin={"l": 10, "r": 10, "t": 35, "b": 10},
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        legend={"orientation": "h", "y": 1.02},
    )
    return fig


def rsi_chart(features: pd.DataFrame) -> go.Figure:
    """Build RSI chart."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=features["timestamp"],
            y=features["rsi_14"],
            name="RSI 14",
            mode="lines",
            line={"color": "#0f766e", "width": 2},
        )
    )
    fig.add_hline(y=70, line_dash="dash", line_color="#dc2626")
    fig.add_hline(y=30, line_dash="dash", line_color="#16a34a")
    fig.update_layout(
        height=260,
        margin={"l": 10, "r": 10, "t": 25, "b": 10},
        template="plotly_white",
        yaxis_range=[0, 100],
    )
    return fig


def equity_curve_chart(trades: pd.DataFrame) -> go.Figure:
    """Build an equity curve from trade PnL."""
    fig = go.Figure()
    if trades.empty or "pnl" not in trades:
        fig.update_layout(template="plotly_white", height=320)
        return fig
    equity = trades["pnl"].cumsum()
    x = trades["closed_at"] if "closed_at" in trades else trades.index
    fig.add_trace(
        go.Scatter(
            x=x,
            y=equity,
            name="Equity",
            mode="lines+markers",
            line={"color": "#2563eb", "width": 2},
        )
    )
    fig.update_layout(
        height=320,
        margin={"l": 10, "r": 10, "t": 25, "b": 10},
        template="plotly_white",
    )
    return fig


def paper_equity_curve_chart(snapshots: pd.DataFrame) -> go.Figure:
    """Build an equity curve from paper account snapshots."""
    fig = go.Figure()
    if snapshots.empty or "equity" not in snapshots:
        fig.update_layout(template="plotly_white", height=320)
        return fig
    x = snapshots["timestamp"] if "timestamp" in snapshots else snapshots.index
    fig.add_trace(
        go.Scatter(
            x=x,
            y=snapshots["equity"],
            name="Paper Equity",
            mode="lines+markers",
            line={"color": "#16a34a", "width": 2},
        )
    )
    fig.update_layout(
        height=320,
        margin={"l": 10, "r": 10, "t": 25, "b": 10},
        template="plotly_white",
    )
    return fig
